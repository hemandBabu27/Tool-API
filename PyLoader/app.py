import os, re, uuid, time, threading, secrets, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from flask import Flask, request, jsonify, session, send_file, render_template, redirect, url_for
import yt_dlp

APP_SECRET = os.environ.get("APP_SECRET", secrets.token_hex(32))
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "")
PORT = int(os.environ.get("PORT", "8080"))
OUT = Path(os.environ.get("DOWNLOAD_DIR", "/tmp/pyloader-downloads"))
OUT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = APP_SECRET
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1") == "1",
                  MAX_CONTENT_LENGTH=1 * 1024 * 1024)
pool = ThreadPoolExecutor(max_workers=int(os.environ.get("MAX_WORKERS", "2")))
jobs, lock, attempts = {}, threading.Lock(), {}

def authenticated(fn):
    @wraps(fn)
    def wrapped(*a, **kw):
        if not session.get("ok"):
            if request.path.startswith("/api/"): return jsonify(error="Please sign in first."), 401
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapped

def clean_old():
    cutoff = time.time() - 6 * 3600
    for p in OUT.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < cutoff: p.unlink()
            elif p.is_dir() and p.stat().st_mtime < cutoff: shutil.rmtree(p, ignore_errors=True)
        except OSError: pass
    with lock:
        for k, v in list(jobs.items()):
            if v.get("created", 0) < cutoff: jobs.pop(k, None)

@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return resp

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not ACCESS_PASSWORD:
            return render_template("login.html", error="The site owner has not configured ACCESS_PASSWORD.")
        if secrets.compare_digest(request.form.get("password", ""), ACCESS_PASSWORD):
            session.clear(); session["ok"] = True
            return redirect(url_for("home"))
        return render_template("login.html", error="Incorrect access password.")
    return render_template("login.html")

@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.get("/")
@authenticated
def home():
    return render_template("index.html")

@app.get("/api/search")
@authenticated
def search():
    clean_old()
    q = (request.args.get("q") or "").strip()
    if len(q) < 2 or len(q) > 120: return jsonify(error="Enter a search term (2–120 characters)."), 400
    key = request.remote_addr or "unknown"
    now = time.time()
    with lock:
        recent = [t for t in attempts.get(key, []) if now-t < 60]
        if len(recent) >= 12: return jsonify(error="Search limit reached. Please wait a minute."), 429
        recent.append(now); attempts[key] = recent
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True,
            "playlistend": 12, "socket_timeout": 15}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info("ytsearch12:" + q, download=False)
        entries = []
        for e in (data or {}).get("entries", []) or []:
            if not e: continue
            vid = e.get("id")
            if not vid or not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", str(vid)): continue
            entries.append({"id": vid, "title": e.get("title") or "Untitled",
                "channel": e.get("channel") or e.get("uploader") or "YouTube creator",
                "duration": e.get("duration"), "thumbnail": e.get("thumbnail") or "",
                "url": "https://www.youtube.com/watch?v=" + vid})
        return jsonify(results=entries)
    except Exception:
        return jsonify(error="Search failed. Try another query or try again later."), 502

def run_job(job_id, video_id, quality):
    dest = OUT / job_id
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with lock: jobs[job_id]["status"] = "processing"
        url = "https://www.youtube.com/watch?v=" + video_id
        opts = {"format": "bestaudio/best", "outtmpl": str(dest / "%(title).80s-%(id)s.%(ext)s"),
            "noplaylist": True, "quiet": True, "no_warnings": True, "socket_timeout": 25, "retries": 2,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": quality}]}
        with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])
        mp3s = list(dest.glob("*.mp3"))
        if not mp3s: raise RuntimeError("Conversion did not produce an MP3.")
        chosen = mp3s[0]
        with lock: jobs[job_id].update(status="done", filename=chosen.name, path=str(chosen), size=chosen.stat().st_size)
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        with lock: jobs[job_id].update(status="error", message="Conversion failed. The video may be unavailable or not permitted for download.")

@app.post("/api/convert")
@authenticated
def convert():
    data = request.get_json(silent=True) or {}
    vid, quality = str(data.get("id", "")), str(data.get("quality", "192"))
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid): return jsonify(error="Invalid video selection."), 400
    if quality not in {"128", "192", "256", "320"}: return jsonify(error="Invalid audio quality."), 400
    if data.get("authorized") is not True:
        return jsonify(error="Confirm that you own the content or have permission to download it."), 400
    jid = uuid.uuid4().hex
    with lock: jobs[jid] = {"status": "queued", "created": time.time()}
    pool.submit(run_job, jid, vid, quality)
    return jsonify(job_id=jid)

@app.get("/api/job/<job_id>")
@authenticated
def job_status(job_id):
    with lock: item = jobs.get(job_id)
    if not item: return jsonify(error="This job has expired."), 404
    safe = {k:v for k,v in item.items() if k != "path"}
    if item["status"] == "done": safe["download_url"] = url_for("download", job_id=job_id)
    return jsonify(safe)

@app.get("/api/download/<job_id>")
@authenticated
def download(job_id):
    with lock: item = jobs.get(job_id)
    if not item or item.get("status") != "done": return "File unavailable or expired.", 404
    path = Path(item.get("path", ""))
    if not path.is_file() or path.parent.parent != OUT: return "File unavailable.", 404
    return send_file(path, as_attachment=True, download_name=path.name, mimetype="audio/mpeg")

@app.get("/manifest.webmanifest")
def manifest():
    return jsonify({"name": "PyLoader", "short_name": "PyLoader", "start_url": "/",
                    "display": "standalone", "background_color": "#10131b", "theme_color": "#10131b", "icons": []})

if __name__ == "__main__":
    if not ACCESS_PASSWORD: print("WARNING: Set ACCESS_PASSWORD before public deployment.")
    app.run(host="0.0.0.0", port=PORT)
