"""Chunking seluruh buku: logika sama dengan 07_chunk.py (table-aware, prosa per baris, overlap lintas halaman,
halaman dilacak per baris) + filter tabel kosong (09) + penanda pola tabel-036.
Pemakaian: python 15_chunk_penuh.py <folder-kerja>   (membaca <folder>/full/, menulis ke <folder>/full/)
"""
import json, re, sys, pathlib

BASE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\sandy\dev\lab-rag")
D = BASE / "full"
TARGET, OVERLAP = 900, 200
RANGE_ONLY = re.compile(r"^\s*(<=|>=|<|>|\d+(\.\d+)?\s*-\s*\d+(\.\d+)?)\s*[\d.,\s]*$")

def tabel_teks(hal, baris):
    lines = [f"[TABEL - halaman {hal}]"]
    for row in baris:
        lines.append(" | ".join((c or "").strip() for c in row))
    return "\n".join(lines)

def kosong(teks):
    body = teks.split("\n", 1)[1] if "\n" in teks else ""
    return re.sub(r"[\s|]", "", body) == ""

def run_rentang(teks):
    best = cur = 0
    for ln in teks.split("\n"):
        ln = ln.replace("|", " ").strip()
        if ln and RANGE_ONLY.match(ln) and not re.search(r"[A-Za-z]", ln):
            cur += 1; best = max(best, cur)
        else:
            cur = 0
    return best

chunks, dibuang, ditandai = [], [], []
tabel = json.loads((D / "tabel_full.json").read_text(encoding="utf-8"))
for k, t in enumerate(tabel, 1):
    teks = tabel_teks(t["hal"], t["baris"])
    cid = f"tabel-{k:04d}"
    if kosong(teks):
        dibuang.append(cid); continue
    run = run_rentang(teks)
    if run >= 3:
        # Pola tabel-036: >= 3 baris berturut-turut berisi rentang saja, tanpa nama analit.
        # Dibuang karena pemasangannya murni posisional. Diverifikasi 29 Sep + 1 Okt 2026: untuk
        # semua kasus yang ditemukan, prosa halaman yang sama memasangkan analit-rentang dengan benar,
        # kecuali hal 190 (angka rentang tanpa pasangan di teks mana pun - celah yang diketahui).
        ditandai.append((cid, t["hal"], run)); continue
    chunks.append({"id": cid, "page": [t["hal"]], "type": "tabel", "text": teks})

raw = (D / "plumber_full.txt").read_text(encoding="utf-8")
p = re.split(r"===== HAL (\d+) =====", raw)
page_texts = {int(p[j]): p[j + 1].strip() for j in range(1, len(p), 2)}
n_prosa, buf = 0, []
def teks_buf(): return "\n".join(l for l, _ in buf)
def emit():
    global n_prosa
    n_prosa += 1
    chunks.append({"id": f"prosa-{n_prosa:04d}", "page": sorted({h for _, h in buf}), "type": "prosa", "text": teks_buf()})
def ekor():
    t = teks_buf(); e = t[-OVERLAP:] if len(t) > OVERLAP else t
    el = e.split("\n"); src = buf[-len(el):]
    return [(el[i], src[i][1]) for i in range(len(el)) if el[i].strip()]
for hal, isi in sorted(page_texts.items()):
    for ln in [x.strip() for x in isi.split("\n") if x.strip()]:
        if not buf or len(teks_buf()) + len(ln) + 1 <= TARGET:
            buf.append((ln, hal))
        else:
            emit(); buf = ekor() + [(ln, hal)]
if buf: emit()

with open(D / "chunks.jsonl", "w", encoding="utf-8") as f:
    for c in chunks:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
lap = {
    "chunk_total": len(chunks),
    "chunk_tabel": sum(c["type"] == "tabel" for c in chunks),
    "chunk_prosa": sum(c["type"] == "prosa" for c in chunks),
    "tabel_kosong_dibuang": len(dibuang),
    "tabel_dibuang_rentang_terpisah": [{"id": a, "hal": b, "run": r} for a, b, r in ditandai],
    "celah_diketahui": ["hal 190: angka rentang (19-153, 303-626, 42-130, 53-101, 37-98) tanpa nama analit di teks maupun tabel - perlu cek visual"],
    "karakter_total": sum(len(c["text"]) for c in chunks),
    "prosa_lintas_halaman": sum(c["type"] == "prosa" and len(c["page"]) > 1 for c in chunks),
}
(D / "laporan_chunk.json").write_text(json.dumps(lap, ensure_ascii=False, indent=1), encoding="utf-8")
print({k: (v if not isinstance(v, list) else len(v)) for k, v in lap.items()})
