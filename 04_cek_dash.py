import re, pathlib
s = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\pilot\plumber.txt").read_text(encoding="utf-8")
print("en-dash \u2013 :", s.count("\u2013"))
print("em-dash \u2014 :", s.count("\u2014"))
print("hyphen   -  :", s.count("-"))
non_ascii = sorted(set(re.findall(r"[^\x00-\x7F]", s)))
print("non-ASCII yang muncul:", non_ascii[:40])
