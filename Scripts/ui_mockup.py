# Макет экранов термометра без железа: повторяет разметку и рисование TempDisplay/src/ui.cpp (Readme §6).
#   python Scripts/ui_mockup.py   ->  Docs/ui_mockup_320x240.png, Docs/ui_mockup_160x128.png (картинки Readme §6)
# Константы разметки - из ui.cpp, цвета и параметры - из config.h, текст - тем же шрифтом font_ui_*.h (биты как в GFX,
# границы строки - как Adafruit_GFX::getTextBounds). При изменении функций рисования в ui.cpp - обновить здесь.
import math
import os
import re

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "TempDisplay")
OUT = os.path.join(ROOT, "Docs")


def defines(path):
    """#define ИМЯ значение -> словарь (числа, {..}-списки, остальное - строкой)."""
    d = {}
    for name, val in re.findall(r"^#define\s+(\w+)\s+([^/\n]+)", open(path, encoding="utf-8").read(), re.M):
        val = val.strip()
        if val.startswith("{"):
            d[name] = [int(v) for v in re.findall(r"\d+", val)]
            continue
        m = re.match(r"^(0x[0-9A-Fa-f]+|\d+)(UL|L|U)?$", val)
        d[name] = int(m.group(1), 0) if m else val
    return d


CFG = defines(os.path.join(SRC, "include", "config.h"))
UIC = defines(os.path.join(SRC, "src", "ui.cpp"))


def rgb(c565):
    r, g, b = (c565 >> 11) & 0x1F, (c565 >> 5) & 0x3F, c565 & 0x1F
    return (r * 255 // 31, g * 255 // 63, b * 255 // 31)


C = {k: rgb(v) for k, v in CFG.items() if k.startswith("COL_")}


class Font:
    """GFXfont из font_ui_*.h: глифы, растр, таблица Unicode."""

    def __init__(self, fname):
        src = open(os.path.join(SRC, "include", fname), encoding="utf-8").read()
        num = lambda name: int(re.search(r"#define %s\s+(0x[0-9A-Fa-f]+|\d+)" % name, src).group(1), 0)
        self.ascii_last, self.map_first = num("FONT_ASCII_LAST"), num("FONT_MAP_FIRST")
        arr = lambda name: re.search(r"%s\[\] PROGMEM = \{(.*?)\};" % name, src, re.S).group(1)
        self.map = [int(v, 16) for v in re.findall(r"0x[0-9A-Fa-f]+", arr("FontUiMap"))]
        self.bitmap = [int(v, 16) for v in re.findall(r"0x[0-9A-Fa-f]+", arr(r"FontUi[SL]Bitmaps"))]
        self.glyphs = [tuple(int(v) for v in g) for g in
                       re.findall(r"\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}", src)]
        m = re.search(r"const GFXfont \w+ PROGMEM = \{[^,]+,[^,]+, (0x[0-9A-F]+), (0x[0-9A-F]+), (\d+) \}", src)
        self.first, self.last, self.y_adv = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3))

    def codes(self, text):                                  # как utf8ToFont()
        out = []
        for ch in text:
            u = ord(ch)
            if u > self.ascii_last:
                u = self.map_first + self.map.index(u) if u in self.map else ord(" ")
            out.append(u)
        return out

    def glyph(self, code):
        return self.glyphs[code - self.first]


class Gfx:
    """Минимум Adafruit GFX на PIL: те же примитивы и текст с шрифтом GFXfont."""

    def __init__(self, w, h, font):
        self.w, self.h, self.font = w, h, font
        self.img = Image.new("RGB", (w, h), C["COL_BG"])
        self.d = ImageDraw.Draw(self.img)
        self.px = self.img.load()

    def fill_rect(self, x, y, w, h, c):
        if w > 0 and h > 0:
            self.d.rectangle([x, y, x + w - 1, y + h - 1], fill=c)

    def fill_screen(self, c):
        self.fill_rect(0, 0, self.w, self.h, c)

    def pixel(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = c

    def hline(self, x, y, w, c):
        self.fill_rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.fill_rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        self.d.line([x0, y0, x1, y1], fill=c)

    def fill_circle(self, cx, cy, r, c):
        for y in range(-r, r + 1):
            dx = int(math.isqrt(r * r - y * y))
            self.hline(cx - dx, cy + y, 2 * dx + 1, c)

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, c):
        self.d.polygon([(x0, y0), (x1, y1), (x2, y2)], fill=c)

    def bounds(self, text):                                 # Adafruit_GFX::getTextBounds(text, 0, 0, ...)
        x = 0
        minx = miny = 0x7FFF
        maxx = maxy = -1
        for code in self.font.codes(text):
            _, gw, gh, adv, xo, yo = self.font.glyph(code)
            x1, y1 = x + xo, yo
            minx, miny = min(minx, x1), min(miny, y1)
            maxx, maxy = max(maxx, x1 + gw - 1), max(maxy, y1 + gh - 1)
            x += adv
        if maxx < minx:
            return 0, 0, 0, 0
        return minx, miny, maxx - minx + 1, maxy - miny + 1

    def text_width(self, text):                             # textWidth() в ui.cpp: w + x1
        x1, _, w, _ = self.bounds(text)
        return w + x1

    def print(self, x, y, text, c):                         # курсор - базовая линия
        for code in self.font.codes(text):
            off, gw, gh, adv, xo, yo = self.font.glyph(code)
            for i in range(gw * gh):
                if self.font.bitmap[off + i // 8] & (0x80 >> (i % 8)):
                    self.pixel(x + xo + i % gw, y + yo + i // gw, c)
            x += adv


# ---------------------------------------------------------------- повтор ui.cpp
SEG_DIGITS = [0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07, 0x7F, 0x6F]
SEG_MINUS, SEG_BLANK, SEG_ONE = 0x40, 0x00, 0x06
DEG = "°"


class Ui:
    def __init__(self, w, h):
        self.g = Gfx(w, h, Font("font_ui_l.h" if w > 200 else "font_ui_s.h"))
        self.layout()

    def layout(self):
        g = self.g
        self.w, self.h = g.w, g.h
        self.m = max(2, self.w // UIC["MARGIN_DIV"])
        _, y1, _, h = g.bounds("ЙКу")
        self.asc, self.lh = -y1, h + 1
        self.aw = self.w * UIC["ARROW_W_PCT"] // 100
        zx, zy = self.m, self.m + self.lh + self.m // 2
        zw, zh = self.w - 2 * self.m - self.aw, self.h - 2 * (self.m + self.lh) - self.m
        self.dh = zh * UIC["DIGIT_FILL_PCT"] // 100
        self.dw = self.dh * UIC["DIGIT_ASPECT_PCT"] // 100
        dw_max = zw * 10 // UIC["DIGIT_W_DIV10"]
        if self.dw > dw_max:
            self.dw = dw_max
            self.dh = self.dw * 100 // UIC["DIGIT_ASPECT_PCT"]
        self.t = max(2, self.dw // UIC["SEG_T_DIV"])
        total = self.dw * UIC["DIGIT_W_DIV10"] // 10
        self.dx, self.dy = zx + (zw - total) // 2, zy + (zh - self.dh) // 2
        self.ax, self.ay, self.ah = self.w - self.m - self.aw, zy, zh

    def text(self, x, top, align, s, c):
        w = self.g.text_width(s)
        x = x - w if align == 1 else x - w // 2 if align == 2 else x
        self.g.print(x, top + self.asc, s, c)

    # крупные цифры
    def cell_x(self, i):
        g = self.t
        return self.dx + i * (self.dw + g) if i < 3 else self.dx + 3 * (self.dw + g) + self.t + g

    def draw_cell(self, x, mask):
        t, w, y = self.t, self.dw, self.dy
        hh = (self.dh - 3 * t) // 2
        if mask == SEG_ONE:                                 # «1» - по центру ячейки (как в ui.cpp)
            xc = x + (w - t) // 2
            self.g.fill_rect(xc, y + t, t, hh, C["COL_TEMP"])
            self.g.fill_rect(xc, y + 2 * t + hh, t, hh, C["COL_TEMP"])
            return
        segs = ((x + t, y, w - 2 * t, t), (x + w - t, y + t, t, hh), (x + w - t, y + 2 * t + hh, t, hh),
                (x + t, y + 2 * t + 2 * hh, w - 2 * t, t), (x, y + 2 * t + hh, t, hh), (x, y + t, t, hh),
                (x + t, y + t + hh, w - 2 * t, t))
        for b, r in enumerate(segs):
            if mask & (1 << b):
                self.g.fill_rect(*r, C["COL_TEMP"])

    def draw_temp(self, valid, c10):
        if not valid:
            m = [SEG_BLANK, SEG_MINUS, SEG_MINUS, SEG_MINUS]
        else:
            neg = c10 < 0
            a = abs(c10)
            frac, a = a % 10, a // 10
            ones, tens, hund = a % 10, (a // 10) % 10, a // 100
            m = [0, 0, SEG_DIGITS[ones], SEG_DIGITS[frac]]
            if hund:
                m[0], m[1] = SEG_DIGITS[hund % 10], SEG_DIGITS[tens]
            elif tens:
                m[0], m[1] = (SEG_MINUS if neg else SEG_BLANK), SEG_DIGITS[tens]
            else:
                m[0], m[1] = SEG_BLANK, (SEG_MINUS if neg else SEG_BLANK)
        for i in range(4):
            self.draw_cell(self.cell_x(i), m[i])

    def draw_temp_static(self):
        x_dot = self.dx + 3 * (self.dw + self.t)
        self.g.fill_rect(x_dot, self.dy + self.dh - self.t, self.t, self.t, C["COL_TEMP"])
        r = self.dw // 5
        cx, cy = self.cell_x(3) + self.dw + self.t + r, self.dy + r
        self.g.fill_circle(cx, cy, r, C["COL_TEMP"])
        self.g.fill_circle(cx, cy, r - (self.t + 1) // 2, C["COL_BG"])

    def draw_arrow(self, d):
        if not d:
            return
        cx, cy = self.ax + self.aw // 2, self.ay + self.ah // 2
        a = min(self.aw // 2 - 1, self.ah // 3)
        sw, sh = max(2, a // 2), a
        col = C["COL_UP"] if d > 0 else C["COL_DOWN"]
        if d > 0:
            self.g.fill_triangle(cx, cy - a - sh // 2, cx - a, cy - sh // 2, cx + a, cy - sh // 2, col)
            self.g.fill_rect(cx - sw // 2, cy - sh // 2, sw, sh + a // 2, col)
        else:
            self.g.fill_triangle(cx, cy + a + sh // 2, cx - a, cy + sh // 2, cx + a, cy + sh // 2, col)
            self.g.fill_rect(cx - sw // 2, cy - sh // 2 - a // 2, sw, sh + a // 2, col)

    @staticmethod
    def c10(v):
        return ("-" if v < 0 else "") + "%d.%d" % (abs(v) // 10, abs(v) % 10)

    def main(self, sensor, t_c10=0, hum=None, heating=False, trend=None, mn=None, mx=None):
        """sensor: None / 'sht' / 'ds'; trend: изменение за период, десятые °C (None - мало данных)."""
        g = self.g
        g.fill_screen(C["COL_BG"])
        ok = sensor is not None
        self.draw_temp_static()
        self.draw_temp(ok, t_c10)
        thr = CFG["TREND_THR_DEF_C10"]
        d = 0
        if ok and trend is not None:
            d = 1 if trend >= thr else -1 if trend <= -thr else 0
        self.draw_arrow(d)
        top, bot = self.m, self.h - self.m - self.lh
        if mx is not None:
            self.text(self.m, top, 0, "макс " + self.c10(mx) + DEG, C["COL_TEXT"])
        if not ok:
            self.text(self.m, bot, 0, "нет датчика", C["COL_UP"])
        elif mn is not None:
            self.text(self.m, bot, 0, "мин " + self.c10(mn) + DEG, C["COL_TEXT"])
        if ok and sensor == "sht" and hum is not None:
            self.text(self.w - self.m, bot, 1, "%d%%" % hum, C["COL_EDIT"] if heating else C["COL_TEXT"])

    def graph(self, pts):
        """pts - точки графика от старой к новой, None - нет данных."""
        g = self.g
        g.fill_screen(C["COL_BG"])
        vals = [v for v in pts if v is not None]
        if not vals:
            self.text(self.w // 2, (self.h - self.lh) // 2, 2, "нет данных за сутки", C["COL_TEXT"])
            return
        vmin, vmax = min(vals), max(vals)
        if vmax - vmin < 10:
            c = (vmax + vmin) // 2
            vmin, vmax = c - 5, c + 5
        x0 = self.m + g.text_width(self.c10(-888)) + self.m
        x1 = self.w - self.m - 1
        y0, y1 = self.m + self.asc // 2, self.h - self.m - self.lh - 3
        pw, ph = x1 - x0, y1 - y0
        g.hline(x0, y1, pw + 1, C["COL_GRID"])
        for hr in range(0, 25, CFG["GRAPH_TICK_H"]):
            x = x1 - hr * pw // 24
            if hr % CFG["GRAPH_LABEL_H"] == 0:
                g.vline(x, y0, ph, C["COL_GRID"])
                if 0 < hr < 24:
                    self.text(x, y1 + 3, 2, "-%dч" % hr, C["COL_TEXT"])
            else:
                g.vline(x, y1 - 2, 5, C["COL_GRID"])
        self.text(x0 - self.m // 2, y0 - self.asc // 2, 1, self.c10(vmax), C["COL_TEXT"])
        self.text(x0 - self.m // 2, y1 - self.lh, 1, self.c10(vmin), C["COL_TEXT"])
        if vmin < 0 < vmax:
            g.hline(x0, y1 - (-vmin) * ph // (vmax - vmin), pw, C["COL_ZERO"])
        n, prev = len(pts), None
        for i, v in enumerate(pts):
            if v is None:
                prev = None
                continue
            age = n - 1 - i
            x = x1 - age * pw // (CFG["GRAPH_SLOTS"] - 1)
            y = y1 - (v - vmin) * ph // (vmax - vmin)
            if prev:
                g.line(prev[0], prev[1], x, y, C["COL_PLOT"])
            else:
                g.pixel(x, y, C["COL_PLOT"])
            prev = (x, y)

    def settings(self, item, edit=False, values=("10 с", "1 ч", "0.5" + DEG, "выкл", "выкл"), edit_value=None):
        g = self.g
        g.fill_screen(C["COL_BG"])
        self.text(self.w // 2, self.m, 2, "Настройки", C["COL_EDIT"])
        labels = ("Опрос датчика", "Тенденция за", "Порог стрелки", "Прогрев датчика", "Переворот")
        rs = min(self.lh + self.m, (self.h - 3 * self.m - 2 * self.lh - self.m) // len(labels))   # rowStep()
        for i, lab in enumerate(labels):
            top = self.m + self.lh + self.m + i * rs
            sel = i == item
            g.fill_rect(0, top - (rs - self.lh) // 2, self.w, rs, C["COL_SEL"] if sel else C["COL_BG"])
            self.text(self.m, top, 0, lab, C["COL_TEXT"])
            val = edit_value if (sel and edit and edit_value) else values[i]
            self.text(self.w - self.m, top, 1, val, C["COL_EDIT"] if (sel and edit) else C["COL_TEMP"])
        top = self.h - self.m - self.lh
        self.text(self.w // 2, top, 2, "ДН Кн.1 - сохранить" if edit else "ДН Кн.1 - правка", C["COL_TEXT"])


# ---------------------------------------------------------------- сценарии
def graph_points():
    pts = []
    for i in range(CFG["GRAPH_SLOTS"]):
        h = i / 6.0                                         # часов от начала суток
        v = -30 + 55 * math.sin((h - 9) / 24 * 2 * math.pi) + 6 * math.sin(i * 0.9)
        pts.append(None if 60 <= i < 66 else int(v))        # час без датчика
    return pts


def scenarios(w, h):
    shots = []

    def shot(caption, fn):
        ui = Ui(w, h)
        fn(ui)
        shots.append((caption, ui.g.img))

    shot("SHT40, холодает", lambda u: u.main("sht", -123, 87, False, -8, -141, -98))
    shot("SHT40, прогрев (влажность жёлтая)", lambda u: u.main("sht", 234, 97, True, 9, 198, 241))
    shot("DS18B20, стабильно", lambda u: u.main("ds", 56, None, False, 2, 41, 63))
    shot("нет датчика", lambda u: u.main(None, 0, None, False, None, 41, 63))
    shot("график за сутки (Кн.1)", lambda u: u.graph(graph_points()))
    shot("настройки (Кн.2 / ДН Кн.1)", lambda u: u.settings(1))
    shot("правка: прогрев", lambda u: u.settings(3, True, edit_value="вкл"))
    shot("правка: переворот экрана", lambda u: u.settings(4, True, edit_value="вкл"))
    shot("100+ и знак: 104.5", lambda u: u.main("ds", 1045, None, False, None, 990, 1045))
    return shots


def sheet(w, h, scale, cols=4):
    shots = scenarios(w, h)
    cap_h, pad = 22, 10
    rows = (len(shots) + cols - 1) // cols
    cw, ch = w * scale, h * scale
    out = Image.new("RGB", (cols * (cw + pad) + pad, rows * (ch + cap_h + pad) + pad), (235, 235, 235))
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(out)
    for i, (cap, img) in enumerate(shots):
        x, y = pad + (i % cols) * (cw + pad), pad + (i // cols) * (ch + cap_h + pad)
        d.text((x, y), cap, fill=(0, 0, 0), font=font)
        out.paste(img.resize((cw, ch), Image.NEAREST), (x, y + cap_h))
    path = os.path.join(OUT, "ui_mockup_%dx%d.png" % (w, h))
    os.makedirs(OUT, exist_ok=True)
    out.save(path)
    print("макет ->", os.path.relpath(path, ROOT))


def singles(w, h, names):
    """Отдельные экраны в натуральную величину (картинки Readme §1): {номер сценария: имя файла}."""
    shots = scenarios(w, h)
    for i, name in names.items():
        path = os.path.join(OUT, "%s_%dx%d.png" % (name, w, h))
        shots[i][1].save(path)
        print("экран ->", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    sheet(320, 240, 2)
    sheet(160, 128, 3)
    singles(320, 240, {0: "ui_main", 4: "ui_graph"})
