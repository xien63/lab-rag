import json, re, pathlib

BASE = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\pilot")
PLUMBER = BASE / "plumber.txt"
TABEL   = BASE / "tabel.json"
OUTDIR  = BASE / "chunks"
OUTDIR.mkdir(exist_ok=True)

TARGET = 900
OVERLAP = 200

chunks = []

tabel_data = json.loads(TABEL.read_text(encoding="utf-8"))
for i, entry in enumerate(tabel_data):
    hal = entry["hal"]
    lines = [f"[TABEL - halaman {hal}]"]
    for row in entry["baris"]:
        cells = [c.strip() if c else "" for c in row]
        lines.append(" | ".join(cells))
    chunks.append({"id": f"tabel-{i+1:03d}", "page": [hal], "type": "tabel", "text": "\n".join(lines)})

raw = PLUMBER.read_text(encoding="utf-8")
pages = re.split(r"===== HAL (\d+) =====", raw)
page_texts = {}
for j in range(1, len(pages), 2):
    page_texts[int(pages[j])] = pages[j + 1].strip()

prosa_counter = 0
buf_lp = []

def buf_text():
    return "\n".join(ln for ln, _ in buf_lp)

def emit():
    global prosa_counter
    prosa_counter += 1
    pg = sorted({p for _, p in buf_lp})
    chunks.append({"id": f"prosa-{prosa_counter:03d}", "page": pg, "type": "prosa", "text": buf_text()})

def tail_lp():
    t = buf_text()
    ekor = t[-OVERLAP:] if len(t) > OVERLAP else t
    ek_lines = ekor.split("\n")
    src = buf_lp[-len(ek_lines):]
    return [(ek_lines[i], src[i][1]) for i in range(len(ek_lines)) if ek_lines[i].strip()]

for hal, isi in sorted(page_texts.items()):
    if not isi:
        continue
    for ln in [x.strip() for x in isi.split("\n") if x.strip()]:
        cur = len(buf_text())
        if not buf_lp or cur + len(ln) + 1 <= TARGET:
            buf_lp.append((ln, hal))
        else:
            emit()
            buf_lp = tail_lp() + [(ln, hal)]
if buf_lp:
    emit()

manifest = []
for c in chunks:
    (OUTDIR / f"{c['id']}.txt").write_text(c["text"], encoding="utf-8")
    manifest.append({"id": c["id"], "page": c["page"], "type": c["type"], "chars": len(c["text"])})

(BASE / "chunks_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

print("total chunk tabel :", sum(1 for c in chunks if c["type"] == "tabel"))
print("total chunk prosa :", sum(1 for c in chunks if c["type"] == "prosa"))
print("total chunk       :", len(chunks))
