import json, os, pathlib
import numpy as np
from google import genai
from google.genai import types, errors
import time

BASE = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\pilot")
CHUNKS = BASE / "chunks"
MANIFEST = BASE / "chunks_manifest.json"
EMB = BASE / "emb_chunks.npy"
OUT = BASE / "jawaban.txt"
EMB_MODEL = "gemini-embedding-001"
CHAT_MODELS = ["gemini-3-flash-preview", "gemini-3.8-flash"]
TOPK = 5

QUESTIONS = [
    ("Q1", "Which pharmaceutical is listed as an anti-fungal intervention for intestinal overgrowth?", ["nystatin"]),
    ("Q2", "What is the reference limit for urinary hippurate?", ["hippurate", "786"]),
    ("Q3", "In what percentage of patients were elevated D-arabinitol/creatinine ratios reported, and in which patient groups?", ["9% of patients"]),
    ("Q4", "What is the reference limit for urinary methylmalonate?", ["methylmalon"]),
    ("Q5", "What is the reference limit for \u03b1-ketoisocaproate?", ["ketoisocaproate", "0.58"]),
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

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def asc(s):
    return str(s).encode("ascii", "replace").decode("ascii")

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
ids = [c["id"] for c in manifest]
meta = {c["id"]: c for c in manifest}
texts = [(CHUNKS / f"{i}.txt").read_text(encoding="utf-8") for i in ids]
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
    raise SystemExit(f"semua model gagal: {asc(last)}")

log = []
for qi, (qid, q, markers) in enumerate(QUESTIONS):
    order = list(np.argsort(-S[qi]))
    gold = [k for k, j in enumerate(order, 1) if all(mk in texts[j].lower() for mk in markers)]
    gold_rank = gold[0] if gold else None
    top = order[:TOPK]
    ctx = []
    for j in top:
        cid = ids[j]
        ctx.append(f"[excerpt {cid} | PDF pages {meta[cid]['page']}]\n{texts[j]}")
    prompt = "Question: " + q + "\n\nExcerpts:\n\n" + "\n\n".join(ctx)
    model_used, raw = ask(prompt)
    try:
        ans = json.loads(raw)
    except Exception:
        ans = {"canAnswer": None, "answer": raw, "quote": "", "chunkIds": [], "note": "JSON tidak valid"}
    pages = sorted({p for cid in ans.get("chunkIds", []) if cid in meta for p in meta[cid]["page"]})
    print(f"{qid}  chunk-emas peringkat: {gold_rank if gold_rank else 'TIDAK ADA'}  | canAnswer={ans.get('canAnswer')}  | hal {pages}")
    log.append(f"\n########## {qid}: {q}")
    log.append(f"model: {model_used}")
    log.append(f"peringkat chunk-emas (penanda {markers}): {gold_rank}")
    log.append("top-5: " + ", ".join(f"{ids[j]}({S[qi, j]:.3f})" for j in top))
    log.append("halaman PDF dari chunkIds jawaban: " + str(pages))
    log.append(json.dumps(ans, ensure_ascii=False, indent=2))
    OUT.write_text("\n".join(log), encoding="utf-8")

print("detail tersimpan di pilot\\jawaban.txt")
