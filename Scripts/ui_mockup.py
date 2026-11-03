# Макет экранов термометра без железа: повторяет разметку и рисование TempDisplay/src/ui.cpp (Readme §6).
#   python Scripts/ui_mockup.py   ->  Docs/ui_mockup_320x240.png, _160x128.png (альбомная), _240x320.png, _128x160.png
#   (книжная: «Поворот» 90 / 270°) - картинки Readme §6
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
# пункты настроек - порядок и названия из menu.h (MENU_ITEMS: X(ITEM_..., "..."))
MENU = re.findall(r'X\(\s*(ITEM_\w+)\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)',
                  open(os.path.join(SRC, "include", "menu.h"), encoding="utf-8").read())
ITEM = {name: i for i, (name, _) in enumerate(MENU)}


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
        self.hum_y = self.h - self.m - self.lh
        land = self.w >= self.h
        band = 2 * self.lh + self.m // 2                   # книжная: строки макс и мин
        zx, zy = self.m, (self.m + self.lh + self.m // 2) if land else self.m
        zw = self.w - 2 * self.m - self.aw if land else self.w - 2 * self.m
        zh = self.h - 2 * (self.m + self.lh) - self.m if land else self.hum_y - band - 3 * self.m
        self.dh = zh * UIC["DIGIT_FILL_PCT"] // 100
        self.dw = self.dh * UIC["DIGIT_ASPECT_PCT"] // 100
        dw_max = zw * 10 // UIC["DIGIT_W_DIV10"]
        if self.dw > dw_max:
            self.dw = dw_max
            self.dh = self.dw * 100 // UIC["DIGIT_ASPECT_PCT"]
        self.t = max(2, self.dw // UIC["SEG_T_DIV"])
        total = self.dw * UIC["DIGIT_W_DIV10"] // 10
        self.dx = zx + (zw - total) // 2
        self.ax = self.w - self.m - self.aw
        if land:
            self.dy = zy + (zh - self.dh) // 2
            self.max_y, self.min_y, self.ay, self.ah = self.m, self.hum_y, zy, zh
        else:                                               # равные зазоры: цифры, макс / мин со стрелкой, влажность
            gap = (self.hum_y - self.m - self.dh - band) // 3
            self.dy = self.m + gap
            self.max_y = self.dy + self.dh + gap
            self.min_y, self.ay, self.ah = self.max_y + band - self.lh, self.max_y, band

    def mm_x(self):                                         # s_mmX: правый край мин / макс
        return self.m + self.g.text_width(self.c10(UIC["MINMAX_WIDEST_C10"]) + DEG)

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

    def draw_temp_static(self):                             # точка («°» у крупных цифр нет)
        x_dot = self.dx + 3 * (self.dw + self.t)
        self.g.fill_rect(x_dot, self.dy + self.dh - self.t, self.t, self.t, C["COL_TEMP"])

    def draw_arrow(self, d):
        if not d:
            return
        cx, cy = self.ax + self.aw // 2, self.ay + self.ah // 2
        ln = min(self.dh, self.ah) * UIC["ARROW_LEN_PCT"] // 100
        hh = ln * UIC["ARROW_HEAD_PCT"] // 100
        hw = min(self.aw // 2 - 1, hh * UIC["ARROW_HEAD_W_PCT"] // 200)
        sw = max(2, hw * 2 * UIC["ARROW_STEM_W_PCT"] // 100)
        tip = cy - ln // 2 if d > 0 else cy + ln // 2
        base = tip + hh if d > 0 else tip - hh
        col = C["COL_UP"] if d > 0 else C["COL_DOWN"]
        self.g.fill_triangle(cx, tip, cx - hw, base, cx + hw, base, col)
        if d > 0:
            self.g.fill_rect(cx - sw // 2, base, sw, cy + ln // 2 - base, col)
        else:
            self.g.fill_rect(cx - sw // 2, cy - ln // 2, sw, base - (cy - ln // 2), col)

    @staticmethod
    def c10(v):
        return ("-" if v < 0 else "") + "%d.%d" % (abs(v) // 10, abs(v) % 10)

    def main(self, sensor, t_c10=0, hum=None, heating=False, trend=None, mn=None, mx=None, failed=False):
        """sensor: None / 'sht' / 'ds'; trend: изменение за период, десятые °C (None - мало данных);
        failed - последнее измерение пропало (ошибка датчика)."""
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
        top, bot = self.max_y, self.min_y
        if mx is not None:
            self.text(self.mm_x(), top, 1, self.c10(mx) + DEG, C["COL_MAX"])
        if not ok:
            self.text(self.m, bot, 0, "нет датчика", C["COL_ERR"])
        elif failed:
            self.text(self.m, bot, 0, "ошибка датчика", C["COL_ERR"])
        elif mn is not None:
            self.text(self.mm_x(), bot, 1, self.c10(mn) + DEG, C["COL_MIN"])
        if ok and sensor == "sht" and hum is not None:
            self.text(self.w - self.m, self.hum_y, 1, "%d%%" % hum, C["COL_EDIT"] if heating else C["COL_TEXT"])

    def splash(self, sensor):
        """Заставка при включении (showSplash в ui.cpp)."""
        self.g.fill_screen(C["COL_BG"])
        step = self.lh * 3 // 2
        top = (self.h - 3 * step - self.lh) // 2
        sens = {"sht": ("5НТ40: а4 а5", C["COL_TEMP"]),
                "ds": ("Дс18В20: Д%d" % CFG["PIN_ONEWIRE"], C["COL_TEMP"]),
                None: ("нет датчика", C["COL_ERR"])}[sensor]
        lines = (("Термометр", C["COL_EDIT"]), ("версия " + CFG["FW_VERSION"].strip('"'), C["COL_TEXT"]),
                 ("автор Вадим", C["COL_TEXT"]), sens)
        for i, (s, c) in enumerate(lines):
            self.text(self.w // 2, top + i * step, 2, s, c)

    def graph(self, pts):
        """pts - точки графика от старой к новой, None - нет данных."""
        g = self.g
        g.fill_screen(C["COL_BG"])
        vals = [v for v in pts if v is not None]
        if not vals:
            self.text(self.w // 2, (self.h - self.lh) // 2, 2, "точки через %d мин" % (CFG["GRAPH_SLOT_S"] // 60),
                      C["COL_TEXT"])
            return
        vmin, vmax = min(vals), max(vals)
        if vmax - vmin < 10:
            c = (vmax + vmin) // 2
            vmin, vmax = c - 5, c + 5
        x0 = self.m + g.text_width(self.c10(-888)) + self.m
        x1 = self.w - self.m - 1
        y0, y1 = self.m + self.asc // 2, self.h - self.m - self.lh - 3
        pw, ph = x1 - x0, y1 - y0
        lbl_h, lbl_w = CFG["GRAPH_LABEL_H"], g.text_width("-24ч") + 1   # не помещаются - реже вдвое
        while lbl_h * pw // 24 < lbl_w and lbl_h < 24:
            lbl_h *= 2
        g.hline(x0, y1, pw + 1, C["COL_GRID"])
        for hr in range(0, 25, CFG["GRAPH_TICK_H"]):
            x = x1 - hr * pw // 24
            if hr % lbl_h == 0:
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

    VALUES = {"ITEM_THR": "0.5" + DEG, "ITEM_TREND": "30 м", "ITEM_MINMAX": "12 ч", "ITEM_POLL": "10 с",
              "ITEM_HEATER": "нет", "ITEM_CORR": "0.0" + DEG, "ITEM_ROT": "0" + DEG, "ITEM_SWAP": "нет", "ITEM_BRIGHT": "100%",
              "ITEM_ERRORS": "37/2"}

    def settings(self, item, edit=False, edit_value=None):
        """item - имя пункта ITEM_* (menu.h)."""
        item = ITEM[item]
        g = self.g
        g.fill_screen(C["COL_BG"])
        self.text(self.w // 2, self.m, 2, "Настройки", C["COL_EDIT"])
        labels = [lab for _, lab in MENU]
        list_h = self.h - 3 * self.m - 2 * self.lh - self.m                 # listH()
        rs = max(self.lh + 1, min(self.lh + self.m, list_h // len(labels)))  # rowStep()
        rows = min(len(labels), list_h // rs)                               # rowsVisible()
        first = max(0, item - rows + 1)                                     # scrollToItem() от первого пункта
        for i in range(first, first + rows):
            lab = labels[i]
            top = self.m + self.lh + self.m + (i - first) * rs
            sel = i == item
            g.fill_rect(0, top - (rs - self.lh) // 2, self.w, rs, C["COL_SEL"] if sel else C["COL_BG"])
            self.text(self.m, top, 0, lab, C["COL_TEXT"])
            val = edit_value if (sel and edit and edit_value) else self.VALUES[MENU[i][0]]
            self.text(self.w - self.m, top, 1, val, C["COL_EDIT"] if (sel and edit) else C["COL_TEMP"])
        top = self.h - self.m - self.lh
        hint = "ДН Кн.1 - сохранить" if edit else "ДН Кн.1 - сброс" if item == ITEM["ITEM_ERRORS"] else "ДН Кн.1 - правка"
        self.text(self.w // 2, top, 2, hint, C["COL_TEXT"])


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
    shot("настройки (Кн.2 / ДН Кн.1)", lambda u: u.settings("ITEM_TREND"))
    shot("правка: корр. температуры", lambda u: u.settings("ITEM_CORR", True, edit_value="-1.2" + DEG))
    shot("правка: яркость (x - ШИМ 31 кГц)", lambda u: u.settings("ITEM_BRIGHT", True, edit_value="50%x"))
    shot("100+ и знак: 104.5", lambda u: u.main("ds", 1045, None, False, None, 990, 1045))
    shot("заставка (3 с или кнопка)", lambda u: u.splash("sht"))
    shot("заставка: DS18B20", lambda u: u.splash("ds"))
    shot("ошибка датчика (старое значение)", lambda u: u.main("sht", -123, 87, False, -8, -141, -98, True))
    shot("правка: мин/макс за", lambda u: u.settings("ITEM_MINMAX", True, edit_value="24 ч"))
    shot("ошибки датчика (ДН Кн.1 - сброс)", lambda u: u.settings("ITEM_ERRORS"))
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
    sheet(240, 320, 2)                                      # «Поворот» 90 / 270°
    sheet(128, 160, 3)
    singles(320, 240, {0: "ui_main", 4: "ui_graph"})
