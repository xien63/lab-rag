"""30_uji_retrieval.py - tolok ukur retrieval TINGKAT CHUNK (hanya panggilan embedding + terjemahan kueri; model jawab TIDAK dipanggil).

Latar: metrik "emas di konteks" di 23_uji_baris.py memakai penanda teks dan terbukti memberi positif palsu (U19: penanda cocok
dengan chunk batas serum, chunk batas urin prosa-3212 tidak ada di konteks). Di sini bukti didefinisikan per butir sebagai POLA TEKS
yang diverifikasi dari buku (chunk benar). Yang diukur: peringkat chunk benar terbaik, dan apakah ia masuk konteks.

Varian:
  V0  dasar (persis 23_uji_baris.py: kueri = pertanyaan + terjemahan, hibrida BM25+embedding RRF, perluasan tetangga, varian C)
  K8, K10  konteks dari 8 / 10 peringkat teratas (bukan 5)  [peringkat sama dengan V0, hanya konteks]
  V3  BM25 prosa dengan stemming ringan (buang bentuk jamak -s/-es/-ies) pada dokumen DAN kueri
  V4  kueri DINETRALKAN (buang kata ganti dan angka pribadi dari pertanyaan sebelum diterjemahkan); hanya berbeda untuk soal pribadi
  V5  V3 + V4
Pakai:  python 30_uji_retrieval.py            # semua butir
Hasil:  full/hasil_retrieval.json dan full/hasil_retrieval.txt   (butir dengan terjemahan netral baru: cache full/terjemah_netral_cache.json)
Aturan baca (dikunci di PILOT.md sebelum dijalankan); tolok ukur ini hanya bisa MENOLAK sebuah varian, tidak cukup untuk menerimanya.
"""
import json, os, sys, pathlib, re, math, collections, time
import numpy as np

K1, B = 1.5, 0.75
RRF_K = 60
SARING = True
EMB_MODEL = "gemini-embedding-001"
CHAT_MODELS = ["gemini-3.8-flash", "gemini-3-flash-preview"]
ROOT = pathlib.Path(os.environ.get("LAB_RAG_ROOT", r"C:\Users\sandy\dev\lab-rag"))
BASE = ROOT / "full"
SISIP_BARIS = 2

TRANS = str.maketrans({"\u00b5": "u", "\u03bc": "u", "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2264": "<=", "\u2265": ">=",
                       "\u03b1": "a", "\u03b2": "b", "\u00df": "b"})

def norm(s):
    t = re.sub(r"\s+", " ", str(s).lower().translate(TRANS)) + " "
    return re.sub(r"(?<=\d),(?=\d{1,2}(?!\d))", ".", t)   # koma desimal Indonesia: 0,3 -> 0.3 (ribuan 3 digit "1,000" tetap)


def norm(s):
    t = re.sub(r"\s+", " ", str(s).lower().translate(TRANS)) + " "
    return re.sub(r"(?<=\d),(?=\d{1,2}(?!\d))", ".", t)

# ---------- butir yang diukur
FILE_SET = {"U": "uji", "B": "buta", "N": "nyata", "M": "nyata2", "P": "nyata3", "Q": "nyata4"}
HCY = (r"(homocysteine \d[\d.]* (h )?2\.5 - 11\.3|homocysteine[^.]{0,60}(<= ?8\b|< ?8\b))", [41, 42, 48, 66, 262, 263, 604])
TARGET = {   # id: (pola bukti pada teks ternormalisasi, halaman PDF); diverifikasi dari teks buku
    "U19": (r"urine lipid peroxide \d[\d.]* h <= 40\.0", [510]),
    "B09": (r"insulin <= [\d.]+ l 2\.0 - 12\.0", [544]),
    "N15": (r"decreased serum ferritin serves as an early sign", [103]),
    "P06": (r"greater than 150 ug/dl", [32, 33]),
    "N02": (r"c-reactive protein \(hs\) \d[\d.]* h <= 3\.0", [156]),
    "B15": (r"pyroglutamate \d[\d.]* (h )?< ?(95|72)", [404, 547]),
    "M01": HCY, "P10": HCY, "Q13": HCY,
}
KONTROL = ["B10", "B18", "B20", "N13", "N20", "M09", "M21", "Q14", "U05", "U06", "U08", "U14"]   # LULUS, emas peringkat 1-2 di hasil RUB3-ARH; bukti = penanda emas set
ITEMS = list(TARGET) + KONTROL
SETS = {}
for n in sorted(set(FILE_SET.values())):
    for u in json.loads((ROOT / f"set_{n}.json").read_text(encoding="utf-8")):
        SETS[u["id"]] = u
STORED = {}
for n in sorted(set(FILE_SET.values())):
    f = BASE / f"hasil_{n}_C-SAR-EKS-LEN-RUB3-ARH.json"
    if f.exists():
        STORED.update(json.loads(f.read_text(encoding="utf-8")))

from google import genai
from google.genai import types
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


STRONG_SITASI = re.compile(r"\b(?:19|20)\d\d;\s?\d+\s?(?:\(\s?[\w\s-]*\))?\s?:\s?[\dA-Za-z]+")
AUTH_SITASI = re.compile(r"\b[A-Z][a-z]+ [A-Z]{1,3}(?:,| et al)")
CMP_TABEL = re.compile(r"<=|>=|\u2264|\u2265")

def chunk_pustaka(cid, t):
    """Chunk daftar pustaka: >=3 pola sitasi 'tahun;volume:halaman' (atau >=2 dengan >=3 pola penulis), kecuali data tabel (>=4 tanda <=/>=)."""
    if cid.startswith("tabel-") or len(CMP_TABEL.findall(t)) >= 4:
        return False
    s_, a_ = len(STRONG_SITASI.findall(t)), len(AUTH_SITASI.findall(t))
    return s_ >= 3 or (s_ >= 2 and a_ >= 3)

PUSTAKA = {j for j, c in enumerate(ids) if chunk_pustaka(c, texts[j])}
if SARING:
    print(f"saring: {len(PUSTAKA)} chunk daftar pustaka dibuang dari peringkat/konteks")


GREEK = str.maketrans({"\u03b1": "a", "\u03b2": "b", "\u00df": "b", "\u03b3": "g", "\u03b4": "d", "\u03bc": "u", "\u00b5": "u"})

def tok(s):
    s = s.lower().translate(GREEK)
    return [t for t in re.split(r"[^a-z0-9.%]+", s) if len(t) >= 2]

def stem(t):
    """Stemming ringan: hanya bentuk jamak bahasa Inggris. Angka dan kata berakhiran -ss/-us/-is tidak diubah."""
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith(("ches", "shes", "sses", "xes", "zes")):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        return t[:-1]
    return t

class Indeks:
    def __init__(self, pakai_stem):
        self.st = pakai_stem
        self.docs = [self.t(x) for x in texts]
        self.N = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / self.N
        self.df = collections.Counter(w for d in self.docs for w in set(d))
        self.tfs = [collections.Counter(d) for d in self.docs]
    def t(self, s):
        x = tok(s)
        return [stem(w) for w in x] if self.st else x
    def bm25(self, q):
        qt = self.t(q)
        out = []
        for i, d in enumerate(self.docs):
            sc = 0.0
            for w in qt:
                f = self.tfs[i].get(w, 0)
                if not f:
                    continue
                idf = math.log(1 + (self.N - self.df[w] + 0.5) / (self.df[w] + 0.5))
                sc += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * len(d) / self.avgdl))
            out.append(sc)
        return out
N = len(texts)
IDX = {False: Indeks(False), True: Indeks(True)}

def tok_baris(s):
    s = s.lower().translate(GREEK)
    out = []
    for t in re.split(r"[^a-z0-9.%\-]+", s):
        t = t.strip("-.")
        if not t:
            continue
        if "-" in t:
            out.append(t)
            out += [p for p in t.split("-") if len(p) >= 2]
        elif len(t) >= 2:
            out.append(t)
    return out

REF = re.compile(r"(<=|>=|=>|=<|\u2264|\u2265|<|>)\s*\d|\d\s*[-\u2013]\s*\d")
SITASI = re.compile(r"\d{4};|;\s*\d{4}|et al|\.{5,}|\d{4}\)|, \d+[\u2013-]\d+(\(|,|$)|J Clin|Am J|Clin Chem")
STOP = set("what which is are the of for in a an and to by does do how much reference range ranges limit limits interval "
           "value values level levels normal urinary urine serum plasma blood listed considered indicates indicate adult "
           "adults during with as at on its it this that from be book according".split())
baris = [(j, ln.strip()) for j, t in enumerate(texts) for ln in t.split("\n")
         if REF.search(ln) and re.search(r"[A-Za-z]{3,}", ln) and not SITASI.search(ln) and min(meta[ids[j]]["page"]) < 649]
bdocs = [tok_baris(l) for _, l in baris]
bN = len(bdocs)
bavg = sum(len(d) for d in bdocs) / bN
bdf = collections.Counter(w for d in bdocs for w in set(d))
btfs = [collections.Counter(d) for d in bdocs]
print(f"indeks baris: {bN} baris dari {len(set(j for j, _ in baris))} chunk")

def induk_dari_baris(q):
    qt = [w for w in tok_baris(q) if w not in STOP]
    sc = [0.0] * bN
    for w in qt:
        if w not in bdf:
            continue
        idf = math.log(1 + (bN - bdf[w] + 0.5) / (bdf[w] + 0.5))
        for i in range(bN):
            f = btfs[i].get(w, 0)
            if f:
                sc[i] += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * len(bdocs[i]) / bavg))
    urut = []
    for k in sorted(range(bN), key=lambda k: -sc[k]):
        if sc[k] <= 0:
            break
        if baris[k][0] not in urut:
            urut.append(baris[k][0])
    return urut

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


PRON = re.compile(r"\b(saya|aku|ku|kami|punya saya|milik saya)\b", re.I)
ANGKA = re.compile(r"(?<![\w-])\d+([.,]\d+)?\s*%?(?![\w-])")   # angka mandiri saja: "omega-3", "25-OH", "B12" tidak disentuh
def netralkan(q):
    if not PRON.search(q):
        return q   # hanya soal berkata ganti orang pertama yang dinetralkan
    t = ANGKA.sub("", PRON.sub("", q))
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,?.])", r"\1", t)
    t = re.sub(r"^[\s,]+|(?<=[,])\s*,", "", t).strip()
    return t

TERJ = json.loads((BASE / "terjemah_cache.json").read_text(encoding="utf-8"))
NF = BASE / "terjemah_netral_cache.json"
NC = json.loads(NF.read_text(encoding="utf-8")) if NF.exists() else {}
SYS_TR = ("Translate the user's question into one concise English question, using the exact terminology of a clinical laboratory and nutrition "
          "reference book (analyte names, drug names, drug classes, nutrient names). Output only the English question, nothing else.")
def terjemah(q):
    for m in CHAT_MODELS:
        for k in range(3):
            try:
                tr = client.models.generate_content(model=m, contents=q, config=types.GenerateContentConfig(
                    system_instruction=SYS_TR, temperature=0, thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)))
                return (tr.text or "").strip().replace("\n", " ")
            except Exception as e:
                print(f"  terjemahan gagal di {m} ({type(e).__name__}), tunggu {10 * (k + 1)} detik")
                time.sleep(10 * (k + 1))
    return None

Q0, QN = {}, {}
for i in ITEMS:
    q = SETS[i]["q"]
    if q not in TERJ:
        raise SystemExit(f"terjemahan {i} tidak ada di terjemah_cache.json - jalankan 23_uji_baris.py --ekspansi untuk set itu dulu")
    Q0[i] = (q + " " + TERJ[q]).strip()
    qn = netralkan(q)
    if qn.lower() == q.lower() or not qn:
        QN[i] = Q0[i]
    else:
        if qn not in NC:
            tr = terjemah(qn)
            if tr is None:
                raise SystemExit(f"terjemahan netral {i} gagal")
            NC[qn] = tr
            NF.write_text(json.dumps(NC, ensure_ascii=False, indent=1), encoding="utf-8")
        QN[i] = (qn + " " + NC[qn]).strip()
        print(f"netral {i}: '{q}' -> '{qn}' -> '{NC[qn]}'")

teks_q = sorted(set(Q0.values()) | set(QN.values()))
vec = {}
for a in range(0, len(teks_q), 50):
    r = client.models.embed_content(model=EMB_MODEL, contents=teks_q[a:a + 50], config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"))
    for t_, e in zip(teks_q[a:a + 50], r.embeddings):
        v = np.array(e.values, dtype=np.float32)
        vec[t_] = (v / np.linalg.norm(v)) @ Mn.T

def peringkat(qtext, pakai_stem):
    emb_order = list(np.argsort(-vec[qtext]))
    b = IDX[pakai_stem].bm25(qtext)
    bm_order = sorted(range(N), key=lambda j: -b[j])
    re_, rb = ranks(emb_order), ranks(bm_order)
    fused = {j: 1 / (RRF_K + re_[j]) + 1 / (RRF_K + rb[j]) for j in range(N)}
    induk = induk_dari_baris(qtext)
    order = [j for j in sorted(range(N), key=lambda j: -fused[j]) if j not in PUSTAKA]
    return order, induk

def konteks_k(order, induk, k):
    ks = [j for j in perluas(order[:k]) if j not in PUSTAKA]
    for j in induk[:SISIP_BARIS]:
        if j not in ks:
            ks.append(j)
    return ks

def relevan(i):
    if i in TARGET:
        pola, hal = TARGET[i]
        return {j for j in range(N) if set(meta[ids[j]]["page"]) & set(hal) and re.search(pola, ntexts[j])} - PUSTAKA
    u = SETS[i]
    return {j for j in range(N) if all(m in ntexts[j] for m in u["emas"]) and set(meta[ids[j]]["page"]) & set(u["halaman"])} - PUSTAKA

VARS = {"V0": (False, False), "V3": (True, False), "V4": (False, True), "V5": (True, True)}
HASIL = {}
for i in ITEMS:
    rel = relevan(i)
    if not rel:
        print(f"{i}: tidak ada chunk relevan (pola/penanda)"); continue
    d = {"relevan": [ids[j] for j in sorted(rel)]}
    for v, (st, net) in VARS.items():
        order, induk = peringkat((QN if net else Q0)[i], st)
        rord = ranks(order)
        d[v] = {"rank": min(rord[j] for j in rel if j in rord),
                "top5": [ids[j] for j in order[:5]],
                "k5": bool(rel & set(konteks_k(order, induk, 5))),
                "k8": bool(rel & set(konteks_k(order, induk, 8))),
                "k10": bool(rel & set(konteks_k(order, induk, 10))),
                "n5": len(konteks_k(order, induk, 5)), "n8": len(konteks_k(order, induk, 8)), "n10": len(konteks_k(order, induk, 10))}
    HASIL[i] = d
(BASE / "hasil_retrieval.json").write_text(json.dumps(HASIL, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------- laporan
L = []
def sel(d, v, k="k5"):
    return f"{d[v]['rank']}{'*' if d[v][k] else ''}"
L.append("rank terbaik chunk benar; * = masuk konteks. kolom K8/K10 = konteks dari 8/10 teratas (rank V0).")
L.append(f"{'id':5}{'tipe':8}{'V0':>7}{'K8':>6}{'K10':>6}{'V3':>7}{'V4':>7}{'V5':>7}   chunk benar")
for i in ITEMS:
    if i not in HASIL: continue
    d = HASIL[i]
    L.append(f"{i:5}{'TARGET' if i in TARGET else 'kontrol':8}{sel(d,'V0'):>7}{('*' if d['V0']['k8'] else '-'):>6}{('*' if d['V0']['k10'] else '-'):>6}"
             f"{sel(d,'V3'):>7}{sel(d,'V4'):>7}{sel(d,'V5'):>7}   {','.join(d['relevan'][:4])}")
tg = [i for i in TARGET if i in HASIL]; ko = [i for i in KONTROL if i in HASIL]
L.append("")
L.append(f"TARGET masuk konteks (dari {len(tg)}): V0 {sum(HASIL[i]['V0']['k5'] for i in tg)}, K8 {sum(HASIL[i]['V0']['k8'] for i in tg)}, K10 {sum(HASIL[i]['V0']['k10'] for i in tg)}, "
         f"V3 {sum(HASIL[i]['V3']['k5'] for i in tg)}, V4 {sum(HASIL[i]['V4']['k5'] for i in tg)}, V5 {sum(HASIL[i]['V5']['k5'] for i in tg)}")
L.append(f"KONTROL keluar dari konteks dibanding V0 (dari {len(ko)}): K8 0 (k lebih besar tidak mengeluarkan), "
         f"V3 {sum(HASIL[i]['V0']['k5'] and not HASIL[i]['V3']['k5'] for i in ko)}, V4 {sum(HASIL[i]['V0']['k5'] and not HASIL[i]['V4']['k5'] for i in ko)}, "
         f"V5 {sum(HASIL[i]['V0']['k5'] and not HASIL[i]['V5']['k5'] for i in ko)}")
L.append(f"KONTROL rank terbaik memburuk >3 posisi: V3 {sum(HASIL[i]['V3']['rank'] > HASIL[i]['V0']['rank'] + 3 for i in ko)}, V5 {sum(HASIL[i]['V5']['rank'] > HASIL[i]['V0']['rank'] + 3 for i in ko)}")
med = lambda key: sorted(HASIL[i]['V0'][key] for i in HASIL)[len(HASIL) // 2]
L.append(f"ukuran konteks (median chunk): k5 {med('n5')}, k8 {med('n8')}, k10 {med('n10')}")
# reproduksi: top5 V0 harus sama dengan hasil tersimpan
cocok, banding, beda = 0, 0, []
for i in ITEMS:
    if i in HASIL and i in STORED:
        banding += 1
        if HASIL[i]["V0"]["top5"] == STORED[i]["top5"]:
            cocok += 1
        else:
            beda.append(i)
L.append(f"REPRODUKSI top-5 V0 = hasil tersimpan 23_uji_baris.py: {cocok}/{banding}" + (f"; BEDA: {','.join(beda)}" if beda else ""))
txt = "\n".join(L)
(BASE / "hasil_retrieval.txt").write_text(txt, encoding="utf-8")
print("\n" + txt)
print("\ndetail: full\\hasil_retrieval.txt / hasil_retrieval.json")
