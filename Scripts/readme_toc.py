# Оглавление Readme.md со ссылками на разделы (якоря - по правилам GitHub).
#   python Scripts/readme_toc.py        - вставить / обновить оглавление между метками <!-- toc --> и <!-- /toc -->
# Уровни: разделы «## » и подразделы «### ». Заголовки внутри блоков кода (```) пропускаются.
# Якорь GitHub: нижний регистр, всё кроме букв (в т. ч. кириллицы), цифр, пробела, «-» и «_» удаляется,
# пробелы -> «-»; повторы - с суффиксом -1, -2, ...
import io
import os
import re

README = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Readme.md")
START, END = "<!-- toc -->", "<!-- /toc -->"
LEVELS = {"## ": 0, "### ": 1}          # отступ в оглавлении


def anchor(title, seen):
    t = re.sub(r"`|\*\*|\[|\]\([^)]*\)", "", title)      # без разметки: `код`, **жирный**, ссылки
    a = re.sub(r"[^\w\- ]", "", t.lower(), flags=re.UNICODE).replace(" ", "-")
    n = seen.get(a, 0)
    seen[a] = n + 1
    return a if n == 0 else "%s-%d" % (a, n)


def clean(title):
    """Текст пункта оглавления: без ссылок-хвостов вида ([схема](...)), разметка ссылок -> текст."""
    t = re.sub(r"\s*\(\[[^\]]*\]\([^)]*\)(,\s*\[[^\]]*\]\([^)]*\))*\)\s*$", "", title)
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t).strip()


def build(lines):
    out, seen, code = [], {}, False
    for line in lines:
        if line.startswith("```"):
            code = not code
            continue
        if code:
            continue
        for mark, level in LEVELS.items():
            if line.startswith(mark):
                title = line[len(mark):].strip()
                out.append("%s- [%s](#%s)" % ("  " * level, clean(title), anchor(title, seen)))
                break
        else:
            if line.startswith("#"):                     # заголовки других уровней - для счёта повторов якорей
                m = re.match(r"#+ (.*)", line)
                if m:
                    anchor(m.group(1).strip(), seen)
    return out


def main():
    s = io.open(README, encoding="utf-8").read()
    if START in s:
        a, b = s.index(START), s.index(END) + len(END)
        s = s[:a] + s[b:]
    lines = s.split("\n")
    toc = [START, "", "**Оглавление**", ""] + build(lines) + ["", END]
    # после вводного абзаца (цитата «> ...») перед первым разделителем «---»
    i = lines.index("---")
    while i > 0 and lines[i - 1] == "":
        i -= 1
    s = "\n".join(lines[:i] + [""] + toc + lines[i:])
    s = re.sub(r"\n{3,}" + re.escape(START), "\n\n" + START, s)
    io.open(README, "w", encoding="utf-8", newline="").write(s)
    print("Оглавление: %d пунктов" % len(build(lines)))


if __name__ == "__main__":
    main()
