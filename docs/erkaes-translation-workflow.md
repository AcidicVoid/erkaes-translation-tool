## Prerequisites
* Rosenkreuzstilette (*ver2.01b is* Steam Version, but you can use whatever version you want)
* DXArc (You may obtain it [here](https://wiki.xentax.spektr.name/index.php/DX_Archive) or [here](https://archive.org/details/dxlibtools))

## Extract files
Encryption key can easily be obtained using DXArc  
You can try this if you're using another version of the game
```
DXArc.exe b "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario.dat"
Quick break v6
  Trying 6A69776F2774756B6EE95EF1 (9596FD09D8D88A927396333D)...
  Trying 6A69776F2774756B676B6972 (9596FD09D8D88A923B1440BE)...
Zero search v5 to v1
  Trying 6A69726F7473756B676A6972 (9596F8098BDF8A923B1540BE)...
  Trying 6A69726F7473756B676A6972 (9596F8098BDF8A923B1540BE)...
  Trying 6A69726F7473756B676A6972 (9596F8098BDF8A923B1540BE)...
  Trying 6A69726F7473756B676A6972 (9596F8098BDF8A923B1540BE)...
  Trying 6A69726F7473756B676A6972 (9596F8098BDF8A923B1540BE)...
  Trying 6A69726F7473756B676A6972 (9596F8098BDF8A923B1540BE)...
  Trying 6A69726F7473756B656A6972 (9596F8098BDF8A922B1540BE)...
Success: 6A69726F7473756B656A6972 (9596F8098BDF8A922B1540BE)
```
Use the key to extract the scenario files:
```
DXArc.exe ^
 e "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario.dat" ^
 -p 6A69726F7473756B656A6972  
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
mkdir temp
cd temp
mv "path\to\SteamLibrary\steamapps\common\Rosenkreuzstilette\data\scenario" "temp"
cp -r "scenario" "scenario_translated"
cd ..
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
```
uv run dxarc-pack.py ^
 -k 6A69726F7473756B656A6972 ^
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
