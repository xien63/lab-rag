"""32_daftar_isi.py - buat full\\daftar_isi.json dari bookmark (outline) source.pdf, 13 Okt 2026.
Isi: daftar entri {d: kedalaman, t: judul, p: halaman PDF}. Hanya judul dan nomor halaman; tidak ada isi buku.
Dipakai antarmuka web (python 31_tanya.py --web) untuk panel "Daftar isi". Folder full/ tidak masuk git.
Pakai:  python 32_daftar_isi.py          (butuh:  pip install pypdf)
"""
import json, os, pathlib, re, sys
from pypdf import PdfReader

ROOT = pathlib.Path(os.environ.get("LAB_RAG_ROOT", r"C:\Users\sandy\dev\lab-rag"))
PDF = ROOT / "source.pdf"
OUT = ROOT / "full" / "daftar_isi.json"

r = PdfReader(str(PDF))
n_hal = len(r.pages)
hasil, tanpa_halaman = [], 0

def jalan(node, d=0):
    global tanpa_halaman
    for it in node:
        if isinstance(it, list):
            jalan(it, d + 1)
            continue
        judul = re.sub(r"\s+", " ", str(it.title or "")).strip()
        try:
            p = r.get_destination_page_number(it) + 1
        except Exception:
            p = None
        if not judul:
            continue
        if p is None or not (1 <= p <= n_hal):
            tanpa_halaman += 1
            continue
        hasil.append({"d": d, "t": judul, "p": p})

jalan(r.outline)
if not hasil:
    raise SystemExit("PDF tidak punya bookmark yang terbaca; daftar isi tidak dibuat.")
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(hasil, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"{len(hasil)} entri ditulis ke {OUT} (dari {n_hal} halaman PDF; {tanpa_halaman} entri dilewati karena tanpa halaman sah)")
