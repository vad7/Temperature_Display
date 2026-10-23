# Плата кнопок и питания на макетке 20 x 47.6 мм (6 рядов A-F x 17 столбцов, шаг 2.54, двусторонняя; обрезана
# после 17-го столбца): Docs/perfboard.svg и work/png/perfboard.png. Геометрия (столбцы кнопок, стойки крышки,
# упоры, C1) - из Scripts/enclosure.py, чтобы рисунок не расходился с корпусом.
# Вид со стороны деталей (от экрана): крышка - вверху, верх корпуса - справа (столбец 1). Детали - красным,
# перемычки и шины стороны пайки (к стенке) - серым, пайка проводов - зелёным.
#   python Scripts/perfboard.py
import importlib.util
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "Docs", "perfboard.svg")
PNG = os.path.join(ROOT, "work", "png", "perfboard.png")

_spec = importlib.util.spec_from_file_location("enclosure", os.path.join(ROOT, "Scripts", "enclosure.py"))
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)

COLS, ROWS = 17, "ABCDEF"
BTN_PIN3 = 1.98          # 3-й вывод кнопки - ближе к тылу корпуса (чертёж кнопки)
HOLE_INSET = 2.2         # угловые отверстия у необрезанного края - по фото, не используются
BUS, TOP, BOT, PAD = "#7f8c8d", "#1f5fbf", "#c0392b", "#1e8449"

fig, ax = plt.subplots(figsize=(13, 10.5))
ax.set_aspect("equal")
ax.axis("off")


def xy(col, row):
    """Столбец (1..17, дробный - между) / ряд ('A'..'F' или число, A = 0) -> координаты рисунка (Y, Z корпуса)."""
    y, z = E.pb_yz(col, ROWS.index(row) if isinstance(row, str) else row)
    return y - E.PB_Y0, z - E.PB_Z0


def bridge(*holes, lw=3.2):
    pts = [xy(c, r) for c, r in holes]
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=BUS, lw=lw, solid_capstyle="round", zorder=2)


def pad(c, r, tag):
    x, y = xy(c, r)
    ax.add_patch(Circle((x, y), 0.75, color=PAD, zorder=4))
    ax.text(x + 0.9, y + 0.5, tag, fontsize=7, color=PAD, fontweight="bold", zorder=5)


def res(c, r0, r1, name):
    """Резистор стоя: выводы в двух соседних отверстиях столбца."""
    (x, y0), (_, y1) = xy(c, r0), xy(c, r1)
    ax.add_patch(Rectangle((x - 0.55, min(y0, y1) + 0.3), 1.1, abs(y1 - y0) - 0.6, fc=BOT, zorder=3))
    ax.text(x - 0.8, (y0 + y1) / 2, name, fontsize=7, color=BOT, ha="right", va="center", zorder=5)


# --- плата, сетка, крышка
L, Wb = E.PB_LEN, E.PB_W
ax.add_patch(Rectangle((0, 0), L, Wb, fc="#e8f3e8", ec="black", zorder=0))
for hy in (HOLE_INSET, Wb - HOLE_INSET):
    ax.add_patch(Circle((L - HOLE_INSET, hy), 1.1, fc="white", ec="black"))
for c in range(1, COLS + 1):
    for r in ROWS:
        ax.add_patch(Circle(xy(c, r), 0.45, fc="white", ec="#888", lw=0.6, zorder=1))
    ax.text(xy(c, "F")[0], -0.6, str(c), ha="center", va="top", fontsize=7)
for r in ROWS:
    ax.text(-0.5, xy(1, r)[1], r, ha="right", va="center", fontsize=8)
    ax.text(L + 0.5, xy(1, r)[1], r, ha="left", va="center", fontsize=8)
lid = Wb + E.PB_EDGE
ax.plot([-3, L + 3], [lid, lid], color="k", lw=1.2, ls="--")
ax.text(L + 3, lid + 0.3, "крышка (внутри)", ha="right", va="bottom", fontsize=8)
ax.text(L + 1.6, Wb / 2, "верх корпуса ->", rotation=90, ha="left", va="center", fontsize=8)
ax.text(-1.6, Wb / 2, "<- низ корпуса", rotation=90, ha="right", va="center", fontsize=8)

# --- стойки крышки (на стороне деталей - пусто), граница деталей, упоры под платой
r_b = E.LID_BOSS_D / 2
for sy in (-1, 1):
    y0, y1 = sorted((sy * (E._ybr - r_b), sy * (E._ybr + r_b)))
    ax.add_patch(Rectangle((y0 - E.PB_Y0, 0), y1 - y0, Wb, fc="none", ec="0.4", hatch="///", lw=0.6, zorder=1))
    s0, s1 = sy * E._ybr - E.PB_STOP_W / 2, sy * E._ybr + E.PB_STOP_W / 2
    ax.add_patch(Rectangle((s0 - E.PB_Y0, -2.6), s1 - s0, 2.6, fc="0.6", ec="k", lw=0.6))
    ax.text((s0 + s1) / 2 - E.PB_Y0, -3.0, "упор", ha="center", va="top", fontsize=7)
yz = E._ybr - r_b - E.PB_PARTS_CLR
for yb in (-yz, yz):
    ax.plot([yb - E.PB_Y0] * 2, [0, Wb], color=BOT, lw=0.8, ls=":")

# --- шины и перемычки (сторона пайки): GND - ряд F, +3.3 - ряд E
bridge((3, "A"), (4, "A"))                                    # Кн.1: GND - через ряд A за стойкой
bridge((3, "A"), (3, "F"))
bridge((3, "F"), (17, "F"), lw=4.5)                           # шина GND
bridge((12, "A"), (17, "A"))                                  # Кн.2: GND - по ряду A к столбцу 17
bridge((17, "A"), (17, "F"))
bridge((4, "E"), (16, "E"), lw=4.5)                           # шина +3.3
bridge((16, "B"), (16, "E"))
bridge((12, "D"), (12, "E"))
bridge((5, "A"), (5, "C"))                                    # сигналы кнопок
bridge((11, "A"), (11, "C"))
for c in (6, 7, 8):                                           # узлы подтяжек
    bridge((c, "B"), (c, "D"))
bridge((9, "A"), (9, "B"))                                    # D6 -> R5
bridge((9, "C"), (9, "D"))                                    # база: R5, R6, Q1
bridge((9, "C"), (10, "C"))
bridge((10, "D"), (10, "E"))                                  # эмиттер Q1 -> +3.3
bridge((10, "A"), (10, "B"))                                  # коллектор Q1 -> LED
ax.text(xy(17, "F")[0] - 0.3, xy(17, "F")[1] - 1.0, "GND", ha="left", va="top", fontsize=8, color=BUS,
        fontweight="bold")
ax.text(xy(4, "E")[0] + 0.3, xy(4, "E")[1] + 0.5, "+3.3", ha="left", va="bottom", fontsize=8, color=BUS,
        fontweight="bold")


# --- кнопки (угловые): выводы 1 / 2 - в ряду A, 3-й - сверлить; толкатель - вверх, через крышку
def button(c0, name):
    yb, zp = E.pb_yz(c0 + 0.5, E.PB_BTN_ROW)
    x, yp = yb - E.PB_Y0, zp - E.PB_Z0
    ax.add_patch(Rectangle((x - E.BTN_W / 2, yp - E.BTN_BODY_L), E.BTN_W, E.BTN_BODY_L + E.BTN_RIVET,
                           fc="none", ec=TOP, lw=2, zorder=3))
    ax.add_patch(Rectangle((x - E.BTN_PLUNGER_D / 2, yp + E.BTN_RIVET), E.BTN_PLUNGER_D,
                           E.BTN_H - E.BTN_BODY_L - E.BTN_RIVET, fc=TOP, alpha=0.5, zorder=3))
    for c in (c0, c0 + 1):
        xp, ypp = xy(c, "A")
        ax.add_patch(Rectangle((xp - 0.5, ypp - 0.35), 1.0, 0.7, fc=TOP, zorder=4))
    ax.add_patch(Circle((x, yp - BTN_PIN3), 0.5, fc="white", ec=TOP, lw=1.5, ls="--", zorder=4))
    ax.text(x, yp + E.BTN_H - E.BTN_BODY_L + 0.3, name, ha="center", va="bottom", fontsize=9, color=TOP,
            fontweight="bold")


button(E.PB_BTN_COLS[0] - 0.5, "Кн.1")
button(E.PB_BTN_COLS[1] - 0.5, "Кн.2")

# --- детали (сторона деталей)
res(6, "D", "E", "R4")
res(7, "D", "E", "R2")
res(8, "D", "E", "R3")
res(9, "B", "C", "R5")
res(9, "D", "E", "R6")
for r, t in (("B", "К"), ("C", "Б"), ("D", "Э")):
    xq, yq = xy(10, r)
    ax.add_patch(Rectangle((xq - 0.5, yq - 0.5), 1.0, 1.0, fc=BOT, zorder=3))
    ax.text(xq + 0.7, yq, t, fontsize=7, color=BOT, va="center", zorder=5)
xq0, yq0 = xy(10, "D")
_, yq1 = xy(10, "B")
ax.add_patch(Rectangle((xq0 - 1.4, yq0 - 0.9), 2.8, yq1 - yq0 + 1.8, fc="none", ec=BOT, lw=1.5, ls="--", zorder=3))
ax.text(xq0 + 1.6, yq1 + 0.6, "Q1", fontsize=8, color=BOT, fontweight="bold")
xc, yc = xy(E.PB_C1_COL, E.PB_C1_ROW)
ax.add_patch(Circle((xc, yc), E.PB_C1_D / 2, fc="none", ec=BOT, lw=2, zorder=3))
for (c, r), t in (((16, "E"), "+"), ((17, "F"), "-")):
    xp, yp = xy(c, r)
    ax.add_patch(Rectangle((xp - 0.4, yp - 0.4), 0.8, 0.8, fc=BOT, zorder=4))
    ax.text(xp - 0.9, yp - 0.2, t, fontsize=9, color=BOT, fontweight="bold", ha="right", zorder=5)
ax.text(xc, yc + 0.3, "C1", ha="center", va="bottom", fontsize=8, color=BOT, fontweight="bold")

# --- провода
WIRES = [
    ("C5", "D4", "Pro Mini D4 - Кн.1"), ("C11", "D5", "Pro Mini D5 - Кн.2"),
    ("C6", "D2", "Pro Mini D2 (1-Wire)"), ("B6", "DQ", "DS18B20 DQ"),
    ("C7", "A4", "Pro Mini A4"), ("B7", "SDA", "SHT40 SDA"),
    ("C8", "A5", "Pro Mini A5"), ("B8", "SCL", "SHT40 SCL"),
    ("A9", "D6", "Pro Mini D6 (подсветка)"), ("A10", "LED", "экран LED / BL"),
    ("B16", "+", "HLK +Vo"), ("B17", "-", "HLK -Vo"),
    ("C16", "+", "Pro Mini VCC"), ("C17", "-", "Pro Mini GND"),
    ("D16", "+", "экран VCC"), ("D17", "-", "экран GND"),
    ("D12", "+", "датчик VDD"), ("F12", "-", "датчик GND"),
]
for hole, tag, _ in WIRES:
    pad(int(hole[1:]), hole[0], tag)

# --- подписи
y = -5.0
lines = [
    "Вид со стороны деталей (от экрана): крышка вверху, верх корпуса справа. Синее - кнопки, красное - детали, серое - "
    "шины и перемычки на стороне пайки (к стенке), зелёное - провода.",
    "Шины: F - GND (Кн.1 - через A3 и столбец 3, Кн.2 - по ряду A и столбцу 17), E - +3.3 В. Штриховка - левые стойки "
    "крышки: на стороне деталей пусто (зазор 0.3), пунктир - граница деталей.",
    "Кнопки угловые 4.5 x 4.5: выводы 1 / 2 (через 3 мм) - в A4 / A5 и A11 / A12 (подогнуть), 3-й - отверстие "
    "сверлить (кружок), к цепям не подключён (проверить тестером).",
    "C1 100 мкФ 6.3 В Ø5 x 11 стоя: + E16, - F17 (выводы по диагонали). R2-R4 4.7 кОм, R5 1 кОм, R6 10 кОм - стоя. "
    "Хвосты пайки - не длиннее 1.5 мм (до стенки).",
    "Ключ подсветки на модуле экрана (2.4\" MSP2401, 1.8\") - Q1 и R6 не ставить, перемычка B10-C10, R5 - "
    "перемычкой (резистор базы - на модуле) или 1 кОм для запаса. R2 / R3 - если нет "
    "подтяжек на модуле SHT40. Цоколёвку Q1 (Э-Б-К) - по даташиту.",
    "Провода (отверстие - метка - куда): " + ", ".join("%s %s" % (h, d) for h, _, d in WIRES) + ".",
]
import textwrap  # noqa: E402
for s in lines:
    for part in textwrap.wrap(s, 125):
        ax.text(-3, y, part, fontsize=8.2, va="top")
        y -= 1.45
ax.set_xlim(-4, L + 4)
ax.set_ylim(y - 0.5, lid + E.BTN_OUT + 6)

os.makedirs(os.path.dirname(PNG), exist_ok=True)
fig.savefig(SVG, bbox_inches="tight")
fig.savefig(PNG, dpi=110, bbox_inches="tight")
print("SVG ->", os.path.relpath(SVG, ROOT))
print("PNG ->", os.path.relpath(PNG, ROOT))
