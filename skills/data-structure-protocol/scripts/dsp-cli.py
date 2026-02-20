#!/usr/bin/env python3
"""dsp-cli — Data Structure Protocol CLI.

Production-ready CLI for building and navigating DSP project graphs.
Used by LLM agents to maintain long-term structural memory of codebases.

Operations mirror ARCHITECTURE.md §5 exactly.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import uuid
from collections import deque
from pathlib import Path

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Constants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") not in ("utf8", "utf16"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
if sys.stderr.encoding and sys.stderr.encoding.lower().replace("-", "") not in ("utf8", "utf16"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

DSP_DIR = ".dsp"
DESC_FILE = "description"
IMPORTS_FILE = "imports"
SHARED_FILE = "shared"
EXPORTS_DIR = "exports"
TOC_BASE = "TOC"

_MAX_DEPTH = 10**6


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Low-level helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _gen_uid(kind: str) -> str:
    prefix = "func" if kind == "function" else "obj"
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _parse_import_line(line: str) -> tuple[str, str | None]:
    parts = line.split()
    if not parts:
        return "", None
    uid = parts[0]
    via: str | None = None
    for p in parts[1:]:
        if p.startswith("via="):
            via = p[4:]
    return uid, via


def _format_import_line(uid: str, via: str | None) -> str:
    return f"{uid} via={via}" if via else uid


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _append_line_unique(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_lines(path)
    if line not in existing:
        existing.append(line)
        _write_lines(path, existing)


def _remove_line_value(path: Path, target: str) -> bool:
    lines = _read_lines(path)
    new = [ln for ln in lines if ln != target]
    changed = len(new) != len(lines)
    _write_lines(path, new)
    return changed


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _safe_unlink(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()


def _safe_rmtree(path: Path) -> None:
    if path.exists() and path.is_dir():
        shutil.rmtree(path)


def _fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Description parsing / serialization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_DESC_KEY_RE = re.compile(r"^([a-z_]+):\s?(.*)", re.DOTALL)
_DESC_ORDERED = ("source", "kind", "purpose")


def _parse_desc(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    cur_key: str | None = None
    cur_lines: list[str] = []
    for raw in text.splitlines():
        m = _DESC_KEY_RE.match(raw)
        if m:
            if cur_key is not None:
                result[cur_key] = "\n".join(cur_lines).strip()
            cur_key = m.group(1)
            cur_lines = [m.group(2)]
        elif cur_key is not None:
            cur_lines.append(raw)
    if cur_key is not None:
        result[cur_key] = "\n".join(cur_lines).strip()
    return result


def _serialize_desc(fields: dict[str, str]) -> str:
    lines: list[str] = []
    for k in _DESC_ORDERED:
        if k in fields:
            lines.append(f"{k}: {fields[k]}")
    for k, v in fields.items():
        if k not in _DESC_ORDERED:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Store — filesystem abstraction over .dsp/
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.base = self.root / DSP_DIR

    # ── guards ──

    def ensure_init(self) -> None:
        if not self.base.is_dir():
            _fail(f"directory {self.base} not found — run 'init' first")

    def entity_exists(self, uid: str) -> bool:
        return (self.base / uid).is_dir()

    def require_entity(self, uid: str) -> None:
        if not self.entity_exists(uid):
            _fail(f"entity {uid} does not exist")

    # ── uid enumeration ──

    def all_uids(self) -> list[str]:
        if not self.base.is_dir():
            return []
        return sorted(
            d.name
            for d in self.base.iterdir()
            if d.is_dir() and (d.name.startswith("obj-") or d.name.startswith("func-"))
        )

    # ── TOC ──

    def toc_path(self, root_uid: str | None = None) -> Path:
        if root_uid:
            return self.base / f"{TOC_BASE}-{root_uid}"
        return self.base / TOC_BASE

    def all_toc_paths(self) -> list[Path]:
        if not self.base.is_dir():
            return []
        return sorted(p for p in self.base.iterdir() if p.is_file() and p.name.startswith(TOC_BASE))

    # ── description ──

    def desc_path(self, uid: str) -> Path:
        return self.base / uid / DESC_FILE

    def read_desc(self, uid: str) -> dict[str, str]:
        return _parse_desc(_read_text(self.desc_path(uid)))

    def write_desc(self, uid: str, fields: dict[str, str]) -> None:
        _write_text(self.desc_path(uid), _serialize_desc(fields))

    # ── imports ──

    def imports_path(self, uid: str) -> Path:
        return self.base / uid / IMPORTS_FILE

    def read_imports(self, uid: str) -> list[tuple[str, str | None]]:
        return [_parse_import_line(ln) for ln in _read_lines(self.imports_path(uid)) if ln]

    def read_import_uids(self, uid: str) -> list[str]:
        return [i[0] for i in self.read_imports(uid) if i[0]]

    # ── shared ──

    def shared_path(self, uid: str) -> Path:
        return self.base / uid / SHARED_FILE

    def read_shared(self, uid: str) -> list[str]:
        return _read_lines(self.shared_path(uid))

    # ── exports ──

    def exports_dir(self, uid: str) -> Path:
        return self.base / uid / EXPORTS_DIR

    def read_direct_recipients(self, uid: str) -> list[tuple[str, str]]:
        d = self.exports_dir(uid)
        if not d.is_dir():
            return []
        return [(e.name, _read_text(e)) for e in sorted(d.iterdir()) if e.is_file()]

    def read_shared_recipients(self, uid: str) -> dict[str, list[tuple[str, str]]]:
        d = self.exports_dir(uid)
        if not d.is_dir():
            return {}
        result: dict[str, list[tuple[str, str]]] = {}
        for entry in sorted(d.iterdir()):
            if entry.is_dir():
                recs: list[tuple[str, str]] = []
                for f in sorted(entry.iterdir()):
                    if f.is_file() and f.name != DESC_FILE:
                        recs.append((f.name, _read_text(f)))
                result[entry.name] = recs
        return result

    def read_shared_export_desc(self, uid: str, shared_uid: str) -> str:
        return _read_text(self.exports_dir(uid) / shared_uid / DESC_FILE)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Engine — all DSP operations (ARCHITECTURE.md §5)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Engine:
    def __init__(self, store: Store):
        self.s = store

    # ── init ──

    def init(self) -> None:
        self.s.base.mkdir(parents=True, exist_ok=True)
        print(f"initialized {self.s.base}")

    # ── §5.1 createObject ──

    def create_object(
        self, source: str, purpose: str, kind: str = "object", toc: str | None = None
    ) -> str:
        self.s.ensure_init()
        uid = _gen_uid("object")
        (self.s.base / uid).mkdir(parents=True)
        self.s.write_desc(uid, {"source": source, "kind": kind, "purpose": purpose})
        _write_lines(self.s.imports_path(uid), [])
        _write_lines(self.s.shared_path(uid), [])
        _append_line_unique(self.s.toc_path(toc), uid)
        return uid

    # ── §5.2 createFunction ──

    def create_function(
        self, source: str, purpose: str, owner: str | None = None, toc: str | None = None
    ) -> str:
        self.s.ensure_init()
        uid = _gen_uid("function")
        (self.s.base / uid).mkdir(parents=True)
        self.s.write_desc(uid, {"source": source, "kind": "function", "purpose": purpose})
        _write_lines(self.s.imports_path(uid), [])
        if owner:
            self.s.require_entity(owner)
            _append_line_unique(self.s.imports_path(owner), uid)
            exp = self.s.exports_dir(uid)
            exp.mkdir(parents=True, exist_ok=True)
            _write_text(exp / owner, "owner: method/member of this object")
        _append_line_unique(self.s.toc_path(toc), uid)
        return uid

    # ── §5.3 createShared ──

    def create_shared(self, exporter: str, shared_uids: list[str]) -> None:
        self.s.ensure_init()
        self.s.require_entity(exporter)
        exp_dir = self.s.exports_dir(exporter)
        exp_dir.mkdir(parents=True, exist_ok=True)
        for sid in shared_uids:
            _append_line_unique(self.s.shared_path(exporter), sid)
            shared_sub = exp_dir / sid
            shared_sub.mkdir(parents=True, exist_ok=True)
            desc_path = shared_sub / DESC_FILE
            if not desc_path.exists():
                purpose = ""
                if self.s.entity_exists(sid):
                    purpose = self.s.read_desc(sid).get("purpose", "")
                _write_text(desc_path, purpose if purpose else sid)

    # ── §5.4 addImport ──

    def add_import(
        self, importer: str, imported: str, why: str, exporter: str | None = None
    ) -> None:
        self.s.ensure_init()
        self.s.require_entity(importer)
        line = _format_import_line(imported, exporter)
        _append_line_unique(self.s.imports_path(importer), line)
        if exporter:
            self.s.require_entity(exporter)
            rev_dir = self.s.exports_dir(exporter) / imported
            rev_dir.mkdir(parents=True, exist_ok=True)
            _write_text(rev_dir / importer, why)
        else:
            self.s.require_entity(imported)
            exp = self.s.exports_dir(imported)
            exp.mkdir(parents=True, exist_ok=True)
            _write_text(exp / importer, why)

    # ── §5.5 updateDescription ──

    def update_description(self, uid: str, fields: dict[str, str]) -> None:
        self.s.ensure_init()
        self.s.require_entity(uid)
        current = self.s.read_desc(uid)
        current.update(fields)
        self.s.write_desc(uid, current)

    # ── §5.6 updateImportWhy ──

    def update_import_why(
        self, importer: str, imported: str, new_why: str, exporter: str | None = None
    ) -> None:
        self.s.ensure_init()
        if exporter:
            path = self.s.exports_dir(exporter) / imported / importer
        else:
            path = self.s.exports_dir(imported) / importer
        if not path.exists():
            _fail(f"reverse entry not found: {imported} ← {importer}" + (f" via {exporter}" if exporter else ""))
        _write_text(path, new_why)

    # ── §5.7 moveEntity ──

    def move_entity(self, uid: str, new_source: str) -> None:
        self.s.ensure_init()
        self.s.require_entity(uid)
        desc = self.s.read_desc(uid)
        desc["source"] = new_source
        self.s.write_desc(uid, desc)

    # ── §5.8 removeImport ──

    def remove_import(self, importer: str, imported: str, exporter: str | None = None) -> None:
        self.s.ensure_init()
        self.s.require_entity(importer)
        imports = self.s.read_imports(importer)
        new_lines: list[str] = []
        removed = False
        for imp_uid, imp_via in imports:
            if imp_uid == imported and not removed:
                if exporter is None or imp_via == exporter:
                    removed = True
                    continue
            new_lines.append(_format_import_line(imp_uid, imp_via))
        _write_lines(self.s.imports_path(importer), new_lines)
        if exporter:
            _safe_unlink(self.s.exports_dir(exporter) / imported / importer)
        else:
            _safe_unlink(self.s.exports_dir(imported) / importer)

    # ── §5.9 removeShared ──

    def remove_shared(self, exporter: str, shared_uid: str) -> None:
        self.s.ensure_init()
        self.s.require_entity(exporter)
        _remove_line_value(self.s.shared_path(exporter), shared_uid)
        shared_dir = self.s.exports_dir(exporter) / shared_uid
        if shared_dir.is_dir():
            for entry in list(shared_dir.iterdir()):
                if entry.is_file() and entry.name != DESC_FILE:
                    recipient_uid = entry.name
                    if self.s.entity_exists(recipient_uid):
                        imports = self.s.read_imports(recipient_uid)
                        new_lines = [
                            _format_import_line(u, v)
                            for u, v in imports
                            if not (u == shared_uid and v == exporter)
                        ]
                        _write_lines(self.s.imports_path(recipient_uid), new_lines)
            _safe_rmtree(shared_dir)

    # ── §5.10 removeEntity ──

    def remove_entity(self, uid: str) -> None:
        self.s.ensure_init()
        self.s.require_entity(uid)

        all_uids = self.s.all_uids()

        for other in all_uids:
            if other == uid:
                continue
            imports = self.s.read_imports(other)
            had = any(u == uid or v == uid for u, v in imports)
            if had:
                new_lines = [
                    _format_import_line(u, v)
                    for u, v in imports
                    if u != uid and v != uid
                ]
                _write_lines(self.s.imports_path(other), new_lines)

        for imp_uid, imp_via in self.s.read_imports(uid):
            if imp_via:
                _safe_unlink(self.s.exports_dir(imp_via) / imp_uid / uid)
            else:
                _safe_unlink(self.s.exports_dir(imp_uid) / uid)

        for other in all_uids:
            if other == uid:
                continue
            shared = self.s.read_shared(other)
            if uid in shared:
                _remove_line_value(self.s.shared_path(other), uid)
                _safe_rmtree(self.s.exports_dir(other) / uid)

        for toc in self.s.all_toc_paths():
            _remove_line_value(toc, uid)

        _safe_rmtree(self.s.base / uid)

    # ── §5.11 getEntity ──

    def get_entity(self, uid: str) -> dict:
        self.s.ensure_init()
        self.s.require_entity(uid)
        desc = self.s.read_desc(uid)
        imports = self.s.read_imports(uid)
        shared = self.s.read_shared(uid)
        recipients = self._all_importers(uid)
        return {
            "uid": uid,
            "description": desc,
            "imports": imports,
            "shared": shared,
            "exported_to": recipients,
        }

    # ── §5.12 getShared ──

    def get_shared(self, uid: str) -> list[dict]:
        self.s.ensure_init()
        self.s.require_entity(uid)
        shared_uids = self.s.read_shared(uid)
        result: list[dict] = []
        for sid in shared_uids:
            desc = self.s.read_shared_export_desc(uid, sid)
            recs: list[tuple[str, str]] = []
            sub = self.s.exports_dir(uid) / sid
            if sub.is_dir():
                for f in sorted(sub.iterdir()):
                    if f.is_file() and f.name != DESC_FILE:
                        recs.append((f.name, _read_text(f)))
            result.append({"shared_uid": sid, "description": desc, "recipients": recs})
        return result

    # ── §5.13 getRecipients ──

    def get_recipients(self, uid: str) -> list[tuple[str, str]]:
        self.s.ensure_init()
        self.s.require_entity(uid)
        return self._all_importers(uid)

    def _all_importers(self, uid: str) -> list[tuple[str, str]]:
        seen: set[str] = set()
        result: list[tuple[str, str]] = []

        for rec_uid, why in self.s.read_direct_recipients(uid):
            if rec_uid not in seen:
                result.append((rec_uid, why))
                seen.add(rec_uid)

        for other in self.s.all_uids():
            if uid in self.s.read_shared(other):
                sub = self.s.exports_dir(other) / uid
                if sub.is_dir():
                    for f in sorted(sub.iterdir()):
                        if f.is_file() and f.name != DESC_FILE and f.name not in seen:
                            result.append((f.name, _read_text(f)))
                            seen.add(f.name)

        for other in self.s.all_uids():
            if other in seen:
                continue
            for imp_uid, _ in self.s.read_imports(other):
                if imp_uid == uid:
                    result.append((other, ""))
                    seen.add(other)
                    break

        return result

    # ── §5.14 getChildren ──

    def get_children(self, uid: str, depth: int = 1) -> dict:
        self.s.ensure_init()
        self.s.require_entity(uid)
        visited: set[str] = set()

        def walk(u: str, d: int) -> dict:
            desc = self.s.read_desc(u) if self.s.entity_exists(u) else {}
            node: dict = {
                "uid": u,
                "kind": desc.get("kind", ""),
                "purpose": desc.get("purpose", ""),
                "children": [],
            }
            if u in visited:
                node["cycle"] = True
                return node
            visited.add(u)
            if d > 0:
                for imp_uid, _ in self.s.read_imports(u):
                    node["children"].append(walk(imp_uid, d - 1))
            return node

        return walk(uid, depth)

    # ── §5.15 getParents ──

    def get_parents(self, uid: str, depth: int = 1) -> dict:
        self.s.ensure_init()
        self.s.require_entity(uid)
        visited: set[str] = set()

        def walk(u: str, d: int) -> dict:
            desc = self.s.read_desc(u) if self.s.entity_exists(u) else {}
            node: dict = {
                "uid": u,
                "kind": desc.get("kind", ""),
                "purpose": desc.get("purpose", ""),
                "parents": [],
            }
            if u in visited:
                node["cycle"] = True
                return node
            visited.add(u)
            if d > 0:
                for rec_uid, why in self._all_importers(u):
                    child = walk(rec_uid, d - 1)
                    child["why"] = why
                    node["parents"].append(child)
            return node

        return walk(uid, depth)

    # ── §5.16 getPath ──

    def get_path(self, from_uid: str, to_uid: str) -> list[str] | None:
        self.s.ensure_init()
        self.s.require_entity(from_uid)
        self.s.require_entity(to_uid)
        if from_uid == to_uid:
            return [from_uid]

        visited: set[str] = {from_uid}
        queue: deque[tuple[str, list[str]]] = deque([(from_uid, [from_uid])])

        while queue:
            current, path = queue.popleft()
            neighbors: set[str] = set()
            for imp_uid, _ in self.s.read_imports(current):
                neighbors.add(imp_uid)
            for rec_uid, _ in self._all_importers(current):
                neighbors.add(rec_uid)
            for nb in sorted(neighbors):
                if nb == to_uid:
                    return path + [nb]
                if nb not in visited and self.s.entity_exists(nb):
                    visited.add(nb)
                    queue.append((nb, path + [nb]))
        return None

    # ── §5.17 search ──

    def search(self, query: str) -> list[dict]:
        self.s.ensure_init()
        q = query.lower()
        results: list[dict] = []
        for uid in self.s.all_uids():
            desc = self.s.read_desc(uid)
            for field, value in desc.items():
                if q in value.lower():
                    results.append({"uid": uid, "field": field, "match": value})
                    break
            else:
                exp = self.s.exports_dir(uid)
                if exp.is_dir():
                    for entry in exp.iterdir():
                        if q in entry.name.lower():
                            results.append({"uid": uid, "field": "exports", "match": entry.name})
                            break
        return results

    # ── §5.18 findBySource ──

    def find_by_source(self, source_path: str) -> list[str]:
        self.s.ensure_init()
        found: list[str] = []
        normalized = source_path.replace("\\", "/")
        for uid in self.s.all_uids():
            desc = self.s.read_desc(uid)
            src = desc.get("source", "").replace("\\", "/")
            if src == normalized or src.startswith(normalized + "#"):
                found.append(uid)
        return found

    # ── §5.19 readTOC ──

    def read_toc(self, root_uid: str | None = None) -> list[str]:
        self.s.ensure_init()
        toc = self.s.toc_path(root_uid)
        if not toc.exists():
            _fail(f"TOC file not found: {toc.name}")
        return _read_lines(toc)

    # ── §5.20 detectCycles ──

    def detect_cycles(self) -> list[list[str]]:
        self.s.ensure_init()
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {}
        path_stack: list[str] = []
        cycles: list[list[str]] = []
        all_uids = self.s.all_uids()
        for u in all_uids:
            color[u] = WHITE

        def dfs(u: str) -> None:
            color[u] = GRAY
            path_stack.append(u)
            for imp_uid in self.s.read_import_uids(u):
                c = color.get(imp_uid, -1)
                if c == GRAY:
                    idx = path_stack.index(imp_uid)
                    cycles.append(path_stack[idx:] + [imp_uid])
                elif c == WHITE:
                    dfs(imp_uid)
            path_stack.pop()
            color[u] = BLACK

        for u in all_uids:
            if color[u] == WHITE:
                dfs(u)
        return cycles

    # ── §5.21 getOrphans ──

    def get_orphans(self) -> list[str]:
        self.s.ensure_init()
        roots: set[str] = set()
        for toc in self.s.all_toc_paths():
            lines = _read_lines(toc)
            if lines:
                roots.add(lines[0])

        imported_uids: set[str] = set()
        for uid in self.s.all_uids():
            for imp_uid, imp_via in self.s.read_imports(uid):
                if imp_uid:
                    imported_uids.add(imp_uid)
                if imp_via:
                    imported_uids.add(imp_via)

        orphans: list[str] = []
        for uid in self.s.all_uids():
            if uid in roots:
                continue
            if uid in imported_uids:
                continue
            exp = self.s.exports_dir(uid)
            if exp.is_dir() and any(True for _ in exp.iterdir()):
                continue
            orphans.append(uid)
        return orphans

    # ── §5.22 getStats ──

    def get_stats(self) -> dict:
        self.s.ensure_init()
        uids = self.s.all_uids()
        objects = functions = externals = total_imports = total_shared = 0
        for uid in uids:
            desc = self.s.read_desc(uid)
            kind = desc.get("kind", "object")
            if kind == "external":
                externals += 1
            elif kind == "function":
                functions += 1
            else:
                objects += 1
            total_imports += len(self.s.read_import_uids(uid))
            total_shared += len(self.s.read_shared(uid))
        cycles = self.detect_cycles()
        orphans = self.get_orphans()
        return {
            "entities": len(uids),
            "objects": objects,
            "functions": functions,
            "externals": externals,
            "imports": total_imports,
            "shared": total_shared,
            "cycles": len(cycles),
            "orphans": len(orphans),
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Output formatting
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _kind_tag(kind: str) -> str:
    if kind and kind not in ("object",):
        return f" [{kind}]"
    return ""


def _print_tree(node: dict, key: str = "children") -> None:
    kt = _kind_tag(node.get("kind", ""))
    why_s = f"  (why: {node['why']})" if node.get("why") else ""
    print(f"{node['uid']}{kt}: {node.get('purpose', '')}{why_s}")
    children = node.get(key, [])
    for i, child in enumerate(children):
        _print_subtree(child, "", i == len(children) - 1, key)


def _print_subtree(node: dict, prefix: str, is_last: bool, key: str) -> None:
    conn = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
    kt = _kind_tag(node.get("kind", ""))
    cycle_mark = " \u21bb" if node.get("cycle") else ""
    why_s = f"  (why: {node['why']})" if node.get("why") else ""
    print(f"{prefix}{conn}{node['uid']}{kt}{cycle_mark}: {node.get('purpose', '')}{why_s}")
    if node.get("cycle"):
        return
    children = node.get(key, [])
    for i, child in enumerate(children):
        ext = "    " if is_last else "\u2502   "
        _print_subtree(child, prefix + ext, i == len(children) - 1, key)


def _print_entity(info: dict) -> None:
    desc = info["description"]
    print(f"uid: {info['uid']}")
    print(f"source: {desc.get('source', '')}")
    print(f"kind: {desc.get('kind', '')}")
    print(f"purpose: {desc.get('purpose', '')}")
    for k, v in desc.items():
        if k not in ("source", "kind", "purpose"):
            print(f"{k}: {v}")

    imp = info["imports"]
    if imp:
        print("\nimports:")
        for uid, via in imp:
            line = f"  {uid}"
            if via:
                line += f" via={via}"
            print(line)

    shared = info["shared"]
    if shared:
        print("\nshared:")
        for s in shared:
            print(f"  {s}")

    exp = info["exported_to"]
    if exp:
        print("\nexported to:")
        for rec_uid, why in exp:
            print(f"  {rec_uid}: {why}" if why else f"  {rec_uid}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI definition
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _depth_type(value: str) -> int:
    if value.lower() in ("inf", "infinity", "all"):
        return _MAX_DEPTH
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("depth must be >= 0")
    return n


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dsp-cli", description="Data Structure Protocol CLI")
    p.add_argument("--root", default=".", help="project root directory (default: cwd)")
    sub = p.add_subparsers(dest="command")
    sub.required = True

    # ── init ──
    sub.add_parser("init", help="initialize .dsp directory")

    # ── create-object ──
    sp = sub.add_parser("create-object", help="§5.1 create an Object entity")
    sp.add_argument("source", help="repo-relative source path")
    sp.add_argument("purpose", help="1-3 sentences: what and why")
    sp.add_argument("--kind", default="object", choices=["object", "external"], help="entity kind")
    sp.add_argument("--toc", default=None, metavar="ROOT_UID", help="TOC root uid (multi-root)")

    # ── create-function ──
    sp = sub.add_parser("create-function", help="§5.2 create a Function entity")
    sp.add_argument("source", help="repo-relative source path (with #symbol if needed)")
    sp.add_argument("purpose", help="1-3 sentences: what and why")
    sp.add_argument("--owner", default=None, metavar="UID", help="owner Object uid")
    sp.add_argument("--toc", default=None, metavar="ROOT_UID", help="TOC root uid (multi-root)")

    # ── create-shared ──
    sp = sub.add_parser("create-shared", help="§5.3 register shared/exported entities")
    sp.add_argument("exporter", help="exporter Object uid")
    sp.add_argument("shared", nargs="+", help="uid(s) of shared entities")

    # ── add-import ──
    sp = sub.add_parser("add-import", help="§5.4 add an import relationship")
    sp.add_argument("importer", help="importer entity uid")
    sp.add_argument("imported", help="imported entity uid")
    sp.add_argument("why", help="1-3 sentences: why this is imported")
    sp.add_argument("--exporter", default=None, metavar="UID", help="exporter Object uid (for shared imports)")

    # ── update-description ──
    sp = sub.add_parser("update-description", help="§5.5 update entity description fields")
    sp.add_argument("uid", help="entity uid")
    sp.add_argument("--source", default=None, dest="new_source")
    sp.add_argument("--purpose", default=None, dest="new_purpose")
    sp.add_argument("--kind", default=None, dest="new_kind")

    # ── update-import-why ──
    sp = sub.add_parser("update-import-why", help="§5.6 update import reason text")
    sp.add_argument("importer", help="importer entity uid")
    sp.add_argument("imported", help="imported entity uid")
    sp.add_argument("why", help="new reason text")
    sp.add_argument("--exporter", default=None, metavar="UID")

    # ── move-entity ──
    sp = sub.add_parser("move-entity", help="§5.7 update source path after rename/move")
    sp.add_argument("uid", help="entity uid")
    sp.add_argument("new_source", help="new repo-relative source path")

    # ── remove-import ──
    sp = sub.add_parser("remove-import", help="§5.8 remove an import relationship")
    sp.add_argument("importer", help="importer entity uid")
    sp.add_argument("imported", help="imported entity uid")
    sp.add_argument("--exporter", default=None, metavar="UID")

    # ── remove-shared ──
    sp = sub.add_parser("remove-shared", help="§5.9 unregister a shared entity")
    sp.add_argument("exporter", help="exporter Object uid")
    sp.add_argument("shared", help="shared entity uid")

    # ── remove-entity ──
    sp = sub.add_parser("remove-entity", help="§5.10 remove entity and all references")
    sp.add_argument("uid", help="entity uid to remove")

    # ── get-entity ──
    sp = sub.add_parser("get-entity", help="§5.11 get full entity snapshot")
    sp.add_argument("uid", help="entity uid")

    # ── get-shared ──
    sp = sub.add_parser("get-shared", help="§5.12 get public API of entity")
    sp.add_argument("uid", help="entity uid")

    # ── get-recipients ──
    sp = sub.add_parser("get-recipients", help="§5.13 get all importers of entity")
    sp.add_argument("uid", help="entity uid")

    # ── get-children ──
    sp = sub.add_parser("get-children", help="§5.14 import tree downward")
    sp.add_argument("uid", help="entity uid")
    sp.add_argument("--depth", type=_depth_type, default=1, help="traversal depth (default 1, 'inf' for full)")

    # ── get-parents ──
    sp = sub.add_parser("get-parents", help="§5.15 import tree upward")
    sp.add_argument("uid", help="entity uid")
    sp.add_argument("--depth", type=_depth_type, default=1, help="traversal depth (default 1, 'inf' for full)")

    # ── get-path ──
    sp = sub.add_parser("get-path", help="§5.16 shortest path between entities")
    sp.add_argument("from_uid", help="start entity uid")
    sp.add_argument("to_uid", help="end entity uid")

    # ── search ──
    sp = sub.add_parser("search", help="§5.17 full-text search across .dsp")
    sp.add_argument("query", help="search query (case-insensitive substring)")

    # ── find-by-source ──
    sp = sub.add_parser("find-by-source", help="§5.18 find entity by source file path")
    sp.add_argument("source_path", help="repo-relative source path")

    # ── read-toc ──
    sp = sub.add_parser("read-toc", help="§5.19 read table of contents")
    sp.add_argument("--toc", default=None, metavar="ROOT_UID", help="TOC root uid (multi-root)")

    # ── detect-cycles ──
    sub.add_parser("detect-cycles", help="§5.20 find circular dependencies")

    # ── get-orphans ──
    sub.add_parser("get-orphans", help="§5.21 find unused entities")

    # ── get-stats ──
    sub.add_parser("get-stats", help="§5.22 project graph statistics")

    return p


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dispatch
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve()
    store = Store(root)
    engine = Engine(store)
    cmd = args.command

    if cmd == "init":
        engine.init()

    elif cmd == "create-object":
        uid = engine.create_object(args.source, args.purpose, args.kind, args.toc)
        print(uid)

    elif cmd == "create-function":
        uid = engine.create_function(args.source, args.purpose, args.owner, args.toc)
        print(uid)

    elif cmd == "create-shared":
        engine.create_shared(args.exporter, args.shared)
        print("ok")

    elif cmd == "add-import":
        engine.add_import(args.importer, args.imported, args.why, args.exporter)
        print("ok")

    elif cmd == "update-description":
        fields: dict[str, str] = {}
        if args.new_source is not None:
            fields["source"] = args.new_source
        if args.new_purpose is not None:
            fields["purpose"] = args.new_purpose
        if args.new_kind is not None:
            fields["kind"] = args.new_kind
        if not fields:
            _fail("provide at least one field to update (--source, --purpose, --kind)")
        engine.update_description(args.uid, fields)
        print("ok")

    elif cmd == "update-import-why":
        engine.update_import_why(args.importer, args.imported, args.why, args.exporter)
        print("ok")

    elif cmd == "move-entity":
        engine.move_entity(args.uid, args.new_source)
        print("ok")

    elif cmd == "remove-import":
        engine.remove_import(args.importer, args.imported, args.exporter)
        print("ok")

    elif cmd == "remove-shared":
        engine.remove_shared(args.exporter, args.shared)
        print("ok")

    elif cmd == "remove-entity":
        engine.remove_entity(args.uid)
        print("ok")

    elif cmd == "get-entity":
        info = engine.get_entity(args.uid)
        _print_entity(info)

    elif cmd == "get-shared":
        items = engine.get_shared(args.uid)
        if not items:
            print("no shared entities")
        for item in items:
            print(f"\n{item['shared_uid']}:")
            print(f"  description: {item['description']}")
            if item["recipients"]:
                print("  imported by:")
                for rec_uid, why in item["recipients"]:
                    print(f"    {rec_uid}: {why}" if why else f"    {rec_uid}")

    elif cmd == "get-recipients":
        recs = engine.get_recipients(args.uid)
        if not recs:
            print("no recipients")
        for rec_uid, why in recs:
            print(f"{rec_uid}: {why}" if why else rec_uid)

    elif cmd == "get-children":
        tree = engine.get_children(args.uid, args.depth)
        _print_tree(tree, key="children")

    elif cmd == "get-parents":
        tree = engine.get_parents(args.uid, args.depth)
        _print_tree(tree, key="parents")

    elif cmd == "get-path":
        path = engine.get_path(args.from_uid, args.to_uid)
        if path is None:
            print("no path found")
            sys.exit(1)
        print(" -> ".join(path))

    elif cmd == "search":
        results = engine.search(args.query)
        if not results:
            print("no matches")
        for r in results:
            print(f"{r['uid']}  [{r['field']}] {r['match']}")

    elif cmd == "find-by-source":
        found = engine.find_by_source(args.source_path)
        if not found:
            print("not found")
            sys.exit(1)
        for uid in found:
            print(uid)

    elif cmd == "read-toc":
        uids = engine.read_toc(args.toc)
        for i, uid in enumerate(uids):
            tag = " [root]" if i == 0 else ""
            print(f"{uid}{tag}")

    elif cmd == "detect-cycles":
        cycles = engine.detect_cycles()
        if not cycles:
            print("no cycles detected")
        for i, cycle in enumerate(cycles, 1):
            print(f"cycle {i}: {' -> '.join(cycle)}")

    elif cmd == "get-orphans":
        orphans = engine.get_orphans()
        if not orphans:
            print("no orphans")
        for uid in orphans:
            print(uid)

    elif cmd == "get-stats":
        stats = engine.get_stats()
        print(f"entities:  {stats['entities']}")
        print(f"  objects:   {stats['objects']}")
        print(f"  functions: {stats['functions']}")
        print(f"  external:  {stats['externals']}")
        print(f"imports:   {stats['imports']}")
        print(f"shared:    {stats['shared']}")
        print(f"cycles:    {stats['cycles']}")
        print(f"orphans:   {stats['orphans']}")


if __name__ == "__main__":
    main()
