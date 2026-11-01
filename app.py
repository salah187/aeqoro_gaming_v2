import os
import hmac
import hashlib
import json
import sqlite3
import time
from urllib.parse import parse_qsl
from flask import Flask, g, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "aeqoro.db"))
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
AFFILIATE_URL = os.environ.get("AFFILIATE_URL", "")  # Set only after written partner approval.
APPROVED_PARTNER_NAME = os.environ.get("APPROVED_PARTNER_NAME", "")
REQUIRE_TELEGRAM_AUTH = os.environ.get("REQUIRE_TELEGRAM_AUTH", "true").lower() == "true"

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            referred_by INTEGER,
            created_at INTEGER NOT NULL,
            clicks INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referral_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL UNIQUE,
            created_at INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# Ensure tables exist when launched by a production WSGI server (e.g. Gunicorn).
init_db()


def verify_telegram_init_data(init_data: str):
    """Verify Telegram WebApp initData per Telegram's documented HMAC scheme."""
    if not BOT_TOKEN or not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            return None
        auth_date = int(pairs.get("auth_date", "0"))
        # Reject data older than 24 hours.
        if auth_date <= 0 or time.time() - auth_date > 86400 or auth_date > time.time() + 60:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        user = json.loads(pairs.get("user", "{}"))
        telegram_id = int(user["id"])
        return {
            "telegram_id": telegram_id,
            "username": str(user.get("username", ""))[:64],
            "first_name": str(user.get("first_name", ""))[:64],
            "start_param": str(pairs.get("start_param", ""))[:80],
        }
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def current_user():
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user = verify_telegram_init_data(init_data)
    if user:
        return user
    if REQUIRE_TELEGRAM_AUTH:
        return None
    # Local development only. Never disable auth on a public production deployment.
    try:
        telegram_id = int(request.headers.get("X-Demo-User-Id", "100001"))
    except ValueError:
        telegram_id = 100001
    return {"telegram_id": telegram_id, "username": "demo_user", "first_name": "Demo", "start_param": ""}


def ensure_user(user):
    conn = db()
    now = int(time.time())
    row = conn.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (user["telegram_id"],)).fetchone()
    if row:
        conn.execute(
            "UPDATE users SET username = ?, first_name = ? WHERE telegram_id = ?",
            (user["username"], user["first_name"], user["telegram_id"])
        )
    else:
        referrer_id = None
        param = user.get("start_param", "")
        if param.startswith("ref_"):
            try:
                candidate = int(param[4:])
                if candidate != user["telegram_id"]:
                    exists = conn.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (candidate,)).fetchone()
                    if exists:
                        referrer_id = candidate
            except ValueError:
                pass
        conn.execute(
            "INSERT INTO users (telegram_id, username, first_name, referred_by, created_at) VALUES (?, ?, ?, ?, ?)",
            (user["telegram_id"], user["username"], user["first_name"], referrer_id, now)
        )
        if referrer_id:
            conn.execute(
                "INSERT OR IGNORE INTO referral_events (referrer_id, referred_id, created_at) VALUES (?, ?, ?)",
                (referrer_id, user["telegram_id"], now)
            )
    conn.commit()


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "app": "AEQORO Gaming"})


@app.get("/api/config")
def config():
    # Never expose bot token or private configuration.
    return jsonify({
        "partner_approved": bool(AFFILIATE_URL and APPROVED_PARTNER_NAME),
        "partner_name": APPROVED_PARTNER_NAME if AFFILIATE_URL and APPROVED_PARTNER_NAME else "",
        "affiliate_url": AFFILIATE_URL if AFFILIATE_URL and APPROVED_PARTNER_NAME else "",
        "demo_mode": not REQUIRE_TELEGRAM_AUTH,
    })


@app.get("/api/me")
def me():
    user = current_user()
    if not user:
        return jsonify({"error": "Open this Mini App from its Telegram bot."}), 401
    ensure_user(user)
    conn = db()
    row = conn.execute("SELECT COUNT(*) AS total FROM referral_events WHERE referrer_id = ?", (user["telegram_id"],)).fetchone()
    return jsonify({
        "id": user["telegram_id"],
        "first_name": user["first_name"] or "Player",
        "username": user["username"],
        "referrals": row["total"],
        "referral_link": f"https://t.me/{os.environ.get('TELEGRAM_BOT_USERNAME', 'YOUR_BOT_USERNAME')}?startapp=ref_{user['telegram_id']}",
        "commission": None,
        "commission_note": "Commissions appear only after an approved partner reports verified results."
    })


@app.post("/api/click")
def track_click():
    user = current_user()
    if not user:
        return jsonify({"error": "Telegram authentication required."}), 401
    ensure_user(user)
    conn = db()
    conn.execute("UPDATE users SET clicks = clicks + 1 WHERE telegram_id = ?", (user["telegram_id"],))
    conn.commit()
    if AFFILIATE_URL and APPROVED_PARTNER_NAME:
        return jsonify({"url": AFFILIATE_URL, "partner": APPROVED_PARTNER_NAME})
    return jsonify({"url": "", "message": "Partner link will be enabled after written approval."})


@app.get("/api/stats")
def stats():
    user = current_user()
    if not user:
        return jsonify({"error": "Telegram authentication required."}), 401
    ensure_user(user)
    conn = db()
    row = conn.execute("SELECT clicks FROM users WHERE telegram_id = ?", (user["telegram_id"],)).fetchone()
    return jsonify({"clicks": row["clicks"], "referrals": conn.execute(
        "SELECT COUNT(*) FROM referral_events WHERE referrer_id = ?", (user["telegram_id"],)
    ).fetchone()[0]})


@app.get("/privacy")
def privacy():
    return send_from_directory(BASE_DIR, "privacy.html")


if __name__ == "__main__":
    init_db()
    # Local testing only. Use a production WSGI server on your hosting provider.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
