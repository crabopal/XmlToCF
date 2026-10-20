"""CF container unpack / pack (32-bit skeleton layout)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from v8unpack import helper
from v8unpack.container import Container
from v8unpack.container_doc import Document
from v8unpack.container_reader import extract as _extract


def unpack_cf(cf_path: str | Path, dest_dir: str | Path) -> Path:
    """Unpack .cf into dest_dir/0/… (deflated brace files)."""
    dest = Path(dest_dir)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _extract(str(cf_path), str(dest), deflate=True, recursive=False)
    return dest / "0"


def pack_cf(container0: str | Path, cf_path: str | Path) -> None:
    """Pack deflated brace files from folder `0` into a .cf container.

    Files are zlib-compressed (raw deflate) then stored without a second inflate
    pass — works around v8unpack Container.add_file(inflate=True) returning None.
    """
    container0 = Path(container0)
    if container0.name != "0":
        raise ValueError("Expected container folder named '0'")
    out = Path(cf_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="xml2cf-pack-") as tmp:
        compressed_root = Path(tmp) / "c"
        compressed0 = compressed_root / "0"
        compressed0.mkdir(parents=True)
        for entry in sorted(container0.iterdir()):
            dest = compressed0 / entry.name
            if entry.is_dir():
                # Nested container (e.g. uuid.0 module): build then compress
                with tempfile.TemporaryFile() as nested_bin:
                    nested = Container()
                    nested.build(nested_bin, str(entry), nested=True)
                    nested_bin.seek(0)
                    with open(dest, "w+b") as out_fd:
                        Document.compress(nested_bin, out_fd)
            else:
                with open(entry, "rb") as src_fd, open(dest, "w+b") as out_fd:
                    Document.compress(src_fd, out_fd)

        with open(out, "w+b") as f:
            container = Container()
            container.build(f, str(compressed0), nested=True)


def rebuild_versions(container0: str | Path) -> None:
    """Rewrite `versions` using UUID placeholders (same strategy as v8unpack)."""
    folder = Path(container0)
    file_list = sorted(
        p.name for p in folder.iterdir() if p.is_file() and p.name != "versions"
    )
    # include nested dir names (uuid.0) as version entries too
    for p in sorted(folder.iterdir()):
        if p.is_dir() and p.name not in file_list:
            file_list.append(p.name)
    file_list = sorted(set(file_list))
    versions = ["1", str(len(file_list) + 1), helper.str_encode(""), str(uuid4())]
    for name in file_list:
        versions.append(helper.str_encode(name))
        versions.append(str(uuid4()))
    helper.brace_file_write([versions], str(folder), "versions")


def unpack_bytes(data: bytes, dest_dir: str | Path) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".cf", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return unpack_cf(tmp_path, dest_dir)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
