"""Ekstraksi seluruh buku: teks + tabel per halaman (pdfplumber), watermark dibuang di level karakter, paralel.
Pemakaian: python 14_ekstrak_penuh.py <folder-kerja>   (folder berisi source.pdf; hasil ke <folder>/full/)
"""
import json, sys, time, pathlib
from multiprocessing import Pool
import pdfplumber

BASE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\sandy\dev\lab-rag")
PDF = BASE / "source.pdf"
OUT = BASE / "full"
WORKERS = 2

def bukan_watermark(obj):
    # Watermark "Genova Diagnostics": 18 huruf Helvetica > 40 pt, identik di ke-672 halaman.
    # Isi buku tidak pernah memakai Helvetica > 40 pt (diverifikasi: Helvetica kecil hanya di hal 467, ukuran <= 40).
    return not (obj.get("object_type") == "char" and obj.get("fontname", "").endswith("Helvetica") and obj.get("size", 0) > 40)

def kerja(rentang):
    a, b = rentang
    hasil = []
    with pdfplumber.open(PDF) as pdf:
        for i in range(a, b):
            pg = pdf.pages[i].filter(bukan_watermark)
            teks = pg.extract_text() or ""
            tabel = pg.extract_tables()
            hasil.append({"hal": i + 1, "teks": teks, "tabel": tabel})
    return hasil

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    with pdfplumber.open(PDF) as pdf:
        n = len(pdf.pages)
    langkah = 24
    rentang = [(s, min(s + langkah, n)) for s in range(0, n, langkah)]
    t0 = time.time()
    semua = []
    with Pool(WORKERS) as pool:
        for k, part in enumerate(pool.imap(kerja, rentang), 1):
            semua.extend(part)
            print(f"blok {k}/{len(rentang)} selesai  ({time.time() - t0:.0f} dtk)", flush=True)
    semua.sort(key=lambda x: x["hal"])
    (OUT / "plumber_full.txt").write_text(
        "".join(f"\n\n===== HAL {p['hal']} =====\n" + p["teks"] for p in semua), encoding="utf-8")
    tabel = [{"hal": p["hal"], "baris": t} for p in semua for t in p["tabel"]]
    (OUT / "tabel_full.json").write_text(json.dumps(tabel, ensure_ascii=False), encoding="utf-8")
    statistik = [{"hal": p["hal"], "karakter": len(p["teks"]), "tabel": len(p["tabel"])} for p in semua]
    (OUT / "statistik_halaman.json").write_text(json.dumps(statistik, ensure_ascii=False, indent=1), encoding="utf-8")
    print("halaman:", n, "| tabel:", len(tabel), "| total karakter:", sum(s["karakter"] for s in statistik))
