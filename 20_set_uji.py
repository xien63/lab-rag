"""Bangun + validasi set uji lintas bab, lalu kunci dengan SHA-256.

Setiap pertanyaan:
  kunci   : list grup; SEMUA grup harus muncul di jawaban model, cukup SATU alternatif per grup.
  halaman : halaman PDF yang sah sebagai sitasi (jawaban harus menyitir minimal satu).
  emas    : penanda chunk-emas (semua harus ada di satu chunk) untuk mengukur peringkat retrieval.
  menolak : True = info tidak ada di buku, jawaban benar adalah canAnswer=false.

RIWAYAT VERSI
  v1 (1 Okt 2026, sha 82ee8661...): versi awal.
  v2 (1 Okt 2026): koreksi KUNCI, bukan kelonggaran untuk model. Uji v1 menunjukkan model menyitir
      hal 65 (U19) yang memang mencetak 'Lipid Peroxides <= 2.0' tetapi tidak saya daftarkan. Audit seluruh
      halaman lalu menemukan: U04 hal 614 mencetak methylmalonate <= 3.0 (batas lain); U08 arginine 42-130
      juga di hal 261-264; U09 histidin 19-102 juga di hal 260; U19 hal 510 mencetak batas urin lain
      (<= 40.0 nM/mg creatinine). Pertanyaan tidak diubah satu kata pun.

Validasi (dijalankan di sumber, sebelum model melihat apa pun):
  - tiap grup kunci harus tertulis di teks halaman yang dinyatakan;
  - penanda emas harus ada di chunk yang halamannya beririsan dengan 'halaman';
  - untuk 'menolak', istilah kunci dicek tidak muncul sebagai data (hit dicetak untuk ditinjau).
"""
import json, re, sys, hashlib, pathlib

BASE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "full")

SET = [
 # --- Bab 1 Basic Concepts
 dict(id="U01", bab="1", tipe="narasi",
      q="How does the book distinguish between the terms 'deficiency' and 'insufficiency'?",
      kunci=[["frank", "pellagra", "scurvy", "beriberi"], ["non-optimal", "nonoptimal", "not optimal"]],
      halaman=[14], emas=["non-optimal"]),
 # --- Bab 2 Vitamins
 dict(id="U02", bab="2", tipe="tabel",
      q="What serum 25-hydroxyvitamin D concentration is considered sufficient?",
      kunci=[["75"], ["250"]], halaman=[54], emas=["sufficient", "250"]),
 dict(id="U03", bab="2", tipe="indonesia",
      q="Pada kadar 25-hidroksivitamin D berapa kondisi dianggap toksik?",
      kunci=[["250"]], halaman=[54], emas=["toxic", "250"]),
 dict(id="U04", bab="2", tipe="regresi",
      q="What is the reference limit for urinary methylmalonate?",
      kunci=[["3.4", "3.0"]], halaman=[65, 66, 614], emas=["methylmalonate", "3.4"]),  # v2: hal 614 mencetak <=3.0
 # --- Bab 3 Elements
 dict(id="U05", bab="3", tipe="tabel",
      q="What median urinary iodine concentration indicates adequate iodine nutrition in a population?",
      kunci=[["100"], ["199"]], halaman=[117], emas=["100", "199"]),
 dict(id="U06", bab="3", tipe="tabel",
      q="Which metals does the chelating agent desferoxamine (DFO) bind?",
      kunci=[["aluminum", "aluminium"], ["iron"]], halaman=[87], emas=["desferoxamine"]),
 dict(id="U07", bab="3", tipe="tabel",
      q="What is the reference interval for selenium in red blood cells (erythrocytes)?",
      kunci=[["0.12"], ["0.40", "0.4"]], halaman=[150, 151, 153, 156], emas=["selenium", "0.12 - 0.40"]),
 # --- Bab 4 Amino Acids
 dict(id="U08", bab="4", tipe="tabel",
      q="What are the adult plasma reference limits for arginine?",
      kunci=[["42"], ["130"]], halaman=[197, 261, 262, 263, 264], emas=["arginine 42"]),  # v2: + laporan kasus 261-264
 dict(id="U09", bab="4", tipe="indonesia",
      q="Berapa batas referensi histidin pada spesimen blood spot untuk orang dewasa?",
      kunci=[["19"], ["102"]], halaman=[197, 260], emas=["histidine 53"]),  # v2: + hal 260
 # --- Bab 5 Fatty Acids
 dict(id="U10", bab="5", tipe="nama-mirip",
      q="What is the total omega-3 fatty acid content of farmed Atlantic salmon?",
      kunci=[["2.01"]], halaman=[307], emas=["2.01"]),
 # --- Bab 6 Organic Acids
 dict(id="U11", bab="6", tipe="tabel",
      q="Which food has the highest serotonin content, and how much does it contain?",
      kunci=[["butternut"], ["398"]], halaman=[364], emas=["butternut"]),
 dict(id="U12", bab="6", tipe="tabel",
      q="What is the reference limit for urinary quinolinate?",
      kunci=[["16.5"]], halaman=[403], emas=["quinolinate", "16.5"]),
 dict(id="U13", bab="6", tipe="lintas-halaman",
      q="In what percentage of patients were elevated D-arabinitol/creatinine ratios reported, and in which patient groups?",
      kunci=[["69"], ["36"], ["bacterial sepsis"]], halaman=[397, 398], emas=["9% of patients"]),
 dict(id="U14", bab="6", tipe="regresi",
      q="Which pharmaceutical is listed as an anti-fungal intervention for intestinal overgrowth?",
      kunci=[["nystatin"]], halaman=[400], emas=["nystatin"]),
 # --- Bab 7 GI
 dict(id="U15", bab="7", tipe="tabel",
      q="What was the overall sensitivity of Tumor M2-PK for colorectal cancer?",
      kunci=[["50"]], halaman=[452], emas=["m2-pk"]),
 dict(id="U16", bab="7", tipe="tabel",
      q="What is the reference limit for D-lactate in the gastrointestinal profile?",
      kunci=[["11.0", "11"]], halaman=[467], emas=["d-lactate", "11.0"]),
 # --- Bab 8 Detoxification
 dict(id="U17", bab="8", tipe="tabel",
      q="What detoxification function does selenium serve?",
      kunci=[["glutathione"], ["mercury"]], halaman=[513], emas=["mercury protection"]),
 dict(id="U18", bab="8", tipe="indonesia",
      q="Intervensi apa yang disebutkan untuk meningkatkan ekskresi toksin melalui feses?",
      kunci=[["olive oil", "cholegogue", "cholagogue"], ["fiber", "fibre", "serat"]], halaman=[514], emas=["fecal excretion"]),
 # --- Bab 9 Oxidant Stress
 dict(id="U19", bab="9", tipe="tabel",
      q="What is the reference limit for urinary lipid peroxides?",
      kunci=[["2.0", "40.0"]], halaman=[65, 317, 510, 535, 536, 546, 547], emas=["lipid peroxides", "2.0"]),  # v2: + hal 65; hal 510 <=40.0 nM/mg
 # --- Bab 10 Hormones
 dict(id="U20", bab="10", tipe="tabel",
      q="What is the serum progesterone reference range during the luteal phase?",
      kunci=[["5"], ["25"]], halaman=[576], emas=["progesterone", "luteal"]),
 dict(id="U21", bab="10", tipe="nama-mirip",
      q="What is the estradiol reference range during the follicular phase?",
      kunci=[["50"], ["300"]], halaman=[576], emas=["estradiol", "follicular"]),
 # --- Bab 11 Genomics
 dict(id="U22", bab="11", tipe="gambar",
      q="What proportion of drugs is metabolized by CYP3A4/5?",
      kunci=[["35"]], halaman=[601], emas=["3a4.5"]),
 # --- Bab 12 Pattern Analysis
 dict(id="U23", bab="12", tipe="tabel",
      q="Which reinforcing tests are suggested for peripheral neuropathy?",
      kunci=[["methylmalon"], ["homocysteine"]], halaman=[613], emas=["peripheral neuropathy"]),
 # --- Lampiran
 dict(id="U24", bab="A", tipe="tabel",
      q="What nutritional intervention is listed for elevated lipoprotein(a), and by what mechanism?",
      kunci=[["niacin"], ["synthesis"]], halaman=[631], emas=["lipoprotein(a) niacin"]),
 dict(id="U25", bab="B", tipe="tabel",
      q="What potential clinical indications are listed for low serum chloride?",
      kunci=[["adrenal"], ["hypochlorhydria"]], halaman=[637], emas=["chloride", "hypochlorhydria"]),
 dict(id="U26", bab="C", tipe="tabel",
      q="Which nutrients can be depleted by aspirin?",
      kunci=[["vitamin c"], ["folic acid", "folate"], ["zinc"]], halaman=[643], emas=["aspirin"]),
 # --- Harus menolak (tidak ada di buku)
 dict(id="U27", bab="-", tipe="menolak", menolak=True,
      q="What is the reference range for hemoglobin A1c (HbA1c)?", cek_absen=["hba1c", "hbalc"]),
 dict(id="U28", bab="-", tipe="menolak-indonesia", menolak=True,
      q="Berapa nilai normal procalcitonin dalam darah?", cek_absen=["procalciton"]),
 dict(id="U29", bab="-", tipe="menolak", menolak=True,
      q="What is the reference range for anti-Mullerian hormone (AMH) in women?", cek_absen=["mullerian", "müllerian", " amh"]),
 dict(id="U30", bab="-", tipe="menolak", menolak=True,
      q="What is the reference limit for urinary glyphosate?", cek_absen=["glyphosate"]),
]

TRANS = str.maketrans({"µ": "u", "μ": "u", "–": "-", "—": "-", "−": "-", "≤": "<=", "≥": ">=",
                       "α": "a", "β": "b", "ß": "b"})

def norm(s):
    return re.sub(r"\s+", " ", str(s).lower().translate(TRANS)) + " "

def ada(alt, teks):
    """Alternatif angka dicocokkan dengan batas digit ('5' tidak cocok di dalam '25' atau '5.6'); teks biasa: substring."""
    a = norm(alt).strip()
    if re.fullmatch(r"[\d.]+", a):
        return re.search(r"(?<![\d.])" + re.escape(a) + r"(?!\d|\.\d)", teks) is not None
    return a in teks

if __name__ == "__main__":
    t = (BASE / "plumber_full.txt").read_text(encoding="utf-8")
    p = re.split(r"===== HAL (\d+) =====", t)
    pg = {int(p[i]): norm(p[i + 1]) for i in range(1, len(p), 2)}
    chunks = [json.loads(l) for l in (BASE / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    gagal = 0
    for u in SET:
        if u.get("menolak"):
            hits = {h: [w for w in u["cek_absen"] if w in pg[h]] for h in pg}
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
        else:
            print(f"{u['id']} ok | emas: {emas[:4]}{' ...' if len(emas) > 4 else ''}")
    if gagal:
        raise SystemExit(f"{gagal} kegagalan - perbaiki sebelum dikunci")
    isi = json.dumps(SET, ensure_ascii=False, indent=1)
    (BASE.parent / "set_uji.json").write_text(isi, encoding="utf-8")
    print("SHA-256 set_uji.json:", hashlib.sha256(isi.encode("utf-8")).hexdigest())
