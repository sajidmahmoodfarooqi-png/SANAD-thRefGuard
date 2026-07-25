"""Import a well-formatted reference list from CSV, Excel (.xlsx), and Word (.docx)."""
import base64
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from sanad_core import db, list_import
from sanad_core.server import create_app

CSV = """title,authors,year,journal,doi,type
The Art of Memory,"Fisher, R. K.",2001,,,book
A framework for distributed caching,"Nguyen, L.; Ortega, P. M.",2016,Journal of Systems Engineering,10.1234/jse.2016.014,journal
"""


def _xlsx_bytes(rows):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _docx_bytes(paragraphs):
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    ps = "".join(f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs)
    doc = f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{ps}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


# --- CSV ------------------------------------------------------------------- #

def test_parse_csv_maps_columns_and_authors():
    rows = list_import.parse_csv(CSV)
    assert len(rows) == 2
    f0, a0 = rows[0]
    assert f0["title"] == "The Art of Memory"
    assert f0["item_type"] == "book"
    assert f0["year"] == 2001
    assert a0 == [{"family": "Fisher", "given": "R. K."}]
    f1, a1 = rows[1]
    assert f1["doi"] == "10.1234/jse.2016.014"
    assert f1["container_title"] == "Journal of Systems Engineering"
    assert [x["family"] for x in a1] == ["Nguyen", "Ortega"]


def test_import_csv_end_to_end():
    conn = db.connect(":memory:")
    ids = list_import.import_csv_text(conn, CSV)
    assert len(ids) == 2
    assert conn.execute("SELECT COUNT(*) c FROM reference").fetchone()["c"] == 2
    row = conn.execute("SELECT item_type, year FROM reference WHERE title LIKE 'The Art%'").fetchone()
    assert row["item_type"] == "book" and row["year"] == 2001


# --- Excel ----------------------------------------------------------------- #

def test_parse_and_import_xlsx():
    data = _xlsx_bytes([
        ["Title", "Authors", "Year", "Journal", "DOI", "Type"],
        ["The Art of Memory", "Fisher, R. K.", 2001, "", "", "book"],
        ["A framework for distributed caching", "Nguyen, L.; Ortega, P. M.", 2016,
         "Journal of Systems Engineering", "10.1234/jse.2016.014", "journal"],
    ])
    rows = list_import.parse_xlsx(data)
    assert len(rows) == 2
    assert rows[0][0]["title"] == "The Art of Memory" and rows[0][0]["year"] == 2001
    conn = db.connect(":memory:")
    assert len(list_import.import_xlsx_bytes(conn, data)) == 2


# --- Word ------------------------------------------------------------------ #

def test_parse_and_import_docx():
    data = _docx_bytes([
        "References",  # a heading -> skipped
        "1. Fisher, R. K. (2001). The Art of Memory. Chandler Press.",
        "2. Bell, A., Carter, M. (2003). Notes on manuscript preservation. Archival Quarterly, 44(2), 219-231.",
    ])
    rows = list_import.parse_docx(data)
    assert len(rows) == 2  # the "References" heading is not a reference
    years = sorted(f.get("year") for f, _ in rows)
    assert years == [2001, 2003]
    conn = db.connect(":memory:")
    assert len(list_import.import_docx_bytes(conn, data)) == 2


# --- through the API ------------------------------------------------------- #

@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "li.db")
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {app.state.token}"})
    return c


def test_api_import_csv(client):
    r = client.post("/v1/library/import", json={"format": "csv", "text": CSV})
    assert r.status_code == 200 and r.json()["imported"] == 2


def test_api_import_xlsx_base64(client):
    data = _xlsx_bytes([["Title", "Year"], ["A neutral paper", 2020]])
    r = client.post("/v1/library/import",
                    json={"format": "xlsx", "data_b64": base64.b64encode(data).decode()})
    assert r.status_code == 200 and r.json()["imported"] == 1


def test_api_import_docx_base64(client):
    data = _docx_bytes(["Smith, J. (2019). A study of things. Journal of Things, 1, 2-3."])
    r = client.post("/v1/library/import",
                    json={"format": "docx", "data_b64": base64.b64encode(data).decode()})
    assert r.status_code == 200 and r.json()["imported"] == 1


def test_api_xlsx_without_data_is_400(client):
    r = client.post("/v1/library/import", json={"format": "xlsx", "text": ""})
    assert r.status_code == 400
