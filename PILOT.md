# Pilot 0A — Uji Kesetiaan Ekstraksi

## Lingkungan
- Python 3.13.15, interpreter: C:\Users\sandy\AppData\Local\Programs\Python\Python313\python.exe
- Paket: pypdf 6.19.0, pdfplumber 0.11.10, pypdfium2 5.13.0, fonttools 4.66.0

## Bab pilot
- Bab 6 - Organic Acids, sub-bagian "Intestinal Dysbiosis Markers" s.d. akhir "Case Illustrations"
- Halaman PDF 380-406 (27 halaman)
- Offset halaman cetak vs PDF: cetak 391 = PDF 401, offset +10
- Alasan pemilihan: kombinasi tabel rujukan formal (Table 6.11-6.17) DAN
  Case Illustrations berisi tabel hasil lab pasien sungguhan vs rentang
  rujukan - ujian paling realistis untuk kebutuhan Fitsol

## Gerbang A1 (halaman 21, 201, 401 dari 672 total)
LULUS - lapisan teks ada, 2227-4807 karakter per sampel, bukan hasil pindaian

## Ekstraksi (A3)
- Dua jalur: pypdf (91291 byte) dan pdfplumber (89430 byte)
- pdfplumber MENANG - satu-satunya yang menghasilkan tabel.json terstruktur
  (64 tabel terdeteksi via extract_tables()); pypdf hanya teks mengalir
- fonttools terpasang setelah warning "not installed" muncul di halaman
  berfont custom (21, 201) - mencegah potensi salah peta karakter

## Integritas karakter (A3)
- en-dash: 4, em-dash: 35, hyphen: 629, minus sign: 1 (semua ter-nama
  benar via unicodedata.name(), nol karakter TIDAK DIKENAL)
- Karakter Yunani (alpha/beta/gamma/delta), micro sign, semua utuh dan
  bermakna sesuai konteks (nama senyawa kimia)
- Tidak ada pengulangan kerusakan dash seperti ekstraksi book-to-skill
  lama (3-7 jadi 3-7 rusak) - pipeline pdfplumber+pypdf jalur ini bersih

## Verifikasi visual (A4) - 3 halaman: 382, 399, 401

### Halaman 401 - Case 6.1 & 6.2 (PRIORITAS UTAMA)
Tabel Compound/Patient/Reference Limit, 10 baris, KECOCOKAN SEMPURNA
termasuk tanda strip kosong (beta-Hydroxybutyrate: 108/-) dan tanda
kurang-dari (Aconitate: 174/<2, alpha-Ketoglutarate: 417/<2).
Tabel Adipate/Suberate/Ethylmalonate 3 baris juga cocok utuh.

### Halaman 382 - Table 6.11
Tabel substrat-kronologis (BUKAN data pasien-vs-rentang). Banyak huruf
tunggal nyasar di antara baris (s, i, t, o, a, n, e, g) - kemungkinan
bocoran superskrip nomor referensi jurnal. Perlu chunking hati-hati per
baris nanti, tapi bukan tabel prioritas tinggi untuk akurasi klinis.

### Halaman 399 - Table 6.16
9 baris bakteri x 5 kolom antibiotik, KECOCOKAN SEMPURNA. Pola noise
terkarakterisasi: satu huruf nyasar SELALU menempel di DEPAN angka,
angkanya sendiri TIDAK PERNAH rusak (i46, t87, n0, a10.5). Sumber
diduga: elemen grafik/superskrip footnote yang overlap dengan sel tabel.
Bisa dibersihkan dengan regex sebelum chunking: strip huruf tunggal
yang menempel langsung di depan digit.

## VONIS: LULUS
Kriteria A5 terpenuhi - nol rentang salah pasangan di seluruh sampel
yang diperiksa. Noise huruf nyasar terkarakterisasi dan bisa dibersihkan
regex, TIDAK merusak pasangan analit-rentang.

## Angka untuk perencanaan 0B
- 89430 byte / 27 halaman = ~3312 karakter/halaman
- Estimasi 672 halaman penuh: ~2.225.000 karakter
- Pada chunk 1000 + overlap 200 (step efektif ~800): ~2780 chunk
- KONSEKUENSI: melebihi kuota Gemini embedding free tier (RPD 1.000)
  hampir 3x lipat dalam satu kali indexing penuh - perlu embeddings
  lokal (Ollama) atau indexing bertahap multi-hari
