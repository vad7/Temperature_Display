# Схема подключения термометра (Readme §4): Docs/schematic.svg и work/png/schematic.png (для просмотра).
#   python Scripts/schematic.py
# Рисуется matplotlib по явным координатам (единица ~ 5 мм). Пины - как в TempDisplay/include/config.h.
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "Docs", "schematic.svg")
PNG = os.path.join(ROOT, "work", "png", "schematic.png")

W, H = 35.0, 19.5          # поле
LW = 1.4                   # толщина линий
FS = 9                     # шрифт подписей
COL = "black"
PCOL = "#b00000"           # цвет имён выводов

fig, ax = plt.subplots(figsize=(W * 0.5, H * 0.5))
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.set_aspect("equal")
ax.axis("off")


def line(*pts, **kw):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=COL, lw=kw.get("lw", LW), solid_capstyle="round")


def text(x, y, s, **kw):
    kw.setdefault("fontsize", FS)
    ax.text(x, y, s, **kw)


def dot(x, y):
    ax.plot([x], [y], "o", color=COL, ms=4)


def term(x, y):
    ax.plot([x], [y], "o", mfc="white", mec=COL, ms=6, mew=LW)


def box(x0, y0, x1, y1, title, pins_l=(), pins_r=(), tsize=10):
    """Прямоугольник с выводами: pins_* = [(имя, y)]. Возвращает словарь имя -> (x, y) конца вывода."""
    line((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))
    text((x0 + x1) / 2, (y0 + y1) / 2, title, ha="center", va="center", fontsize=tsize, fontweight="bold")
    out = {}
    for name, y in pins_l:
        line((x0 - 0.5, y), (x0, y))
        text(x0 + 0.15, y, name, ha="left", va="center", color=PCOL)
        out[name] = (x0 - 0.5, y)
    for name, y in pins_r:
        line((x1, y), (x1 + 0.5, y))
        text(x1 - 0.15, y, name, ha="right", va="center", color=PCOL)
        out[name] = (x1 + 0.5, y)
    return out


def vdd(x, y, label="3.3 В"):
    """Символ питания: вертикальный отвод вверх и перекладина."""
    line((x, y), (x, y + 0.5))
    line((x - 0.35, y + 0.5), (x + 0.35, y + 0.5))
    text(x, y + 0.6, label, ha="center", va="bottom", fontsize=FS - 1)


def gnd(x, y):
    line((x, y), (x, y - 0.4))
    for i, w in enumerate((0.4, 0.26, 0.12)):
        line((x - w, y - 0.4 - i * 0.14), (x + w, y - 0.4 - i * 0.14), lw=LW)


def res_v(x, y0, y1, label):
    """Резистор вертикальный (зигзаг) от y0 до y1."""
    n, a = 6, 0.22
    seg = (y1 - y0) * 0.6
    ys = y0 + (y1 - y0) * 0.2
    pts = [(x, y0), (x, ys)]
    for i in range(n):
        pts.append((x + (a if i % 2 == 0 else -a), ys + seg * (i + 0.5) / n))
    pts += [(x, ys + seg), (x, y1)]
    line(*pts)
    text(x + 0.35, (y0 + y1) / 2, label, ha="left", va="center", fontsize=FS - 1)


def res_h(x0, x1, y, label):
    n, a = 6, 0.22
    seg = (x1 - x0) * 0.6
    xs = x0 + (x1 - x0) * 0.2
    pts = [(x0, y), (xs, y)]
    for i in range(n):
        pts.append((xs + seg * (i + 0.5) / n, y + (a if i % 2 == 0 else -a)))
    pts += [(xs + seg, y), (x1, y)]
    line(*pts)
    text((x0 + x1) / 2, y + 0.35, label, ha="center", va="bottom", fontsize=FS - 1)


def button_h(x0, x1, y, label):
    """Кнопка без фиксации (замыкающая) между x0 и x1."""
    a, b = x0 + (x1 - x0) * 0.25, x1 - (x1 - x0) * 0.25
    line((x0, y), (a, y))
    line((b, y), (x1, y))
    term(a, y)
    term(b, y)
    line((a - 0.1, y + 0.45), (b + 0.1, y + 0.45))
    line(((a + b) / 2, y + 0.45), ((a + b) / 2, y + 0.75))
    text((x0 + x1) / 2, y + 0.85, label, ha="center", va="bottom", fontsize=FS - 1)


def fuse_h(x0, x1, y, label):
    a, b = x0 + (x1 - x0) * 0.25, x1 - (x1 - x0) * 0.25
    line((x0, y), (x1, y))
    line((a, y - 0.22), (b, y - 0.22), (b, y + 0.22), (a, y + 0.22), (a, y - 0.22))
    text((x0 + x1) / 2, y + 0.35, label, ha="center", va="bottom", fontsize=FS - 1)


def pnp(xb, yb):
    """PNP: база слева в (xb, yb), эмиттер сверху (стрелка к базе), коллектор снизу. Возвращает (эмиттер, коллектор)."""
    xbar = xb + 0.5
    line((xb, yb), (xbar, yb))
    line((xbar, yb - 0.5), (xbar, yb + 0.5), lw=LW * 1.6)            # база
    xe = xbar + 0.6
    line((xbar, yb - 0.2), (xe, yb - 0.6), (xe, yb - 1.0))           # коллектор вниз
    line((xe, yb + 0.6), (xe, yb + 1.0))                               # эмиттер вверх
    ax.annotate("", xy=(xbar + 0.05, yb + 0.22), xytext=(xe, yb + 0.6),  # стрелка эмиттера к базе - PNP
                arrowprops=dict(arrowstyle="-|>", color=COL, lw=LW, shrinkA=0, shrinkB=0))
    return (xe, yb + 1.0), (xe, yb - 1.0)


# ---------------------------------------------------------------- Arduino Pro Mini (запасная - Nano)
nano = box(14, 2.2, 19, 16.6, "Arduino\nPro Mini 328\n3.3 В, 8 МГц\n(Baite\nBTE13-010)",
           pins_l=[("VCC", 15.4), ("GND", 13.9), ("A4", 11.0), ("A5", 10.0), ("D2", 7.5), ("D4", 5.2), ("D5", 3.6)],
           pins_r=[("D6", 15.4), ("D8", 12.0), ("D9", 11.0), ("D10", 10.0), ("D11", 9.0), ("D13", 8.0)], tsize=10)
text(14.0, 16.9, "питание 3.3 В - на VCC (не RAW); Nano - на +5V (не VIN)", ha="left", fontsize=FS - 1)

# ---------------------------------------------------------------- TFT
tft = box(28.5, 4.0, 33.5, 15.0, "TFT SPI\nST7735S /\nST7789V",
          pins_l=[("LED", 13.8), ("RST", 12.0), ("DC", 11.0), ("CS", 10.0), ("MOSI", 9.0), ("SCK", 8.0),
                  ("VCC", 6.2), ("GND", 5.0)], tsize=10)
text(31.0, 3.4, "имена выводов у модулей разные -\nсм. таблицы Readme §2", ha="center", va="top", fontsize=FS - 1)
for a, b in (("D8", "RST"), ("D9", "DC"), ("D10", "CS"), ("D11", "MOSI"), ("D13", "SCK")):
    line(nano[a], tft[b])
vdd(27.0, 6.2)
line(tft["VCC"], (27.0, 6.2))
line(tft["GND"], (27.0, 5.0))
gnd(27.0, 5.0)

# Подсветка: D6 -> 1 кОм -> база PNP; база подтянута к эмиттеру 10 кОм (по умолчанию выключено); LOW - светит
xg, yg = 23.2, 15.4
res_h(nano["D6"][0], 22.0, yg, "R5 1 кОм")
line((22.0, yg), (xg, yg))
dot(22.4, yg)
res_v(22.4, yg, 17.6, "R6 10к")
vdd(22.4, 17.6)
src, drn = pnp(xg, yg)
vdd(src[0], src[1])
line(drn, (drn[0], tft["LED"][1]), tft["LED"])
text(src[0] + 0.3, yg + 0.1, "Q1 PNP S8550 / BC327 (TO-92,\nцоколёвку - по даташиту);\nне нужен, если ключ на модуле",
     ha="left", va="center", fontsize=FS - 1)

# ---------------------------------------------------------------- HLK-3M03C
hlk = box(4.0, 13.0, 8.0, 16.3, "HLK-3M03C\n~220 -> 3.3 В",
          pins_l=[("L", 15.4), ("N", 13.9)], pins_r=[("+Vo", 15.4), ("-Vo", 13.9)], tsize=9)
line(hlk["+Vo"], nano["VCC"])
text(12.3, 15.55, "+3.3 В", ha="center", va="bottom", fontsize=FS - 1)
# C1 - на выходе HLK (даташит 3W-C, п. 6.2: электролит 100-220 мкФ)
dot(10.0, 15.4)
dot(10.0, 13.9)
line((10.0, 15.4), (10.0, 14.78))
line((9.7, 14.78), (10.3, 14.78))
line((9.7, 14.55), (10.3, 14.55))
line((10.0, 14.55), (10.0, 13.9))
text(9.55, 14.95, "+", ha="center", va="center", fontsize=FS - 1)
text(10.4, 14.66, "C1 100 мкФ", ha="left", va="center", fontsize=FS - 1)
line(hlk["-Vo"], nano["GND"])
gnd(12.5, 13.9)
dot(12.5, 13.9)
# Вход (даташит 3W-C, п. 6.1): F1 1 А / 250 В медленный (варистор 10D561K - по решению пользователя не ставится)
fuse_h(0.8, 2.6, 15.4, "F1 1А T")
line((2.6, 15.4), hlk["L"])
line((0.8, 13.9), hlk["N"])
term(0.8, 15.4)
term(0.8, 13.9)
text(0.65, 15.4, "L", ha="right", va="center")
text(0.65, 13.9, "N", ha="right", va="center")
text(0.2, 16.4, "~220 В", ha="left", va="bottom", fontsize=FS)

# ---------------------------------------------------------------- SHT40
sht = box(3.5, 8.6, 6.8, 12.3, "SHT40\n(I2C)",
          pins_r=[("VDD", 11.95), ("SDA", 11.0), ("SCL", 10.0), ("GND", 9.0)], tsize=9)
line(sht["SDA"], nano["A4"])
line(sht["SCL"], nano["A5"])
line(sht["VDD"], (7.9, 11.95))
vdd(7.9, 11.95)
line(sht["GND"], (8.5, 9.0))
gnd(8.5, 9.0)
dot(9.6, 11.0)
res_v(9.6, 11.0, 12.6, "R2 4.7к")
vdd(9.6, 12.6, "")
dot(11.2, 10.0)
res_v(11.2, 10.0, 12.6, "R3 4.7к")
vdd(11.2, 12.6, "")

# ---------------------------------------------------------------- DS18B20
ds = box(3.5, 6.4, 6.8, 8.4, "DS18B20",
         pins_r=[("VDD", 8.05), ("DQ", 7.5), ("GND", 6.8)], tsize=9)
line(ds["DQ"], nano["D2"])
line(ds["VDD"], (7.3, 8.05))
vdd(7.3, 8.05, "")
line(ds["GND"], (7.9, 6.8))
gnd(7.9, 6.8)
dot(9.6, 7.5)
res_v(9.6, 7.5, 9.0, "R4 4.7к")
vdd(9.6, 9.0, "")

# ---------------------------------------------------------------- Кнопки (на GND, подтяжка - внутренняя МК)
for p, name in (("D4", "Кн.1 (верхняя)"), ("D5", "Кн.2 (нижняя)")):
    x, y = nano[p]
    button_h(9.0, x, y, name)
    gnd(9.0, y)

text(0.3, 1.5, "GND всех модулей, Pro Mini и выхода HLK - общий. Подтяжки I2C - если их нет на модуле SHT40. "
     "Кнопки - на GND, подтяжка внутренняя (INPUT_PULLUP).", ha="left", fontsize=FS - 1)
text(0.3, 0.9, "Прошивка при питании от HLK - VCC адаптера USB-UART не подключать (Nano: USB даёт 5 В на +5V).",
     ha="left", fontsize=FS - 1)
text(0.3, 0.3, "Подсветка: с Q1 D6 = LOW - светит; ключ на модуле - вместо Q1 перемычка база-коллектор, R5 - перемычка (резистор базы на модуле) "
     "или 1 кОм для запаса, D6 на LED/BL "
     "(TFT_BL_ACTIVE_LOW в config.h).", ha="left", fontsize=FS - 1)

os.makedirs(os.path.dirname(PNG), exist_ok=True)
fig.savefig(SVG, bbox_inches="tight")
fig.savefig(PNG, dpi=90, bbox_inches="tight")
print("SVG ->", os.path.relpath(SVG, ROOT))
print("PNG ->", os.path.relpath(PNG, ROOT))
