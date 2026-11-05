# Копирование прошивки после сборки в Build/ корня проекта (extra_scripts PlatformIO, post:).
# Результат: Build/<папка проекта PlatformIO>_<окружение><HEX_SUFFIX>.hex (HEX_SUFFIX задаёт pre-скрипт, если есть)
#   корень (TempDisplay) -> Build/TempDisplay_nano8_240x320_ST7789.hex (суффикс - Scripts/display_select.py)
#   Tests/ChipInfo/     -> Build/ChipInfo_nano16.hex
# Затем обновляет архив Build/TempDisplay_flash.zip (Scripts/make_flash_zip.py): архив не расходится с hex.
import os
import shutil
import subprocess

Import("env")  # noqa: F821 - имя задаёт PlatformIO (SCons)


def project_root(start):
    """Корень репозитория: ближайшая вверх папка с Readme.md и Scripts/."""
    d = start
    while True:
        if os.path.isfile(os.path.join(d, "Readme.md")) and os.path.isdir(os.path.join(d, "Scripts")):
            return d
        up = os.path.dirname(d)
        if up == d:
            return os.path.dirname(start)
        d = up


def copy_hex(source, target, env):
    proj = env.subst("$PROJECT_DIR")
    root = project_root(proj)
    out = os.path.join(root, "Build")
    os.makedirs(out, exist_ok=True)
    dst = os.path.join(out, "%s_%s%s.hex" % (os.path.basename(proj), env.subst("$PIOENV"), env.get("HEX_SUFFIX", "")))
    shutil.copyfile(str(target[0]), dst)
    print("HEX -> " + os.path.relpath(dst, root))
    subprocess.check_call([env.subst("$PYTHONEXE"), os.path.join(root, "Scripts", "make_flash_zip.py")],
                          env=dict(os.environ, PYTHONIOENCODING="utf-8"))


env.AddPostAction("$BUILD_DIR/${PROGNAME}.hex", copy_hex)  # noqa: F821
