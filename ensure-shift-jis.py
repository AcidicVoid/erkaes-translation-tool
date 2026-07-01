import argparse
import shutil
import re
from pathlib import Path

# Explicit direct mapping table using strict Unicode Hex Escapes
# This prevents text editors from misinterpreting full-width characters.
TRANSLATION_MAP = {
    '\u00a0': '\u3000', # Non-breaking Space -> Full-width Ideographic Space
    #'\u00a0': '\uff65', # Non-breaking Space -> Halfwidth Katakana Middle Dot
    '\u0020': '\u3000', # Half-width Space -> Full-width Ideographic Space
    #'\u0020': '\uff65', # Half-width Space -> Halfwidth Katakana Middle Dot
    '\u0021': '\uff01', # ! -> ！
    '\u002c': '\uff0c', # , -> ，
    # '\u002e': '\uff0e', # . -> ．
    '\u002e': '\u3002', # . -> ．(Japanese period: 。)
    # '\u002d': '\uff0d', # - -> －
    # '\u005f': '\uff3f', # _ -> ＿
    # '\u002b': '\uff0b', # + -> ＋
    # '\u003d': '\uff1d', # = -> ＝
    # '\u003b': '\uff1b', # ; -> ；
    # '\u003a': '\uff1a', # : -> ；
    # '\u0028': '\uff08', # ( -> （
    # '\u0029': '\uff09', # ) -> ）
    # '\u005b': '\uff3b', # [ -> ［
    # '\u005d': '\uff3d', # ] -> ］
    # '\u007b': '\uff5b', # { -> ｛
    # '\u007d': '\uff5d', # } -> ｝
    # '\u0027': '\u2019', # ' -> ’
    # '\u0022': '\u201d', # " -> ”
    # '\u002f': '\uff0f', # / -> ／
    # '\u005c': '\uff3c', # \ -> ＼
    # '\u003c': '\uff1c', # < -> ＜
    # '\u003e': '\uff1e', # > -> ＞
    # '\u0023': '\uff03', # # -> ＃
    # '\u0024': '\uff04', # $ -> ＄
    # '\u0025': '\uff05', # % -> ％
    # '\u005e': '\uff3e', # ^ -> ＾
    # '\u0026': '\uff06', # & -> ＆
    # '\u002a': '\uff0a', # * -> ＊
    # '\u0060': '\uff40', # ` -> ｀
    # '\u007c': '\uff5c', # | -> ｜
}

TRANS_TABLE = str.maketrans(TRANSLATION_MAP)

def convert_dialogue_elements_shiftjis(input_path, output_path):
    print(f"Processing characters via code-escapes for {input_path} ...")

    try:
        # Read the file as raw binary data to ensure safe line slicing
        with open(input_path, 'rb') as f:
            raw_bytes = f.read()
    except Exception as e:
        print(f"   Error reading file {input_path}: {e}")
        return

    # binary split covering all newline formats (\r\n, \n, \r)
    binary_lines = re.split(b'(\r\n|\n|\r)', raw_bytes)

    processed_bytes_list = []

    for item in binary_lines:
        if not item:
            continue

        # If it's a binary line delimiter, preserve it exactly as-is
        if item in (b'\r\n', b'\n', b'\r'):
            processed_bytes_list.append(item)
            continue

        # Decode the isolated line segment safely using cp932
        try:
            line_str = item.decode('cp932', errors='replace')
        except Exception:
            processed_bytes_list.append(item)
            continue

        # Condition Check: Must start with 「 (\u300c), space (\u0020), or non-breaking space (\u00a0)
        if line_str.startswith('\u300c') or line_str.startswith('\u0020') or line_str.startswith('\u00a0'):
            # handle multi-character string replacements (Triple dots -> Full-width Ellipsis '\u2026')
            line_str = line_str.replace("...", "\u2026")
            # translate targeted special characters using our escape-guaranteed map
            line_str = line_str.translate(TRANS_TABLE)
            # Full-with periods have some kind of space in them, so we kill the regular spaces appearing directly after them.
            # line_str = line_str.replace("\uff0e\u3000", "\u3002")  # "． " -> "．"
            line_str = line_str.replace("「", "")

        # Convert back into clean Shift-JIS bytes
        processed_bytes_list.append(line_str.encode('cp932', errors='replace'))

    # Reassemble the file architecture natively
    final_binary_data = b"".join(processed_bytes_list)

    try:
        filename = input_path.name
        target = Path.joinpath(output_path, filename)
        with open(target, 'wb') as f:
            f.write(final_binary_data)
        print(f"   File exported to: {target}")
    except Exception as e:
        print(f"   Error during file write: {e}")

    print("...done!")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sanitize spacing and special punctuation variations for Rosenkreuzstilette translation strings via escape-code translation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "input_path",
        help="Path to the input file or directory. Positional and required.",
    )

    parser.add_argument(
        "-o", "--output",
        required=False,
        metavar="OUT",
        help="Output file path.",
        default=None
    )

    parser.add_argument(
        "-b", "--backup",
        required=False,
        metavar="BAK",
        help="Backs up the original files before conversion.",
        default=True
    )

    args = parser.parse_args()

    backup = args.backup if isinstance(args.backup, bool) else str(args.backup).lower() in ['true', '1', 't']

    input_path  = Path(args.input_path).absolute()
    backup_path = Path(input_path.as_posix() + "_backup").absolute()
    output_path = Path(args.output if args.output is not None else input_path).absolute()

    print(f" Input path: {input_path}")
    print(f"Output path: {output_path}")
    print(f"Backup path: {backup_path}")

    files_to_process = []
    if input_path.is_dir():
        files_to_process = list(input_path.glob("*.txt"))
        if backup:
            backup_path.mkdir(parents=True, exist_ok=True)
        if not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)
    else:
        if input_path.suffix == ".txt":
            files_to_process = [input_path]
            if args.output is None:
                output_path = input_path.parent

    for file_path in files_to_process:
        if backup:
            backup_target_dir = backup_path if input_path.is_dir() else input_path.parent / "backup"
            backup_target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(file_path, backup_target_dir / file_path.name)

        convert_dialogue_elements_shiftjis(file_path, output_path)

if __name__ == "__main__":
    main()
