"""Embedding seluruh chunk buku (full/chunks.jsonl) dengan gemini-embedding-001. Bisa dilanjutkan (resumable).

Pemakaian:
  python 16_embed_penuh.py --batas 100   # uji: berhenti setelah 100 chunk -> cek biaya nyata di AI Studio (Spend)
  python 16_embed_penuh.py               # lanjutkan sampai semua chunk selesai (yang sudah ada tidak diulang)
"""
import json, os, sys, time, pathlib
import numpy as np
from google import genai
from google.genai import types, errors

BASE = pathlib.Path(r"C:\Users\sandy\dev\lab-rag")
D = BASE / "full"
EMB, IDS = D / "emb_full.npy", D / "emb_full_ids.json"
MODEL, BATCH, MAKS_KARAKTER = "gemini-embedding-001", 50, 5000

batas = None
if "--batas" in sys.argv:
    batas = int(sys.argv[sys.argv.index("--batas") + 1])

chunks = [json.loads(l) for l in (D / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
selesai_ids = json.loads(IDS.read_text(encoding="utf-8")) if IDS.exists() else []
vek = list(np.load(EMB)) if EMB.exists() else []
assert len(vek) == len(selesai_ids), "cache embedding tidak konsisten - hapus emb_full.* lalu ulangi"
sudah = set(selesai_ids)
antre = [c for c in chunks if c["id"] not in sudah]
if batas is not None:
    antre = antre[:max(0, batas - len(selesai_ids))]
dipotong = [c["id"] for c in antre if len(c["text"]) > MAKS_KARAKTER]
print(f"total chunk: {len(chunks)} | sudah: {len(selesai_ids)} | akan diproses sekarang: {len(antre)}")
if dipotong:
    print(f"catatan: {len(dipotong)} chunk > {MAKS_KARAKTER} karakter, embedding memakai {MAKS_KARAKTER} karakter pertama: {dipotong}")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def embed(teks):
    tunggu = 10
    for _ in range(6):
        try:
            r = client.models.embed_content(model=MODEL, contents=teks,
                                            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"))
            return [e.values for e in r.embeddings]
        except errors.ServerError as e:
            print(f"  server sibuk, tunggu {tunggu} dtk"); time.sleep(tunggu); tunggu *= 2
        except errors.ClientError as e:
            if getattr(e, "code", None) == 429:
                print(f"  batas kecepatan (429), tunggu {tunggu} dtk"); time.sleep(tunggu); tunggu *= 2
            else:
                raise SystemExit(f"berhenti: error {getattr(e, 'code', '?')} - periksa API key/model")
    raise SystemExit("berhenti: gagal 6x berturut-turut - jalankan ulang nanti, progres tersimpan")

t0 = time.time()
for s in range(0, len(antre), BATCH):
    part = antre[s:s + BATCH]
    vek.extend(embed([c["text"][:MAKS_KARAKTER] for c in part]))
    selesai_ids.extend(c["id"] for c in part)
    np.save(EMB, np.array(vek, dtype=np.float32))
    IDS.write_text(json.dumps(selesai_ids), encoding="utf-8")
    print(f"  {len(selesai_ids)}/{len(chunks)} tersimpan ({time.time() - t0:.0f} dtk)")
print("SELESAI SEMUA" if len(selesai_ids) == len(chunks) else f"berhenti di {len(selesai_ids)} - jalankan tanpa --batas untuk melanjutkan")
