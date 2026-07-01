Erka:es Translation Tool
---
Tool for re-packing [Rosenkreuzstilette](https://rks.fandom.com/wiki/Rosenkreuzstilette) files.  
This is intended for modification of translation files. Fan-Translations are now an easy thing to do!  
Modification of other files SHOULD be possible but has not been tested.  
Pull requests are welcome!

![Image with example translation](/.github/media/rks-trnsltn-german.png)  
*Example showing German translation*


## Prerequisites
* Rosenkreuzstilette
* [DxArc](https://wiki.xentax.spektr.name/index.php/DX_Archive)
* [uv](https://docs.astral.sh/uv/) (optional)

## Scripts
* **dxarc-pack.py** will pack modified translation files back to an DxLib archive the game can read

## Usage
You can use this workflow to unpack, modify and re-pack translation files:
[Translation Workflow](docs/erkaes-translation-workflow.md)

### Shift-JIS Encoding
Shift-JIS encoding is required for the game to read the translation files. Additionally, the game requires some characters to be [full-width](https://en.wikipedia.org/wiki/Halfwidth_and_fullwidth_forms).  
Since this can be very annoying to maintain, I provide this little tool to ensure all characters are encoded correctly.  
Unfortunately, the game doesn't support propper word-wrapping.

#### Example
```bash
uv run ensure-shift-jis.py "./temp/scenario_translated"
```
#### Notes:
* Character conversion is only roughly tested with a bit of the german translation I wrote. Using languages with non-roman characters may not work as expected.
* Converting command lines like `*プロローグ開始時` or `@c @n` will crash the game.
