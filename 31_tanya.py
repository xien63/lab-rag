"""31_tanya.py - alat tanya pribadi atas buku Lord & Bralley (RAG), 13 Okt 2026.

Memakai mesin yang sama dengan 23_uji_baris.py pada konfigurasi tervalidasi:
  varian C + --saring --ekspansi --lengkap --rubrik3 --arah   (opsi --v5 menambah --stem --netral; V5 belum diterima)
Jalur gagal-aman (--aman): router gagal -> penolakan tetap bila ada penanda pribadi/dosis, selain itu jalur campuran.

Tambahan khusus alat ini (tidak mengubah kebijakan, hanya menambah pengaman):
  - Pemeriksa angka: setiap angka (bukan bilangan bulat 0-10) di jawaban harus ada di kutipan atau teks chunk yang dikutip.
    Bila tidak, jawaban ringkas DISEMBUNYIKAN dan hanya kutipan + halaman yang ditampilkan.
  - Label Repletion (Q11-B, 13 Okt): jawaban berangka dosis yang mengutip chunk berkata "repletion" diberi catatan tetap
    (dosis pemulihan defisiensi terbukti lab, bukan dosis harian umum). Deterministik, bukan dari model.
  - Setiap tanya dicatat ke full\\tanya_log.jsonl (folder full/ tidak masuk git).

Pakai:
  python 31_tanya.py                      # mode interaktif
  python 31_tanya.py "pertanyaan"        # satu pertanyaan
  python 31_tanya.py --file pertanyaan_15.txt   # banyak pertanyaan, satu per baris
  opsi: --teks (cetak teks lengkap chunk yang dikutip)  --v5
  python 31_tanya.py --web                # antarmuka web lokal di http://127.0.0.1:8765 (opsi: --port N, --no-open)
"""
import json, os, sys, pathlib, re, math, collections, time, datetime
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(os.environ.get("LAB_RAG_ROOT", r"C:\Users\sandy\dev\lab-rag"))
BASE = ROOT / "full"
V5 = "--v5" in sys.argv
STEM, NETRAL = V5, V5
SARING = EKSPANSI = LENGKAP = RUBRIK3 = ARAH = True
RUBRIK = RUBRIK2 = False
TEKS = "--teks" in sys.argv

EMB_MODEL = "gemini-embedding-001"
CHAT_MODELS = ["gemini-3.8-flash", "gemini-3-flash-preview"]
TOPK = 5
SISIP_BARIS = 2
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

SYSTEM_LENGKAP = (
    " Exception for list questions: if the question asks for a list (which drugs, which nutrients, which tests) and the excerpts show only some items, "
    "set canAnswer to true, list only the items that appear in the excerpts, and end the answer with one sentence, in the language of the question, "
    "saying that the list is based only on the excerpts provided and may be incomplete. Never imply that the list is complete. "
    "This exception overrides the partial-answer rule above for list questions only."
)
SYSTEM_RUBRIK = (
    " Policy for personal and medical questions. (1) General education about what a test measures, what a result can mean, reference limits printed in the book, "
    "or which drugs and nutrients interact: answer from the excerpts. (2) If the user states their own lab value, you may report the reference limits printed in the excerpts "
    "and what the excerpts say such a result can be associated with, framed as information to discuss with a healthcare professional; never state or deny a diagnosis "
    "for the user, and never tell them to start, stop or change a medication. (3) If the user asks for a personal dose, whether to start or stop a medication, or how to treat or cure "
    "a condition: set canAnswer to false, leave answer empty, and make note a single neutral sentence asking them to consult a healthcare professional; "
    "do not put doses, numeric ranges with units, or treatment advice in note. For a mixed question (for example a drug interaction plus a dose), set canAnswer to true, "
    "answer only the part the excerpts support, state that dosing must be decided with a healthcare professional, and never give a dose. "
    "This policy overrides the partial-answer rule above for such mixed questions."
)
SYSTEM_RUBRIK2 = (
    " Policy for personal and medical questions (version 2). "
    "(1) General questions about the book (what a test measures, what a result can mean, reference limits, drug-nutrient interactions, and doses or intake limits that the excerpts print): "
    "answer from the excerpts. Every dose or intake number you give must stay in the same sentence as its source and population, for example 'the book reports ... for adults ...' "
    "(translate the sentence into the language of the question); never write a dose number in a sentence of its own, never present an adult dose as a dose for children or any other group, "
    "and never present a printed dose as a recommendation to the user. "
    "(2) If the user states their own lab value, you may report the reference limits printed in the excerpts and what the excerpts say such a result can be associated with, "
    "framed as information to discuss with a healthcare professional; never state or deny a diagnosis for the user, and never tell them to start, stop or change a medication. "
    "(3) If the user asks for a personal dose (for example 'my', 'my child', 'how much should I take'), whether to start or stop a medication, or how to treat or cure a condition: "
    "set canAnswer to false, leave answer empty, and make note a single neutral sentence, in the language of the question, asking them to consult a healthcare professional; "
    "the note must contain no number, no dose, no supplement or drug name and no treatment advice. "
    "For a mixed question (for example a drug interaction plus a personal dose), set canAnswer to true, answer only the part the excerpts support, state that dosing must be decided "
    "with a healthcare professional, and write no dose and no number with a dose unit anywhere, in answer or note, even if the excerpts print one. "
    "This policy overrides the partial-answer rule above for such mixed questions."
)
SYSTEM_RUBRIK3 = (
    " Policy for personal and medical questions (version 3). "
    "(1) General questions about the book (what a test measures, what a result can mean, reference limits, drug-nutrient interactions, and doses or intake limits that the excerpts print): "
    "answer from the excerpts. Every dose or intake number you give must stay in the same sentence as its source, for example 'the book reports ...' "
    "(translate the sentence into the language of the question). If the excerpt states the population (for example adults, men), keep that population in the same sentence. "
    "If the excerpt does not state a population, say that the book does not specify one; never refuse a general question only because the population is unstated. "
    "Never write a dose number in a sentence of its own, never present an adult dose as a dose for children or any other group, and never present a printed dose as a recommendation to the user. "
    "If the only value in the excerpts is a concentration or typical level from a table that is not presented as a reference range or normal limit (for example a table of antioxidants found in serum), "
    "either refuse, or state in the same sentence that it is a concentration reported in that table and is not a clinical reference range. "
    "(2) If the user states their own lab value, you may report the reference limits printed in the excerpts and what the excerpts say such a result can be associated with, "
    "framed as information to discuss with a healthcare professional; never state or deny a diagnosis for the user, and never tell them to start, stop or change a medication. "
    "(3) If the user asks for a personal dose (for example 'my', 'my child', 'how much should I take'), whether to start or stop a medication, or how to treat or cure a condition: "
    "set canAnswer to false, leave answer empty, and make note a single neutral sentence, in the language of the question, asking them to consult a healthcare professional; "
    "the note must contain no number, no dose, no supplement or drug name and no treatment advice. "
    "For a mixed question (for example a drug interaction plus a personal dose), set canAnswer to true, answer only the part the excerpts support, state that dosing must be decided "
    "with a healthcare professional, and write no dose and no number with a dose unit anywhere, in answer or note, even if the excerpts print one. "
    "This policy overrides the partial-answer rule above for such mixed questions."
)
SYSTEM_ARAH = (
    "You are a safety router for a question-answering system built on a clinical laboratory reference book. Classify the user's question (Indonesian or English) into exactly one class. "
    'Reply with JSON only: {"tingkat": "1" | "2" | "3" | "campuran", "alasan": "<max 12 words>"}. '
    'Class "3": the user asks for a personal dose or amount to take (words such as saya, anak saya, ibu saya, untuk saya, yang cocok untuk saya, harus saya minum), how long to take something, '
    "whether to start, stop or change a medication or supplement, which supplements they should take, whether they need a treatment or detox, or how to cure, treat, heal or overcome a disease or condition "
    "(even in general phrasing such as 'bagaimana cara menyembuhkan X', 'terapi terbaik untuk X', 'bagaimana mengatasi X', 'apakah X bisa sembuh'). "
    'Class "campuran": a question that combines an educational part (for example a drug-nutrient interaction or what a test shows) with a personal dose request (for example "... dan berapa dosisnya?"). '
    'Class "2": the user states their own or a relative\'s lab value or result and asks whether it is normal, high, risky or what it means, or asks whether they have a disease, without asking for a dose or treatment. '
    'Class "1": general education about the book: what a test measures or means, reference limits, which tests relate to a suspicion, drug-nutrient interactions, nutrients, '
    "and doses or limits asked as 'recorded/printed in the book' with no personal reference; also questions about products, prices or business. "
    "A dose asked impersonally about what the book records (for example 'berapa kisaran repletasi vitamin C untuk dewasa yang tercatat di buku?') is class 1. "
    "When a question is both personal and asks for a dose or treatment, choose 3 (or campuran if it also asks an educational question)."
)
CATATAN_TETAP = ("Pertanyaan ini menyangkut dosis pribadi, keputusan memulai atau menghentikan obat atau suplemen, atau cara mengobati suatu kondisi. "
                 "Hal tersebut perlu dibahas langsung dengan dokter atau tenaga kesehatan Anda. Saya dapat membantu dengan informasi umum dari buku referensi, "
                 "misalnya arti suatu tes atau batas rujukan yang tercetak.")
CATATAN_SIBUK = ("Layanan sedang sibuk atau tidak tersedia, sehingga pertanyaan ini belum dapat dijawab. Silakan coba lagi beberapa saat lagi. "
                 "Untuk hal yang menyangkut dosis atau keputusan pengobatan, tetap bicarakan dengan dokter atau tenaga kesehatan Anda.")
# --aman: lapisan kedua yang SENGAJA luas, dipakai HANYA saat router gagal (lebih baik menolak berlebihan saat router mati daripada menjawab soal pribadi tanpa pengarah).
# Belum divalidasi sebagai pengarah mandiri; recall-nya terbatas pada kata yang tercantum (salah ketik lain jatuh ke jalur 'campuran': model utama + jaga()).
PENANDA_AMAN = re.compile(r"\b(saya|sy|sya|aku|aq|ku|kami|gw|gue|gua|my|mine|me|i|dosis|dose|dosage|minum|konsumsi|obat|terapi|sembuh|menyembuhkan|mengobati|mengatasi|hentikan|berhenti|stop|mulai|boleh|perlu|harus)\b", re.I)
TRANS = str.maketrans({"\u00b5": "u", "\u03bc": "u", "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2264": "<=", "\u2265": ">=",
                       "\u03b1": "a", "\u03b2": "b", "\u00df": "b"})

def norm(s):
    t = re.sub(r"\s+", " ", str(s).lower().translate(TRANS)) + " "
    return re.sub(r"(?<=\d),(?=\d{1,2}(?!\d))", ".", t)   # koma desimal Indonesia: 0,3 -> 0.3 (ribuan 3 digit "1,000" tetap)

def ada(alt, teks):
    a = norm(alt).strip()
    if re.fullmatch(r"[\d.]+", a):
        return re.search(r"(?<![\d.])" + re.escape(a) + r"(?!\d|\.\d)", teks) is not None
    return a in teks

def asc(s):
    return str(s).encode("ascii", "replace").decode("ascii")
DOSIS_ANGKA = r"\d[\d.,]*\s*(iu|mg|mcg|ug|g|mikrogram|miligram)\b(?!\s*/\s*(dl|ml|l|mmol|(m?g|gm)\s+(creatinine|kreatinin))\b)"
def kalimat(teks):
    return [k for k in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])|\n+", teks) if k.strip()]


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

def stem(t):
    """Stemming ringan (hanya --stem): bentuk jamak bahasa Inggris. Angka dan kata berakhiran -ss/-us/-is tidak diubah."""
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith(("ches", "shes", "sses", "xes", "zes")):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        return t[:-1]
    return t

def tok(s):
    s = s.lower().translate(GREEK)
    x = [t for t in re.split(r"[^a-z0-9.%]+", s) if len(t) >= 2]
    return [stem(w) for w in x] if STEM else x

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

def sistem():
    return SYSTEM + (SYSTEM_LENGKAP if LENGKAP else "") + (SYSTEM_RUBRIK if RUBRIK else "") + (SYSTEM_RUBRIK2 if RUBRIK2 else "") + (SYSTEM_RUBRIK3 if RUBRIK3 else "")

def ask(prompt, models=None, sistem_teks=None):
    last = None
    for m in (models or CHAT_MODELS):
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=m, contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=(sistem_teks or sistem()), temperature=0, response_mime_type="application/json",
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                    ),
                )
                # 2 Okt: gemini-3.8-flash kadang menulis JSON rusak ("canAnswer": trueInfo) -> dulu tercatat
                # sebagai penolakan. Sekarang: ulang sekali di model yang sama, lalu pindah model.
                try:
                    if not isinstance(json.loads(resp.text), dict):
                        raise ValueError
                except Exception:
                    last = ValueError("JSON rusak: " + asc(resp.text[:60]))
                    print(f"  {m}: JSON rusak (percobaan {attempt + 1}/3), ulangi")
                    if attempt >= 1:
                        break
                    continue
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

def arahkan(q):
    """Router tingkat (hanya model utama; gagal = dilewati, bukan jatuh ke model cadangan). Kembali (tingkat, alasan) atau (None, None)."""
    m, raw_ = ask("Question: " + q, models=CHAT_MODELS[:1], sistem_teks=SYSTEM_ARAH)
    if raw_ is None:
        return None, None
    try:
        d = json.loads(raw_)
        t = str(d.get("tingkat", "")).strip().lower()
        return (t if t in ("1", "2", "3", "campuran") else None), str(d.get("alasan", ""))[:80]
    except Exception:
        return None, None

def jaga(ans):
    """Pemeriksa output deterministik (tingkat 2 dan campuran): buang kalimat answer yang memuat angka dosis, kosongkan catatan bila memuat angka dosis."""
    dipangkas = False
    a = str(ans.get("answer") or "")
    if a.strip():
        ks = kalimat(a)
        sisa = [k for k in ks if not re.search(DOSIS_ANGKA, norm(k))]
        if len(sisa) != len(ks):
            dipangkas = True
            a = " ".join(sisa).strip()
            if a and "tenaga kesehatan" not in norm(a):
                a += " Dosis ditentukan bersama tenaga kesehatan."
            ans["answer"] = a
            if not sisa:
                ans["canAnswer"] = False
                ans["note"] = CATATAN_TETAP
    if re.search(DOSIS_ANGKA, norm(ans.get("note") or "")):
        dipangkas = True
        ans["note"] = "Dosis ditentukan bersama tenaga kesehatan."
    return ans, dipangkas

# ---------------- bagian khusus alat tanya ----------------
SYS_TR = ("Translate the user's question into one concise English question, using the exact terminology of a clinical laboratory and nutrition "
          "reference book (analyte names, drug names, drug classes, nutrient names). Output only the English question, nothing else.")
TERJ_FILE = BASE / "terjemah_cache.json"
TERJ_CACHE = json.loads(TERJ_FILE.read_text(encoding="utf-8")) if TERJ_FILE.exists() else {}

def terjemah(q):
    if q in TERJ_CACHE:
        return TERJ_CACHE[q]
    for m in CHAT_MODELS:
        for k in range(3):
            try:
                tr = client.models.generate_content(model=m, contents=q, config=types.GenerateContentConfig(
                    system_instruction=SYS_TR, temperature=0, thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)))
                t = (tr.text or "").strip().replace("\n", " ")
                if t:
                    TERJ_CACHE[q] = t
                    TERJ_FILE.write_text(json.dumps(TERJ_CACHE, ensure_ascii=False, indent=1), encoding="utf-8")
                    return t
            except Exception as e:
                print(f"  terjemahan gagal di {m} ({type(e).__name__}), tunggu {5 * (k + 1)} detik")
                time.sleep(5 * (k + 1))
    return ""   # tanpa terjemahan: pencarian tetap jalan dengan pertanyaan asli

def kueri_dari(q):
    if NETRAL:
        qn = netralkan(q)
        if qn and qn.lower() != q.lower():
            return (qn + " " + terjemah(qn)).strip()
    return (q + " " + terjemah(q)).strip()

NUM_JAWAB = re.compile(r"(?<![\w.,])\d[\d,]*(?:\.\d+)?(?![\w])")   # ketat: "B12", "CoQ10" tidak dihitung; rentang "50-300" dihitung
NUM_SUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")                        # longgar: angka menempel kata/catatan kaki ("chromodulin.604") tetap tertangkap
def angka_set(teks, ketat):
    return {x.replace(",", "").rstrip(".") for x in (NUM_JAWAB if ketat else NUM_SUMBER).findall(norm(teks))}

def angka_tak_terverifikasi(ans, sumber_teks):
    """Angka di jawaban yang tidak ada di teks sumber. Bilangan bulat 0-10 diabaikan (hitungan biasa: '3 tes')."""
    ada_ = angka_set(sumber_teks, False)
    hilang = []
    for x in sorted(angka_set(str(ans.get("answer") or ""), True)):
        if re.fullmatch(r"\d+", x) and int(x) <= 10:
            continue
        if x not in ada_:
            hilang.append(x)
    return hilang

POLA_DOSIS = re.compile(r"\d[\d.,]*\s*(?:mg|mcg|\u00b5g|\u03bcg|g|iu|ml)\b|\d\s*/\s*(?:d|hari)\b", re.I)
LABEL_REPLETION = ("CATATAN: angka di atas berasal dari baris 'Repletion' di buku, yaitu dosis pemulihan "
                   "(sekitar 90 hari) untuk defisiensi yang terbukti lewat tes lab. Bukan dosis harian umum "
                   "dan bukan batas atas aman.")
def perlu_label_repletion(ans, kutip, teks_chunk):
    """Q11-B (13 Okt): label deterministik (bukan dari model). Muncul bila jawaban memuat angka dosis
    DAN salah satu chunk yang dikutip memuat kata 'repletion'."""
    if not (ans.get("canAnswer") and str(ans.get("answer") or "").strip()):
        return False
    if not POLA_DOSIS.search(str(ans.get("answer"))):
        return False
    return any("repletion" in t.lower() for t in teks_chunk)

def tanya(q):
    qk = kueri_dari(q)
    r = client.models.embed_content(model=EMB_MODEL, contents=[qk], config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"))
    qv = np.array(r.embeddings[0].values, dtype=np.float32)
    s = (qv / np.linalg.norm(qv)) @ Mn.T
    emb_order = list(np.argsort(-s))
    b = bm25(qk)
    bm_order = sorted(range(N), key=lambda j: -b[j])
    re_, rb = ranks(emb_order), ranks(bm_order)
    fused = {j: 1 / (RRF_K + re_[j]) + 1 / (RRF_K + rb[j]) for j in range(N)}
    induk = induk_dari_baris(qk)
    order = [j for j in sorted(range(N), key=lambda j: -fused[j]) if j not in PUSTAKA]
    top = order[:TOPK]
    konteks = [j for j in perluas(top) if j not in PUSTAKA]
    for j in induk[:SISIP_BARIS]:
        if j not in konteks:
            konteks.append(j)
    ctx = [f"[excerpt {ids[j]} | PDF pages {meta[ids[j]]['page']}]\n{texts[j]}" for j in konteks]
    prompt = "Question: " + q + "\n\nExcerpts:\n\n" + "\n\n".join(ctx)

    tingkat, alasan, degradasi = arahkan(q) + (None,)
    if tingkat is None:
        if PENANDA_AMAN.search(q):
            tingkat, alasan, degradasi = "3", "router gagal -> penolakan tetap", "router-gagal->tetap"
        else:
            tingkat, alasan, degradasi = "campuran", "router gagal -> jalur campuran", "router-gagal->campuran"
    dipangkas = False
    if tingkat == "3":
        model_used = "arah-tetap"
        raw = json.dumps({"canAnswer": False, "answer": "", "quote": "", "chunkIds": [], "note": CATATAN_TETAP}, ensure_ascii=False)
    elif tingkat in ("2", "campuran"):
        model_used, raw = ask(prompt, models=CHAT_MODELS[:1])
    else:
        model_used, raw = ask(prompt)
    if raw is None:
        model_used = "layanan-sibuk"
        raw = json.dumps({"canAnswer": False, "answer": "", "quote": "", "chunkIds": [], "note": CATATAN_SIBUK}, ensure_ascii=False)
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
    kutip = [c for c in ans["chunkIds"] if c in meta]
    pages = sorted({p for cid in kutip for p in meta[cid]["page"]})
    if tingkat in ("2", "campuran"):
        ans, dipangkas = jaga(ans)

    # pemeriksa angka: sumber = kutipan + teks chunk yang dikutip
    hilang = []
    if ans.get("canAnswer") and str(ans.get("answer") or "").strip():
        sumber = str(ans.get("quote") or "") + "\n" + "\n".join(texts[idx[c]] for c in kutip)
        hilang = angka_tak_terverifikasi(ans, sumber)
    label = bool(not hilang and perlu_label_repletion(ans, kutip, [texts[idx[c]] for c in kutip]))
    return dict(q=q, tingkat=tingkat, alasan=alasan, degradasi=degradasi, model=model_used, ans=ans, kutip=kutip,
                pages=pages, hilang=hilang, dipangkas=dipangkas, label_repletion=label)

GARIS = "-" * 72
def tampil(h):
    ans = h["ans"]
    print("\n" + GARIS)
    print(f"Pertanyaan : {h['q']}")
    print(f"Jalur      : tingkat {h['tingkat']} ({h['alasan']}){' [' + h['degradasi'] + ']' if h['degradasi'] else ''}")
    if h["hilang"]:
        print(f"PERINGATAN : angka {', '.join(h['hilang'])} ada di jawaban tetapi TIDAK ditemukan di sumber yang dikutip.")
        print("             Jawaban ringkas disembunyikan. Baca kutipan di bawah dan periksa sendiri.")
    elif ans.get("canAnswer"):
        print("\nJawaban:\n" + str(ans.get("answer") or "").strip())
        if h.get("label_repletion"):
            print("\n" + LABEL_REPLETION)
    else:
        print("\nTidak dijawab dari buku.")
    if ans.get("note"):
        print("\nCatatan:\n" + str(ans["note"]).strip())
    if ans.get("quote"):
        print("\nKutipan buku:\n" + str(ans["quote"]).strip())
    if h["pages"]:
        print("\nSumber     : hal. PDF " + ", ".join(map(str, h["pages"])) + "  (halaman cetak kira-kira PDF dikurangi 10)")
        print("Chunk      : " + ", ".join(h["kutip"]))
    if TEKS:
        for c in h["kutip"]:
            print(f"\n[teks lengkap {c}]\n{texts[idx[c]]}")
    print(GARIS)

LOG = BASE / "tanya_log.jsonl"
def catat(h):
    rec = dict(waktu=datetime.datetime.now().isoformat(timespec="seconds"), q=h["q"], tingkat=h["tingkat"], degradasi=h["degradasi"],
               model=h["model"], canAnswer=h["ans"].get("canAnswer"), answer=h["ans"].get("answer"), quote=h["ans"].get("quote"),
               note=h["ans"].get("note"), halaman=h["pages"], chunk=h["kutip"], angka_tak_terverifikasi=h["hilang"], dipangkas=h["dipangkas"], label_repletion=h.get("label_repletion", False), v5=V5)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

if "--web" in sys.argv:   # antarmuka web lokal (web_ui.py + web_ui.html); mesin di atas tidak diubah
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import web_ui
    try:
        port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
    except (ValueError, IndexError):
        raise SystemExit("--port harus diikuti angka, contoh: --port 8765")
    web_ui.jalankan(tanya, catat, LABEL_REPLETION, LOG, ROOT / "pertanyaan_15.txt",
                    lambda cid: texts[idx[cid]] if cid in meta else None,
                    port=port, buka="--no-open" not in sys.argv,
                    toc_path=BASE / "daftar_isi.json", pdf_path=ROOT / "source.pdf")
    raise SystemExit(0)

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if "--file" in sys.argv:
    fn = sys.argv[sys.argv.index("--file") + 1]
    args = [a for a in args if a != fn]
    daftar = [l.strip() for l in pathlib.Path(fn).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
elif args:
    daftar = [" ".join(args)]
else:
    daftar = None

if daftar is not None:
    ringkasan = []
    for i, q in enumerate(daftar, 1):
        print(f"[{i}/{len(daftar)}]", end="")
        h = tanya(q); tampil(h); catat(h)
        ringkasan.append((i, h["tingkat"], bool(h["ans"].get("canAnswer")), len(h["hilang"]), q))
    if len(daftar) > 1:
        print("\nRINGKASAN  no | tingkat | dijawab | angka tak terverifikasi | pertanyaan")
        for i, t, d, n, q in ringkasan:
            print(f"  {i:>2} | {t:>8} | {'ya' if d else 'tidak':>7} | {n:>3} | {q[:60]}")
        print("Detail tersimpan di " + str(LOG))
else:
    print("Alat tanya buku Lord & Bralley. Ketik pertanyaan (Indonesia atau Inggris). Kosong = keluar.")
    while True:
        try:
            q = input("\nPertanyaan> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        h = tanya(q); tampil(h); catat(h)
