import hashlib
import hmac
import json

from flask import current_app

GENESIS = "0" * 64


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seal(prev_hash, student_id, seq, kind, at, payload_json):
    """Keyed fingerprint. The key lives in .env, outside the database."""
    key = current_app.config["HMAC_KEY"].encode()
    msg = canonical([prev_hash, student_id, seq, kind, at, payload_json])
    return hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()