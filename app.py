import os
import re
import secrets
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash

from storage import get_store

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JST = timezone(timedelta(hours=9))

GRADES = ["高1", "高2", "高3", "既卒生", "卒業生"]
SENIOR_GRADE = "卒業生"
ROUTES = ["一般選抜", "総合型選抜", "学校推薦型選抜", "専門学校", "就活", "まだ決めていない"]
FIELDS = ["文系", "理系", "医療・看護", "芸術・体育", "その他"]

EXAM_NAME = os.environ.get("EXAM_NAME", "共通テスト")
EXAM_DATE = date.fromisoformat(os.environ.get("EXAM_DATE", "2027-01-16"))
EXAM_TIME = datetime.strptime(os.environ.get("EXAM_TIME", "09:30"), "%H:%M").time()
DEFAULT_HERO = "hero-modern.svg"
RESUME_IMAGE = "resume.webp"
SITE_ASSETS = [DEFAULT_HERO, RESUME_IMAGE]
HERO_IMAGE = os.environ.get("HERO_IMAGE", DEFAULT_HERO)

UPLOAD_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|gif|webp)$")
SITE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}\.(svg|jpg|jpeg|png|webp)$")
THREAD_ID = re.compile(r"^\d{13}-[0-9a-f]{8}$")
CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
}

BLOCK_RULES = [
    (re.compile(r"0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}"), "電話番号"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "メールアドレス"),
    (re.compile(r"(line|ライン|インスタ|instagram|twitter|tiktok)\s*(id)?\s*[:は]\s*@?[a-z0-9_.-]{3,}", re.I), "SNSのID"),
    (re.compile(r"(?<![\w])@[A-Za-z0-9_]{4,}"), "SNSのID"),
]
NG_WORDS = ["死ね", "殺す", "消えろ", "きもい", "キモい", "うざい", "ウザい"]


store = get_store(os.path.join(BASE_DIR, "local_data"))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=store.secret_key(),
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=bool(os.environ.get("WEBSITE_HOSTNAME")),
)


def seed_hero():
    for name in SITE_ASSETS:
        try:
            if not store.image_exists("site", name):
                with open(os.path.join(BASE_DIR, "assets", name), "rb") as f:
                    store.save_image("site", name, f.read(), CONTENT_TYPES[name.rsplit(".", 1)[1]])
        except Exception as e:
            app.logger.warning("site image seed failed: %s %s", name, e)


seed_hero()


def check_text(*texts):
    joined = unicodedata.normalize("NFKC", "\n".join(texts))
    for pattern, label in BLOCK_RULES:
        if pattern.search(joined):
            return f"{label}のような文字が含まれています。個人情報は書かないでください。"
    for word in NG_WORDS:
        if word in joined:
            return "人を傷つける言葉が含まれています。やさしい言葉で書き直してください。"
    return None


def sniff_image(data):
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def read_image():
    file = request.files.get("image")
    if not file or not file.filename:
        return "", None
    data = file.read()
    ext = sniff_image(data)
    if not ext:
        return "", "画像は JPEG・PNG・GIF・WebP のどれかにしてください。"
    return (f"{uuid.uuid4().hex}.{ext}", data), None


def save_image(image):
    if not image:
        return ""
    name, data = image
    store.save_image("uploads", name, data, CONTENT_TYPES[name.rsplit(".", 1)[1]])
    return name


def read_common_fields():
    nickname = request.form.get("nickname", "").strip()[:20] or "名無しの受験生"
    grade = request.form.get("grade", "")
    body = request.form.get("body", "").strip()
    key = request.form.get("key", "")
    errors = []
    if grade not in GRADES:
        errors.append("学年を選んでください。")
    if not body or len(body) > 2000:
        errors.append("本文は1〜2000文字で書いてください。")
    if not 4 <= len(key) <= 32:
        errors.append("あいことばは4〜32文字にしてください。")
    return nickname, grade, body, key, errors


def now_text():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")


def get_thread_or_404(tid):
    if not THREAD_ID.match(tid):
        abort(404)
    thread = store.get_thread(tid)
    if not thread:
        abort(404)
    return thread


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        token = request.form.get("csrf", "")
        if not token or not secrets.compare_digest(token, session.get("csrf", "")):
            abort(400)


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


@app.context_processor
def inject_globals():
    days_left = (EXAM_DATE - datetime.now(JST).date()).days
    return {
        "csrf_token": csrf_token,
        "exam_name": EXAM_NAME,
        "days_left": days_left,
        "exam_iso": datetime.combine(EXAM_DATE, EXAM_TIME, JST).isoformat(),
        "hero_image": HERO_IMAGE,
        "resume_image": RESUME_IMAGE,
        "grades": GRADES,
        "routes": ROUTES,
        "fields": FIELDS,
        "senior_grade": SENIOR_GRADE,
    }


@app.route("/")
def index():
    route = request.args.get("route", "")
    field = request.args.get("field", "")
    q = request.args.get("q", "").strip()
    unsolved = request.args.get("unsolved") == "1"
    sort = request.args.get("sort", "new")

    threads = store.list_threads()
    if route in ROUTES:
        threads = [t for t in threads if t.get("route") == route]
    if field in FIELDS:
        threads = [t for t in threads if t.get("field") == field]
    if unsolved:
        threads = [t for t in threads if not t.get("solved")]
    if q:
        threads = [t for t in threads if q in t.get("title", "") or q in t.get("body", "")]
    if sort == "empathy":
        threads.sort(key=lambda t: t.get("empathy", 0), reverse=True)

    return render_template(
        "index.html", threads=threads, route=route, field=field, q=q, unsolved=unsolved, sort=sort
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/new", methods=["GET", "POST"])
def new_thread():
    form = {}
    if request.method == "POST":
        form = request.form
        title = form.get("title", "").strip()
        route = form.get("route", "")
        field = form.get("field", "")
        nickname, grade, body, key, errors = read_common_fields()
        if not title or len(title) > 60:
            errors.append("タイトルは1〜60文字で書いてください。")
        if route not in ROUTES:
            errors.append("受験方式を選んでください。")
        if field not in FIELDS:
            errors.append("分野を選んでください。")
        image, image_error = read_image()
        if image_error:
            errors.append(image_error)
        blocked = check_text(title, body, nickname)
        if blocked:
            errors.append(blocked)
        if not errors:
            tid = store.add_thread(
                {
                    "title": title,
                    "body": body,
                    "nickname": nickname,
                    "grade": grade,
                    "route": route,
                    "field": field,
                    "image": save_image(image),
                    "created": now_text(),
                    "solved": False,
                    "empathy": 0,
                    "reply_count": 0,
                    "key_hash": generate_password_hash(key),
                }
            )
            flash("相談を投稿しました。")
            return redirect(url_for("thread", tid=tid))
        for e in errors:
            flash(e, "error")
    return render_template("new.html", form=form)


@app.route("/t/<tid>")
def thread(tid):
    t = get_thread_or_404(tid)
    replies = store.list_replies(tid)
    liked = tid in session.get("liked", [])
    return render_template("thread.html", t=t, replies=replies, liked=liked)


@app.route("/t/<tid>/reply", methods=["POST"])
def reply(tid):
    t = get_thread_or_404(tid)
    nickname, grade, body, key, errors = read_common_fields()
    image, image_error = read_image()
    if image_error:
        errors.append(image_error)
    blocked = check_text(body, nickname)
    if blocked:
        errors.append(blocked)
    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("thread", tid=tid) + "#reply-form")
    store.add_reply(
        tid,
        {
            "body": body,
            "nickname": nickname,
            "grade": grade,
            "image": save_image(image),
            "created": now_text(),
            "key_hash": generate_password_hash(key),
        },
    )
    store.update_thread(tid, reply_count=int(t.get("reply_count", 0)) + 1)
    flash("返信しました。")
    return redirect(url_for("thread", tid=tid) + "#replies")


@app.route("/t/<tid>/empathy", methods=["POST"])
def empathy(tid):
    t = get_thread_or_404(tid)
    liked = session.get("liked", [])
    if tid not in liked:
        store.update_thread(tid, empathy=int(t.get("empathy", 0)) + 1)
        session["liked"] = (liked + [tid])[-200:]
    return redirect(url_for("thread", tid=tid))


@app.route("/t/<tid>/solve", methods=["POST"])
def solve(tid):
    t = get_thread_or_404(tid)
    if check_password_hash(t["key_hash"], request.form.get("key", "")):
        store.update_thread(tid, solved=True)
        flash("解決済みにしました。おめでとう！")
    else:
        flash("あいことばがちがいます。", "error")
    return redirect(url_for("thread", tid=tid))


@app.route("/t/<tid>/delete", methods=["POST"])
def delete_thread(tid):
    t = get_thread_or_404(tid)
    if not check_password_hash(t["key_hash"], request.form.get("key", "")):
        flash("あいことばがちがいます。", "error")
        return redirect(url_for("thread", tid=tid))
    for r in store.delete_thread(tid):
        if r.get("image"):
            store.delete_image("uploads", r["image"])
    if t.get("image"):
        store.delete_image("uploads", t["image"])
    flash("相談を削除しました。")
    return redirect(url_for("index"))


@app.route("/t/<tid>/r/<rid>/delete", methods=["POST"])
def delete_reply(tid, rid):
    t = get_thread_or_404(tid)
    r = store.get_reply(tid, rid) if THREAD_ID.match(rid) else None
    if not r:
        abort(404)
    if not check_password_hash(r["key_hash"], request.form.get("key", "")):
        flash("あいことばがちがいます。", "error")
        return redirect(url_for("thread", tid=tid) + "#replies")
    store.delete_reply(tid, rid)
    if r.get("image"):
        store.delete_image("uploads", r["image"])
    store.update_thread(tid, reply_count=max(int(t.get("reply_count", 1)) - 1, 0))
    flash("返信を削除しました。")
    return redirect(url_for("thread", tid=tid) + "#replies")


@app.route("/media/<container>/<name>")
def media(container, name):
    if container == "uploads" and UPLOAD_NAME.match(name):
        pass
    elif container == "site" and SITE_NAME.match(name):
        pass
    else:
        abort(404)
    data = store.load_image(container, name)
    if data is None:
        abort(404)
    resp = Response(data, mimetype=CONTENT_TYPES[name.rsplit(".", 1)[1].lower()])
    resp.headers["Cache-Control"] = "public, max-age=86400"
    if container == "site":
        resp.headers["Cache-Control"] = "no-cache"
        resp.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return resp


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", message="もう一度ページを開きなおしてから送信してください。"), 400


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", message="ページが見つかりませんでした。"), 404


@app.errorhandler(413)
def too_large(e):
    return render_template("error.html", message="画像は5MBまでにしてください。"), 413


if __name__ == "__main__":
    app.run(debug=False, port=5000)
