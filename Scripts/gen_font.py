# Шрифт интерфейса для Adafruit GFX (формат GFXfont) из DejaVu Sans - только символы, которые выводит прошивка.
#   python Scripts/gen_font.py   -> TempDisplay/include/font_ui_s.h (12 px, 128x160), font_ui_l.h (20 px, 240x320)
#                                   + work/png/font_preview.png (строка из сгенерированных битов, x3)
# Набор символов: строки PSTR("...") в TempDisplay/src/*.cpp + ALWAYS (цифры и знаки чисел). После изменения текстов
# на экране - перезапустить (скилл build-check), иначе новый символ не нарисуется.
# Коды: символы чисел (ASCII из ALWAYS: цифры, знаки) - свои коды 0x20 .. FONT_ASCII_LAST; все остальные (буквы,
# в т. ч. латинские, «°») - подряд следом по возрастанию Unicode; таблица FontUiMap[] (Unicode) - для перекодировки
# в utf8ToFont() (ui.cpp). Так таблица глифов не растягивается из-за редких латинских букв.
# Таблица глифов - только на этот диапазон (7 байт на код), растр - 1 бит, глиф с границы байта.
# DejaVu Sans - свободная лицензия (Bitstream Vera / DejaVu), берётся из пакета matplotlib.
import glob
import os
import re

import matplotlib
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf")
FIRST = 0x20
THRESHOLD = 110                          # порог 1 бит из сглаженного растра (0..255)
ALWAYS = "0123456789-.%: " + "°"     # выводятся числами / знаками, не строками PSTR
FONTS = (                                # (имя в C, размер в пикселях, файл)
    ("FontUiS", 12, "font_ui_s.h"),      # экраны 128x160
    ("FontUiL", 20, "font_ui_l.h"),      # экран 240x320
)


def used_chars():
    chars = set(ALWAYS)
    for path in glob.glob(os.path.join(ROOT, "TempDisplay", "src", "*.cpp")):
        src = open(path, encoding="utf-8").read()
        for s in re.findall(r'PSTR\("((?:[^"\\]|\\.)*)"\)', src):
            chars.update(s)
    return chars


def code_table():
    """[(код, символ или None)] от FIRST: ASCII - на своих местах, остальное - подряд следом; и список Unicode."""
    used = used_chars()
    ascii_used = sorted(c for c in used if c in ALWAYS and " " <= c <= "~")
    other = sorted(c for c in used if c not in ascii_used)
    last_ascii = ord(ascii_used[-1]) if ascii_used else FIRST
    table = [(code, chr(code) if chr(code) in used else None) for code in range(FIRST, last_ascii + 1)]
    map_first = last_ascii + 1
    table += [(map_first + i, c) for i, c in enumerate(other)]
    return table, map_first, other


def render(font, ch):
    """Растр глифа: (ширина, высота, xOffset, yOffset от базовой линии, xAdvance, биты построчно)."""
    adv = int(round(font.getlength(ch)))
    size = font.size * 3
    img = Image.new("L", (size, size), 0)
    ox, oy = font.size, font.size * 2                      # перо: левый край, базовая линия
    ImageDraw.Draw(img).text((ox, oy), ch, font=font, fill=255, anchor="ls")
    px = img.load()
    pts = [(x, y) for y in range(size) for x in range(size) if px[x, y] >= THRESHOLD]
    if not pts:
        return 0, 0, 0, 0, adv, []
    x0 = min(p[0] for p in pts)
    x1 = max(p[0] for p in pts)
    y0 = min(p[1] for p in pts)
    y1 = max(p[1] for p in pts)
    bits = [1 if px[x, y] >= THRESHOLD else 0 for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    return x1 - x0 + 1, y1 - y0 + 1, x0 - ox, y0 - oy, adv, bits


def make(cname, px_size, fname, table, map_first, mapped):
    font = ImageFont.truetype(TTF, px_size)
    bitmap, glyphs = [], []
    for code, ch in table:
        if ch is None:
            glyphs.append((len(bitmap), 0, 0, 0, 0, 0, code, ""))
            continue
        w, h, xo, yo, adv, bits = render(font, ch)
        off = len(bitmap)
        acc, n = 0, 0
        for b in bits:                                      # биты подряд, старший первым
            acc = (acc << 1) | b
            n += 1
            if n == 8:
                bitmap.append(acc)
                acc, n = 0, 0
        if n:
            bitmap.append(acc << (8 - n))
        glyphs.append((off, w, h, adv, xo, yo, code, ch))
    ascent, descent = font.getmetrics()
    y_adv = ascent + descent
    last = table[-1][0]

    out = os.path.join(ROOT, "TempDisplay", "include", fname)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("// %s - сгенерировано Scripts/gen_font.py (DejaVu Sans %d px), не править руками.\n" % (fname, px_size))
        f.write("// Коды: ASCII - свои, с 0x%02X - символы FontUiMap[] (Unicode) подряд.\n#pragma once\n" % map_first)
        f.write("#include <Adafruit_GFX.h>\n\n")
        f.write("#define FONT_ASCII_LAST 0x%02X   // ASCII до этого кода - свои коды\n" % (map_first - 1))
        f.write("#define FONT_MAP_FIRST  0x%02X\n" % map_first)
        f.write("#define FONT_MAP_COUNT  %d\n" % len(mapped))
        if "°" in mapped:
            f.write("#define FONT_CODE_DEG   0x%02X   // «°»\n" % (map_first + mapped.index("°")))
        f.write("\nconst uint16_t FontUiMap[] PROGMEM = {\n")
        for i in range(0, len(mapped), 12):
            f.write("    " + ", ".join("0x%04X" % ord(c) for c in mapped[i:i + 12]) + ",\n")
        f.write("};\n\nconst uint8_t %sBitmaps[] PROGMEM = {\n" % cname)
        for i in range(0, len(bitmap), 16):
            f.write("    " + ", ".join("0x%02X" % b for b in bitmap[i:i + 16]) + ",\n")
        f.write("};\n\nconst GFXglyph %sGlyphs[] PROGMEM = {\n" % cname)
        for off, w, h, adv, xo, yo, code, ch in glyphs:
            f.write("    { %5d, %2d, %2d, %2d, %3d, %3d },  // 0x%02X %s\n"
                    % (off, w, h, adv, xo, yo, code, ch if ch.strip() else ""))
        f.write("};\n\nconst GFXfont %s PROGMEM = { (uint8_t*)%sBitmaps, (GFXglyph*)%sGlyphs, 0x%02X, 0x%02X, %d };\n"
                % (cname, cname, cname, FIRST, last, y_adv))
    print("%s: %d б растр + %d б глифы (%d кодов) + %d б таблица Unicode, высота строки %d -> %s"
          % (cname, len(bitmap), len(glyphs) * 7, len(glyphs), len(mapped) * 2, y_adv, os.path.relpath(out, ROOT)))
    return bitmap, glyphs, y_adv


def preview(fonts, table, text="макс 23.4° мин -12.5° 85% Опрос датчика 10 с Тенденция за 1 ч -6ч"):
    """work/png/font_preview.png - строка, нарисованная из сгенерированных битов (как в GFX), увеличение x3."""
    code_of = {ch: code for code, ch in table if ch}
    codes = [code_of.get(c, FIRST) for c in text]
    rows = []
    for bitmap, glyphs, y_adv in fonts:
        w = sum(glyphs[c - FIRST][3] for c in codes) + 4
        img = Image.new("L", (w, y_adv + 4), 255)
        px = img.load()
        x, base = 2, y_adv - 4
        for c in codes:
            off, gw, gh, adv, xo, yo, _, _ = glyphs[c - FIRST]
            for i in range(gw * gh):
                if bitmap[off + i // 8] & (0x80 >> (i % 8)):
                    px[x + xo + i % gw, base + yo + i // gw] = 0
            x += adv
        rows.append(img)
    out = Image.new("L", (max(r.width for r in rows), sum(r.height for r in rows)), 255)
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height
    out = out.resize((out.width * 3, out.height * 3), Image.NEAREST)
    path = os.path.join(ROOT, "work", "png", "font_preview.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)
    print("предпросмотр ->", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    TABLE, MAP_FIRST, MAPPED = code_table()
    preview([make(c, s, f, TABLE, MAP_FIRST, MAPPED) for c, s, f in FONTS], TABLE)
