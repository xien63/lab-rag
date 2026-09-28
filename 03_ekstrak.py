import json, pathlib
import pdfplumber
from pypdf import PdfReader

PDF   = r"C:\Users\sandy\dev\lab-rag\source.pdf"
OUT   = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\pilot")
START = 380
END   = 406

r = PdfReader(PDF)
buf = []
for i in range(START - 1, END):
    buf.append(f"\n\n===== HAL {i+1} =====\n" + (r.pages[i].extract_text() or ""))
(OUT / "pypdf.txt").write_text("".join(buf), encoding="utf-8")

buf, tabel = [], []
with pdfplumber.open(PDF) as pdf:
    for i in range(START - 1, END):
        pg = pdf.pages[i]
        buf.append(f"\n\n===== HAL {i+1} =====\n" + (pg.extract_text() or ""))
        for t in pg.extract_tables():
            tabel.append({"hal": i + 1, "baris": t})
(OUT / "plumber.txt").write_text("".join(buf), encoding="utf-8")
(OUT / "tabel.json").write_text(json.dumps(tabel, ensure_ascii=False, indent=2), encoding="utf-8")

print("halaman diproses:", END - START + 1)
print("tabel terdeteksi :", len(tabel))
print("pypdf    :", (OUT / "pypdf.txt").stat().st_size, "byte")
print("plumber  :", (OUT / "plumber.txt").stat().st_size, "byte")
