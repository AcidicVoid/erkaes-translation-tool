## Prerequisites
* Rosenkreuzstilette (*ver2.01b is* Steam Version, but you can use whatever version you want)
* DXArc (You may obtain it [here](https://wiki.xentax.spektr.name/index.php/DX_Archive) or [here](https://archive.org/details/dxlibtools))

## Extract files
Encryption key can easily be obtained using DXArc  
You can try this if you're using another version of the game
```
DXArc.exe b "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario.dat"
Quick break v6
  Trying ...
Zero search v5 to v1
  Trying ...
Success: <key> // Key will appear here on success
```
Use the key to extract the scenario files:
```
DXArc.exe ^
 e "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario.dat" ^
 -p <key>  
```
This will create an output folder next to the .dat file:
```
"path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario
├─ talk.ini
├─ talk.txt
├─ talk_grolla.txt
```

Prepare extracted files
---
Now move the output folder to a temp folder. We'll create a copy we can safely edit.  
In this example, this copy will be packed to create a translated scenario.dat file the game will read.
```
cd erkaes-translation-tool
mkdir temp
mv path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario \temp
cd temp
cp -r "scenario" "scenario_translated"
```
Also, make a backup of original scenario file before we overwrite it:
```
cp "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario.dat" ^
 "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario.dat.bak"
```
You now can safely edit the files in scenario_translated


Format
---
* translation files are encoded in Shift JIS
* using standard UTF-8 romaji characters results in super narrow text
  * be sure to write everything in Shift JIS or convert your text

## Pack Files
Use key obtained from DXArc
```
uv run dxarc-pack.py ^
 -k <key> ^
 -i "temp\scenario_translated" ^
 -o "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario.dat"
```

Revert
---
```
cp "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario.dat.bak" ^
 "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario.dat"
```
---
Have fin!  
<◉ )))><<
