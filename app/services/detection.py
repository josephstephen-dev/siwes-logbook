import re
from datetime import datetime, timedelta, timezone

from markupsafe import Markup, escape
from sqlalchemy import or_

from ..extensions import db
from ..models.entry import Entry
from ..models.flag import Flag

K, THRESHOLD, MIN_WORDS = 4, 0.6, 12


def _tokens(text):
    return re.findall(r"\S+", text)


def _norm(tok):
    return re.sub(r"\W+", "", tok.lower())


def _words(text):
    return [w for w in (_norm(t) for t in _tokens(text)) if w]


def _shingles(words):
    return {tuple(words[i:i + K]) for i in range(len(words) - K + 1)}


def similarity(a_words, b_words):
    sa, sb = _shingles(a_words), _shingles(b_words)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def highlight(text, other):
    """The text with phrases it shares with `other` wrapped in <mark>."""
    toks = _tokens(text)
    idx = [i for i, t in enumerate(toks) if _norm(t)]
    words = [_norm(toks[i]) for i in idx]
    shared = _shingles(_words(other))
    marked = [False] * len(toks)
    for j in range(len(words) - K + 1):
        if tuple(words[j:j + K]) in shared:
            for i in idx[j:j + K]:
                marked[i] = True
    parts, run = [], []

    def flush():
        if run:
            parts.append("<mark>" + " ".join(run) + "</mark>")
            run.clear()

    for tok, m in zip(toks, marked):
        if m:
            run.append(str(escape(tok)))
        else:
            flush()
            parts.append(str(escape(tok)))
    flush()
    return Markup(" ".join(parts))


def scan(since_days=3):
    """Flags new pairs of similar entries written by different students. Needs no human input."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    pool = Entry.query.all()
    cache = {e.id: _words(e.body) for e in pool}
    created = 0
    for a in pool:
        if a.recorded_at is None or a.recorded_at.replace(tzinfo=a.recorded_at.tzinfo or timezone.utc) < cutoff:
            continue
        wa = cache[a.id]
        if len(wa) < MIN_WORDS:
            continue
        for b in pool:
            if b.student_id == a.student_id or b.id == a.id or len(cache[b.id]) < MIN_WORDS:
                continue
            score = similarity(wa, cache[b.id])
            if score >= THRESHOLD:
                lo, hi = sorted((a.id, b.id))
                if not Flag.query.filter_by(entry_a_id=lo, entry_b_id=hi).first():
                    db.session.add(Flag(entry_a_id=lo, entry_b_id=hi, score=round(score, 2)))
                    created += 1
    db.session.commit()
    return created


def open_flags_for(student_id):
    ids = [e.id for e in Entry.query.filter_by(student_id=student_id)]
    if not ids:
        return 0
    return Flag.query.filter(Flag.status == "open",
                             or_(Flag.entry_a_id.in_(ids), Flag.entry_b_id.in_(ids))).count()