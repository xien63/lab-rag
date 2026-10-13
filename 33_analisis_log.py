"""33_analisis_log.py - analisis READ-ONLY atas full\\tanya_log.jsonl.

Tidak mengimpor 31_tanya.py, tidak memanggil model, tidak menyentuh gerbang/ambang.
Hanya membaca log, lalu menulis dua berkas di full\\ (folder ini tidak masuk git):
  - analisis_log.md       : ringkasan DESKRIPTIF (hitungan, daftar, pengulangan)
  - lembar_nilai.csv      : satu baris per pertanyaan; kolom penilaian KOSONG, diisi Sandy sendiri

Prinsip:
  * Status otomatis hanya diturunkan dari field log (tingkat, canAnswer, angka_tak_terverifikasi).
    Skrip TIDAK menyimpulkan "gagal di mana". Itu keputusan manusia, di lembar nilai.
  * Menjalankan ulang aman: kolom isian Sandy di lembar_nilai.csv dipertahankan (kunci = waktu + pertanyaan).
  * Keluaran tidak memuat teks buku selain 200 karakter awal jawaban model (untuk orientasi saat menilai).

Pakai:
  python 33_analisis_log.py                 # log default, kedua berkas ditulis ke full\\
  python 33_analisis_log.py --sejak 2026-10-14   # laporan .md hanya memuat baris sejak tanggal itu;
                                                 # lembar_nilai.csv TETAP memuat seluruh log
  python 33_analisis_log.py --log jalur\\lain.jsonl --keluar jalur\\keluar
"""
import csv, datetime, json, pathlib, re, sys
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent


def argv_val(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 >= len(sys.argv):
            raise SystemExit(f"{flag} harus diikuti nilai")
        return sys.argv[i + 1]
    return default


LOG = pathlib.Path(argv_val("--log", ROOT / "full" / "tanya_log.jsonl"))
OUT = pathlib.Path(argv_val("--keluar", ROOT / "full"))
BAKU = pathlib.Path(argv_val("--baku", ROOT / "pertanyaan_15.txt"))
SEJAK = argv_val("--sejak")

KOLOM_ISIAN = ["kegagalan_di", "klaim_dicek", "halaman_dicek", "kesesuaian", "catatan"]
KOLOM_OTOMATIS = ["no", "waktu", "sumber", "tingkat", "status_otomatis", "halaman", "jml_chunk", "pertanyaan", "jawaban_awal_200"]


def norm(q):
    return re.sub(r"[^a-z0-9]+", " ", q.lower()).strip()


if not LOG.exists():
    raise SystemExit(f"Log tidak ditemukan: {LOG}")

rows = []
salah_baca = 0
for n, line in enumerate(LOG.read_text(encoding="utf-8").splitlines(), 1):
    if not line.strip():
        continue
    try:
        rows.append(json.loads(line))
    except json.JSONDecodeError:
        salah_baca += 1
semua_baris = list(rows)   # lembar nilai SELALU memuat seluruh log; --sejak hanya menyaring laporan .md
if SEJAK:
    rows = [r for r in rows if r.get("waktu", "")[:10] >= SEJAK]

baku = set()
if BAKU.exists():
    baku = {norm(l) for l in BAKU.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}


def status(r):
    """Turunan murni dari field log. Bukan penilaian kebenaran."""
    if str(r.get("tingkat")) == "3":
        return "ditolak"
    if r.get("degradasi"):
        return "degradasi"
    if r.get("angka_tak_terverifikasi"):
        return "angka_tak_terverifikasi"
    if not r.get("canAnswer"):
        return "tidak_dijawab"
    return "dijawab"


for r in semua_baris:
    r["_status"] = status(r)
    r["_sumber"] = "baku" if norm(r.get("q", "")) in baku else "pakai"

pakai = [r for r in rows if r["_sumber"] == "pakai"]
ctr_all = Counter(r["_status"] for r in rows)
ctr_pakai = Counter(r["_status"] for r in pakai)

# ---- pengulangan: pertanyaan sama ditanyakan >1 kali (sinyal stabilitas gratis) ----
grup = defaultdict(list)
for r in rows:
    grup[norm(r.get("q", ""))].append(r)
ulang = {k: v for k, v in grup.items() if len(v) > 1}

# ---- pasangan mirip: satu ditolak, yang lain dijawab (kandidat pengamatan router) ----
def kata(q):
    return {w for w in norm(q).split() if len(w) > 3}

pasangan = []
tol = [r for r in rows if r["_status"] == "ditolak"]
jaw = [r for r in rows if r["_status"] == "dijawab"]
for a in tol:
    for b in jaw:
        ka, kb = kata(a["q"]), kata(b["q"])
        if ka and kb and len(ka & kb) / min(len(ka), len(kb)) >= 0.5 and norm(a["q"]) != norm(b["q"]):
            pasangan.append((a, b))


def pot(s, n):
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def jam(r):
    return r.get("waktu", "")[:16].replace("T", " ")


L = []
w = L.append
w(f"# Analisis log tanya — dibuat {datetime.datetime.now().isoformat(timespec='seconds')}")
w("")
w(f"Sumber: `{LOG.name}` · {len(rows)} baris" + (f" (sejak {SEJAK})" if SEJAK else "") + (f" · {salah_baca} baris rusak dilewati" if salah_baca else ""))
w("Berkas ini DESKRIPTIF. Tidak ada kesimpulan 'gagal di pencarian/jawaban/router'; itu diisi Sandy di `lembar_nilai.csv`.")
w("'baku' = pertanyaan identik dengan `pertanyaan_15.txt`; 'pakai' = selain itu (pemakaian nyata). Menjalankan ulang baku lewat web tetap tercatat sebagai baku.")
w("")
w("## 1. Hitungan")
w("")
w("| status (turunan dari field log) | semua | pemakaian nyata |")
w("|---|---:|---:|")
for s in ["dijawab", "tidak_dijawab", "ditolak", "angka_tak_terverifikasi", "degradasi"]:
    w(f"| {s} | {ctr_all.get(s, 0)} | {ctr_pakai.get(s, 0)} |")
w(f"| **total** | **{len(rows)}** | **{len(pakai)}** |")
w("")
lr = sum(1 for r in rows if r.get("label_repletion"))
w(f"Label Repletion terpasang: {lr} baris · dipangkas: {sum(1 for r in rows if r.get('dipangkas'))} · mode --v5: {sum(1 for r in rows if r.get('v5'))} · model: " + ", ".join(f"{k}×{v}" for k, v in Counter(r.get('model') for r in rows).items()))
w("")
w("Catatan baca: 'tidak_dijawab' di tingkat 1 bisa berarti pencarian tidak menemukan, atau buku memang tidak memuatnya, atau model memilih abstain. Log saja tidak membedakan ketiganya; itu yang perlu Sandy nilai.")
w("")

w("## 2. Pemakaian nyata, urut waktu")
w("")
w("| # | waktu | tingkat | status | hal. PDF | pertanyaan |")
w("|--:|---|:-:|---|---|---|")
for i, r in enumerate(pakai, 1):
    w(f"| {i} | {jam(r)} | {r.get('tingkat')} | {r['_status']} | {', '.join(map(str, r.get('halaman') or [])) or '-'} | {pot(r.get('q'), 90)} |")
w("")

w("## 3. Tidak dijawab (tingkat 1) — baca alasan model")
w("")
td = [r for r in rows if r["_status"] == "tidak_dijawab"]
if not td:
    w("_Tidak ada._")
for r in td:
    w(f"- **{jam(r)}** — {pot(r.get('q'), 100)}")
    w(f"  - catatan model: {pot(r.get('note'), 260)}")
w("")

w("## 4. Ditolak oleh router (tingkat 3)")
w("")
if not tol:
    w("_Tidak ada._")
for r in tol:
    w(f"- **{jam(r)}** — {pot(r.get('q'), 120)}")
w("")
if pasangan:
    w("### 4a. Pasangan mirip: satu ditolak, satu dijawab")
    w("")
    w("Pengamatan murni, bukan keputusan mengubah router (router parkir, gerbang dibekukan). Dicatat agar pola terlihat bila berulang.")
    w("")
    for a, b in pasangan:
        w(f"- DITOLAK {jam(a)}: {pot(a['q'], 110)}")
        w(f"  - DIJAWAB {jam(b)}: {pot(b['q'], 110)}")
    w("")

w("## 5. Pertanyaan yang sama ditanyakan berulang")
w("")
if not ulang:
    w("_Tidak ada._")
else:
    w("Sinyal stabilitas dari pemakaian biasa (bukan pengganti uji 3 putaran yang diparkir).")
    w("")
    for k, v in ulang.items():
        sets = [tuple(sorted(r.get("halaman") or [])) for r in v]
        stat = [r["_status"] for r in v]
        sama_hal = len(set(sets)) == 1
        sama_stat = len(set(stat)) == 1
        w(f"- {pot(v[0]['q'], 100)} — ×{len(v)} · status {'sama' if sama_stat else 'BERBEDA'} ({', '.join(stat)}) · halaman {'sama' if sama_hal else 'BERBEDA'}")
        if not sama_hal:
            for r, s in zip(v, sets):
                w(f"  - {jam(r)}: {list(s)}")
w("")

w("## 6. Kriteria lembar nilai (diisi Sandy)")
w("")
w("- `kegagalan_di`: isi **tidak ada** / **pencarian** (buku memuat jawabannya tetapi chunk yang benar tidak terambil) / **jawaban** (chunk benar terambil, tetapi model salah memakainya, termasuk salah-atribusi umum→khusus) / **router** (tingkat salah: info umum ditolak, atau dosis pribadi lolos) / **buku tidak memuat** (abstain benar).")
w("- `klaim_dicek` + `halaman_dicek`: tulis satu klaim yang kamu verifikasi dan halaman PDF yang kamu buka. Prioritas: klaim yang kamu pakai sungguhan.")
w("- `kesesuaian`: **sesuai** / **sebagian** / **tidak**.")
w("- Salah-atribusi tanpa angka tidak tertangkap pemeriksa angka. Untuk jawaban tentang fungsi/peran sesuatu, cek: apakah buku menyebut ini khas zat itu, atau umum untuk banyak zat? (kasus acuan: triptofan → 'sintesis glukosa', PDF 191).")
w("- Aturan: **jangan mengubah gerbang/ambang sampai seluruh lembar terisi dan polanya ditulis.**")
w("")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "analisis_log.md").write_text("\n".join(L) + "\n", encoding="utf-8")

# ---- lembar nilai: pertahankan isian lama ----
csv_path = OUT / "lembar_nilai.csv"
lama = {}
if csv_path.exists():
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for d in csv.DictReader(f):
            lama[(d.get("waktu", ""), d.get("pertanyaan", ""))] = {k: d.get(k, "") for k in KOLOM_ISIAN}

ada = {(r.get("waktu", ""), r.get("q", "")) for r in semua_baris}
yatim = {k: v for k, v in lama.items() if k not in ada and any(v.values())}
with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(KOLOM_OTOMATIS + KOLOM_ISIAN)
    for i, r in enumerate(semua_baris, 1):
        key = (r.get("waktu", ""), r.get("q", ""))
        isi = lama.get(key, {})
        wr.writerow([
            i, r.get("waktu", ""), r["_sumber"], r.get("tingkat"), r["_status"],
            " ".join(map(str, r.get("halaman") or [])), len(r.get("chunk") or []),
            r.get("q", ""), pot(r.get("answer"), 200),
        ] + [isi.get(k, "") for k in KOLOM_ISIAN])
    for (waktu, q), isi in yatim.items():   # baris yang sudah tidak ada di log tetapi sudah Sandy nilai: jangan dibuang
        wr.writerow(["", waktu, "(tidak di log)", "", "", "", "", q, ""] + [isi.get(k, "") for k in KOLOM_ISIAN])

dipertahankan = sum(1 for v in lama.values() if any(v.values()))
print(f"Dibaca {len(rows)} baris ({len(pakai)} pemakaian nyata). Status semua: " + ", ".join(f"{k}={v}" for k, v in ctr_all.items()))
print(f"Ditulis: {OUT / 'analisis_log.md'}")
print(f"Ditulis: {csv_path}  ({len(semua_baris)} baris; isian lama dipertahankan: {dipertahankan} baris" + (f", {len(yatim)} baris yatim ikut disimpan" if yatim else "") + ")")
