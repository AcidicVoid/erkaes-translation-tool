#!/usr/bin/env python3
"""
Re-pack a directory into a DxLib v2 .dat archive.
This is intended for use with the Rosenkreuzstilette games. Nothing else has been tested.

The produced archive is byte-for-byte format-compatible with the
Rosenkreuzstilette games (and any other DxLib title using format version 3).

Usage
-----
    python dxarc_pack.py -k <hex_key> -i <input_dir> -o <output.dat>

Example
-------
    python dxarc_pack.py \\
        -k 6A69726F7473756B656A6972 \\
        -i "temp\\scenario_translated" \\
        -o "scenario.dat"

Parameters
----------
-k / --key   Hex-encoded password bytes exactly as shown by DXArc.exe 'b'.
             (The 12-byte value like 6A69726F7473756B656A6972.)
-i / --input Directory whose contents become the archive root.
-o / --output Output .dat path.

Format notes
-----------------
Header (24 bytes, Cipher1 @ position 0):
  u16  id            = 0x5844 ("DX")
  u16  version       = 3
  u32  tablesSize
  u32  dataPosition  = 24     (header size; data follows immediately)
  u32  tablesPosition         (absolute file offset of tables blob)
  u32  entryTableOffset       (within tables blob)
  u32  directoryTableOffset   (within tables blob)

File layout:
  [header 24 B]
  [data region  – compressed files concatenated, each 4-byte aligned]
  [tables blob  – starts at next 4-byte boundary after last file]

  Files are wrapped in DxLib's LZ compression envelope (store-only,
  no actual LZ matching) so that the PressDataSize entry field holds
  the blob size — required by old DxLib v2.x runtimes.

Tables blob (Cipher1 @ position = tablesPosition):
  [name table] [entry table @ entryTableOffset] [dir table @ dirTableOffset]
  NOTE: In v5 the tables cipher seed is always 0; in v3 (and earlier?) it is tablesPosition.

File data (Cipher1 @ position = entry.dataOffset):
  The cipher key offset is seeded with the file's dataOffset (its byte
  offset within the data region), NOT with the file size as in v5.
  Files are stored uncompressed (compressedDataSize = 0xFFFFFFFF).
"""

import argparse
import os
import struct
import sys
from pathlib import Path


# ── Constants ────────────────────────────────────────────────────────────────

DX_ID       = 0x5844           # b"DX"
DX_VERSION  = 3                # Rosenkreuzstilette uses format version 3, not 5

ATTR_DIRECTORY = 0x0010        # FILE_ATTRIBUTE_DIRECTORY
ATTR_ARCHIVE   = 0x0020        # FILE_ATTRIBUTE_ARCHIVE

ENTRY_SIZE     = 44            # one entry-table row (same across v2–v5)
DIR_ENTRY_SIZE = 16            # one directory-table row (same across v2–v5)

NO_COMPRESS    = 0xFFFF_FFFF   # compressedDataSize sentinel = not compressed

HEADER_SIZE = 24

# 100-nanosecond ticks between 1601-01-01 (Windows FILETIME epoch) and
# 1970-01-01 (Unix epoch).
FILETIME_EPOCH_DIFF = 116_444_736_000_000_000
ROOT_PARENT = 0xFFFF_FFFF      # parentDirectoryOffset sentinel for the root dir


# ── Cipher1 ──────────────────────────────────────────────────────────────────

def create_key1(password: bytes) -> bytes:
    """Derive the 12-byte Cipher1 XOR key from the raw password bytes."""
    if not password:
        raise ValueError("Password must not be empty.")

    k = bytearray(12)
    for i in range(12):
        k[i] = password[i % len(password)]

    k[0]  = (~k[0])                           & 0xFF
    k[1]  = ((k[1]  >> 4) | (k[1]  << 4))    & 0xFF
    k[2]  =  (k[2]  ^ 0x8A)                  & 0xFF
    k[3]  = (~((k[3]  >> 4) | (k[3]  << 4))) & 0xFF
    k[4]  = (~k[4])                           & 0xFF
    k[5]  =  (k[5]  ^ 0xAC)                  & 0xFF
    k[6]  = (~k[6])                           & 0xFF
    k[7]  = (~((k[7]  >> 3) | (k[7]  << 5))) & 0xFF
    k[8]  =  ((k[8]  >> 5) | (k[8]  << 3))   & 0xFF
    k[9]  =  (k[9]  ^ 0x7F)                  & 0xFF
    k[10] = (((k[10] >> 4) | (k[10] << 4)) ^ 0xD6) & 0xFF
    k[11] =  (k[11] ^ 0xCC)                  & 0xFF

    return bytes(k)


def cipher1(data: bytes, key: bytes, position: int) -> bytes:
    """Apply (or undo) the Cipher1 stream cipher.

    XOR is symmetric, so this function is identical for encryption and
    decryption.  `position` is the starting offset in the 12-byte key cycle.
    """
    k = int(position) % 12
    out = bytearray(data)
    for i in range(len(out)):
        out[i] ^= key[k]
        k = 0 if k == 11 else k + 1
    return bytes(out)


# ── Time helpers ──────────────────────────────────────────────────────────────

def unix_to_filetime(ts: float) -> int:
    """Convert a Unix timestamp (float seconds) to a Windows FILETIME int."""
    return int(ts * 10_000_000) + FILETIME_EPOCH_DIFF


# ── Directory tree ────────────────────────────────────────────────────────────

class FileNode:
    """Represents a single file inside the archive."""

    __slots__ = (
        "name", "path", "size",
        "ctime", "atime", "mtime",
        # assigned during layout:
        "entry_off", "name_off", "data_off", "compressed_size",
    )

    def __init__(self, name: str, path: Path) -> None:
        self.name = name
        self.path = path
        st = path.stat()
        self.size  = st.st_size
        self.ctime = unix_to_filetime(st.st_ctime)
        self.atime = unix_to_filetime(st.st_atime)
        self.mtime = unix_to_filetime(st.st_mtime)
        self.entry_off = 0
        self.name_off  = 0
        self.data_off  = 0
        self.compressed_size = 0


class DirNode:
    """Represents a directory (including the archive root) inside the archive."""

    __slots__ = (
        "name", "path", "children",
        "ctime", "atime", "mtime",
        # assigned during layout:
        "entry_off", "name_off", "dir_off",
        "child_entry_start", "parent_dir_off",
    )

    def __init__(self, name: str, path: Path) -> None:
        self.name     = name
        self.path     = path
        self.children: list = []   # FileNode | DirNode, sorted
        st = path.stat(follow_symlinks=False)
        self.ctime = unix_to_filetime(st.st_ctime)
        self.atime = unix_to_filetime(st.st_atime)
        self.mtime = unix_to_filetime(st.st_mtime)
        self.entry_off        = 0
        self.name_off         = 0
        self.dir_off          = 0
        self.child_entry_start = 0
        self.parent_dir_off   = ROOT_PARENT


def scan_directory(root_path: Path) -> DirNode:
    """Recursively scan *root_path* and return a DirNode tree."""
    root = DirNode("", root_path)

    def fill(node: DirNode, path: Path) -> None:
        dirs, files = [], []
        for entry in path.iterdir():
            if entry.is_dir():
                dirs.append(entry)
            elif entry.is_file():
                files.append(entry)
        dirs.sort(key=lambda p: p.name.lower())
        files.sort(key=lambda p: p.name.lower())

        for d in dirs:
            child = DirNode(d.name, d)
            fill(child, d)
            node.children.append(child)
        for f in files:
            node.children.append(FileNode(f.name, f))

    fill(root, root_path)
    return root


# ── Name table ────────────────────────────────────────────────────────────────

def _encode_name_entry(name: str) -> bytes:
    """Serialise one name-table entry.

    Layout (from DXArchive.ReadName):
        u16  length4    -- padded_len / 4  (0 for empty root name)
        u16  checksum   -- sum of canonical (upper-case) name bytes & 0xFFFF
        u8[padded_len]  canonical  (upper-case, NUL-padded to multiple of 4)
        u8[padded_len]  regular    (original case, NUL-padded)
    """
    if name == "":
        return struct.pack("<HH", 0, 0)

    try:
        regular_b   = name.encode("shift_jis")
        canonical_b = name.upper().encode("shift_jis")
    except (UnicodeEncodeError, LookupError):
        regular_b   = name.encode("utf-8")
        canonical_b = name.upper().encode("utf-8")

    # +1 for the NUL terminator that DxLib expects inside the padded area.
    raw_len    = max(len(regular_b), len(canonical_b)) + 1
    padded_len = ((raw_len + 3) // 4) * 4
    length4    = padded_len // 4

    # Checksum = sum of canonical (upper-case) name bytes, truncated to u16.
    checksum   = sum(canonical_b) & 0xFFFF

    canonical_padded = canonical_b.ljust(padded_len, b"\x00")
    regular_padded   = regular_b.ljust(padded_len,   b"\x00")

    return struct.pack("<HH", length4, checksum) + canonical_padded + regular_padded


# ── DxLib store-only compression ──────────────────────────────────────────────

def dxlib_compress_store(data: bytes) -> bytes:
    """Wrap *data* in a DxLib compression envelope without real compression.

    Format understood by DXArchive.Decode / Decompressor2:
      u32  decompressedSize
      u32  totalBlobSize        (header + stream)
      u8   escape              (chosen to minimise escaping overhead)
      ...  stream              (literals; escape bytes are doubled)

    Returns the complete blob (header + stream).
    """
    # Pick the byte value that occurs least often as the escape character.
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    escape = min(range(256), key=lambda x: freq[x])

    stream = bytearray()
    for b in data:
        stream.append(b)
        if b == escape:
            stream.append(escape)          # double-escape

    total_size = 9 + len(stream)
    header = struct.pack("<II", len(data), total_size) + bytes([escape])
    return header + bytes(stream)



def _align4(n: int) -> int:
    """Round *n* up to the next multiple of 4."""
    return (n + 3) & ~3


def build_archive(root: DirNode, key: bytes) -> bytes:
    """Construct and return the complete encrypted DxLib archive bytes."""

    # Collect nodes in BFS order
    all_dirs:  list[DirNode]  = [root]
    all_files: list[FileNode] = []
    queue = [root]

    while queue:
        d = queue.pop(0)
        for child in d.children:
            if isinstance(child, DirNode):
                all_dirs.append(child)
                queue.append(child)
            else:
                all_files.append(child)

    # Build name table and assign name_off to every node
    name_table = bytearray()

    def alloc_name(node) -> None:
        node.name_off = len(name_table)
        name_table.extend(_encode_name_entry(node.name))

    alloc_name(root)
    for d in all_dirs[1:]:
        alloc_name(d)
    for f in all_files:
        alloc_name(f)

    #Assign entry-table offsets
    root.entry_off = 0
    next_entry = ENTRY_SIZE

    for d in all_dirs:
        d.child_entry_start = next_entry
        for child in d.children:
            child.entry_off = next_entry
            next_entry += ENTRY_SIZE

    # Assign directory-table offsets
    for idx, d in enumerate(all_dirs):
        d.dir_off = idx * DIR_ENTRY_SIZE

    for d in all_dirs:
        for child in d.children:
            if isinstance(child, DirNode):
                child.parent_dir_off = d.dir_off

    # Compress, then encrypt file data
    # cipher seed: dataOff (each file's offset within the data region).
    # Each file's start is 4-byte aligned within the data region.
    data_buf = bytearray()

    for f in all_files:
        # Align the current write position to a 4-byte boundary.
        aligned = _align4(len(data_buf))
        if aligned > len(data_buf):
            data_buf.extend(b"\x00" * (aligned - len(data_buf)))

        f.data_off = len(data_buf)   # offset within data region
        raw = f.path.read_bytes()
        compressed = dxlib_compress_store(raw)
        f.compressed_size = len(compressed)
        # XOR with key starting at position = dataOff
        enc = cipher1(compressed, key, f.data_off)
        data_buf.extend(enc)

    # Build entry table
    _ENTRY_FMT = "<IIQQQIII"

    entry_table = bytearray()

    def append_entry(node, data_offset: int, data_size: int, attributes: int,
                     compressed_size: int = NO_COMPRESS) -> None:
        entry_table.extend(struct.pack(
            _ENTRY_FMT,
            node.name_off,
            attributes,
            node.ctime,
            node.atime,
            node.mtime,
            data_offset,
            data_size,
            compressed_size,
        ))

    append_entry(root, root.dir_off, 0, ATTR_DIRECTORY)

    for d in all_dirs:
        for child in d.children:
            if isinstance(child, DirNode):
                append_entry(child, child.dir_off, 0, ATTR_DIRECTORY)
            else:
                append_entry(child, child.data_off, child.size, ATTR_ARCHIVE,
                             child.compressed_size)

    # Build directory table
    dir_table = bytearray()

    for d in all_dirs:
        child_count     = len(d.children)
        child_entry_off = d.child_entry_start if child_count > 0 else 0
        dir_table.extend(struct.pack(
            "<IIII",
            d.entry_off,
            d.parent_dir_off,
            child_count,
            child_entry_off,
        ))

    # Compute file-layout positions
    # layout: [header 24 B][data region][tables blob]
    # Tables start at the first 4-byte boundary after the data region.
    data_region_size = len(data_buf)
    tables_position  = HEADER_SIZE + _align4(data_region_size)

    # Assemble tables blob and encrypt
    entry_table_offset = len(name_table)
    dir_table_offset   = entry_table_offset + len(entry_table)

    tables_plain = bytes(name_table) + bytes(entry_table) + bytes(dir_table)
    # tables cipher seed = tablesPosition  (v5 always uses 0).
    tables_enc   = cipher1(tables_plain, key, tables_position)
    tables_size  = len(tables_enc)

    # Build and encrypt header
    # header (24 bytes, no encodingCode field):
    #   u16  id                = 0x5844
    #   u16  version           = 3
    #   u32  tablesSize
    #   u32  dataPosition      = HEADER_SIZE (24)
    #   u32  tablesPosition
    #   u32  entryTableOffset
    #   u32  directoryTableOffset
    header_plain = struct.pack(
        "<HHIIIII",
        DX_ID,
        DX_VERSION,
        tables_size,
        HEADER_SIZE,       # dataPosition — data immediately follows header
        tables_position,
        entry_table_offset,
        dir_table_offset,
    )
    assert len(header_plain) == HEADER_SIZE

    header_enc = cipher1(header_plain, key, 0)

    # Add any padding between data region and tables
    padding_size = tables_position - HEADER_SIZE - data_region_size
    padding      = b"\x00" * padding_size

    # Concatenate and return
    return header_enc + bytes(data_buf) + padding + tables_enc


# CLI

def parse_hex_key(hex_str: str) -> bytes:
    hex_str = hex_str.strip()
    if len(hex_str) % 2 != 0:
        raise argparse.ArgumentTypeError(
            f"Hex key has odd length ({len(hex_str)} chars)."
        )
    try:
        return bytes.fromhex(hex_str)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid hex key: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-pack a directory into a DxLib .dat archive "
                    "(Rosenkreuzstilette compatible).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python dxarc_pack.py \\\n"
            "      -k 6A69726F7473756B656A6972 \\\n"
            "      -i temp\\scenario_translated \\\n"
            "      -o scenario.dat\n"
        ),
    )
    parser.add_argument(
        "-k", "--key",
        required=True,
        metavar="HEX",
        help="Hex-encoded password bytes as shown by 'DXArc.exe b'.",
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        metavar="DIR",
        help="Input directory whose contents become the archive root.",
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        metavar="FILE",
        help="Output .dat path.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        parser.error(f"Input path is not a directory: {input_dir}")

    try:
        password = parse_hex_key(args.key)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
        return

    key = create_key1(password)

    output_path = Path(args.output)

    print(f"Scanning {input_dir} …")
    root = scan_directory(input_dir)

    file_count = sum(1 for _ in _iter_files(root))
    dir_count  = sum(1 for _ in _iter_dirs(root)) - 1
    print(f"  {file_count} file(s), {dir_count} subdirectory/ies")

    print("Building archive …")
    archive_bytes = build_archive(root, key)

    print(f"Writing {len(archive_bytes):,} bytes → {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(archive_bytes)
    print("Done.")


def _iter_files(node: DirNode):
    for child in node.children:
        if isinstance(child, FileNode):
            yield child
        else:
            yield from _iter_files(child)


def _iter_dirs(node: DirNode):
    yield node
    for child in node.children:
        if isinstance(child, DirNode):
            yield from _iter_dirs(child)


if __name__ == "__main__":
    main()
