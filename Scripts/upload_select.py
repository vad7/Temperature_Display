# Выбор загрузчика платы при прошивке (extra_scripts PlatformIO, pre:): тип - из platformio.ini (секция [upload] ->
# custom_bootloader окружения) -> протокол и скорость avrdude, место под загрузчик (лимит размера программы).
# Разово без правки platformio.ini - переменная окружения BOOTLOADER (скорость - BOOT_SPEED):
#   PowerShell:  $env:BOOTLOADER="atmegaboot"; pio run -e nano -t upload   (потом Remove-Item env:BOOTLOADER)
#   sh:          BOOTLOADER=atmegaboot pio run -e nano -t upload
# Какой загрузчик на плате - чтением подписи без записи (Readme §8, «Новая плата»).
# Окружения с программатором (upload_protocol не urclock / arduino, например isp) - не трогаются.
import os

Import("env")  # noqa: F821 - имя задаёт PlatformIO (SCons)

# тип -> (протокол avrdude, {частота кварца: скорость}, место под загрузчик, байт)
BOOTLOADERS = {
    # MiniCore urboot (autobaud: скорость любая из стандартных; как в boards.txt MiniCore)
    "urboot": ("urclock", {8000000: 57600, 16000000: 115200}, 384),
    # Optiboot - «новый» загрузчик Nano / Uno (Arduino IDE: ATmega328P), стандартный у китайских Nano;
    # 8 МГц - ОЦЕНКА / ПРОВЕРИТЬ чтением подписи (при другой скорости - BOOT_SPEED)
    "optiboot": ("arduino", {8000000: 57600, 16000000: 115200}, 512),
    # ATmegaBOOT - штатный Pro Mini и «Old Bootloader» Nano (Arduino IDE), STK500 v1 1.16, 2 КБ с 0x7800
    "atmegaboot": ("arduino", {8000000: 57600, 16000000: 57600}, 2048),
}
ALIASES = {"old": "atmegaboot", "new": "optiboot", "minicore": "urboot"}

protocol_cfg = env.subst("$UPLOAD_PROTOCOL")                                                      # noqa: F821
if protocol_cfg in ("urclock", "arduino"):
    name = (os.environ.get("BOOTLOADER") or env.GetProjectOption("custom_bootloader", "urboot")).strip().lower()  # noqa: F821
    name = ALIASES.get(name, name)
    if name not in BOOTLOADERS:
        raise SystemExit("upload_select: загрузчик '%s' - нужно одно из %s (или %s)"
                         % (name, ", ".join(BOOTLOADERS), ", ".join(ALIASES)))
    protocol, speeds, size = BOOTLOADERS[name]
    board = env.BoardConfig()                                                                     # noqa: F821
    # кварц платы (у Nano с делителем CLKPR f_cpu = 8 МГц, а загрузчик работает до делителя на 16 МГц)
    xtal = int(env.GetProjectOption("custom_xtal", "") or board.get("build.f_cpu").rstrip("L"))   # noqa: F821
    if xtal not in speeds:
        raise SystemExit("upload_select: нет скорости загрузчика %s для кварца %d Гц - задать BOOT_SPEED" % (name, xtal))
    speed = int(os.environ.get("BOOT_SPEED") or speeds[xtal])
    env.Replace(UPLOAD_PROTOCOL=protocol, UPLOAD_SPEED=speed)                                     # noqa: F821
    board.update("upload.protocol", protocol)
    board.update("bootloader.size", size)      # frameworks/arduino.py платформы вычтет из upload.maximum_size
    print("Загрузчик: %s (%s, %d бод, %d б)%s" % (name, protocol, speed, size,
                                                 " (переменные окружения)" if os.environ.get("BOOTLOADER") else ""))
