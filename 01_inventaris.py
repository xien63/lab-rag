from pypdf import PdfReader

PDF = r"C:\Users\sandy\dev\lab-rag\source.pdf"
r = PdfReader(PDF)
print("Total halaman PDF:", len(r.pages))

for n in (20, 200, 400):
    t = r.pages[n].extract_text() or ""
    print(f"\n===== halaman PDF {n+1} - {len(t)} karakter =====")
    print(t[:400])
