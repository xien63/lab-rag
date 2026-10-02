"""Uji stabilitas: bandingkan putaran penuh yang sama (hasil_uji_<V>_p1.json, _p2, ...), tanpa memanggil API.

Pakai:  python 24_stabilitas.py            # varian D (default)
        python 24_stabilitas.py --varian C

Yang dilaporkan:
  - skor tiap putaran (LULUS dst.) dan pertanyaan yang belum selesai di sebuah putaran
  - pertanyaan TIDAK STABIL: nilainya berbeda antar putaran (atau jawaban canAnswer berbeda)
  - pertanyaan 'menolak' yang pernah dijawab (halusinasi di salah satu putaran = bahaya, walau putaran lain benar)
  - perbedaan isi jawaban (jawaban LULUS di semua putaran tapi kalimat/angkanya berbeda) hanya ditandai untuk dibaca manual
"""
import json, sys, pathlib, collections, re, os

ROOT = pathlib.Path(os.environ.get("LAB_RAG_ROOT", r"C:\Users\sandy\dev\lab-rag"))
BASE = ROOT / "full"
V = sys.argv[sys.argv.index("--varian") + 1].upper() if "--varian" in sys.argv else "D"
SETNAME = sys.argv[sys.argv.index("--set") + 1].lower() if "--set" in sys.argv else "uji"
SET = json.loads((ROOT / f"set_{SETNAME}.json").read_text(encoding="utf-8"))
files = sorted(BASE.glob(f"hasil_{SETNAME}_{V}_p*.json"), key=lambda p: int(re.search(r"_p(\d+)", p.name).group(1)))
if len(files) < 2:
    raise SystemExit(f"butuh minimal 2 putaran (hasil_{SETNAME}_{V}_p1.json, _p2.json). Ditemukan: {[f.name for f in files]}")
R = {int(re.search(r"_p(\d+)", f.name).group(1)): json.loads(f.read_text(encoding="utf-8")) for f in files}
ps = sorted(R)

def angka(a):
    t = str(a.get("answer", ""))
    # buang rujukan "Table 4.7"/"Tabel 2.10"/"Figure 3.1" dan "95%": itu nomor tabel, bukan nilai klinis
    t = re.sub(r"(?i)\b(table|tabel|figure|gambar)\s+[A-Z]?\d+(?:\.\d+)?", " ", t)
    t = re.sub(r"\d+(?:\.\d+)?\s*%", " ", t)
    return sorted(set(re.findall(r"\d+(?:\.\d+)?", t)))

print(f"===== STABILITAS varian {V}: {len(ps)} putaran =====")
for p in ps:
    c = collections.Counter(R[p][u["id"]]["nilai"] for u in SET if u["id"] in R[p])
    kosong = [u["id"] for u in SET if u["id"] not in R[p]]
    print(f"  putaran {p}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())) + (f" | BELUM ADA: {','.join(kosong)}" if kosong else ""))

tidak_stabil, halus, isi_beda = [], [], []
lengkap = [u for u in SET if all(u["id"] in R[p] for p in ps)]
for u in lengkap:
    nil = [R[p][u["id"]]["nilai"] for p in ps]
    if len(set(nil)) > 1:
        tidak_stabil.append((u["id"], u["tipe"], nil))
    if u.get("menolak") and any(n == "HALUSINASI" for n in nil):
        halus.append(u["id"])
    if not u.get("menolak") and len(set(nil)) == 1 and nil[0] == "LULUS":
        a = [angka(R[p][u["id"]]["jawaban"]) for p in ps]
        if any(x != a[0] for x in a):
            isi_beda.append((u["id"], a))

print(f"\npertanyaan dibandingkan: {len(lengkap)}/{len(SET)}")
print(f"STABIL (nilai sama di semua putaran): {len(lengkap) - len(tidak_stabil)}/{len(lengkap)}")
if tidak_stabil:
    print("TIDAK STABIL:")
    for i, t, n in tidak_stabil:
        print(f"  {i} [{t}]: " + " -> ".join(n))
else:
    print("TIDAK STABIL: tidak ada")
print("HALUSINASI di salah satu putaran: " + (", ".join(halus) if halus else "tidak ada"))
if isi_beda:
    print("LULUS semua putaran tetapi ANGKA di jawaban berbeda (baca manual):")
    for i, a in isi_beda:
        print(f"  {i}: {a}")
semua_lulus = [u["id"] for u in lengkap if all(R[p][u["id"]]["nilai"] == "LULUS" for p in ps)]
print(f"LULUS di SEMUA putaran: {len(semua_lulus)}/{len(lengkap)}")
