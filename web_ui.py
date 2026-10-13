"""web_ui.py - antarmuka web LOKAL untuk 31_tanya.py (13 Okt 2026).

Rute: / (halaman), /api/tanya, /api/chunk, /api/riwayat, /api/contoh, /api/toc (daftar isi dari full\\daftar_isi.json),
/buku.pdf (source.pdf lokal, untuk membuka halaman: /buku.pdf#page=N).
Dipanggil dari 31_tanya.py bila ada opsi --web:  python 31_tanya.py --web [--port 8765] [--no-open]
- Server hanya mendengarkan di 127.0.0.1 (laptop ini saja). Tidak ada kunci API atau teks buku yang dikirim ke luar laptop
  selain panggilan Gemini yang memang dilakukan mesin 31_tanya.py.
- Mesin, router, kebijakan, dan pemeriksa angka TIDAK diubah; berkas ini hanya membungkusnya.
- Perlindungan: cek header Host (anti DNS-rebinding), POST wajib application/json, Origin harus sama bila ada, batas ukuran.
"""
import json, pathlib, threading, webbrowser, sys, traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HTML_FILE = pathlib.Path(__file__).with_name("web_ui.html")
MAKS_BODY = 4096
MAKS_Q = 500
PESAN_SIBUK = ("Layanan sedang sibuk atau tidak tersedia, sehingga pertanyaan ini belum dapat dijawab. "
               "Silakan coba lagi beberapa saat lagi. Untuk hal yang menyangkut dosis atau keputusan pengobatan, "
               "tetap bicarakan dengan dokter atau tenaga kesehatan Anda.")


def halaman_cetak(p):
    """Halaman cetak kira-kira = halaman PDF - 10; None untuk bagian awal buku."""
    return p - 10 if p > 10 else None


def jalankan(tanya, catat, label_teks, log_path, contoh_path, chunk_teks, port=8765, buka=True, toc_path=None, pdf_path=None):
    kunci = threading.Lock()  # mesin memakai satu klien dan cache global: layani satu pertanyaan sekali jalan
    host_ok = {f"127.0.0.1:{port}", f"localhost:{port}"}
    html = HTML_FILE.read_text(encoding="utf-8")

    def hasil_json(h):
        ans = h["ans"]
        tersembunyi = bool(h["hilang"])
        pdf = list(h["pages"])
        return {
            "q": h["q"], "tingkat": h["tingkat"], "alasan": h["alasan"], "degradasi": h["degradasi"], "model": h["model"],
            "canAnswer": bool(ans.get("canAnswer")),
            "answer": "" if tersembunyi else str(ans.get("answer") or "").strip(),
            "tersembunyi": tersembunyi, "angka_hilang": list(h["hilang"]),
            "note": str(ans.get("note") or "").strip(),
            "quote": str(ans.get("quote") or "").strip(),
            "halaman": [{"pdf": p, "cetak": halaman_cetak(p)} for p in pdf],
            "chunks": list(h["kutip"]),
            "dipangkas": bool(h["dipangkas"]),
            "label": label_teks if h.get("label_repletion") else "",
        }

    def riwayat(n=30):
        if not log_path.exists():
            return []
        baris = [b for b in log_path.read_text(encoding="utf-8").splitlines() if b.strip()][-n:]
        out = []
        for b in reversed(baris):
            try:
                r = json.loads(b)
                out.append({"waktu": r.get("waktu", ""), "q": r.get("q", ""), "tingkat": r.get("tingkat"),
                            "canAnswer": bool(r.get("canAnswer")),
                            "tersembunyi": bool(r.get("angka_tak_terverifikasi"))})
            except Exception:
                pass
        return out

    def contoh():
        if not contoh_path.exists():
            return []
        return [l.strip() for l in contoh_path.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]

    class H(BaseHTTPRequestHandler):
        server_version = "labrag-lokal"

        def log_message(self, fmt, *a):  # log ringkas, tanpa isi pertanyaan
            sys.stderr.write("[web] " + (fmt % a) + "\n")

        def _kirim(self, kode, tipe, data):
            b = data if isinstance(data, bytes) else data.encode("utf-8")
            self.send_response(kode)
            self.send_header("Content-Type", tipe)
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(b)

        def _json(self, kode, obj):
            self._kirim(kode, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False))

        def _kirim_pdf(self):
            """Sajikan source.pdf dari laptop ini (untuk #page=N). Mendukung Range supaya penampil PDF browser cepat."""
            if pdf_path is None or not pdf_path.exists():
                return self._json(404, {"error": "source.pdf tidak ditemukan di folder proyek"})
            total = pdf_path.stat().st_size
            mulai, akhir, kode = 0, total - 1, 200
            rng = self.headers.get("Range")
            if rng and rng.startswith("bytes="):
                try:
                    a, b = rng[6:].split(",")[0].split("-")
                    if a == "":
                        mulai = max(0, total - int(b))
                    else:
                        mulai = int(a)
                        akhir = int(b) if b else total - 1
                    akhir = min(akhir, total - 1)
                    if mulai > akhir or mulai < 0:
                        raise ValueError
                    kode = 206
                except ValueError:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{total}")
                    self.end_headers()
                    return
            panjang = akhir - mulai + 1
            self.send_response(kode)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(panjang))
            self.send_header("Content-Disposition", 'inline; filename="buku.pdf"')
            self.send_header("X-Content-Type-Options", "nosniff")
            if kode == 206:
                self.send_header("Content-Range", f"bytes {mulai}-{akhir}/{total}")
            self.end_headers()
            try:
                with pdf_path.open("rb") as f:
                    f.seek(mulai)
                    sisa = panjang
                    while sisa > 0:
                        blok = f.read(min(65536, sisa))
                        if not blok:
                            break
                        self.wfile.write(blok)
                        sisa -= len(blok)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # penampil PDF sering menutup koneksi di tengah jalan; bukan galat

        def _host_sah(self):
            if (self.headers.get("Host") or "").lower() not in host_ok:
                self._json(403, {"error": "host tidak diizinkan"})
                return False
            return True

        def do_GET(self):
            if not self._host_sah():
                return
            u = urlparse(self.path)
            if u.path == "/":
                self._kirim(200, "text/html; charset=utf-8", html)
            elif u.path == "/api/contoh":
                self._json(200, contoh())
            elif u.path == "/api/riwayat":
                self._json(200, riwayat())
            elif u.path == "/api/toc":
                if toc_path is not None and toc_path.exists():
                    self._kirim(200, "application/json; charset=utf-8", toc_path.read_text(encoding="utf-8"))
                else:
                    self._json(200, [])
            elif u.path == "/buku.pdf":
                self._kirim_pdf()
            elif u.path == "/api/chunk":
                cid = (parse_qs(u.query).get("id") or [""])[0]
                t = chunk_teks(cid)
                if t is None:
                    self._json(404, {"error": "chunk tidak dikenal"})
                else:
                    self._json(200, {"id": cid, "teks": t})
            else:
                self._json(404, {"error": "tidak ada"})

        def do_POST(self):
            if not self._host_sah():
                return
            if urlparse(self.path).path != "/api/tanya":
                return self._json(404, {"error": "tidak ada"})
            if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
                return self._json(415, {"error": "harus application/json"})
            org = self.headers.get("Origin")
            if org and org not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
                return self._json(403, {"error": "origin tidak diizinkan"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = -1
            if n <= 0 or n > MAKS_BODY:
                return self._json(413, {"error": "ukuran tidak sah"})
            try:
                q = str(json.loads(self.rfile.read(n)).get("q", "")).strip()
            except Exception:
                return self._json(400, {"error": "JSON tidak terbaca"})
            if not q:
                return self._json(400, {"error": "pertanyaan kosong"})
            if len(q) > MAKS_Q:
                return self._json(400, {"error": f"pertanyaan terlalu panjang (maks {MAKS_Q} karakter)"})
            try:
                with kunci:
                    h = tanya(q)
                    catat(h)
                self._json(200, hasil_json(h))
            except Exception:
                traceback.print_exc()  # detail hanya di konsol; layar menerima pesan layanan sibuk
                self._json(503, {"error": "sibuk", "pesan": PESAN_SIBUK})

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}/"
    print(f"Antarmuka web lokal siap di {url}  (hanya bisa dibuka dari laptop ini). Ctrl+C untuk berhenti.")
    if buka:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBerhenti.")
    finally:
        srv.server_close()
