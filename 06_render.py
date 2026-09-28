import pathlib
import pypdfium2 as pdfium

PDF = r"C:\Users\sandy\dev\lab-rag\source.pdf"
OUT = pathlib.Path(r"C:\Users\sandy\dev\lab-rag\pilot")
HALAMAN = [382, 399, 401]

doc = pdfium.PdfDocument(PDF)
for n in HALAMAN:
    doc[n - 1].render(scale=2).to_pil().save(OUT / f"hal-{n}.png")
    print("render:", OUT / f"hal-{n}.png")
