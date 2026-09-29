import json, re, pathlib

BASE = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\pilot")
MANIFEST = BASE / "chunks_manifest.json"
CHUNKS = BASE / "chunks"

DROP_EXPLICIT = {"tabel-036"}

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

def is_empty_tabel(cid):
    text = (CHUNKS / f"{cid}.txt").read_text(encoding="utf-8")
    body = text.split("\n", 1)[1] if "\n" in text else ""
    stripped = re.sub(r"[\s|]", "", body)
    return len(stripped) == 0

kept = []
dropped = []
for entry in manifest:
    cid = entry["id"]
    if entry["type"] != "tabel":
        kept.append(entry)
        continue
    if cid in DROP_EXPLICIT:
        dropped.append((cid, "rusak - analit terpisah dari rentang"))
        continue
    if is_empty_tabel(cid):
        dropped.append((cid, "kosong - artefak bingkai/chart"))
        continue
    kept.append(entry)

for cid, alasan in dropped:
    (CHUNKS / f"{cid}.txt").unlink(missing_ok=True)

MANIFEST.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")

print("dibuang:", len(dropped))
for cid, alasan in dropped:
    print(" -", cid, ":", alasan)
print("total chunk tabel tersisa :", sum(1 for c in kept if c["type"] == "tabel"))
print("total chunk prosa tersisa :", sum(1 for c in kept if c["type"] == "prosa"))
print("total chunk akhir          :", len(kept))
