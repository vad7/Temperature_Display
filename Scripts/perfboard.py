# Плата кнопок и питания на макетке 20 x 47.6 мм (6 рядов x 17 столбцов, шаг 2.54, двусторонняя; обрезана
# после 17-го столбца): Docs/perfboard.svg и work/png/perfboard.png. Обозначения на рисунке - как напечатаны на
# стороне деталей макетки (perfboard_v2.py): столбцы B, A, Z, Y, ... L от края с площадками, ряды 06 (у крышки) ... 01;
# в коде - номер столбца 1..17 (1 = B) и ряд 'A'..'F' (A = 06), подписи - hole() / col_name(). Геометрия (столбцы кнопок, стойки крышки,
# упоры, C1) - из Scripts/enclosure.py, чтобы рисунок не расходился с корпусом.
# Вид со стороны деталей (от экрана): крышка - вверху, верх корпуса - справа (столбец 1). Детали - красным,
# перемычки и шины стороны пайки (к стенке) - серым, пайка проводов - зелёным.
#   python Scripts/perfboard.py            - с ключом подсветки Q1 (Docs/perfboard.svg)
#   python Scripts/perfboard.py --no-q1    - ключ подсветки на модуле экрана: без Q1 / R6 (Docs/perfboard_noq1.svg)
import importlib.util
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOQ1 = "--no-q1" in sys.argv
SUFFIX = "_noq1" if NOQ1 else ""
SVG = os.path.join(ROOT, "Docs", "perfboard%s.svg" % SUFFIX)
PNG = os.path.join(ROOT, "work", "png", "perfboard%s.png" % SUFFIX)

_spec = importlib.util.spec_from_file_location("enclosure", os.path.join(ROOT, "Scripts", "enclosure.py"))
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)

COLS, ROWS = 17, "ABCDEF"
COL_NAMES = "BAZYXWVUTSRQPONML"    # подпись столбца 1..17 (как на макетке, стороне деталей)


def col_name(c):
    return COL_NAMES[c - 1]


def row_name(r):
    """'A'..'F' -> '06'..'01' (06 - у крышки)."""
    return "%02d" % (len(ROWS) - ROWS.index(r))


def hole(c, r):
    return col_name(c) + row_name(r)


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
    ax.text(xy(c, "F")[0], -0.6, col_name(c), ha="center", va="top", fontsize=7)
for r in ROWS:
    ax.text(-0.5, xy(1, r)[1], row_name(r), ha="right", va="center", fontsize=8)
    ax.text(L + 0.5, xy(1, r)[1], row_name(r), ha="left", va="center", fontsize=8)
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
for s0, s1 in [sorted((sy * E.PB_Y1, sy * (E.PB_Y1 - E.PB_STOP_W))) for sy in (-1, 1)]         + [(-E.PB_STOP_W / 2, E.PB_STOP_W / 2)]:                # упоры: у торцов и по центру (enclosure.pb_stops)
    ax.add_patch(Rectangle((s0 - E.PB_Y0, -2.6), s1 - s0, 2.6, fc="0.6", ec="k", lw=0.6))
    ax.text((s0 + s1) / 2 - E.PB_Y0, -3.0, "упор", ha="center", va="top", fontsize=7)
yz = E._ybr - r_b - E.PB_PARTS_CLR
for yb in (-yz, yz):
    ax.plot([yb - E.PB_Y0] * 2, [0, Wb], color=BOT, lw=0.8, ls=":")

# --- шины и перемычки (сторона пайки): GND - ряд F (01), +3.3 - ряд E (02)
bridge((3, "A"), (4, "A"))                                    # Кн.1: GND - через ряд A (06)
bridge((3, "A"), (3, "F"))
PP, PG = E.PB_PWR_COLS                                        # столбцы питания: + / GND
bridge((3, "F"), (PG, "F"), lw=4.5)                           # шина GND
bridge((12, "A"), (PG, "A"))                                  # Кн.2: GND - по ряду A (06) к столбцу GND
bridge((PG, "A"), (PG, "F"))
bridge((4, "E"), (PP, "E"), lw=4.5)                           # шина +3.3
bridge((PP, "B"), (PP, "E"))
bridge((12, "D"), (12, "E"))
bridge((5, "A"), (5, "C"))                                    # сигналы кнопок
bridge((11, "A"), (11, "C"))
for c in (6, 7, 8):                                           # узлы подтяжек
    bridge((c, "B"), (c, "D"))
bridge((9, "A"), (9, "B"))                                    # D3 -> R5
bridge((9, "C"), (10, "C"))
if NOQ1:
    bridge((10, "A"), (10, "C"))                              # R5 -> LED / BL экрана (ключ - на модуле)
else:
    bridge((9, "C"), (9, "D"))                                # база: R5, R6, Q1
    bridge((10, "D"), (10, "E"))                              # эмиттер Q1 -> +3.3
    bridge((10, "A"), (10, "B"))                              # коллектор Q1 -> LED
ax.text(xy(PG, "F")[0] - 0.3, xy(PG, "F")[1] - 1.0, "GND", ha="left", va="top", fontsize=8, color=BUS,
        fontweight="bold")
ax.text(xy(4, "E")[0] + 0.3, xy(4, "E")[1] + 0.5, "+3.3", ha="left", va="bottom", fontsize=8, color=BUS,
        fontweight="bold")


# --- кнопки (угловые): выводы 1 / 2 - в ряду A, средний - ближе к толкателю, сверлить; толкатель - через крышку
def button(c0, name):
    yb, zp = E.pb_yz(c0 + 0.5, E.PB_BTN_ROW)
    x, yp = yb - E.PB_Y0, zp - E.PB_Z0                    # yp - выводы 1 / 2
    yback = yp - E.BTN_PIN12_L                             # тыл корпуса кнопки
    ax.add_patch(Rectangle((x - E.BTN_W / 2, yback), E.BTN_W, E.BTN_BODY_L + E.BTN_RIVET,
                           fc="none", ec=TOP, lw=2, zorder=3))
    ax.add_patch(Rectangle((x - E.BTN_PLUNGER_D / 2, yback + E.BTN_BODY_L + E.BTN_RIVET), E.BTN_PLUNGER_D,
                           E.BTN_H - E.BTN_BODY_L - E.BTN_RIVET, fc=TOP, alpha=0.5, zorder=3))
    for c in (c0, c0 + 1):
        xp, ypp = xy(c, "A")
        ax.add_patch(Rectangle((xp - 0.5, ypp - 0.35), 1.0, 0.7, fc=TOP, zorder=4))
    ax.add_patch(Circle((x, yp + E.BTN_PIN3_DZ), 0.5, fc="white", ec=TOP, lw=1.5, ls="--", zorder=4))
    ax.text(x, yback + E.BTN_H + 0.3, name, ha="center", va="bottom", fontsize=9, color=TOP,
            fontweight="bold")


button(E.PB_BTN_COLS[0] - 0.5, "Кн.1")
button(E.PB_BTN_COLS[1] - 0.5, "Кн.2")

# --- детали (сторона деталей)
res(6, "D", "E", "R4")
res(7, "D", "E", "R2")
res(8, "D", "E", "R3")
res(9, "B", "C", "R5")
if not NOQ1:
    res(9, "D", "E", "R6")
    for r, t in (("B", "К"), ("C", "Б"), ("D", "Э")):
        xq, yq = xy(10, r)
        ax.add_patch(Rectangle((xq - 0.5, yq - 0.5), 1.0, 1.0, fc=BOT, zorder=3))
        ax.text(xq + 0.7, yq, t, fontsize=7, color=BOT, va="center", zorder=5)
    xq0, yq0 = xy(10, "D")
    _, yq1 = xy(10, "B")
    ax.add_patch(Rectangle((xq0 - 1.4, yq0 - 0.9), 2.8, yq1 - yq0 + 1.8, fc="none", ec=BOT, lw=1.5, ls="--",
                           zorder=3))
    ax.text(xq0 + 1.6, yq1 + 0.6, "Q1", fontsize=8, color=BOT, fontweight="bold")
xc, yc = xy(E.PB_C1_COL, E.PB_C1_ROW)
ax.add_patch(Circle((xc, yc), E.PB_C1_D / 2, fc="none", ec=BOT, lw=2, zorder=3))
for (c, r), t in (((PP, "E"), "+"), ((PG, "F"), "-")):
    xp, yp = xy(c, r)
    ax.add_patch(Rectangle((xp - 0.4, yp - 0.4), 0.8, 0.8, fc=BOT, zorder=4))
    ax.text(xp - 0.9, yp - 0.2, t, fontsize=9, color=BOT, fontweight="bold", ha="right", zorder=5)
ax.text(xc, yc + 0.3, "C1", ha="center", va="bottom", fontsize=8, color=BOT, fontweight="bold")

# --- провода
WIRES = [                                                     # (столбец, ряд, метка, куда)
    (5, "C", "D4", "Pro Mini D4 - Кн.1"), (11, "C", "D5", "Pro Mini D5 - Кн.2"),
    (6, "C", "D2", "Pro Mini D2 (1-Wire)"), (6, "B", "DQ", "DS18B20 DQ"),
    (7, "C", "A4", "Pro Mini A4"), (7, "B", "SDA", "SHT40 SDA"),
    (8, "C", "A5", "Pro Mini A5"), (8, "B", "SCL", "SHT40 SCL"),
    (9, "A", "D3", "Pro Mini D3 (подсветка)"), (10, "A", "LED", "экран LED / BL"),
    (PP, "B", "+", "HLK +Vo"), (PG, "B", "-", "HLK -Vo"),
    (PP, "C", "+", "Pro Mini VCC"), (PG, "C", "-", "Pro Mini GND"),
    (PP, "D", "+", "экран VCC"), (PG, "D", "-", "экран GND"),
    (12, "D", "+", "датчик VDD"), (12, "F", "-", "датчик GND"),
]
for c, r, tag, _ in WIRES:
    pad(c, r, tag)

# --- подписи
y = -5.0
lines = [
    "Вид со стороны деталей (от экрана): крышка вверху, верх корпуса справа. Синее - кнопки, красное - детали, серое - "
    "шины и перемычки на стороне пайки (к стенке), зелёное - провода.",
    "Обозначения - как напечатаны на стороне деталей макетки: столбцы B, A, Z, Y, ... L от края с площадками, ряды "
    "06 (у крышки) ... 01.",
    "Шины: ряд 01 - GND (Кн.1 - через %s и столбец %s, Кн.2 - по ряду 06 и столбцу %s), ряд 02 - +3.3 В. "
    % (hole(3, "A"), col_name(3), col_name(PG)) + "Штриховка - левые стойки крышки: на стороне деталей пусто "
    "(зазор 0.3), пунктир - граница деталей.",
    "Кнопки угловые 4.5 x 4.5: выводы 1 / 2 (через 3 мм) - в %s / %s и %s / %s (подогнуть), средний - на 1.98 мм "
    % (hole(4, "A"), hole(5, "A"), hole(11, "A"), hole(12, "A")) + "ближе к толкателю, в 1.7 мм от края платы: "
    "отверстие Ø0.8 сверлить (кружок) или вывод откусить; к цепям не подключён (проверить тестером).",
    "C1 100 мкФ 6.3 В Ø5 x 11 стоя: + %s, - %s (выводы по диагонали)." % (hole(PP, "E"), hole(PG, "F"))
    + " R2-R4 4.7 кОм, R5 1 кОм"
    + ("" if NOQ1 else ", R6 10 кОм") + " - стоя. Хвосты пайки - не длиннее 1.5 мм (до стенки).",
    ("Ключ подсветки - на модуле экрана (Q1 и R6 нет): D3 - R5 - LED / BL, высокий уровень - горит "
     "(TFT_BL_ACTIVE_LOW 0). R5 - 1 кОм для запаса или перемычка (резистор базы - на модуле). R2 / R3 - если нет "
     "подтяжек на модуле SHT40." if NOQ1 else
     "Ключ подсветки на модуле экрана (2.4\" MSP2401, 1.8\") - Q1 и R6 не ставить, перемычка %s-%s, R5 - "
     % (hole(10, "B"), hole(10, "C")) +
     "перемычкой (резистор базы - на модуле) или 1 кОм для запаса (раскладка без Q1 - perfboard_noq1.svg). R2 / R3 - "
     "если нет подтяжек на модуле SHT40. Цоколёвку Q1 (Э-Б-К) - по даташиту."),
    "Провода (отверстие - метка - куда): " + ", ".join("%s %s" % (hole(c, r), d) for c, r, _, d in WIRES) + ".",
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
