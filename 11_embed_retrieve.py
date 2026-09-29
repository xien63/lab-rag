import json, os, time, pathlib
import numpy as np
from google import genai
from google.genai import types

BASE = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\pilot")
CHUNKS = BASE / "chunks"
MANIFEST = BASE / "chunks_manifest.json"
EMB = BASE / "emb_chunks.npy"
EMB_IDS = BASE / "emb_chunks_ids.json"
OUT = BASE / "retrieval.txt"
MODEL = "gemini-embedding-001"
BATCH = 40
TOPK = 5

QUESTIONS = [
    ("Q1", "Which pharmaceutical is listed as an anti-fungal intervention for intestinal overgrowth?"),
    ("Q2", "What is the reference limit for urinary hippurate?"),
    ("Q3", "In what percentage of patients were elevated D-arabinitol/creatinine ratios reported, and in which patient groups?"),
    ("Q4", "What is the reference limit for urinary methylmalonate?"),
    ("Q5", "What is the reference limit for \u03b1-ketoisocaproate?"),
]

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def embed(texts, task):
    for attempt in range(5):
        try:
            r = client.models.embed_content(
                model=MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task),
            )
            return [e.values for e in r.embeddings]
        except Exception as e:
            wait = 30 * (attempt + 1)
            print(f"  gagal ({type(e).__name__}), coba lagi dalam {wait} detik")
            time.sleep(wait)
    raise SystemExit("embedding gagal 5x berturut-turut - berhenti")

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
ids = [c["id"] for c in manifest]
meta = {c["id"]: c for c in manifest}
texts = [(CHUNKS / f"{i}.txt").read_text(encoding="utf-8") for i in ids]

if EMB.exists() and EMB_IDS.exists() and json.loads(EMB_IDS.read_text(encoding="utf-8")) == ids:
    M = np.load(EMB)
    print("pakai cache embedding:", M.shape)
else:
    vecs = []
    for s in range(0, len(texts), BATCH):
        part = texts[s:s + BATCH]
        print(f"embed chunk {s + 1}-{s + len(part)} dari {len(texts)}")
        vecs.extend(embed(part, "RETRIEVAL_DOCUMENT"))
        if s + BATCH < len(texts):
            time.sleep(62)
    M = np.array(vecs, dtype=np.float32)
    np.save(EMB, M)
    EMB_IDS.write_text(json.dumps(ids), encoding="utf-8")
    print("embedding tersimpan:", M.shape)

Q = np.array(embed([q for _, q in QUESTIONS], "RETRIEVAL_QUERY"), dtype=np.float32)

Mn = M / np.linalg.norm(M, axis=1, keepdims=True)
Qn = Q / np.linalg.norm(Q, axis=1, keepdims=True)
S = Qn @ Mn.T

lines = []
for qi, (qid, q) in enumerate(QUESTIONS):
    order = np.argsort(-S[qi])[:TOPK]
    lines.append(f"\n########## {qid}: {q}")
    summary = []
    for rank, j in enumerate(order, 1):
        cid = ids[j]
        lines.append(f"\n--- #{rank}  {cid}  hal {meta[cid]['page']}  skor {S[qi, j]:.4f}")
        lines.append(texts[j][:600])
        summary.append(f"{cid}({S[qi, j]:.3f})")
    print(qid, " | ".join(summary))

OUT.write_text("\n".join(lines), encoding="utf-8")
print("detail tersimpan di pilot\\retrieval.txt")
