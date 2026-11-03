# Разбор flash прошивки по группам (по именам символов avr-nm).
#   python Scripts/flash_report.py [окружение]      (по умолчанию nano8; прошивка должна быть собрана)
# LTO встраивает функции друг в друга: часть нашего кода и библиотек попадает в `main` и в функции экрана -
# группа «main (+ встроенное)» поэтому велика. «Не по символам» - векторы прерываний, код запуска, выравнивание.
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = sys.argv[1] if len(sys.argv) > 1 else "nano8"
ELF = os.path.join(ROOT, ".pio", "build", ENV, "firmware.elf")
TC = os.path.join(os.path.expanduser("~"), ".platformio", "packages", "toolchain-atmelavr", "bin")

GROUPS = (   # (название, регулярное выражение по имени символа) - первая подходящая
    ("Шрифт интерфейса (font_ui_*.h)", r"^FontUi"),
    ("Встроенный шрифт GFX (не используется, держит drawChar)", r"^font$"),
    ("Adafruit GFX: текст (drawChar, write, getTextBounds)", r"Adafruit_GFX::(drawChar|write|getTextBounds|charBounds)"),
    ("Adafruit GFX: графика", r"Adafruit_GFX::"),
    ("Драйвер экрана (SPITFT, ST77xx, SPI)", r"Adafruit_SPITFT|Adafruit_ST77|Adafruit_ST7789|Adafruit_ST7735|SPIClass"),
    ("I2C (Wire, twi, прерывание TWI)", r"TwoWire|twi_|__vector_24"),
    ("1-Wire + DallasTemperature", r"OneWire|DallasTemperature"),
    ("Плавающая точка (float)", r"^__\w*(sf|fp)\w*|lround|floor|^__fixunssfsi|^__floatsisf|^__floatunsisf"),
    ("malloc / free (динамическая память - не должно быть)", r"^malloc$|^free$|__brkval|__flp|operator new|operator delete"),
    ("Наш код: экраны (ui.cpp)", r"drawMainValues|drawGraph|drawRow|drawHint|showMain|showSettings|drawTemp|drawCell|"
                                  r"drawArrow|drawText|textWidth|utf8ToFont|append(Num|C10|Char)|layout|segRect|"
                                  r"cellX|editStep|selectStep|item(Label|Value)|rowTop|Ui::"),
    ("Наш код: датчик, история, кнопки, настройки", r"detect|store|fail|cooling|sht\w+|crc8|Sensor::|History::|accClose|"
                                                     r"push|Buttons::|pollOne|Cfg::|crcOf|indexOf|defaults"),
    ("main (+ встроенное LTO: setup, loop, части модулей)", r"^main$"),
    ("Ядро Arduino (millis, пины, Print, таймер, конструкторы)", r"Print::|digital|pinMode|millis|micros|delay|"
                                                                 r"__vector_16|^init$|global constructors|turnOffPWM|"
                                                                 r"Stream::|itoa|__u?div|__u?mul|__ctors|__do_"),
)


def main():
    out = subprocess.run([os.path.join(TC, "avr-nm"), "-C", "--size-sort", "-S", "-t", "d", ELF],
                         capture_output=True, text=True, check=True).stdout
    sizes = {name: 0 for name, _ in GROUPS}
    sizes["Прочее"] = 0
    rest = []
    total_sym = 0
    for line in out.splitlines():
        m = re.match(r"^\d+ (\d+) ([tTwWdDvV]) (.+)$", line)     # только то, что лежит во flash (без b/B - ОЗУ)
        if not m:
            continue
        size, name = int(m.group(1)), m.group(3)
        total_sym += size
        for gname, rx in GROUPS:
            if re.search(rx, name):
                sizes[gname] += size
                break
        else:
            sizes["Прочее"] += size
            rest.append((size, name))
    flash = int(re.search(r"(\d+)", subprocess.run(
        [os.path.join(TC, "avr-size"), "-A", ELF], capture_output=True, text=True).stdout.split(".text")[1]).group(1))
    data = subprocess.run([os.path.join(TC, "avr-size"), "-A", ELF], capture_output=True, text=True).stdout
    m = re.search(r"^\.data\s+(\d+)", data, re.M)
    flash += int(m.group(1)) if m else 0
    sizes["Не по символам (векторы, запуск, выравнивание)"] = max(0, flash - total_sym)

    print("Flash %s: %d б\n" % (ENV, flash))
    for name, size in sorted(sizes.items(), key=lambda kv: -kv[1]):
        if size:
            print("%6d б  %5.1f %%  %s" % (size, 100.0 * size / flash, name))
    if rest:
        print("\nКрупное в «Прочее»:")
        for size, name in sorted(rest, reverse=True)[:10]:
            print("%6d б  %s" % (size, name))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
