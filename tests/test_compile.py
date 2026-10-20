from __future__ import annotations

import json
from pathlib import Path

import pytest
from v8unpack import helper

from xml2cf.compiler import compile_dump, inspect_dump, supported_types, unpack_cf
from xml2cf.layout import current_layout

FIXTURES = Path(__file__).parent / "fixtures"
EMPTY = FIXTURES / "cf-empty-infobase"
SMALL = FIXTURES / "cf-small"


def test_supported_types_lists_mvp():
    types = supported_types()
    assert "Catalog" in types
    assert "Enum" in types
    assert "Language" in types
    assert current_layout().id == "32bit"


def test_inspect_empty():
    info = inspect_dump(EMPTY)
    assert info["name"]
    assert "Language" in info["object_counts"]
    assert info["unsupported"] == []


def test_compile_empty_roundtrip(tmp_path: Path):
    out = tmp_path / "empty.cf"
    report = compile_dump(EMPTY, out)
    assert report.ok, report.error
    assert out.is_file() and out.stat().st_size > 100

    dest = tmp_path / "unpacked"
    folder = unpack_cf(out, dest)
    names = {p.name for p in folder.iterdir()}
    assert "root" in names
    assert "version" in names
    assert "versions" in names
    root = helper.brace_file_read(str(folder), "root")
    header = helper.brace_file_read(str(folder), root[0][1])
    blob = json.dumps(header, ensure_ascii=False)
    assert report.configuration_uuid in blob
    assert report.configuration_name in blob or f'"{report.configuration_name}"' in blob


def test_compile_small_catalog_enum(tmp_path: Path):
    out = tmp_path / "small.cf"
    report = compile_dump(SMALL, out)
    assert report.ok, report.error
    by_type = {o["type"]: o for o in report.objects}
    assert by_type["Catalog"]["name"] == "Товары"
    assert by_type["Catalog"]["attributes"] == 1
    assert by_type["Catalog"]["tabular_sections"] == 1
    assert by_type["Enum"]["name"] == "Статусы"
    assert by_type["Enum"]["enum_values"] == 2

    folder = unpack_cf(out, tmp_path / "u")
    # object uuid files present
    cat_uuid = by_type["Catalog"]["uuid"]
    enum_uuid = by_type["Enum"]["uuid"]
    assert (folder / cat_uuid).is_file()
    assert (folder / enum_uuid).is_file()
    cat_header = helper.brace_file_read(str(folder), cat_uuid)
    text = json.dumps(cat_header, ensure_ascii=False)
    assert "Товары" in text
    assert "Артикул" in text
    assert "Цены" in text
    enum_header = helper.brace_file_read(str(folder), enum_uuid)
    etext = json.dumps(enum_header, ensure_ascii=False)
    assert "Статусы" in etext
    assert "Новый" in etext
    assert "Закрыт" in etext


def test_fail_loud_unsupported(tmp_path: Path):
    # clone empty and add a Document child reference without supporting it
    dump = tmp_path / "bad"
    import shutil

    shutil.copytree(EMPTY, dump)
    cfg = (dump / "Configuration.xml").read_text(encoding="utf-8")
    cfg = cfg.replace("</ChildObjects>", "\t\t<Document>Док1</Document>\n\t</ChildObjects>")
    (dump / "Configuration.xml").write_text(cfg, encoding="utf-8")
    (dump / "Documents").mkdir()
    (dump / "Documents" / "Док1.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.17">
  <Document uuid="11111111-1111-1111-1111-111111111111">
    <Properties><Name>Док1</Name><Synonym/><Comment/></Properties>
    <ChildObjects/>
  </Document>
</MetaDataObject>
""",
        encoding="utf-8",
    )
    report = compile_dump(dump, tmp_path / "x.cf")
    assert not report.ok
    assert "Document" in (report.error or "")


def test_compile_report_json(tmp_path: Path):
    report = compile_dump(EMPTY, tmp_path / "e.cf")
    data = json.loads(report.to_json())
    assert data["ok"] is True
    assert data["layout"] == "32bit"
