"""Uji set lintas bab (set_uji.json, dikunci SHA-256) dengan pipeline 18: hibrida BM25+embedding (RRF) + perluasan tetangga.

Penilaian otomatis per pertanyaan:
  LULUS            jawaban memuat semua grup kunci DAN menyitir halaman yang sah
  LULUS_HAL_SALAH  isi benar, tetapi sitasi halaman meleset (cek manual)
  MENOLAK_AMAN     info ada di buku tetapi model menolak (gagal yang aman)
  PERIKSA          model menjawab tetapi kunci tidak lengkap (bisa salah = berbahaya; WAJIB cek manual)
  HALUSINASI       model menjawab pertanyaan yang jawabannya tidak ada di buku (gagal fatal)
  (pertanyaan 'menolak' yang ditolak = LULUS)

Pakai:
  python 21_uji_set.py                 # semua pertanyaan (hasil lama yang sudah ada ditimpa)
  python 21_uji_set.py --hanya U03,U17 # ulang sebagian saja
  python 21_uji_set.py --ringkas       # hanya cetak ringkasan dari hasil tersimpan, tanpa memanggil API
  python 21_uji_set.py --nilai-ulang   # nilai ulang jawaban tersimpan dengan kunci terbaru, tanpa memanggil API
"""
import json, os, sys, pathlib, re, math, collections, hashlib, time
import numpy as np

ROOT = pathlib.Path(os.environ.get("LAB_RAG_ROOT", r"C:\Users\sandy\dev\lab-rag"))
BASE = ROOT / "full"
SET_FILE = ROOT / "set_uji.json"
SHA_KUNCI = "c1eb2aead6a7ded75cc98cf9dc975a3d6bcaa5ad0be0b78f389f5d0bfb676b62"  # set_uji v2 (lihat RIWAYAT VERSI di 20_set_uji.py)
HASIL = BASE / "hasil_uji.json"
LAPORAN = BASE / "hasil_uji.txt"
EMB_MODEL = "gemini-embedding-001"
CHAT_MODELS = ["gemini-3.8-flash", "gemini-3-flash-preview"]
TOPK = 5
K1, B = 1.5, 0.75
RRF_K = 60

SYSTEM = (
    "You answer questions using ONLY the numbered excerpts provided from a clinical laboratory reference book. "
    "Never use outside knowledge, even if you are confident. "
    "If the excerpts do not explicitly state the answer, set canAnswer to false and leave answer empty. "
    "If the excerpts contain only part of the answer, set canAnswer to false and explain what is missing in note. "
    "Copy every number exactly as printed, including units and comparison signs such as <= or <. "
    "The excerpts contain extraction noise: isolated single letters on their own lines come from a vertical page watermark and carry no meaning. "
    "Respond as JSON with keys: canAnswer (boolean), answer (string), quote (the exact line or sentence from the excerpt that supports the answer), "
    "chunkIds (list of excerpt ids used), note (string)."
)

TRANS = str.maketrans({"\u00b5": "u", "\u03bc": "u", "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2264": "<=", "\u2265": ">=",
                       "\u03b1": "a", "\u03b2": "b", "\u00df": "b"})

def norm(s):
    return re.sub(r"\s+", " ", str(s).lower().translate(TRANS)) + " "

def ada(alt, teks):
    a = norm(alt).strip()
    if re.fullmatch(r"[\d.]+", a):
        return re.search(r"(?<![\d.])" + re.escape(a) + r"(?!\d|\.\d)", teks) is not None
    return a in teks

def asc(s):
    return str(s).encode("ascii", "replace").decode("ascii")

# ---------- set uji: tolak kalau isinya berubah sejak dikunci
isi = SET_FILE.read_text(encoding="utf-8")
sha = hashlib.sha256(isi.encode("utf-8")).hexdigest()
if sha != SHA_KUNCI:
    raise SystemExit(f"set_uji.json BERUBAH sejak dikunci (sha {sha[:12]}...). Hasil tidak sebanding - batalkan.")
SET = json.loads(isi)

def nilai(u, ans, pages):
    if ans.get("canAnswer") is not True:
        return "LULUS" if u.get("menolak") else "MENOLAK_AMAN"
    if u.get("menolak"):
        return "HALUSINASI"
    teks = norm(ans.get("answer", ""))
    if not all(any(ada(a, teks) for a in grp) for grp in u["kunci"]):
        return "PERIKSA"
    return "LULUS" if set(pages) & set(u["halaman"]) else "LULUS_HAL_SALAH"

def ringkas(hasil):
    baris = []
    urut = [u for u in SET if u["id"] in hasil]
    hit = collections.Counter(hasil[u["id"]]["nilai"] for u in urut)
    baris.append(f"\n===== RINGKASAN {len(urut)}/{len(SET)} pertanyaan =====")
    for k in ["LULUS", "LULUS_HAL_SALAH", "MENOLAK_AMAN", "PERIKSA", "HALUSINASI"]:
        baris.append(f"  {k:16} {hit.get(k, 0)}")
    for nama, kunci in [("per tipe", "tipe"), ("per bab", "bab")]:
        g = collections.defaultdict(list)
        for u in urut:
            g[u[kunci]].append(hasil[u["id"]]["nilai"] == "LULUS")
        baris.append(f"  -- {nama}: " + ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in g.items()))
    dapat = [hasil[u["id"]] for u in urut if not u.get("menolak")]
    ada_rank = [h["rank_emas"] for h in dapat if h["rank_emas"]]
    baris.append(f"  -- retrieval: emas di top-5 {sum(r <= 5 for r in ada_rank)}/{len(dapat)}, "
                 f"emas di konteks (setelah perluasan) {sum(h['emas_di_konteks'] for h in dapat)}/{len(dapat)}")
    perlu = [u["id"] + "=" + hasil[u["id"]]["nilai"] for u in urut if hasil[u["id"]]["nilai"] not in ("LULUS",)]
    baris.append("  -- cek manual: " + (", ".join(perlu) if perlu else "tidak ada"))
    return "\n".join(baris)

def tulis_laporan(hasil):
    lap = []
    for u in SET:
        if u["id"] not in hasil:
            continue
        h = hasil[u["id"]]
        lap.append(f"\n########## {u['id']} [bab {u['bab']} | {u['tipe']}] {h['nilai']}\n{u['q']}")
        lap.append(f"kunci: {u.get('kunci', 'HARUS MENOLAK')} | halaman sah: {u.get('halaman', '-')}")
        lap.append(f"model: {h['model']} | emas#{h['rank_emas']} | emas di konteks: {h['emas_di_konteks']} | top-5: {', '.join(h['top5'])}")
        lap.append(json.dumps(h["jawaban"], ensure_ascii=False, indent=2))
    r_ = ringkas(hasil)
    LAPORAN.write_text("\n".join(lap) + "\n" + r_, encoding="utf-8")
    return r_

hasil = json.loads(HASIL.read_text(encoding="utf-8")) if HASIL.exists() else {}
if "--ringkas" in sys.argv:
    print(ringkas(hasil)); raise SystemExit
if "--nilai-ulang" in sys.argv:
    # Catatan: rank_emas & emas_di_konteks tetap dari saat dijalankan (penanda emas tidak berubah di v2).
    for u in SET:
        if u["id"] in hasil:
            lama = hasil[u["id"]]["nilai"]
            baru = nilai(u, hasil[u["id"]]["jawaban"], hasil[u["id"]]["halaman_jawaban"])
            if lama != baru:
                print(f"{u['id']}: {lama} -> {baru}")
            hasil[u["id"]]["nilai"] = baru
    HASIL.write_text(json.dumps(hasil, ensure_ascii=False, indent=1), encoding="utf-8")
    print(tulis_laporan(hasil)); raise SystemExit

hanya = None
if "--hanya" in sys.argv:
    hanya = set(sys.argv[sys.argv.index("--hanya") + 1].upper().split(","))
JALAN = [u for u in SET if not hanya or u["id"] in hanya]
if not JALAN:
    raise SystemExit("tidak ada pertanyaan yang cocok dengan --hanya")

from google import genai
from google.genai import types, errors

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(timeout=60000))

chunks = [json.loads(l) for l in (BASE / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
emb_ids = json.loads((BASE / "emb_full_ids.json").read_text(encoding="utf-8"))
if len(emb_ids) != len(chunks):
    raise SystemExit(f"embedding belum lengkap: {len(emb_ids)}/{len(chunks)}")
pos = {cid: k for k, cid in enumerate(emb_ids)}
chunks.sort(key=lambda c: pos[c["id"]])
ids = [c["id"] for c in chunks]
meta = {c["id"]: c for c in chunks}
texts = [c["text"] for c in chunks]
ntexts = [norm(t) for t in texts]
M = np.load(BASE / "emb_full.npy")
Mn = M / np.linalg.norm(M, axis=1, keepdims=True)

r = client.models.embed_content(model=EMB_MODEL, contents=[u["q"] for u in JALAN],
                                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"))
Q = np.array([e.values for e in r.embeddings], dtype=np.float32)
S = (Q / np.linalg.norm(Q, axis=1, keepdims=True)) @ Mn.T

GREEK = str.maketrans({"\u03b1": "a", "\u03b2": "b", "\u00df": "b", "\u03b3": "g", "\u03b4": "d", "\u03bc": "u", "\u00b5": "u"})

def tok(s):
    s = s.lower().translate(GREEK)
    return [t for t in re.split(r"[^a-z0-9.%]+", s) if len(t) >= 2]

docs = [tok(t) for t in texts]
N = len(docs)
avgdl = sum(len(d) for d in docs) / N
df = collections.Counter(w for d in docs for w in set(d))
tfs = [collections.Counter(d) for d in docs]

def bm25(q):
    qt = tok(q)
    out = []
    for i, d in enumerate(docs):
        sc = 0.0
        for w in qt:
            f = tfs[i].get(w, 0)
            if not f:
                continue
            idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
            sc += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * len(d) / avgdl))
        out.append(sc)
    return out

prosa_urut = sorted((c for c in ids if c.startswith("prosa-")), key=lambda x: int(x.split("-")[1]))
tetangga = {}
for k, cid in enumerate(prosa_urut):
    tetangga[cid] = ([prosa_urut[k - 1]] if k > 0 else []) + ([prosa_urut[k + 1]] if k + 1 < len(prosa_urut) else [])
idx = {cid: j for j, cid in enumerate(ids)}

def perluas(top):
    hasil_ = []
    for j in top:
        cid = ids[j]
        grup = [cid]
        if cid.startswith("prosa-"):
            a = tetangga[cid]
            grup = ([a[0]] if a and a[0] < cid else []) + [cid] + [x for x in a if x > cid]
        for g in grup:
            if g not in hasil_:
                hasil_.append(g)
    return [idx[g] for g in hasil_]

def ranks(order):
    return {j: r for r, j in enumerate(order, 1)}

def ask(prompt):
    last = None
    for m in CHAT_MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=m, contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM, temperature=0, response_mime_type="application/json",
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                    ),
                )
                return m, resp.text
            except errors.ServerError as e:
                last = e
                print(f"  {m}: server sibuk (percobaan {attempt + 1}/3), tunggu {10 * (attempt + 1)} detik")
                time.sleep(10 * (attempt + 1))
            except Exception as e:
                last = e
                print(f"  {m}: gagal ({type(e).__name__}), pindah ke model berikutnya")
                break
    print(f"  semua model gagal: {asc(last)[:160]}")
    return None, None

dilewati = []
for qi, u in enumerate(JALAN):
    q = u["q"]
    emb_order = list(np.argsort(-S[qi]))
    b = bm25(q)
    bm_order = sorted(range(N), key=lambda j: -b[j])
    re_, rb = ranks(emb_order), ranks(bm_order)
    fused = {j: 1 / (RRF_K + re_[j]) + 1 / (RRF_K + rb[j]) for j in range(N)}
    order = sorted(range(N), key=lambda j: -fused[j])
    rord = ranks(order)
    emas = set()
    if not u.get("menolak"):
        emas = {j for j in range(N) if all(m in ntexts[j] for m in u["emas"]) and set(meta[ids[j]]["page"]) & set(u["halaman"])}
    rank_emas = min((rord[j] for j in emas), default=None)
    top = order[:TOPK]
    konteks = perluas(top)
    emas_di_konteks = bool(emas & set(konteks))
    ctx = [f"[excerpt {ids[j]} | PDF pages {meta[ids[j]]['page']}]\n{texts[j]}" for j in konteks]
    prompt = "Question: " + q + "\n\nExcerpts:\n\n" + "\n\n".join(ctx)
    model_used, raw = ask(prompt)
    if raw is None:
        dilewati.append(u["id"])
        print(f"{u['id']}  DILEWATI - semua model gagal, hasil lama (kalau ada) tidak diubah")
        continue
    try:
        ans = json.loads(raw)
        if not isinstance(ans, dict):
            raise ValueError
    except Exception:
        ans = {"canAnswer": None, "answer": raw, "quote": "", "chunkIds": [], "note": "JSON tidak valid"}
    ans["chunkIds"] = [re.sub(r"^\s*\[?\s*excerpt\s+", "", str(c), flags=re.I).strip(" ]") for c in (ans.get("chunkIds") or [])]
    asing = [c for c in ans["chunkIds"] if c not in meta]
    if asing:
        ans["note"] = (ans.get("note") or "") + f" [PERINGATAN: chunkIds tidak dikenal {asing}]"
    pages = sorted({p for cid in ans["chunkIds"] if cid in meta for p in meta[cid]["page"]})
    v = nilai(u, ans, pages)
    print(f"{u['id']} [{u['tipe']}] {v:16} emas#{rank_emas} konteks:{'YA' if emas_di_konteks else '-'} hal {pages}")
    hasil[u["id"]] = dict(nilai=v, model=model_used, rank_emas=rank_emas, emas_di_konteks=emas_di_konteks,
                          halaman_jawaban=pages, top5=[ids[j] for j in top], konteks=[ids[j] for j in konteks], jawaban=ans)
    HASIL.write_text(json.dumps(hasil, ensure_ascii=False, indent=1), encoding="utf-8")

print(tulis_laporan(hasil))
if dilewati:
    print("DILEWATI:", ",".join(dilewati), "-> jalankan lagi: python 21_uji_set.py --hanya " + ",".join(dilewati))
print("detail: full\\hasil_uji.txt")
