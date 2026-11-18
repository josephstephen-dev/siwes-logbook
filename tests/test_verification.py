import io
from datetime import date

from test_entries import _fill_week, _setup

from app.extensions import db
from app.models.entry import Entry
from app.models.placement import Placement
from app.models.user import User
from app.services import approvals, finalize, pdf_report, weeks


def test_issue_verify_and_tamper(app, client, monkeypatch, tmp_path):
    app.config["ISSUED_DIR"] = str(tmp_path)
    st, sup = _setup(monkeypatch)
    Placement.query.one().end_date = date(2025, 5, 17)       # a one-week placement
    coord = User(role="coordinator", status="active", full_name="C", email="c@x.ng")
    db.session.add(coord)
    db.session.commit()
    with app.test_request_context():
        _fill_week(st)
        wk = weeks.get_week(st, 1)
        approvals.submit_week(st, wk, "Amara Okoye", True)
        approvals.approve_week(sup, wk, "Good", "Chinedu Okafor", "Engineer")
        assert finalize.checklist(st).ready
        rec = pdf_report.issue(st, coord)
        pdf = open(f"{tmp_path}/{rec.filename}", "rb").read()

    r = client.get(f"/v/{rec.vid}")
    assert b"NOT VALID" not in r.data and b"VALID" in r.data
    r = client.post("/v/check", data={"file": (io.BytesIO(pdf), "x.pdf")}, content_type="multipart/form-data")
    assert b"matches the issued copy" in r.data
    r = client.post("/v/check", data={"file": (io.BytesIO(pdf + b"x"), "x.pdf")}, content_type="multipart/form-data")
    assert b"does not match" in r.data

    Entry.query.first().body = "Changed after the logbook was issued, which must be noticed."
    db.session.commit()
    assert b"NOT VALID" in client.get(f"/v/{rec.vid}").data
    assert b"NOT VALID" in client.get("/v/SW-00-XX-AAAA").data