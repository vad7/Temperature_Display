# Собранный вариант платы кнопок и питания (пользователь 2026-10-29): кнопки 6 x 6, клеммник DS18B20, подтяжка DQ,
# C1 и 0.1 мкФ параллельно. Docs/perfboard_v2.svg и work/png/perfboard_v2.png.
# Обозначения - как напечатано на стороне деталей: буквы по длинной стороне (от края с площадками: B, A, Z, Y, ...),
# ряды 01-06 (06 - у кнопок). На стороне пайки буквы свои: A пайки = B деталей, B = A, C = Z, D = Y, E = X, ...
# Положение деталей - пользователь (кнопки, клеммник, C1); разводка стороны пайки - по фото, ОЦЕНКА / СВЕРИТЬ.
#   python Scripts/perfboard_v2.py
import importlib.util
import os
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# геометрия корпуса (стойки крышки, столбцы макетки) - из enclosure.py, main() не запускается
_argv, sys.argv = sys.argv, [sys.argv[0]]
_spec = importlib.util.spec_from_file_location("enclosure", os.path.join(ROOT, "Scripts", "enclosure.py"))
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)
sys.argv = _argv
SVG = os.path.join(ROOT, "Docs", "perfboard_v2.svg")
PNG = os.path.join(ROOT, "work", "png", "perfboard_v2.png")

COLS = "LMNOPQRSTUVWXYZAB"     # слева направо, вид со стороны деталей; B - у края с площадками
PITCH = 2.54
BUS, TOP, BOT, PAD = "#7f8c8d", "#1f5fbf", "#c0392b", "#1e8449"
PADS_ROWS = (2, 3, 4, 5)       # контактные площадки у края - по фото
BTN_W, BTN_H, BTN_PLUNGER = 6.0, 6.0, 3.5      # кнопка 6 x 6, толкатель - по фото
TERM_PITCH_ROWS = 2            # клеммник 5 мм = 2 шага (по фото)
# Столбцы от края B совпадают с perfboard.py (Кн.1 X / Y = 4-5, Кн.2 Q / R = 11-12): столбец n = COLS[17 - n].
# Стойки крышки (на стороне деталей против них пусто) - по enclosure.py (LID_BOSS_Y); питание - у нижней стойки
# (пользователь 2026-11-02: со столбцов M / L на P / O).
PWR_PLUS, PWR_GND = "P", "O"


def col_x(col):
    """Номер столбца (1 - у края B, дробный - между столбцами) -> X рисунка, мм."""
    return (len(COLS) - col) * PITCH


def y_col(y):
    """Y корпуса -> номер столбца (дробный)."""
    return (E.PB_Y1 - E.PB_COL0 - y) / PITCH + 1

fig, ax = plt.subplots(figsize=(13, 7))
ax.set_aspect("equal")
ax.axis("off")


def xy(hole):
    """'T05' -> координаты рисунка, мм."""
    return COLS.index(hole[0]) * PITCH, (int(hole[1:]) - 1) * PITCH


def wire(*holes, lw=3.0):
    """Отверстия ('T05') или точки рисунка (x, y) - провод вне сетки."""
    pts = [xy(h) if isinstance(h, str) else h for h in holes]
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=BUS, lw=lw, solid_capstyle="round", zorder=2)


def pin(hole, tag="", color=BOT):
    x, y = xy(hole)
    ax.add_patch(Rectangle((x - 0.45, y - 0.45), 0.9, 0.9, fc=color, zorder=4))
    if tag:
        ax.text(x + 0.7, y + 0.4, tag, fontsize=8, color=color, fontweight="bold", zorder=5)


def free_end(hole, tag):
    x, y = xy(hole)
    ax.add_patch(Circle((x, y), 0.7, color=PAD, zorder=4))
    ax.text(x, y - 1.0, tag, fontsize=7, color=PAD, ha="center", va="top", fontweight="bold", zorder=5)


# --- плата и сетка
x_last = (len(COLS) - 1) * PITCH
x_edge = x_last + 5.5
ax.add_patch(Rectangle((-1.6, -1.9), x_edge + 1.6, 6 * PITCH + 1.2, fc="#e8f3e8", ec="black", zorder=0))
for i, c in enumerate(COLS):
    for r in range(1, 7):
        ax.add_patch(Circle((i * PITCH, (r - 1) * PITCH), 0.45, fc="white", ec="#888", lw=0.6, zorder=1))
    ax.text(i * PITCH, -2.3, c, ha="center", va="top", fontsize=8)
for r in range(1, 7):
    ax.text(-2.0, (r - 1) * PITCH, "%02d" % r, ha="right", va="center", fontsize=8)
for r in PADS_ROWS:
    ax.add_patch(FancyBboxPatch((x_last + 1.6, (r - 1) * PITCH - 0.6), 2.4, 1.2,
                                boxstyle="round,pad=0.1", fc="#ccc", ec="#888", zorder=1))
x_lo, x_hi = -1.6, x_edge                  # края платы на рисунке
for sy in (-1, 1):                         # стойка Ø LID_BOSS_D + зазор деталей, обрезанная краями платы
    ya, yb = sy * E._ybr - E.LID_BOSS_D / 2 - E.PB_PARTS_CLR, sy * E._ybr + E.LID_BOSS_D / 2 + E.PB_PARTS_CLR
    xa0, xa1 = sorted((col_x(y_col(ya)), col_x(y_col(yb))))
    xa0, xa1 = max(xa0, x_lo), min(xa1, x_hi)
    if xa1 <= xa0:
        continue
    ax.add_patch(Rectangle((xa0, -1.9), xa1 - xa0, 6 * PITCH + 1.2, fc="none", ec="0.4", hatch="///",
                           lw=0.6, zorder=1))
    ax.text((xa0 + xa1) / 2, -4.0, "стойка", ha="center", va="top", fontsize=7, color="0.3")


# --- кнопки 6 x 6 (над рядом 06, толкатель - наружу)
def button(c0, name):
    x0, y6 = xy("%s06" % c0)
    x1 = x0 + PITCH
    xc = (x0 + x1) / 2
    ax.add_patch(Rectangle((xc - BTN_W / 2, y6 + 1.0), BTN_W, BTN_H / 2, fc="none", ec=TOP, lw=2, zorder=3))
    ax.add_patch(Rectangle((xc - BTN_PLUNGER / 2, y6 + 1.0 + BTN_H / 2), BTN_PLUNGER, BTN_H, fc=TOP, alpha=0.5,
                           zorder=3))
    for c in (c0, COLS[COLS.index(c0) + 1]):
        pin("%s06" % c, color=TOP)
    ax.text(xc, y6 + 1.0 + BTN_H * 1.5 + 0.3, name, ha="center", va="bottom", fontsize=9, color=TOP,
            fontweight="bold")


button("X", "Кн.1")
button("Q", "Кн.2")

# --- клеммник: + T05, DQ T03, - T01 (+ ближе к кнопкам)
xt, _ = xy("T01")
ax.add_patch(Rectangle((xt - 2.2, -1.3), 4.6, 5 * PITCH + 2.6, fc="none", ec=BOT, lw=1.5, ls="--", zorder=3))
ax.text(xt + 0.2, 5 * PITCH + 1.5, "клеммник\nDS18B20", ha="center", va="bottom", fontsize=7, color=BOT)
for h, t in (("T05", "+"), ("T03", "DQ"), ("T01", "-")):
    pin(h, t)

# --- подтяжка DQ: V06 - V03 (лёжа вдоль столбца)
(xr, y0), (_, y1) = xy("V03"), xy("V06")
ax.add_patch(Rectangle((xr - 0.55, y0 + 0.6), 1.1, y1 - y0 - 1.2, fc=BOT, alpha=0.6, zorder=3))
ax.text(xr + 0.8, (y0 + y1) / 2, "R 4.7к", fontsize=7, color=BOT, va="center", zorder=5)
pin("V06")
pin("V03")

# --- 0.1 мкФ: W04 - Y04 (по фото)
pin("W04")
pin("Y04")
xa, ya = xy("W04")
xb, _ = xy("Y04")
ax.add_patch(Rectangle((xa + 0.5, ya + 0.6), xb - xa - 1.0, 1.4, fc="#e6c229", ec=BOT, zorder=3))
ax.text((xa + xb) / 2, ya + 2.2, "0.1 мкФ", ha="center", va="bottom", fontsize=7, color=BOT)

# --- C1: + X03 (вверх), - X02 (вниз)
xc1, yc1 = xy("X03")
ax.add_patch(Circle((xc1, yc1 - PITCH / 2), 3.2, fc="none", ec=BOT, lw=2, zorder=3))
pin("X03", "+")
pin("X02", "-")
ax.text(xc1 + 3.4, yc1 - PITCH, "C1", fontsize=8, color=BOT, fontweight="bold", va="center")

# --- сторона пайки (по фото - СВЕРИТЬ)
wire("V06", "T05")                         # + : подтяжка - клеммник
wire("T05", "S05", "S04", PWR_PLUS + "04")   # +  дальше по ряду 04 (ниже D5) в столбец питания
wire("V06", "W04", "X03")                  # + : 0.1 мкФ, C1 +
wire("V03", "T03", "S03")                  # DQ: подтяжка - клеммник
wire("Y04", "Y02", "X02")                  # GND: 0.1 мкФ, C1 -
wire("X02", "T01", PWR_GND + "01", PWR_GND + "04")   # GND: клеммник, по ряду 01 в столбец питания
free_end("S03", "D2")

# --- предложение (не по фото): кнопки, питание у нижней стойки (PWR_PLUS / PWR_GND)
wire("Y06", "Y04")                         # Кн.1 -> GND (вывод 0.1 мкФ)
y_top = xy("R06")[1] + 1.2                 # Кн.2 -> GND: провод над рядом 06 к Y06
wire("R06", (xy("R06")[0], y_top), (xy("Y06")[0], y_top), "Y06")
wire("Q06", "Q05")                         # Кн.2 -> D5
wire("X06", "W06")                         # Кн.1 -> D4
wire(PWR_PLUS + "03", PWR_PLUS + "05")     # + : столбец питания (провод + приходит в 04)
for h, t in (("Q05", "D5"), ("W06", "D4"), (PWR_PLUS + "05", ""), (PWR_PLUS + "03", "+"), (PWR_GND + "04", ""),
             (PWR_GND + "03", ""), (PWR_GND + "02", "GND")):
    free_end(h, t)

# --- подписи
y = -5.0
lines = [
    "Вид со стороны деталей (буквы и ряды - как напечатаны на этой стороне; B - у края с площадками, 06 - у кнопок). "
    "Синее - кнопки, красное - детали, серое - провода на стороне пайки, зелёное - концы проводов дальше.",
    "Клеммник DS18B20: T05 +, T03 DQ, T01 - (+ ближе к кнопкам). Подтяжка DQ к + - 4.7 кОм, V06 - V03. "
    "C1 (+ вверх) и 0.1 мкФ - параллельно, между + и GND.",
    "На стороне пайки буквы свои: A пайки = B деталей, B = A, C = Z, D = Y, E = X, ... K = R, L = Q.",
    "Разводка стороны пайки и выводы 0.1 мкФ / C1 - по фото (ОЦЕНКА, сверить). Дорисовано (предложение): Кн.1 - "
    "Y06 -> Y04 GND, X06 -> W06 - провод к D4; Кн.2 - R06 -> провод над рядом 06 -> Y06 GND, Q06 -> Q05 - провод к "
    "D5 (рабочие контакты кнопки 6 x 6 равноправны); DQ S03 - провод к D2 Pro Mini.",
    "Питание - у нижней стойки крышки: + - столбец %s (%s03 - %s05), GND - по ряду 01 (T01 -> %s01) в столбец %s "
    "(%s02 - %s04); провода HLK, Pro Mini и экрана - сюда. Штриховка - стойки крышки (на уровне правых, по корпусу "
    "enclosure.py): на стороне деталей против них ничего не ставить." % (PWR_PLUS, PWR_PLUS, PWR_PLUS, PWR_GND, PWR_GND,
                                                                          PWR_GND, PWR_GND),
]
for s in lines:
    for part in textwrap.wrap(s, 125):
        ax.text(-3, y, part, fontsize=8.2, va="top")
        y -= 1.45
ax.set_xlim(-4, x_edge + 2)
ax.set_ylim(y - 0.5, 5 * PITCH + BTN_H * 1.5 + 4)

os.makedirs(os.path.dirname(PNG), exist_ok=True)
fig.savefig(SVG, bbox_inches="tight")
fig.savefig(PNG, dpi=110, bbox_inches="tight")
print("SVG ->", os.path.relpath(SVG, ROOT))
print("PNG ->", os.path.relpath(PNG, ROOT))
