# Выбор экрана при сборке (extra_scripts PlatformIO, pre:): разрешение и контроллер - из platformio.ini
# (секция [display] -> custom_lcd_res / custom_lcd_ctrl окружения) -> макросы LCD_RES / LCD_CTRL для config.h.
# Разовая сборка другого экрана без правки platformio.ini - переменные окружения (у pio run нет ключа -O):
#   PowerShell:  $env:LCD_RES="128x160"; $env:LCD_CTRL="ST7735"; pio run -e promini   (потом Remove-Item env:LCD_*)
#   sh:          LCD_RES=128x160 LCD_CTRL=ST7735 pio run -e promini
# Имя hex получает суффикс экрана (HEX_SUFFIX - для copy_hex.py): Build/TempDisplay_promini_240x320_ST7789.hex
import os

Import("env")  # noqa: F821 - имя задаёт PlatformIO (SCons)

# контроллер -> допустимые разрешения
CTRL_RES = {
    "ST7735": ("128x160",),
    "ST7789": ("240x320",),
    "ILI9341": ("240x320",),
}

res = (os.environ.get("LCD_RES") or env.GetProjectOption("custom_lcd_res", "")).strip()                  # noqa: F821
ctrl = (os.environ.get("LCD_CTRL") or env.GetProjectOption("custom_lcd_ctrl", "")).strip().upper()       # noqa: F821
if ctrl not in CTRL_RES:
    raise SystemExit("display_select: контроллер '%s' - нужно одно из %s" % (ctrl, ", ".join(CTRL_RES)))
if res not in CTRL_RES[ctrl]:
    raise SystemExit("display_select: %s - разрешение '%s' не поддерживается (можно: %s)"
                     % (ctrl, res, ", ".join(CTRL_RES[ctrl])))

env.Append(CPPDEFINES=[("LCD_RES", "LCD_RES_" + res), ("LCD_CTRL", "LCD_" + ctrl)])   # noqa: F821
env.Replace(HEX_SUFFIX="_%s_%s" % (res, ctrl))                                        # noqa: F821
print("Экран: %s %s%s" % (res, ctrl, " (переменные окружения)" if os.environ.get("LCD_CTRL") else ""))
