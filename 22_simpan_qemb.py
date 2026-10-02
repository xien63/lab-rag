"""Simpan embedding 30 pertanyaan set uji (1 panggilan API) supaya varian retrieval bisa disimulasikan offline.

Output: full/qemb_uji.npy (30 x 3072) + full/qemb_uji_ids.json. Tidak memanggil model jawaban.
"""
import json, os, pathlib
import numpy as np
from google import genai
from google.genai import types

ROOT = pathlib.Path(r"C:\Users\sandy\dev\lab-rag")
SET = json.loads((ROOT / "set_uji.json").read_text(encoding="utf-8"))
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(timeout=60000))
r = client.models.embed_content(model="gemini-embedding-001", contents=[u["q"] for u in SET],
                                config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"))
Q = np.array([e.values for e in r.embeddings], dtype=np.float32)
np.save(ROOT / "full" / "qemb_uji.npy", Q)
(ROOT / "full" / "qemb_uji_ids.json").write_text(json.dumps([u["id"] for u in SET]), encoding="utf-8")
print("tersimpan:", Q.shape, "-> full\\qemb_uji.npy")
