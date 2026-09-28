import re, pathlib, unicodedata
s = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\pilot\plumber.txt").read_text(encoding="utf-8")
non_ascii = sorted(set(re.findall(r"[^\x00-\x7F]", s)))
for ch in non_ascii:
    try:
        name = unicodedata.name(ch)
    except ValueError:
        name = "TIDAK DIKENAL"
    print(f"U+{ord(ch):04X}  {name}")
