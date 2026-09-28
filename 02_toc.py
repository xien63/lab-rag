from pypdf import PdfReader

PDF = r"C:\Users\sandy\dev\lab-rag\source.pdf"
OUT = r"C:\Users\sandy\dev\lab-rag\pilot\toc.txt"

r = PdfReader(PDF)
lines = []

def walk(items, depth=0):
    for it in items:
        if isinstance(it, list):
            walk(it, depth + 1)
        else:
            try:
                p = r.get_destination_page_number(it) + 1
            except Exception:
                p = "?"
            lines.append(f"{"  " * depth}[{p:>4}] {it.title}")

if r.outline:
    walk(r.outline)
else:
    lines.append("TIDAK ADA outline terbaca mesin - baca daftar isi manual.")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Selesai. Total baris:", len(lines))
