"""Diagnosa kenapa Q3 (dengan neighbor expansion) selalu 503 sementara Q1,Q2,Q4-Q6 berhasil.
Mengirim konteks Q3 yang sama dalam 4 variasi; tiap variasi mengubah SATU hal. 1 panggilan per variasi, tanpa retry.
"""
import json, os, time, pathlib, re
from google import genai
from google.genai import types

BASE = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\full")
MODEL = "gemini-3-flash-preview"
Q = "In what percentage of patients were elevated D-arabinitol/creatinine ratios reported, and in which patient groups?"
# Urutan konteks persis seperti 18_hibrida_tetangga.py untuk Q3 (top-5: 2469, 2467, 2879, 2463, 2470 + tetangga)
KONTEKS = ["prosa-2468", "prosa-2469", "prosa-2470", "prosa-2466", "prosa-2467", "prosa-2878", "prosa-2879",
           "prosa-2880", "prosa-2462", "prosa-2463", "prosa-2464", "prosa-2471"]
EMAS = ["prosa-2467", "prosa-2468"]

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

chunks = {}
for l in (BASE / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
    if l.strip():
        c = json.loads(l); chunks[c["id"]] = c

def prompt(ids):
    return "Question: " + Q + "\n\nExcerpts:\n\n" + "\n\n".join(
        f"[excerpt {i} | PDF pages {chunks[i]['page']}]\n{chunks[i]['text']}" for i in ids)

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(timeout=90000))

def cfg(json_mode=True, thinking=None):
    k = dict(system_instruction=SYSTEM, temperature=0,
             automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
    if json_mode:
        k["response_mime_type"] = "application/json"
    if thinking:
        k["thinking_config"] = types.ThinkingConfig(thinking_level=thinking)
    return types.GenerateContentConfig(**k)

VARIASI = [
    ("A  sama persis dengan skrip 18", KONTEKS, cfg()),
    ("B  thinking_level LOW",          KONTEKS, cfg(thinking=types.ThinkingLevel.LOW)),
    ("C  tanpa format JSON",           KONTEKS, cfg(json_mode=False)),
    ("D  hanya 2 chunk emas",          EMAS,    cfg()),
]

for nama, ids, c in VARIASI:
    t0 = time.time()
    try:
        r = client.models.generate_content(model=MODEL, contents=prompt(ids), config=c)
        teks = (r.text or "").replace("\n", " ")
        print(f"{nama}: BERHASIL ({time.time() - t0:.0f} dtk) -> {teks[:220].encode('ascii', 'replace').decode()}")
    except Exception as e:
        print(f"{nama}: GAGAL ({time.time() - t0:.0f} dtk) -> {type(e).__name__} {str(e)[:120].encode('ascii', 'replace').decode()}")
    time.sleep(3)
