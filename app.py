from flask import Flask, render_template, jsonify, Response, send_from_directory, session, redirect, url_for, request
import requests
import random
import os
import re
import threading
import urllib.parse
import hmac
from functools import wraps
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

_USERNAME = os.environ["SIREN_USERNAME"]
_PASSWORD = os.environ["SIREN_PASSWORD"]


def _check_credentials(username: str, password: str) -> bool:
    ok_user = hmac.compare_digest(username.encode(), _USERNAME.encode())
    ok_pass = hmac.compare_digest(password.encode(), _PASSWORD.encode())
    return ok_user and ok_pass


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
]

HEADERS = {
    "referer": "https://monster-siren.hypergryph.com/music",
    "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "user-agent": random.choice(user_agents),
}

DEFAULT_MAX_RETRIES = 5
COVER_DIR = "covers"

http_session = requests.Session()
retries = Retry(
    total=DEFAULT_MAX_RETRIES,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
)
http_session.mount("https://", HTTPAdapter(max_retries=retries))

os.makedirs(COVER_DIR, exist_ok=True)

_cover_semaphore = threading.Semaphore(3)


def _valid_cid(cid: str) -> bool:
    return bool(re.match(r"^\d+$", cid))


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\']', "_", name)


def fetch_with_retry(url: str, stream: bool = False):
    try:
        r = http_session.get(url, headers=HEADERS, stream=stream)
        r.raise_for_status()
        return r
    except requests.exceptions.RequestException:
        return None


def fetch_album_list():
    r = fetch_with_retry("https://monster-siren.hypergryph.com/api/albums")
    if not r:
        return []
    data = r.json()
    if data.get("code") == 0:
        return [{"cid": a["cid"], "name": a["name"]} for a in data["data"]]
    return []


def fetch_album_detail(cid: str):
    r = fetch_with_retry(f"https://monster-siren.hypergryph.com/api/album/{cid}/detail")
    if not r:
        return None
    return r.json().get("data")


def fetch_song_source(cid: str):
    r = fetch_with_retry(f"https://monster-siren.hypergryph.com/api/song/{cid}")
    if not r:
        return None, None
    data = r.json()
    if data.get("code") == 0:
        return data["data"].get("sourceUrl"), sanitize_filename(data["data"].get("name", ""))
    return None, None


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if _check_credentials(username, password):
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "帳號或密碼錯誤"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/albums")
@login_required
def api_albums():
    return jsonify(fetch_album_list())


@app.route("/api/album/<cid>/cover")
@login_required
def api_cover(cid):
    if not _valid_cid(cid):
        return "", 400

    filename = f"{cid}.jpg"
    abs_cover_dir = os.path.abspath(COVER_DIR)
    local_path = os.path.join(abs_cover_dir, filename)

    if os.path.exists(local_path):
        return send_from_directory(abs_cover_dir, filename)

    with _cover_semaphore:
        if os.path.exists(local_path):
            return send_from_directory(abs_cover_dir, filename)

        detail = fetch_album_detail(cid)
        if not detail:
            return "", 404

        cover_url = detail.get("coverUrl")
        if cover_url:
            try:
                r = requests.get(cover_url, headers=HEADERS, timeout=15)
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(r.content)
                return send_from_directory(abs_cover_dir, filename)
            except Exception:
                pass

    return "", 404


@app.route("/api/album/<cid>/songs")
@login_required
def api_album_songs(cid):
    if not _valid_cid(cid):
        return "", 400
    detail = fetch_album_detail(cid)
    if not detail:
        return jsonify([])
    return jsonify([{"cid": s["cid"], "name": s["name"]} for s in detail.get("songs", [])])


@app.route("/api/song/<cid>/download")
@login_required
def api_song_download(cid):
    if not _valid_cid(cid):
        return "", 400

    source_url, song_name = fetch_song_source(cid)
    if not source_url or not song_name:
        return "Song not found", 404

    ext = source_url.rsplit(".", 1)[-1]
    filename = f"{song_name}.{ext}"

    r = requests.get(source_url, headers=HEADERS, stream=True, timeout=30)
    if not r.ok:
        return "Upstream error", 502

    resp_headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}",
        "X-Accel-Buffering": "no",
    }
    if "Content-Length" in r.headers:
        resp_headers["Content-Length"] = r.headers["Content-Length"]

    content_type = r.headers.get("Content-Type", "application/octet-stream")

    def generate():
        for chunk in r.iter_content(chunk_size=65536):
            yield chunk

    return Response(generate(), mimetype=content_type, headers=resp_headers)


if __name__ == "__main__":
    app.run(debug=True, threaded=True, port=5000)
