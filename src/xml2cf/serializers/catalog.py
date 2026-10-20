from __future__ import annotations

from uuid import uuid4

from v8unpack import helper

from ..brace import deep_copy
from ..dump_parser import Attribute, MetaObject, TabularSection
from ..types import CATALOG_ATTRIBUTE, CATALOG_TABULAR_SECTION
from .base import (
    SerializedObject,
    load_template,
    patch_identity,
    set_include,
    synonym_brace,
)


def _type_pattern(type_names: list[str]) -> list:
    """Map Designer type XML to CF Pattern descriptor."""
    if not type_names:
        return ['"Pattern"', ['"S"']]
    t = type_names[0]
    if t in ("xs:string", "xs:string"):
        return ['"Pattern"', ['"S"']]
    if t in ("xs:boolean",):
        return ['"Pattern"', ['"B"']]
    if t in ("xs:decimal", "xs:integer"):
        return ['"Pattern"', ['"N"', "10", "0"]]
    if t.startswith("cfg:CatalogRef.") or t.startswith("cfg:EnumRef."):
        # Untyped reference placeholder — UUID of type unknown without full link table
        return ['"Pattern"', ['"S"', "36", "1"]]
    if t.startswith("xs:"):
        return ['"Pattern"', ['"S"']]
    return ['"Pattern"', ['"S"']]


def _attribute_entry(attr: Attribute) -> list:
    tpl = deep_copy(load_template("catalog_attribute"))
    # tpl structure: [["5", ["27", ["2", identity, pattern], ...flags], ...], "0"]
    ident = tpl[0][1][1][1]
    uid = attr.uuid or str(uuid4())
    ident[2] = uid
    ident[3] = helper.str_encode(attr.name)
    ident[4] = synonym_brace(attr.synonym, attr.name)
    ident[5] = helper.str_encode(attr.comment or "")
    # pattern sibling
    tpl[0][1][1][2] = _type_pattern(attr.type_names)
    # bool template tweak
    if attr.type_names and attr.type_names[0] == "xs:boolean":
        bool_tpl = deep_copy(load_template("catalog_attribute_bool"))
        bool_ident = bool_tpl[0][1][1][1]
        bool_ident[2] = uid
        bool_ident[3] = helper.str_encode(attr.name)
        bool_ident[4] = synonym_brace(attr.synonym, attr.name)
        bool_ident[5] = helper.str_encode(attr.comment or "")
        return bool_tpl
    return tpl


def _ts_entry(ts: TabularSection) -> list:
    tpl = deep_copy(load_template("catalog_tabular_section"))
    # [["1", ["11", typeId, valueId, ..., ["0", ["2", ident...]], ...], attrs include], ...]
    block = tpl[0][1]
    gens = ts.generated
    if "TabularSection" in gens and gens["TabularSection"][0]:
        block[1] = gens["TabularSection"][0]
    if "TabularSectionRow" in gens and gens["TabularSectionRow"][0]:
        block[2] = gens["TabularSectionRow"][0]
    # TS identity shape: ["2", ["1", "0", uuid], "\"Name\"", synonym, "\"comment\"", ...]
    ident = None

    def find_ident(node):
        nonlocal ident
        if not isinstance(node, list):
            return
        if (
            len(node) >= 5
            and node[0] == "2"
            and isinstance(node[1], list)
            and len(node[1]) >= 3
            and isinstance(node[2], str)
            and node[2].startswith('"')
        ):
            ident = node
            return
        for x in node:
            find_ident(x)
            if ident is not None:
                return

    find_ident(block)
    if ident is not None:
        ident[1][2] = ts.uuid or str(uuid4())
        ident[2] = helper.str_encode(ts.name)
        ident[3] = synonym_brace(ts.synonym, ts.name)
        ident[4] = helper.str_encode(ts.comment or "")

    # Nested attributes of tabular section: type 888744e1... (TS attribute)
    TS_ATTR = "888744e1-b616-11d4-9436-004095e12fc7"
    ts_attrs = [_attribute_entry(a) for a in ts.attributes]
    # TS attribute entries use a slightly different wrapper in real CF ("8" instead of "5")
    # For MVP reuse catalog attribute shape; set_include on TS block
    try:
        set_include(tpl, TS_ATTR, ts_attrs)
    except ValueError:
        pass
    return tpl


def serialize_catalog(obj: MetaObject) -> SerializedObject:
    tpl = load_template("Catalog")
    header = deep_copy(tpl["header"])
    patch_identity(
        header,
        uuid=obj.uuid,
        name=obj.name,
        synonym=obj.synonym,
        comment=obj.comment,
    )
    block = header[0][1]
    # Catalog generated types: Object, Ref, Selection, List, Manager — slots 1..8 in template
    # Template starts: ["53", uuid1..uuid8, identity, ...]
    gen_order = ["Object", "Ref", "Selection", "List", "Manager"]
    # Map first 5 type ids if present
    for i, cat in enumerate(gen_order):
        idx = 1 + i
        if idx < len(block) and cat in obj.generated and obj.generated[cat][0]:
            block[idx] = obj.generated[cat][0]

    # CodeLength / DescriptionLength
    if "CodeLength" in obj.props:
        # positions vary; best-effort scan for "9" default code length near identity
        pass
    try:
        # common positions in 802 catalog template after identity
        # leave template defaults unless obvious
        if obj.props.get("CodeLength"):
            # find first "9" after identity that looks like CodeLength — skip for safety
            pass
    except Exception:
        pass

    attr_entries = [_attribute_entry(a) for a in obj.attributes]
    set_include(header, CATALOG_ATTRIBUTE, attr_entries)

    ts_entries = [_ts_entry(ts) for ts in obj.tabular_sections]
    set_include(header, CATALOG_TABULAR_SECTION, ts_entries)

    return SerializedObject(
        uuid=obj.uuid,
        type_name="Catalog",
        name=obj.name,
        files={obj.uuid: header},
    )
