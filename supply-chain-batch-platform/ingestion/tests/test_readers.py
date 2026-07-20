import io
import json

from ingestion.readers import read_csv, read_entity, read_excel_sheet, read_json


def test_read_csv_preserves_leading_zeros_and_delimiter():
    data = b"material_id|qty\n00100000|5\n00100001|\n"
    rows = read_csv(data, delimiter="|")
    assert rows[0]["material_id"] == "00100000"  # not 100000
    assert rows[1]["qty"] == ""  # empty preserved, not NaN


def test_read_json_extracts_records():
    payload = {"totalSize": 2, "records": [{"Id": "C1"}, {"Id": "C2"}]}
    rows = read_json(json.dumps(payload).encode())
    assert [r["Id"] for r in rows] == ["C1", "C2"]


def test_read_excel_sheet_skips_title_row(tmp_path):
    # Build a workbook shaped like the generator's (title row above header).
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "price_list"
    ws.append(["Supplier Portal Export - price_list"])  # title row
    ws.append(["supplier_id", "unit_price"])  # header
    ws.append(["V00001", "12.50"])
    ws.append([None, None])  # blank trailing row
    buf = io.BytesIO()
    wb.save(buf)

    rows = read_excel_sheet(buf.getvalue(), sheet="price_list")
    assert len(rows) == 1
    assert rows[0]["supplier_id"] == "V00001"


def test_read_entity_dispatch_and_unknown():
    assert read_entity(b'{"records":[{"a":1}]}', fmt="json") == [{"a": 1}]
    try:
        read_entity(b"", fmt="avro")
        raised = False
    except ValueError:
        raised = True
    assert raised
