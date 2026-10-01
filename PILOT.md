# Pilot Langkah 0 - Lord & Bralley (Laboratory Evaluations for Integrative and Functional Medicine)

Status: 0A LULUS (28 Sep 2026) - 0B LULUS (29 Sep 2026, retrieval hibrida)

---

# Pilot 0A - Uji Kesetiaan Ekstraksi

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
bocoran superskrip nomor referensi jurnal. [DIKOREKSI di 0B: sumbernya
watermark, lihat bagian Koreksi.] Perlu chunking hati-hati per
baris nanti, tapi bukan tabel prioritas tinggi untuk akurasi klinis.

### Halaman 399 - Table 6.16
9 baris bakteri x 5 kolom antibiotik, KECOCOKAN SEMPURNA. Pola noise
terkarakterisasi: satu huruf nyasar SELALU menempel di DEPAN angka,
angkanya sendiri TIDAK PERNAH rusak (i46, t87, n0, a10.5). Sumber
diduga: elemen grafik/superskrip footnote yang overlap dengan sel tabel.
Bisa dibersihkan dengan regex sebelum chunking: strip huruf tunggal
yang menempel langsung di depan digit. [DIKOREKSI di 0B: regex ini
TIDAK aman, lihat bagian Koreksi.]

## VONIS: LULUS
Kriteria A5 terpenuhi - nol rentang salah pasangan di seluruh sampel
yang diperiksa. Noise huruf nyasar terkarakterisasi dan bisa dibersihkan
regex, TIDAK merusak pasangan analit-rentang.

## Angka untuk perencanaan 0B [DIGANTI - lihat angka revisi di akhir 0B]
- 89430 byte / 27 halaman = ~3312 karakter/halaman
- Estimasi 672 halaman penuh: ~2.225.000 karakter
- Pada chunk 1000 + overlap 200 (step efektif ~800): ~2780 chunk
- KONSEKUENSI: melebihi kuota Gemini embedding free tier (RPD 1.000)
  hampir 3x lipat dalam satu kali indexing penuh - perlu embeddings
  lokal (Ollama) atau indexing bertahap multi-hari

---

# Pilot 0B - Uji Chunking & Retrieval (29 Sep 2026)

## Koreksi atas catatan 0A
- Huruf nyasar BUKAN superskrip footnote. Sumbernya watermark vertikal
  "Genova Diagnostics" di margin halaman, terbaca satu huruf per baris
  dalam urutan terbalik: s c i t s o n g a i D a v o n e G. Polanya tetap,
  jadi bisa dibersihkan secara deterministik kalau diperlukan.
- Regex "strip huruf tunggal di depan digit" TIDAK aman: (1) label
  skenario A/B/C/D di Case 6.9 juga huruf tunggal yang bermakna;
  (2) watermark juga menempel ke kata, bukan hanya angka
  (iLactobacillus, oTricarballylate). Untuk pilot, noise dibiarkan dan
  model diberi tahu bahwa huruf tunggal itu watermark.
- Sampel visual 0A (3 halaman) tidak mencakup halaman 405, padahal
  satu-satunya tabel yang rusak di pilot justru ada di sana (lihat B1).
  Pelajaran: sampel 3 halaman tidak cukup untuk menyatakan semua tabel
  aman; review per-chunk menemukan yang dilewatkan sampel.
- Angka kuota di "Angka untuk perencanaan 0B" tidak berlaku lagi: pilot
  berjalan di project berbayar (Tier 1 prepay), bukan free tier.
  Estimasi jumlah chunk juga direvisi (lihat akhir dokumen).

## B1 - Chunking (07_chunk.py, 09_filter_tabel.py)

Strategi: table-aware.
- Tabel: 1 tabel dari extract_tables() = 1 chunk. Sel dalam satu baris
  digabung dengan " | ", sehingga nama analit, nilai pasien, dan rentang
  tetap satu baris. Pemisahan analit-rentang tidak bisa terjadi akibat
  pemotongan, karena tabel tidak pernah dipotong.
- Prosa: dipotong per BARIS, target 900 karakter, overlap 200. Overlap
  dibawa melintasi batas halaman supaya kalimat yang terpotong
  pergantian halaman muncul utuh di satu chunk.
- Nomor halaman dilacak per baris. Chunk yang membawa ekor overlap dari
  halaman sebelumnya mencatat kedua halaman.

Hasil: 64 tabel + 132 prosa = 196 chunk. Setelah filter: 153 chunk
(21 tabel + 132 prosa). 31 chunk prosa melintasi 2 halaman, 0 yang 3.

Filter:
- 42 tabel dibuang karena isinya murni spasi/garis pembatas: bingkai
  chart yang salah terdeteksi sebagai tabel, terutama di halaman 402-406.
  Tidak ada data yang hilang karena filter hanya membuang tabel tanpa
  satu karakter pun selain spasi dan "|".
- 1 tabel dibuang eksplisit: tabel-036 (halaman 405, Case 6.9).
  pdfplumber mengembalikan DUA kandidat tabel untuk halaman yang sama.
  tabel-036 memisahkan blok nama+nilai dari blok rentang: "<= 8.2 ...
  <= 3.6" muncul 8 baris kemudian tanpa nama analit, sehingga pasangannya
  murni posisional. Ini satu-satunya pelanggaran kriteria "analit
  terpisah dari rentang" di 64 tabel. Isinya tetap tercakup oleh
  tabel-035 dan prosa-126/127, yang memasangkan dengan benar.
- Pasangan kandidat duplikat lain (hal 400: tabel-012/013; hal 403:
  tabel-022/023; hal 401: tabel-014/016/017) diperiksa manual. Satu
  kandidat lebih berisik (kebocoran angka sumbu chart), tapi pasangan
  analit-nilai-rentang tetap satu baris. Semua disimpan; redundansi
  tidak berbahaya.

Kegagalan yang ditabrak di B1:
- Versi pertama memotong prosa per "\n\n". Ekstraksi pdfplumber buku ini
  tidak menyisipkan baris kosong antar paragraf, jadi hasilnya 27 chunk
  prosa (1 per halaman), dan target serta overlap tidak pernah bekerja.
- Label halaman ekor overlap salah: hanya halaman terakhir yang dicatat,
  sehingga prosa-093 tercatat [398] padahal memuat teks halaman 397.
  Perbaikan pertama (max halaman) juga keliru karena ekor 200 karakter
  bisa melintasi dua halaman. Perbaikan final: halaman dilacak per baris.
- Heuristik "rasio orphan" untuk mendeteksi tabel rusak menghasilkan
  62/64 false positive, karena memecah per sel mentah, bukan per baris
  seperti isi chunk yang sebenarnya. Skrip dihapus; keputusan filter
  diambil dari pembacaan manual.

## B2 - Embedding & lima pertanyaan uji

- Embedding: gemini-embedding-001 (3072 dimensi), task_type
  RETRIEVAL_DOCUMENT untuk chunk dan RETRIEVAL_QUERY untuk pertanyaan.
  Cache di pilot/emb_chunks.npy.
- Project: Default Gemini Project (Tier 1 prepay), terpisah dari AISPlus
  (free tier, dipakai agent support).
- Model jawab: gemini-3-flash-preview (sering 503; skrip mencoba ulang
  3x), cadangan gemini-3.8-flash. gemini-2.5-flash sudah tidak tersedia
  untuk pengguna baru.
- Instruksi model: jawab hanya dari kutipan; jawaban sebagian berarti
  canAnswer false; salin angka persis beserta tanda <= atau <; huruf
  tunggal adalah watermark. Model SENGAJA tidak diberi tahu soal angka
  sumbu chart, supaya pengecoh Q5 tetap menjadi ujian yang jujur.

Pertanyaan (bahasa Inggris, dikunci sebelum hasil):

| # | Jenis | Jawaban benar | Hal PDF / cetak |
|---|---|---|---|
| Q1 | Kontrol | Nystatin (anti-fungal, Table 6.17) | 400 / 390 |
| Q2 | Angka tabel | hippurate <= 786 | 405 / 395 |
| Q3 | Lintas halaman | DA/creatinine: 69% Candida sepsis, 36% Candida colonization, 9% bacterial sepsis | 397-398 / 387-388 |
| Q4 | Tidak ada di sumber | methylmalonate: 0 kemunculan di halaman pilot | - |
| Q5 | Nama mirip | a-ketoisocaproate <= 0.58 ug/mg creatinine | 403 / 393 |

Catatan Q2: satuan TIDAK tercetak di halaman 405/406. Kunci jawaban awal
menulis "mcg/mg creatinine"; itu tambahan penyusun kunci, bukan isi
sumber. Model menjawab "No units are specified in the excerpts", yang
justru benar.

Catatan Q5: baris sumber berbunyi "16 a-Ketoisocaproate <0.1 0.39 <= 0.58".
Pengecoh: 0.39 (kemungkinan label sumbu chart) dan 0.94 (batas
a-ketoisovalerate di baris tepat di atasnya).

Kriteria lulus (dikunci sebelum hasil): chunk jawaban masuk top-5, jawaban
benar, halaman benar, dan Q4 harus menolak. Tidak ada angka yang disetel
setelah melihat hasil.

## B3 - Hasil

Peringkat chunk yang memuat jawaban lengkap:

| | Embedding saja (12_jawab.py) | Hibrida (13_hibrida.py) |
|---|---|---|
| Q1 | #1 - LULUS | #1 - LULUS |
| Q2 | #1 - LULUS | #3 - LULUS |
| Q3 | #6 - GAGAL (model menolak: kalimat terpotong) | #3 - LULUS, jawaban lengkap |
| Q4 | menolak - LULUS | menolak - LULUS |
| Q5 | #2 - LULUS | #2 - LULUS |

Hibrida = BM25 (k1 1.5, b 0.75; huruf Yunani dinormalkan ke latin;
token < 2 huruf dibuang) + embedding, digabung dengan Reciprocal Rank
Fusion (k = 60). Semua parameter adalah nilai standar dan ditetapkan
sebelum hasil keluar.

Kenapa hibrida: Q3 gagal di embedding karena chunk jawabannya didominasi
noise (watermark, angka sumbu chart, teks vertikal terbaca terbalik
"noitalumits emyzne mureS", dan kolom sebelah yang membahas asam amino).
Kata kunci di kalimat target ("creatinine ratios", "elevated",
"patients") tetap menemukannya (BM25 #2). Menaikkan top-k ke 8 SENGAJA
tidak dipilih: itu menyetel angka dari satu pengamatan (pola yang sama
dengan maxIterations = 3 di agent support).

## VONIS 0B: LULUS (retrieval hibrida, top-5)

## Temuan untuk produksi

1. Skor kemiripan tidak bisa menjadi gerbang "tidak ada di sumber". Q4
   (tidak ada) mendapat skor 0.736, Q2 (ada) 0.771. Penolakan harus
   dilakukan di tahap jawaban (canAnswer), bukan dengan ambang skor.
2. Aturan "jawaban sebagian -> canAnswer false" mengubah kegagalan
   retrieval Q3 menjadi penolakan yang aman, bukan jawaban setengah yang
   meyakinkan. Aturan ini wajib ada di produksi.
3. Hibrida bukan kemenangan mutlak: Q3 membaik (#6 -> #3), Q2 memburuk
   (#1 -> #3). Di 672 halaman persaingan lebih ketat, jadi perlu set uji
   lebih besar (20-30 pertanyaan lintas bab) sebelum indexing penuh
   dinyatakan siap.
4. Satuan tidak selalu tercetak di halaman yang sama dengan angkanya
   (Q2). Sistem harus menyebut "satuan tidak tercantum", bukan menambal.
5. Kolom note dari model bisa berisi tafsiran tak berdasar (putaran
   embedding saja: klaim "0.39 ada di kolom Reference"). Yang
   ditampilkan ke pengguna hanya jawaban, kutipan, dan halaman.
6. Kutipan lintas halaman dirangkai oleh model (Q3), bukan salinan
   kontigu. Verifikasi kutipan otomatis harus toleran (per token),
   bukan pencocokan string persis.

## Angka untuk perencanaan indexing penuh (revisi)

- 153 chunk / 27 halaman = ~5,7 chunk per halaman. Lebih tinggi dari
  estimasi 0A karena chunk tabel terpisah dan target prosa 900 karakter.
- Estimasi 672 halaman: ~3.800 chunk. Kepadatan tabel berbeda antar bab,
  jadi anggap ini kisaran, bukan angka pasti.
- Embedding berjalan di project Tier 1 prepay, jadi batas kuota free tier
  bukan lagi penghalang. Biaya satu kali indexing penuh perlu dihitung
  dari halaman harga Gemini sebelum dieksekusi.
- Retrieval hibrida butuh indeks kata kunci di samping vector store.
  Pilihan infrastruktur (vector store yang mendukung sparse/hybrid
  search, atau BM25 terpisah) diputuskan di sesi berikutnya.

## Insiden keamanan & prosedur baku

- API key (...0qfA) terlihat utuh di screenshot karena Read-Host dipakai
  tanpa -AsSecureString. Key dihapus dan diganti (...Wfsg). Project-nya
  berbayar, jadi kebocoran key berarti risiko saldo, bukan hanya kuota.
- Jebakan clipboard terjadi untuk KETIGA kalinya: nilai 54 karakter
  berakhiran "ring" = teks perintah Read-Host itu sendiri.
- Menjalankan ulang SetEnvironmentVariable dengan nilai kosong MENGHAPUS
  variabel tersebut.
- Prosedur baku menyimpan key:
  1. Ketik dengan tangan (jangan copy-paste): $s = Read-Host -AsSecureString
  2. Salin key dari AI Studio, tempel di prompt, Enter.
  3. Jalankan blok penjaga yang menolak nilai berspasi atau kurang dari
     30 karakter sebelum SetEnvironmentVariable.
  4. Verifikasi dengan panjang + 4 karakter terakhir saja, jangan pernah
     menampilkan key utuh.

## File

- 07_chunk.py - chunking table-aware + pelacakan halaman per baris
- 09_filter_tabel.py - buang tabel kosong + tabel-036
- 10_smoke.py - uji koneksi API (satu embedding)
- 11_embed_retrieve.py - embedding 153 chunk + retrieval embedding saja
- 12_jawab.py - jawaban model, retrieval embedding saja
- 13_hibrida.py - jawaban model, retrieval hibrida (BM25 + embedding, RRF)
- Output (chunks, embedding, retrieval.txt, jawaban*.txt) ada di pilot/,
  sengaja tidak di-commit karena berisi teks buku berhak cipta.

---

# Pipeline buku penuh - 672 halaman (1 Okt 2026)

Dijalankan di workspace cloud (bukan di laptop), hasil dikirim ke full/ (di-gitignore).

## Ekstraksi (14_ekstrak_penuh.py)
- pdfplumber 0.11.10 + pypdf 6.19.0 (versi disamakan dengan laptop). 672 halaman dalam 73 detik (2 proses).
- Bukti kesetaraan dengan laptop: sebelum filter watermark, teks 27/27 halaman pilot dan 64/64 tabel pilot
  IDENTIK dengan hasil laptop. Semua verifikasi pilot berlaku untuk ekstraksi ini.
- Semua halaman punya lapisan teks. 26 halaman < 300 karakter = halaman judul bab / kosong. Tidak perlu OCR.

## Watermark dibuang di level karakter
- Watermark "Genova Diagnostics" (sumber huruf nyasar sejak 0A) = 18 karakter Helvetica > 40 pt,
  IDENTIK di ke-672 halaman. Isi buku tidak pernah memakai Helvetica > 40 pt
  (Helvetica kecil hanya di hal 467, 79 karakter, ukuran <= 40 - tidak tersentuh).
- Filter: page.filter() membuang char Helvetica dengan size > 40, SEBELUM teks dirangkai.
- Bukti: di semua 672 halaman yang terbuang tepat 17 huruf G-e-n-o-v-a-D-i-a-g-n-o-s-t-i-c-s, tidak ada
  digit yang berubah di halaman mana pun, tidak ada huruf baru. Total 19.067 karakter terbuang.
- Kenapa penting: watermark ternyata menyusup ke TENGAH kata ("Hydrovxyphenylacetate", "Elemnents",
  "Pharmsaceutical") - merusak pencarian kata kunci yang jadi penyelamat Q3. Sekarang utuh.
  Regex tidak mungkin memperbaikinya; filter posisi/font bisa, dan terbukti.

## Chunking (15_chunk_penuh.py) - logika sama dengan 07 + 09
- 524 tabel terdeteksi -> 202 kosong dibuang, 7 dibuang karena pola tabel-036, 315 disimpan.
- 4.116 chunk prosa (868 melintasi 2 halaman). TOTAL 4.431 chunk, 3,77 juta karakter.
- Detektor pola tabel-036: >= 3 baris berturut-turut berisi rentang saja tanpa nama analit.
  Di halaman pilot menandai tepat 1 tabel (tabel-036 lama, kini tabel-0324) dan 0 tabel sehat.
  Di seluruh buku menandai 7; semua diperiksa manual dan semuanya benar bermasalah:
  0324 (405), 0105 (153, uji tantang logam berat), 0051+0092 (150-151, kolom rentang terduplikasi;
  hal 150 juga tertimpa keterangan gambar), 0169 (159), 0195 (190), 0418 (535) = potongan rentang tanpa nama.
  Untuk 150, 151, 153, 159, 405, 535: prosa halaman yang sama memasangkan analit-rentang dengan benar.
- Selisih pilot: di hal 380-406 sekarang 19 tabel (pilot 21). Dua yang hilang (tabel-033, tabel-063 pilot)
  isinya hanya satu huruf watermark ("v", "c") -> kosong setelah filter. Bukan kehilangan data.

## Celah yang diketahui
- Hal 190: angka rentang (19-153, 303-626, 42-130, 53-101, 37-98) tidak terpasang dengan nama analit di teks
  maupun tabel. Perlu cek visual halaman itu.
- Ukuran chunk terbesar 5.873 karakter (tabel-0101, hal 153). Embedding memakai 5.000 karakter pertama untuk
  chunk > 5.000 (hanya chunk ini); teks lengkap tetap tersimpan dan tetap terindeks kata kunci.

## Embedding (16_embed_penuh.py) - dijalankan di laptop
- Bisa dilanjutkan: progres disimpan per 50 chunk ke full/emb_full.npy + emb_full_ids.json.
- Perkiraan ~0,94 juta token (karakter/4). Harga tidak bisa diverifikasi dari halaman harga saat ini,
  jadi biaya diukur langsung: jalankan --batas 100 dulu, cek Spend di AI Studio, baru lanjut.

## Uji retrieval di buku penuh (17_hibrida_penuh.py) - 1 Okt 2026
- Embedding 4.431 chunk selesai dalam 174 detik (Tier 1, tanpa 429, tanpa error).
- Pertanyaan disesuaikan untuk skala penuh SEBELUM hasil keluar:
  - Q4 lama (methylmalonate) ternyata ADA di buku penuh (59 kemunculan; <= 3.4 ug/mg creatinine, hal 66)
    -> dipindah jadi Q6 yang WAJIB DIJAWAB.
  - Q4 baru: HbA1c. Tidak ada rentang di seluruh buku; "haemoglobin A1c" hanya muncul di judul artikel
    daftar pustaka (hal 590-591) -> WAJIB DITOLAK.
- Parameter sama dengan pilot (top-5, BM25 k1 1.5 b 0.75, RRF k 60).

| | Peringkat chunk jawaban (gabungan) | Jawaban | Hasil |
|---|---|---|---|
| Q1 Nystatin | #1 | Nystatin, hal 400 | LULUS |
| Q2 Hippurate | #4 | <= 786 ug/mg creatinine, hal 606 (satuan memang tercetak di hal 606) | LULUS |
| Q3 D-arabinitol | #11 | menolak: "kalimat terpotong, persentase dan kelompok tidak lengkap" | GAGAL retrieval, penolakan aman |
| Q4 HbA1c | - | menolak; tidak terkecoh rentang hemoglobin total 120-150 g/L di kutipan | LULUS |
| Q5 a-ketoisocaproate | #2 | <= 0.58 ug/mg creatinine, hal 403 dan 65 | LULUS |
| Q6 Methylmalonate | #2 | <= 3.4 ug/mg creatinine, hal 66 | LULUS |

VONIS: 5/6. Belum lulus penuh karena Q3.

Temuan:
1. Q4 lama -> Q6: pertanyaan yang SAMA ditolak di pilot (tidak ada di sumber) dan dijawab benar dengan halaman
   di buku penuh. Bukti bahwa jawaban mengikuti isi indeks, bukan ingatan model.
2. Mekanisme kegagalan Q3 teridentifikasi persis: di antara dua belahan kalimat ("...reported in 69, 36," |
   "and 9% of patients with Candida sepsis...") ada ~250 karakter sampah batas halaman: footer "387", angka
   sumbu chart (25 20 15 10 5 0), keterangan gambar, label sumbu vertikal terbaca terbalik
   ("noitalumits emyzne mureS"), running header "Chapter 6". Overlap 200 karakter habis untuk sampah itu.
   Chunk belahan pertama (prosa-2467) justru masuk top-5 (#2).
3. Kandidat perbaikan (belum dikerjakan): (a) buang sampah batas halaman di level karakter seperti watermark
   - karakter tidak tegak (label sumbu vertikal) dan baris running header/footer; (b) "neighbor expansion":
   chunk yang terambil dikirim bersama chunk sesudah/sebelumnya - di kasus ini otomatis membawa prosa-2468.
