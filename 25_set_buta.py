"""Set uji BUTA (blind) untuk lab-rag - pertanyaan BARU, belum pernah dilihat saat merancang indeks baris (varian D).

Dibuat 2 Okt 2026 SETELAH memilih varian D. Tidak ada pertanyaan di sini yang dipakai untuk memperbaiki apa pun.
Format sama dengan 20_set_uji.py (kunci = daftar grup, semua grup harus muncul, cukup satu alternatif per grup).
  tipe "baris-laporan" : jawaban hanya tercetak sebagai satu baris di laporan lab contoh (pola U12/U16)
  tipe "multi-nilai"   : analit yang sama punya >1 batas di bagian buku berbeda; kunci menerima nilai mana pun yang sah
  tipe "spesimen"      : pertanyaan menyebut spesimen/laporan tertentu; hanya satu nilai yang benar
Pakai:  python 25_set_buta.py full            # validasi + audit halaman lain
        python 25_set_buta.py full --kunci    # + tulis set_buta.json dan cetak SHA-256

Catatan audit sebelum dikunci (2 Okt): B03 indican 115 (panel asam organik, hal 405-406) vs 124 (profil GI, hal 467) -> pertanyaan
menyebut profil GI. B12 magnesium 28-100 di hal 154 adalah profil rambut -> pertanyaan menyebut sel darah merah. B17 taurine blood
spot 138-355 (hal 197) vs 133-355 (hal 260). B26 lithium dibahas (hal 128) tetapi tanpa batas referensi tercetak.

RIWAYAT VERSI
  v1 (2 Okt 2026, sha 36f92d22...6e94): versi awal, dipakai untuk uji C dan D (1 putaran) dan C (3 putaran).
  v2 (2 Okt 2026): koreksi KUNCI B16, BUKAN kelonggaran untuk model. Hasil uji v1 menunjukkan model menyitir hal 102, yang
      mencetak tabel acuan "Ferritin Male 12-300 / Female 10-150 ng/mL" (Tabel 3.6). Audit v1 melewatkannya karena nama analit
      dan angka ada di baris terpisah pada tata letak itu. Perubahan: halaman + [102]; alternatif kunci + "12-300", "10-150"
      (nilai tercetak di hal 102). Hal 101 (ambang tahap defisiensi: >300, >150, 20, <10) sengaja TIDAK ditambahkan karena
      bukan batas referensi. Pertanyaan tidak diubah satu kata pun. Audit ulang seluruh halaman untuk 21 soal berjawab
      lainnya (jendela 3 baris) tidak menemukan halaman sah lain; kandidat yang muncul adalah baris campuran dua kolom,
      dosis (mg/hari), profil rambut/plasma, atau ambang tahap.
"""
import json, re, sys, hashlib, pathlib

BASE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "full")
TRANS = str.maketrans({"µ": "u", "μ": "u", "–": "-", "—": "-", "−": "-", "≤": "<=", "≥": ">=",
                       "α": "a", "β": "b", "ß": "b"})
def norm(s):
    return re.sub(r"\s+", " ", str(s).lower().translate(TRANS)) + " "
def ada(alt, teks):
    a = norm(alt).strip()
    if re.fullmatch(r"[\d.]+", a):
        return re.search(r"(?<![\d.])" + re.escape(a) + r"(?!\d|\.\d)", teks) is not None
    return a in teks

SET = [
 # ---- baris-laporan
 dict(id="B01", bab="6", tipe="baris-laporan", analit="xanthurenate", q="What is the reference limit for urinary xanthurenate?",
      kunci=[["1.10"]], halaman=[403], emas=["xanthurenate", "1.10"]),
 dict(id="B02", bab="6", tipe="baris-laporan", analit="kynurenate", q="What is the reference limit for urinary kynurenate?",
      kunci=[["2.5"]], halaman=[403], emas=["kynurenate", "2.5"]),
 dict(id="B03", bab="7", tipe="spesimen", analit="indican", q="In the gastrointestinal function profile, what is the reference limit for indican?",
      kunci=[["124"]], halaman=[467], emas=["indican", "124"]),
 dict(id="B04", bab="7", tipe="baris-laporan", analit="glucarate", q="What is the reference limit for urinary glucarate in the organic acid profile?",
      kunci=[["11.9"]], halaman=[404, 547], emas=["glucarate", "11.9"]),
 dict(id="B05", bab="7", tipe="baris-laporan", analit="scfa", q="What is the reference limit for total short-chain fatty acids (SCFA) in the stool profile?",
      kunci=[["40"]], halaman=[467], emas=["total scfa", "40"]),
 dict(id="B06", bab="7", tipe="baris-laporan", analit="bacteroides", q="What is the reference value for Bacteroides in the GI function profile?",
      kunci=[["1.3"]], halaman=[467], emas=["bacteroides", "1.3"]),
 dict(id="B07", bab="3", tipe="baris-laporan", analit="homovanillate", q="What is the reference interval for urinary homovanillate?",
      kunci=[["1.3"], ["15.2"]], halaman=[157, 604, 605], emas=["homovanillate", "15.2"]),
 dict(id="B08", bab="10", tipe="baris-laporan", analit="sex hormone", q="What is the reference range for sex hormone-binding globulin (SHBG)?",
      kunci=[["18"], ["114"]], halaman=[544], emas=["sex hormone-binding", "114"]),
 dict(id="B09", bab="10", tipe="baris-laporan", analit="insulin", q="What is the reference range for insulin in the cardiovascular risk profile?",
      kunci=[["2.0"], ["12.0"]], halaman=[544], emas=["insulin", "12.0"]),
 dict(id="B10", bab="9", tipe="baris-laporan", analit="lipoprotein (a)", q="What is the reference limit for lipoprotein(a)?",
      kunci=[["37"]], halaman=[544], emas=["lipoprotein (a)", "37"]),
 dict(id="B11", bab="3", tipe="baris-laporan", analit="transferrin saturation", q="What is the reference range for transferrin saturation in the iron status example?",
      kunci=[["14"], ["50"]], halaman=[155], emas=["transferrin saturation", "14"]),
 dict(id="B12", bab="3", tipe="baris-laporan", analit="magnesium", q="What is the reference interval for magnesium in red blood cells?",
      kunci=[["40"], ["80"]], halaman=[150, 151, 153], emas=["magnesium", "40 - 80"]),
 # ---- multi-nilai (batas berbeda di bagian buku berbeda)
 dict(id="B13", bab="6", tipe="multi-nilai", analit="tricarballylate", q="What is the reference limit for tricarballylate?",
      kunci=[["3.6", "1.8"]], halaman=[405, 406, 467, 614], emas=["tricarballylate", "3.6"]),
 dict(id="B14", bab="6", tipe="multi-nilai", analit="orotate", q="What is the reference limit for orotate?",
      kunci=[["1.6", "180"]], halaman=[404, 547, 614], emas=["orotate", "1.6"]),
 dict(id="B15", bab="6", tipe="multi-nilai", analit="pyroglutamate", q="What is the reference limit for pyroglutamate?",
      kunci=[["95", "72", "80"]], halaman=[404, 547, 614], emas=["pyroglutamate", "95"]),
 dict(id="B16", bab="3", tipe="multi-nilai", analit="ferritin", q="What is the reference range for serum ferritin?",
      kunci=[["40", "28", "12-300", "10-150"]], halaman=[102, 155, 156], emas=["ferritin", "40"]),  # v2: + hal 102
 dict(id="B17", bab="4", tipe="spesimen", analit="taurine", q="What is the blood spot reference range for taurine?",
      kunci=[["138", "133"], ["355"]], halaman=[197, 260], emas=["taurine", "138"]),  # hal 260 (kasus blood spot) mencetak 133-355
 # ---- narasi / tabel (EN + Indonesia)
 dict(id="B18", bab="8", tipe="indonesia", analit="vitamin c", q="Apa fungsi vitamin C dalam detoksifikasi menurut tabel fungsi detoksifikasi nutrien?",
      kunci=[["mobilization", "mobilisasi"], ["antioxidant", "antioksidan"]], halaman=[513], emas=["vitamin c", "mobilization"]),
 dict(id="B19", bab="8", tipe="indonesia", analit="lead protection", q="Nutrien mana yang memberi perlindungan terhadap timbal (lead) dalam tabel fungsi detoksifikasi nutrien?",
      kunci=[["calcium", "kalsium"]], halaman=[513], emas=["calcium", "lead protection"]),
 dict(id="B20", bab="8", tipe="indonesia", analit="soft tissue", q="Intervensi apa saja yang disebutkan untuk meningkatkan laju mobilisasi toksin dari jaringan lunak dan tulang?",
      kunci=[["dmps", "dmsa", "edta", "penicillamine", "chelation"]], halaman=[514], emas=["rate of mobilization", "dmsa"]),
 dict(id="B21", bab="8", tipe="tabel", analit="mehp", q="What percentage of children had detectable mono-(2-ethylhexyl) phthalate (mEHP) in the New York City study?",
      kunci=[["97.5"]], halaman=[490], emas=["mehp", "97.5"]),
 dict(id="B22", bab="3", tipe="tabel", analit="edta", q="Which chelating agent binds cadmium, lead and manganese?",
      kunci=[["canaedta", "cana-edta", "calcium disodium"]], halaman=[87], emas=["cadmium, lead, manganese"]),
 # ---- harus menolak
 dict(id="B23", bab="-", tipe="menolak", menolak=True, q="What is the reference range for CA-125?", cek_absen=["ca-125", "ca 125"]),
 dict(id="B24", bab="-", tipe="menolak-indonesia", menolak=True, q="Berapa batas normal cystatin C dalam serum?", cek_absen=["cystatin"]),
 dict(id="B25", bab="-", tipe="menolak", menolak=True, q="What is the reference range for serum PSA (prostate-specific antigen)?", cek_absen=["psa"]),
 dict(id="B26", bab="-", tipe="menolak", menolak=True, q="What is the reference limit for urinary lithium?", cek_absen=["urinary lithium", "lithium <=", "lithium  <"]),
]

if __name__ == "__main__":
    t = (BASE / "plumber_full.txt").read_text(encoding="utf-8")
    p = re.split(r"===== HAL (\d+) =====", t)
    raw = {int(p[i]): p[i + 1] for i in range(1, len(p), 2)}
    pg = {h: norm(v) for h, v in raw.items()}
    chunks = [json.loads(l) for l in (BASE / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    gagal = 0
    for u in SET:
        if u.get("menolak"):
            hits = {h: [w for w in u["cek_absen"] if w in pg[h]] for h in pg if h < 649}
            hits = {h: w for h, w in hits.items() if w}
            print(f"{u['id']} menolak | istilah muncul di halaman: {sorted(hits) or 'tidak ada'}")
            continue
        teks = "".join(pg[h] for h in u["halaman"])
        for grp in u["kunci"]:
            if not any(ada(a, teks) for a in grp):
                print(f"{u['id']} GAGAL: kunci {grp} tidak ada di halaman {u['halaman']}"); gagal += 1
        emas = [c["id"] for c in chunks if all(m in norm(c["text"]) for m in u["emas"]) and set(c["page"]) & set(u["halaman"])]
        if not emas:
            print(f"{u['id']} GAGAL: penanda emas {u['emas']} tidak ada di chunk halaman {u['halaman']}"); gagal += 1
        # audit: baris lain di halaman LAIN yang memuat analit + angka (kandidat nilai alternatif)
        lain = []
        for h in sorted(raw):
            if h in u["halaman"] or h >= 649:
                continue
            for l in raw[h].split("\n"):
                nl = norm(l)
                if u["analit"] in nl and re.search(r"(<=|>=|<|>|\d\s*-\s*\d)\s*[\d.]", nl) and not re.search(r"\d{4};|et al|\.{4}", nl):
                    lain.append(f"{h}| {l.strip()[:80]}")
        print(f"{u['id']} {'ok' if emas else '??'} | emas: {emas[:3]}" + (f" | LAIN({len(lain)}): {lain[:4]}" if lain else ""))
    if gagal:
        raise SystemExit(f"{gagal} kegagalan - perbaiki sebelum dikunci")
    if "--kunci" in sys.argv:
        isi = json.dumps(SET, ensure_ascii=False, indent=1)
        (BASE.parent / "set_buta.json").write_text(isi, encoding="utf-8")
        print("SHA-256 set_buta.json:", hashlib.sha256(isi.encode("utf-8")).hexdigest())
    else:
        print("(belum dikunci: jalankan dengan --kunci setelah audit LAIN ditinjau)")
