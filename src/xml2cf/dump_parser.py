"""Parse hierarchical Designer XML dumps (Configuration.xml + object tree)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import SUPPORTED

NS = {
    "md": "http://v8.1c.ru/8.3/MDClasses",
    "xr": "http://v8.1c.ru/8.3/xcf/readable",
    "v8": "http://v8.1c.ru/8.1/data/core",
    "app": "http://v8.1c.ru/8.2/managed-application/core",
}


@dataclass
class LocalString:
    items: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_elem(cls, elem: ET.Element | None) -> "LocalString":
        if elem is None:
            return cls()
        items: dict[str, str] = {}
        for item in elem:
            if item.tag.split("}")[-1] != "item":
                continue
            lang = ""
            content = ""
            for ch in item:
                t = ch.tag.split("}")[-1]
                if t == "lang":
                    lang = (ch.text or "").strip()
                elif t == "content":
                    content = (ch.text or "").strip()
            if lang:
                items[lang] = content
        return cls(items)

    def ru(self, fallback: str = "") -> str:
        return self.items.get("ru") or next(iter(self.items.values()), fallback)


@dataclass
class Attribute:
    uuid: str
    name: str
    synonym: LocalString
    comment: str
    type_names: list[str]  # e.g. ["xs:string"], ["cfg:CatalogRef.X"]


@dataclass
class TabularSection:
    uuid: str
    name: str
    synonym: LocalString
    comment: str
    attributes: list[Attribute] = field(default_factory=list)
    generated: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass
class EnumValue:
    uuid: str
    name: str
    synonym: LocalString
    comment: str


@dataclass
class MetaObject:
    type_name: str
    uuid: str
    name: str
    synonym: LocalString
    comment: str
    path: Path
    props: dict[str, str] = field(default_factory=dict)
    generated: dict[str, tuple[str, str]] = field(default_factory=dict)
    attributes: list[Attribute] = field(default_factory=list)
    tabular_sections: list[TabularSection] = field(default_factory=list)
    enum_values: list[EnumValue] = field(default_factory=list)
    module_path: Path | None = None  # Ext/Module.bsl for CommonModule


@dataclass
class ConfigurationDump:
    root: Path
    uuid: str
    name: str
    synonym: LocalString
    comment: str
    vendor: str
    version: str
    compatibility_mode: str
    default_language: str  # Language.Name
    format_version: str
    script_variant: str
    contained: dict[str, str]  # ClassId -> ObjectId (InternalInfo groups)
    child_names: dict[str, list[str]]  # type -> [object names]
    objects: list[MetaObject]


def _tag(elem: ET.Element) -> str:
    return elem.tag.split("}")[-1]


def _child(parent: ET.Element, name: str) -> ET.Element | None:
    for ch in parent:
        if _tag(ch) == name:
            return ch
    return None


def _children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [ch for ch in parent if _tag(ch) == name]


def _local(tag_parent: ET.Element, tag: str) -> LocalString:
    return LocalString.from_elem(_child(tag_parent, tag))


def _text(parent: ET.Element, tag: str, default: str = "") -> str:
    node = _child(parent, tag)
    if node is None:
        return default
    return (node.text or "").strip()


def _parse_types(type_elem: ET.Element | None) -> list[str]:
    if type_elem is None:
        return []
    names: list[str] = []
    for t in type_elem:
        if _tag(t) == "Type" and t.text:
            names.append(t.text.strip())
        elif t.text and _tag(t).endswith("Type"):
            names.append(t.text.strip())
    # also accept direct v8:Type children already matched
    if not names:
        for t in type_elem:
            if t.text and "Type" in _tag(t):
                names.append(t.text.strip())
    return names


def _parse_attribute(elem: ET.Element) -> Attribute:
    props = _child(elem, "Properties")
    if props is None:
        props = elem
    return Attribute(
        uuid=elem.get("uuid", ""),
        name=_text(props, "Name"),
        synonym=_local(props, "Synonym"),
        comment=_text(props, "Comment"),
        type_names=_parse_types(_child(props, "Type")),
    )


def _parse_tabular_section(elem: ET.Element) -> TabularSection:
    props = _child(elem, "Properties")
    assert props is not None
    generated: dict[str, tuple[str, str]] = {}
    internal = _child(elem, "InternalInfo")
    if internal is not None:
        for gt in internal:
            if _tag(gt) != "GeneratedType":
                continue
            cat = gt.get("category", "")
            tid = ""
            vid = ""
            for gch in gt:
                if _tag(gch) == "TypeId":
                    tid = (gch.text or "").strip()
                elif _tag(gch) == "ValueId":
                    vid = (gch.text or "").strip()
            generated[cat] = (tid, vid)
    children = _child(elem, "ChildObjects")
    attrs: list[Attribute] = []
    if children is not None:
        for a in _children(children, "Attribute"):
            attrs.append(_parse_attribute(a))
    return TabularSection(
        uuid=elem.get("uuid", ""),
        name=_text(props, "Name"),
        synonym=_local(props, "Synonym"),
        comment=_text(props, "Comment"),
        attributes=attrs,
        generated=generated,
    )


def _parse_enum_value(elem: ET.Element) -> EnumValue:
    props = _child(elem, "Properties")
    if props is None:
        props = elem
    return EnumValue(
        uuid=elem.get("uuid", ""),
        name=_text(props, "Name"),
        synonym=_local(props, "Synonym"),
        comment=_text(props, "Comment"),
    )


def _parse_object(type_name: str, path: Path) -> MetaObject:
    tree = ET.parse(path)
    root = tree.getroot()
    obj = _child(root, type_name)
    if obj is None:
        raise ValueError(f"{path}: missing {type_name} element")

    props = _child(obj, "Properties")
    if props is None:
        raise ValueError(f"{path}: missing Properties")

    generated: dict[str, tuple[str, str]] = {}
    internal = _child(obj, "InternalInfo")
    if internal is not None:
        for gt in internal:
            if _tag(gt) != "GeneratedType":
                continue
            name = gt.get("name", "")
            cat = gt.get("category", "")
            tid = ""
            vid = ""
            for gch in gt:
                if _tag(gch) == "TypeId":
                    tid = (gch.text or "").strip()
                elif _tag(gch) == "ValueId":
                    vid = (gch.text or "").strip()
            generated[cat or name] = (tid, vid)

    attributes: list[Attribute] = []
    tabular_sections: list[TabularSection] = []
    enum_values: list[EnumValue] = []
    children = _child(obj, "ChildObjects")
    if children is not None:
        for ch in children:
            tag = _tag(ch)
            if tag == "Attribute":
                attributes.append(_parse_attribute(ch))
            elif tag == "TabularSection":
                tabular_sections.append(_parse_tabular_section(ch))
            elif tag == "EnumValue":
                enum_values.append(_parse_enum_value(ch))

    # Also load EnumValues from sibling folder Enums/Name/EnumValues/*.xml
    if type_name == "Enum":
        ev_dir = path.parent / path.stem / "EnumValues"
        if ev_dir.is_dir():
            for ev_file in sorted(ev_dir.glob("*.xml")):
                ev_tree = ET.parse(ev_file)
                ev_root = ev_tree.getroot()
                ev_elem = _child(ev_root, "EnumValue")
                if ev_elem is not None:
                    enum_values.append(_parse_enum_value(ev_elem))

    module_path = None
    if type_name == "CommonModule":
        cand = path.parent / path.stem / "Ext" / "Module.bsl"
        if cand.is_file():
            module_path = cand

    prop_map: dict[str, str] = {}
    for p in props:
        tag = _tag(p)
        if list(p):
            continue
        prop_map[tag] = (p.text or "").strip()

    return MetaObject(
        type_name=type_name,
        uuid=obj.get("uuid", ""),
        name=_text(props, "Name"),
        synonym=_local(props, "Synonym"),
        comment=_text(props, "Comment"),
        path=path,
        props=prop_map,
        generated=generated,
        attributes=attributes,
        tabular_sections=tabular_sections,
        enum_values=enum_values,
        module_path=module_path,
    )


def parse_dump(dump_dir: str | Path) -> ConfigurationDump:
    root = Path(dump_dir)
    cfg_path = root / "Configuration.xml"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"Configuration.xml not found in {root}")

    tree = ET.parse(cfg_path)
    md_root = tree.getroot()
    cfg = _child(md_root, "Configuration")
    if cfg is None:
        raise ValueError("Configuration element not found")

    format_version = md_root.get("version", "")
    props = _child(cfg, "Properties")
    if props is None:
        raise ValueError("Configuration/Properties missing")

    contained: dict[str, str] = {}
    internal = _child(cfg, "InternalInfo")
    if internal is not None:
        for co in internal:
            if _tag(co) != "ContainedObject":
                continue
            cid = ""
            oid = ""
            for gch in co:
                if _tag(gch) == "ClassId":
                    cid = (gch.text or "").strip()
                elif _tag(gch) == "ObjectId":
                    oid = (gch.text or "").strip()
            if cid and oid:
                contained[cid] = oid

    child_names: dict[str, list[str]] = {}
    children = _child(cfg, "ChildObjects")
    if children is not None:
        for ch in children:
            tag = _tag(ch)
            name = (ch.text or "").strip()
            if not name:
                continue
            child_names.setdefault(tag, []).append(name)

    objects: list[MetaObject] = []
    for type_name, names in child_names.items():
        meta = SUPPORTED.get(type_name)
        folder = meta.folder if meta else f"{type_name}s"
        # Designer folders: Languages, CommonModules, Catalogs, Enums, Constants
        for name in names:
            # try supported folder first, then generic
            candidates = []
            if meta:
                candidates.append(root / meta.folder / f"{name}.xml")
            candidates.append(root / folder / f"{name}.xml")
            # Language special: Languages/
            if type_name == "Language":
                candidates.insert(0, root / "Languages" / f"{name}.xml")
            path = next((p for p in candidates if p.is_file()), None)
            if path is None:
                raise FileNotFoundError(f"Object file not found for {type_name}.{name}")
            objects.append(_parse_object(type_name, path))

    default_lang = _text(props, "DefaultLanguage")
    if default_lang.startswith("Language."):
        default_lang = default_lang.split(".", 1)[1]

    return ConfigurationDump(
        root=root,
        uuid=cfg.get("uuid", ""),
        name=_text(props, "Name"),
        synonym=_local(props, "Synonym"),
        comment=_text(props, "Comment"),
        vendor=_text(props, "Vendor"),
        version=_text(props, "Version"),
        compatibility_mode=_text(props, "CompatibilityMode")
        or _text(props, "ConfigurationExtensionCompatibilityMode"),
        default_language=default_lang,
        format_version=format_version,
        script_variant=_text(props, "ScriptVariant", "Russian"),
        contained=contained,
        child_names=child_names,
        objects=objects,
    )


def inspect_dump(dump_dir: str | Path) -> dict[str, Any]:
    dump = parse_dump(dump_dir)
    unsupported = sorted(t for t in dump.child_names if t not in SUPPORTED)
    return {
        "name": dump.name,
        "uuid": dump.uuid,
        "format_version": dump.format_version,
        "compatibility_mode": dump.compatibility_mode,
        "default_language": dump.default_language,
        "object_counts": {t: len(names) for t, names in sorted(dump.child_names.items())},
        "supported": sorted(t for t in dump.child_names if t in SUPPORTED),
        "unsupported": unsupported,
        "objects": [
            {
                "type": o.type_name,
                "name": o.name,
                "uuid": o.uuid,
                "attributes": len(o.attributes),
                "tabular_sections": len(o.tabular_sections),
                "enum_values": len(o.enum_values),
            }
            for o in dump.objects
        ],
    }
