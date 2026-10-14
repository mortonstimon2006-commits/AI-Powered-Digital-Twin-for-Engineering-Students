from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import docx
from sqlalchemy import text

from tests.conftest import STRONG_PASSWORD
from tests.test_rag import fake_vectors  # noqa: F401 - fixture re-export

API = "/api/v1"

RESUME = """Asha Kulkarni
asha@example.edu | +91 98765 43210 | github.com/asha

Education
B.Tech Information Technology, 2027 — CGPA 8.4

Skills
Python, SQL, pandas, Power BI, Docker, Tableau

Projects
Sales dashboard
- Worked on a dashboard in Power BI using SQL queries over 2 years of sales data
- Helped clean data with pandas

Experience
Data intern, Example Analytics (3 months)
- Responsible for weekly reports
"""


def make_pdf(text_line: str) -> bytes:
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = f"BT /F1 12 Tf 72 712 Td ({text_line}) Tj ET".encode()
    objs[3] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def make_docx(paragraphs: list[str]) -> bytes:
    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def upload(client, data: bytes, name: str, kind: str = "resume"):
    return client.post(f"{API}/documents", files={"file": (name, data, "application/octet-stream")}, data={"kind": kind})


def test_resume_upload_txt_analysis(seeded, student, fake_vectors):  # noqa: F811
    c = student()
    r = upload(c, RESUME.encode(), "resume.txt")
    assert r.status_code == 201, r.text
    d = r.json()
    names = {s["name"] for s in d["extracted"]["skills"]}
    assert {"Python", "SQL", "Data Wrangling", "BI & Dashboards", "Docker & Containers"} <= names
    codes = {s["code"] for s in d["extracted"]["suggestions"]}
    assert "weak_verbs" in codes and "unsupported_skills" in codes
    assert d["status"] == "indexed" and d["chunk_count"] >= 1
    assert "98765" not in str(d["extracted"]) and "asha@example.edu" not in str(d["extracted"])  # no contact data stored
    assert d["retention_until"] is not None


def test_resume_upload_pdf_and_docx(seeded, student, fake_vectors):  # noqa: F811
    c = student()
    r = upload(c, make_pdf("Skills: Python and SQL and Docker"), "cv.pdf")
    assert r.status_code == 201, r.text
    assert {"Python", "SQL"} <= {s["name"] for s in r.json()["extracted"]["skills"]}
    r = upload(c, make_docx(["Projects", "Built a React app with FastAPI backend"]), "cv.docx")
    assert r.status_code == 201, r.text
    assert {"React", "Server-side Web Frameworks"} <= {s["name"] for s in r.json()["extracted"]["skills"]}


def test_malicious_and_invalid_files_rejected(seeded, student):
    c = student()
    assert upload(c, b"MZ\x90\x00" + b"\x00" * 100, "resume.pdf").status_code == 422  # executable renamed .pdf
    assert upload(c, b"", "empty.txt").status_code == 422
    assert upload(c, "résumé".encode("latin-1"), "latin.txt").status_code == 422  # not UTF-8
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.txt", "just a zip")
    assert upload(c, buf.getvalue(), "file.docx").status_code == 422  # zip that is not a docx
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "A" * (40 * 1024 * 1024))  # expands to 40 MB
    assert upload(c, bomb.getvalue(), "bomb.docx").json()["error"]["code"] == "file_rejected"
    macro = io.BytesIO()
    with zipfile.ZipFile(macro, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
        zf.writestr("word/vbaProject.bin", "macro")
    assert upload(c, macro.getvalue(), "macro.docx").status_code == 422
    big = b"a" * (6 * 1024 * 1024)
    assert upload(c, big, "big.txt").status_code == 413


def test_document_access_control_and_deletion(seeded, student, fake_vectors):  # noqa: F811
    a, b = student("a@example.edu"), student("b@example.edu")
    doc = upload(a, RESUME.encode(), "../../etc/passwd").json()
    assert doc["original_filename"] == "passwd"  # path components stripped
    assert b.get(f"{API}/documents/{doc['id']}").status_code == 404
    assert b.get(f"{API}/documents/{doc['id']}/download").status_code == 404
    dl = a.get(f"{API}/documents/{doc['id']}/download")
    assert dl.status_code == 200 and dl.headers["content-disposition"].startswith("attachment")
    assert dl.headers["x-content-type-options"] == "nosniff"
    stored = list((Path(os.environ["DATA_DIR"]) / "uploads").rglob("*.txt"))
    assert stored and all("passwd" not in p.name for p in stored)
    assert a.delete(f"{API}/documents/{doc['id']}").status_code == 200
    assert a.get(f"{API}/documents/{doc['id']}").status_code == 404


def test_confirm_resume_skills_and_jd_compare(seeded, student, fake_vectors):  # noqa: F811
    c = student()
    doc = upload(c, RESUME.encode(), "resume.txt").json()
    sql = next(s for s in doc["extracted"]["skills"] if s["name"] == "SQL")
    react_id = next(s["id"] for s in c.get(f"{API}/catalogue/skills").json()["skills"] if s["slug"] == "react")
    bad = c.post(f"{API}/documents/{doc['id']}/confirm-skills", json={"skills": [{"skill_id": react_id, "self_rating": 3}]})
    assert bad.status_code == 422  # cannot smuggle in skills the resume did not mention
    ok = c.post(f"{API}/documents/{doc['id']}/confirm-skills", json={"skills": [{"skill_id": sql["skill_id"], "self_rating": 2}]})
    assert ok.status_code == 200
    skill = next(s for s in c.get(f"{API}/twin/skills").json()["items"] if s["skill_id"] == sql["skill_id"])
    assert skill["status"] == "self_reported"  # confirmed resume skills are still only self-reported
    jd = c.post(
        f"{API}/documents/job-description",
        json={
            "title": "Junior Data Analyst",
            "text": "Requirements:\n- Strong SQL and Excel pivot tables\n- Power BI dashboards\nNice to have:\n- Python, A/B testing",
        },
    )
    assert jd.status_code == 201
    cmp_ = c.post(f"{API}/documents/compare", json={"job_description_id": jd.json()["id"], "resume_id": doc["id"]}).json()
    rows = {r["skill"]: r for r in cmp_["skills"]}
    assert rows["SQL"]["status"] == "claimed" and rows["SQL"]["in_resume"] is True
    assert rows["Experimentation & A/B Testing"]["status"] == "missing"
    assert cmp_["closest_roles"][0]["role_name"] == "Data Analyst"


def test_consents_and_attendance_purpose_limitation(seeded, student):
    c = student()
    items = {i["purpose"]: i for i in c.get(f"{API}/privacy/consents").json()["items"]}
    assert items["profile_processing"]["granted"] and not items["mentor_sharing"]["granted"]
    assert c.put(f"{API}/privacy/consents/profile_processing", json={"granted": False}).status_code == 422
    c.put(f"{API}/privacy/consents/attendance_data", json={"granted": True})
    assert c.put(f"{API}/profile", json={"attendance_pct": 88}).json()["attendance_pct"] == 88
    c.put(f"{API}/privacy/consents/attendance_data", json={"granted": False})
    assert c.get(f"{API}/profile").json()["attendance_pct"] is None


def test_export_contains_own_data_without_secrets(seeded, student):
    a, b = student("a@example.edu"), student("b@example.edu")
    a.post(f"{API}/twin/projects", json={"title": "Alpha project"})
    b.post(f"{API}/twin/projects", json={"title": "Bravo project"})
    r = a.get(f"{API}/privacy/export")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    body = r.text
    assert "Alpha project" in body and "Bravo project" not in body and "b@example.edu" not in body
    assert "argon2" not in body and "token_hash" not in body and "csrf_hash" not in body
    assert r.json()["projects"][0]["title"] == "Alpha project"


def test_account_deletion_is_complete(seeded, student, owner_engine, fake_vectors):  # noqa: F811
    c = student("gone@example.edu")
    c.post(f"{API}/twin/projects", json={"title": "Doomed"})
    upload(c, RESUME.encode(), "resume.txt")
    uid = c.get(f"{API}/auth/me").json()["user"]["id"]
    bad = c.post(f"{API}/privacy/delete-account", json={"password": "wrong-password-xx", "confirmation": "DELETE MY ACCOUNT"})
    assert bad.status_code == 400
    assert c.post(f"{API}/privacy/delete-account", json={"password": STRONG_PASSWORD, "confirmation": "nope"}).status_code == 422
    ok = c.post(f"{API}/privacy/delete-account", json={"password": STRONG_PASSWORD, "confirmation": "DELETE MY ACCOUNT"})
    assert ok.status_code == 200
    with owner_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users WHERE email='gone@example.edu'")).scalar_one() == 0
        for table in ("projects", "documents", "twin_snapshots", "consents", "user_sessions", "student_profiles"):
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0, table  # noqa: S608
        assert conn.execute(text("SELECT count(*) FROM audit_events WHERE action='privacy.account_deleted'")).scalar_one() == 1
    assert not (Path(os.environ["DATA_DIR"]) / "uploads" / uid).exists()
    assert c.post(f"{API}/auth/login", json={"email": "gone@example.edu", "password": STRONG_PASSWORD}).status_code == 401


def test_retention_removes_expired_documents(seeded, student, owner_engine, fake_vectors):  # noqa: F811
    from app.db import system_session
    from app.services.privacy import apply_retention

    c = student()
    doc = upload(c, RESUME.encode(), "resume.txt").json()
    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE documents SET retention_until = now() - interval '1 day'"))
    with system_session() as db:
        result = apply_retention(db)
    assert result["documents"] == 1
    assert c.get(f"{API}/documents/{doc['id']}").status_code == 404
