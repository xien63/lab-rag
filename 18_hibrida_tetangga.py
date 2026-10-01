import json, os, sys, pathlib, re, math, collections
import numpy as np
from google import genai
from google.genai import types, errors
import time

BASE = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\full")
EMB = BASE / "emb_full.npy"
EMB_IDS = BASE / "emb_full_ids.json"
OUT = BASE / "jawaban_tetangga.txt"
EMB_MODEL = "gemini-embedding-001"
CHAT_MODELS = ["gemini-3.8-flash", "gemini-3-flash-preview"]  # 1 Okt: model stabil jadi utama; preview sering 503
TOPK = 5
K1, B = 1.5, 0.75
RRF_K = 60

QUESTIONS = [
    ("Q1", "Which pharmaceutical is listed as an anti-fungal intervention for intestinal overgrowth?", ["nystatin"]),
    ("Q2", "What is the reference limit for urinary hippurate?", ["hippurate", "786"]),
    ("Q3", "In what percentage of patients were elevated D-arabinitol/creatinine ratios reported, and in which patient groups?", ["9% of patients"]),
    ("Q4", "What is the reference range for hemoglobin A1c (HbA1c)?", None),
    ("Q5", "What is the reference limit for \u03b1-ketoisocaproate?", ["ketoisocaproate", "0.58"]),
    ("Q6", "What is the reference limit for urinary methylmalonate?", ["methylmalonate", "3.4"]),
]

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

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(timeout=60000))  # batas 60 detik per permintaan

def asc(s):
    return str(s).encode("ascii", "replace").decode("ascii")

chunks = [json.loads(l) for l in (BASE / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
emb_ids = json.loads(EMB_IDS.read_text(encoding="utf-8"))
if len(emb_ids) != len(chunks):
    raise SystemExit(f"embedding belum lengkap: {len(emb_ids)}/{len(chunks)} - jalankan 16_embed_penuh.py dulu")
pos = {cid: k for k, cid in enumerate(emb_ids)}
chunks.sort(key=lambda c: pos[c["id"]])
ids = [c["id"] for c in chunks]
meta = {c["id"]: c for c in chunks}
texts = [c["text"] for c in chunks]
M = np.load(EMB)
Mn = M / np.linalg.norm(M, axis=1, keepdims=True)

r = client.models.embed_content(
    model=EMB_MODEL,
    contents=[q for _, q, _ in QUESTIONS],
    config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
)
Q = np.array([e.values for e in r.embeddings], dtype=np.float32)
Qn = Q / np.linalg.norm(Q, axis=1, keepdims=True)
S = Qn @ Mn.T

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
    """Neighbor expansion: chunk prosa yang terambil dibawa bersama chunk sebelum & sesudahnya (urutan baca buku)."""
    hasil = []
    for j in top:
        cid = ids[j]
        grup = [cid]
        if cid.startswith("prosa-"):
            a = tetangga[cid]
            grup = ([a[0]] if a and a[0] < cid else []) + [cid] + [x for x in a if x > cid]
        for g in grup:
            if g not in hasil:
                hasil.append(g)
    return [idx[g] for g in hasil]

def ranks(order):
    return {j: r for r, j in enumerate(order, 1)}

def ask(prompt):
    last = None
    for m in CHAT_MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM,
                        temperature=0,
                        response_mime_type="application/json",
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                        # Diagnosa 19 (1 Okt): JSON + thinking default -> 503 cepat (5-6 dtk) khusus Q3;
                        # JSON + thinking LOW -> berhasil. Dipakai untuk SEMUA pertanyaan supaya hasil sebanding.
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

HASIL = BASE / "jawaban_tetangga.json"
hasil = json.loads(HASIL.read_text(encoding="utf-8")) if HASIL.exists() else {}
hanya = None
if "--hanya" in sys.argv:
    hanya = set(sys.argv[sys.argv.index("--hanya") + 1].upper().split(","))
dilewati = []
for qi, (qid, q, markers) in enumerate(QUESTIONS):
    if hanya and qid not in hanya:
        continue
    emb_order = list(np.argsort(-S[qi]))
    b = bm25(q)
    bm_order = sorted(range(N), key=lambda j: -b[j])
    re_, rb = ranks(emb_order), ranks(bm_order)
    fused = {j: 1 / (RRF_K + re_[j]) + 1 / (RRF_K + rb[j]) for j in range(N)}
    order = sorted(range(N), key=lambda j: -fused[j])
    rord = ranks(order)
    gold_idx = [j for j in range(N) if markers and all(mk in texts[j].lower() for mk in markers)]
    if gold_idx:
        g = min(gold_idx, key=lambda j: rord[j])
        gold_rank = rord[g]
        gold_info = f"{ids[g]} emb#{re_[g]} bm25#{rb[g]} gabungan#{gold_rank}"
    else:
        gold_rank = None
        gold_info = "tidak ada (jawaban benar: menolak)" if markers is None else "TIDAK DITEMUKAN"
    top = order[:TOPK]
    konteks = perluas(top)
    emas_di_konteks = any(markers and all(mk in texts[j].lower() for mk in markers) for j in konteks)
    ctx = []
    for j in konteks:
        cid = ids[j]
        ctx.append(f"[excerpt {cid} | PDF pages {meta[cid]['page']}]\n{texts[j]}")
    prompt = "Question: " + q + "\n\nExcerpts:\n\n" + "\n\n".join(ctx)
    model_used, raw = ask(prompt)
    if raw is None:
        dilewati.append(qid)
        print(f"{qid}  DILEWATI - server sibuk, hasil lama (kalau ada) tidak diubah")
        continue
    try:
        ans = json.loads(raw)
    except Exception:
        ans = {"canAnswer": None, "answer": raw, "quote": "", "chunkIds": [], "note": "JSON tidak valid"}
    # Model kadang menyalin label kutipan ("excerpt prosa-2467") - normalisasi supaya halaman tetap terbaca.
    ans["chunkIds"] = [re.sub(r"^\s*\[?\s*excerpt\s+", "", str(c), flags=re.I).strip(" ]") for c in (ans.get("chunkIds") or [])]
    asing = [c for c in ans["chunkIds"] if c not in meta]
    if asing:
        ans["note"] = (ans.get("note") or "") + f" [PERINGATAN: chunkIds tidak dikenal {asing}]"
    pages = sorted({p for cid in ans["chunkIds"] if cid in meta for p in meta[cid]["page"]})
    print(f"{qid}  chunk-emas: {gold_info} | di konteks: {'YA' if emas_di_konteks else 'tidak'} ({len(konteks)} chunk)  | canAnswer={ans.get('canAnswer')}  | hal {pages}")
    blok = [f"\n########## {qid}: {q}", f"model: {model_used}", f"chunk-emas (penanda {markers}): {gold_info}",
            "top-5 gabungan: " + ", ".join(f"{ids[j]}(emb#{re_[j]} bm25#{rb[j]})" for j in top),
            "konteks setelah perluasan (" + str(len(konteks)) + "): " + ", ".join(ids[j] for j in konteks),
            "halaman PDF dari chunkIds jawaban: " + str(pages), json.dumps(ans, ensure_ascii=False, indent=2)]
    hasil[qid] = "\n".join(blok)
    HASIL.write_text(json.dumps(hasil, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT.write_text("\n".join(hasil[k] for k in sorted(hasil)), encoding="utf-8")

if dilewati:
    print("DILEWATI:", ",".join(dilewati), "-> nanti jalankan: python 18_hibrida_tetangga.py --hanya " + ",".join(dilewati))
print("detail tersimpan di full\\jawaban_tetangga.txt")
