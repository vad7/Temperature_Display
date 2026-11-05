# Архив для прошивки на компьютере без сред разработки: Build/TempDisplay_flash.zip (Readme §8).
#   python Scripts/make_flash_zip.py     - вызывается после каждой сборки (copy_hex.py), берёт hex из Build/;
#                                          вручную - только если менялся Scripts/flash.bat без сборки
# В архиве - папка TempDisplay_flash: flash.bat, avrdude.exe + avrdude.conf (Tools/avrdude), hex TempDisplay_* и ChipInfo_*.
# flash.bat, лежащий рядом с avrdude.exe, ищет avrdude и hex в своей папке.
import glob
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "Build")
OUT = os.path.join(BUILD, "TempDisplay_flash.zip")
FOLDER = "TempDisplay_flash"
TOOL_FILES = ("avrdude.exe", "avrdude.conf", "LICENSE.txt")
HEX_MASKS = ("TempDisplay_*.hex", "ChipInfo_*.hex")

files = [os.path.join(ROOT, "Scripts", "flash.bat")]
files += [os.path.join(ROOT, "Tools", "avrdude", f) for f in TOOL_FILES]
for mask in HEX_MASKS:
    files += sorted(glob.glob(os.path.join(BUILD, mask)))

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in files:
        z.write(f, FOLDER + "/" + os.path.basename(f))

print("архив ->", os.path.relpath(OUT, ROOT), "%.1f МБ, файлов: %d" % (os.path.getsize(OUT) / 1e6, len(files)))
