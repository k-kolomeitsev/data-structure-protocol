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

_UID_RE = re.compile(r"^(obj|func)-[0-9a-f]{8}$")

_VALID_KINDS = ("object", "function", "external")

# TOC spec: literal "default" (the .dsp/TOC file) or a root uid (TOC-<uid>).
_DEFAULT_TOC = "default"


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


def _normalize_scope(scope: str) -> str:
    s = scope.strip().replace("\\", "/")
    if not s:
        _fail("scope must be a repo-relative directory or '.'")
    while s.startswith("./"):
        s = s[2:]
    s = s.strip("/")
    return s if s and s != "." else "."


def _normalize_source_path(source: str) -> str:
    # "#symbol" fragments anchor entities inside a file; scope matching
    # works on the file path alone.
    s = source.split("#", 1)[0].replace("\\", "/").strip()
    while s.startswith("./"):
        s = s[2:]
    return s.strip("/")


def _scope_matches(scope: str, source: str) -> bool:
    if scope == ".":
        return True
    src = _normalize_source_path(source)
    return src == scope or src.startswith(scope + "/")


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

# A key line is "<key>: <value>" or a bare "<key>:" — the space (or end of
# line) after the colon distinguishes key lines from URLs like "https://..."
# appearing inside multi-line freeform values.
_DESC_KEY_RE = re.compile(r"^([a-z_]+):(?:[ \t](.*)|[ \t]*$)")
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
            cur_lines = [m.group(2) or ""]
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
        # Format guard doubles as a path-safety check: uids are used as
        # path segments under .dsp/, so anything else must never reach disk.
        if not _UID_RE.match(uid):
            return False
        return (self.base / uid).is_dir()

    def require_entity(self, uid: str) -> None:
        if not _UID_RE.match(uid):
            _fail(f"invalid uid '{uid}' (expected obj-<8hex> or func-<8hex>)")
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
            if not _UID_RE.match(root_uid):
                _fail(f"invalid root uid '{root_uid}' (expected obj-<8hex> or func-<8hex>)")
            return self.base / f"{TOC_BASE}-{root_uid}"
        return self.base / TOC_BASE

    def all_toc_paths(self) -> list[Path]:
        if not self.base.is_dir():
            return []
        return sorted(p for p in self.base.iterdir() if p.is_file() and p.name.startswith(TOC_BASE))

    def toc_root_uid(self, toc_path: Path) -> str | None:
        lines = _read_lines(toc_path)
        return lines[0] if lines else None

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
# RevCache — persistent, incrementally-maintained reverse index
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RevCache:
    """On-disk reverse-edge index: imported_uid → importer uids.

    Why this exists
    ---------------
    dsp-cli is a one-shot process: every invocation starts cold. The only
    queries that cannot be answered from a few local files are the *reverse*
    ones — "who imports X" — which otherwise scan the whole graph (O(N)), and
    get-path, whose BFS asked that per visited node (O(N²) — the original
    timeout). An in-memory cache cannot help: it dies with the process. So the
    reverse index lives on disk and is maintained incrementally by mutations.

    What is stored (and what is NOT)
    --------------------------------
    Only the reverse adjacency, one file per imported entity::

        .dsp/.cache/rev/<imported>   →  importer uids, one per line (sorted)

    A sentinel ``.dsp/.cache/built`` tells "X has no importers" (file absent,
    cache built) apart from "cache not built yet" (sentinel absent).

    ``importers_of(X)`` is the COMPLETE reverse set: every importer names X as
    the first token of an imports line (direct, via-exporter, and owner edges
    all do), so a single forward scan reconstructs it. The ``why`` text and the
    direct/shared recipient names are NOT stored — they are cheap local reads
    (``exports/<X>/`` and the importer's own imports line), so they stay live
    and can never go stale on their own.

    Freshness
    ---------
    The CLI is the sole writer of ``.dsp/`` (project rule), so incremental
    upkeep keeps the index correct. Changes made OUTSIDE the CLI (git
    checkout/pull, manual edits) are NOT detected — run ``rebuild-cache`` after
    those. A missing cache is rebuilt automatically on the next reverse/heavy
    command or rev-affecting mutation.
    """

    def __init__(self, store: "Store"):
        self.s = store
        self.dir = store.base / ".cache"
        self.rev_dir = self.dir / "rev"
        self.sentinel = self.dir / "built"

    # ── state ──

    def is_built(self) -> bool:
        return self.sentinel.is_file()

    def _rev_file(self, imported_uid: str) -> Path:
        return self.rev_dir / imported_uid

    # ── reads ──

    def importers_of(self, imported_uid: str) -> list[str]:
        """Importer uids of *imported_uid* (sorted). Empty list if none."""
        return _read_lines(self._rev_file(imported_uid))

    # ── incremental upkeep (a no-op until the cache is built) ──

    def add_edge(self, imported_uid: str, importer_uid: str) -> None:
        if not self.is_built():
            return
        f = self._rev_file(imported_uid)
        lines = _read_lines(f)
        if importer_uid not in lines:
            lines.append(importer_uid)
            _write_lines(f, sorted(lines))

    def remove_edge(self, imported_uid: str, importer_uid: str) -> None:
        if not self.is_built():
            return
        f = self._rev_file(imported_uid)
        remaining = [ln for ln in _read_lines(f) if ln != importer_uid]
        if remaining:
            _write_lines(f, remaining)
        else:
            _safe_unlink(f)

    # ── build / invalidate ──

    def ensure_built(self) -> None:
        """Build the index from disk if it is missing."""
        if not self.is_built():
            self.rebuild()

    def rebuild(self) -> int:
        """Full rebuild from the forward imports of every entity.

        Returns the number of imported entities indexed.
        """
        _safe_rmtree(self.dir)
        if not self.s.base.is_dir():
            return 0
        self.rev_dir.mkdir(parents=True, exist_ok=True)
        rev: dict[str, set[str]] = {}
        for uid in self.s.all_uids():
            for imp_uid, _via in self.s.read_imports(uid):
                if imp_uid:
                    rev.setdefault(imp_uid, set()).add(uid)
        for imported_uid, importers in rev.items():
            _write_lines(self._rev_file(imported_uid), sorted(importers))
        _write_text(self.sentinel, "1")
        return len(rev)

    def invalidate(self) -> None:
        """Drop the whole cache; the next reverse/heavy command rebuilds it."""
        _safe_rmtree(self.dir)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Engine — all DSP operations (ARCHITECTURE.md §5)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Engine:
    def __init__(self, store: Store):
        self.s = store
        self._rev = RevCache(store)

    # ── reverse adjacency (served by the persistent RevCache) ──

    def _all_importers(self, uid: str) -> list[tuple[str, str]]:
        """Every entity that imports *uid*, paired with its ``why`` text.

        The importer set comes from the persistent reverse index; the ``why``
        is read live from ``exports/`` — directly for a plain import / owner
        edge, or via the exporter for a shared (``--exporter``) import.
        """
        self._rev.ensure_built()
        return [(importer, self._why_for(uid, importer))
                for importer in self._rev.importers_of(uid)]

    def _all_importer_uids(self, uid: str) -> set[str]:
        """Set of importer uids of *uid* — no ``why`` reads (for traversal)."""
        self._rev.ensure_built()
        return set(self._rev.importers_of(uid))

    def _why_for(self, uid: str, importer: str) -> str:
        """Reason text for the edge importer → uid, read live from exports/."""
        direct = self.s.exports_dir(uid) / importer
        if direct.is_file():
            return _read_text(direct)
        # Shared import: locate the exporter from the importer's own imports line.
        for imp_uid, via in self.s.read_imports(importer):
            if imp_uid == uid and via:
                f = self.s.exports_dir(via) / uid / importer
                return _read_text(f) if f.is_file() else ""
        return ""

    # ── init ──

    def init(self) -> None:
        self.s.base.mkdir(parents=True, exist_ok=True)
        print(f"initialized {self.s.base}")

    # ── uid / TOC resolution helpers ──

    def _resolve_uid(self, uid: str | None, kind: str) -> str:
        """Generate a fresh uid, or validate a caller-supplied one (re-indexing)."""
        if uid is None:
            return _gen_uid(kind)
        want = "func" if kind == "function" else "obj"
        if not _UID_RE.match(uid):
            _fail(f"invalid uid '{uid}' (expected obj-<8hex> or func-<8hex>)")
        if not uid.startswith(want + "-"):
            _fail(f"uid prefix mismatch: a {kind} entity requires {want}-<8hex>, got '{uid}'")
        if self.s.entity_exists(uid):
            _fail(f"entity {uid} already exists — pass a different uid or remove the existing entity first")
        return uid

    def _toc_spec_path(self, spec: str, for_create: bool = False) -> Path:
        """Resolve a TOC spec ('default' or a root uid) to its TOC file.

        Explicit targets must exist — roots are born only via --new-root. The
        single exception: on a fresh project with no TOC files at all, the
        default TOC may be created by the first create-* call.
        """
        if spec == _DEFAULT_TOC:
            p = self.s.toc_path(None)
            if p.is_file() or (for_create and not self.s.all_toc_paths()):
                return p
            _fail("default TOC does not exist — pass --toc <ROOT_UID> of an existing root instead")
        p = self.s.toc_path(spec)
        if not p.is_file():
            _fail(f"TOC file {p.name} not found — roots are created with 'create-object ... --new-root'")
        return p

    def _auto_toc_targets(self, source: str) -> list[Path]:
        """All TOCs whose root scope covers `source`; fall back to the default TOC."""
        matches: list[Path] = []
        for toc in self.s.all_toc_paths():
            root_uid = self.s.toc_root_uid(toc)
            if not root_uid or not self.s.entity_exists(root_uid):
                continue
            scope = self.s.read_desc(root_uid).get("scope", "").strip()
            if scope and _scope_matches(_normalize_scope(scope), source):
                matches.append(toc)
        if matches:
            return matches
        default_p = self.s.toc_path(None)
        if default_p.is_file() or not self.s.all_toc_paths():
            return [default_p]
        _fail(
            f"cannot determine target TOC for '{source}': no root scope matches and no default TOC exists; "
            "pass --toc <ROOT_UID|default> explicitly, or set a scope on a root "
            "(update-description <root-uid> --scope <dir>)"
        )

    def _toc_targets(self, source: str, tocs: list[str] | None) -> list[Path]:
        if tocs:
            paths: list[Path] = []
            seen: set[Path] = set()
            for spec in tocs:
                p = self._toc_spec_path(spec, for_create=True)
                if p not in seen:
                    seen.add(p)
                    paths.append(p)
            return paths
        return self._auto_toc_targets(source)

    @staticmethod
    def _report_tocs(targets: list[Path]) -> None:
        # Informational status on stdout, not stderr: on Windows/PowerShell a
        # native process writing to stderr is wrapped in NativeCommandError
        # noise on every call. stderr stays reserved for real errors (_fail).
        print(f"toc: {', '.join(t.name for t in targets)}")

    # ── §5.1 createObject ──

    def create_object(
        self,
        source: str,
        purpose: str,
        kind: str = "object",
        tocs: list[str] | None = None,
        new_root: bool = False,
        uid: str | None = None,
        scope: str | None = None,
    ) -> str:
        self.s.ensure_init()
        if scope and not new_root:
            _fail("--scope is only valid together with --new-root "
                  "(for an existing root use update-description <uid> --scope)")
        uid = self._resolve_uid(uid, "object")
        # Resolve TOC targets before any write so a failure leaves no trace.
        # --new-root: the object becomes TOC[0] of its own TOC-<uid>.
        targets = [self.s.toc_path(uid)] if new_root else self._toc_targets(source, tocs)
        (self.s.base / uid).mkdir(parents=True)
        desc = {"source": source, "kind": kind, "purpose": purpose}
        if new_root and scope:
            desc["scope"] = _normalize_scope(scope)
        self.s.write_desc(uid, desc)
        _write_lines(self.s.imports_path(uid), [])
        _write_lines(self.s.shared_path(uid), [])
        for t in targets:
            _append_line_unique(t, uid)
        self._report_tocs(targets)
        return uid

    # ── §5.2 createFunction ──

    def create_function(
        self,
        source: str,
        purpose: str,
        owner: str | None = None,
        tocs: list[str] | None = None,
        uid: str | None = None,
    ) -> str:
        self.s.ensure_init()
        uid = self._resolve_uid(uid, "function")
        if owner:
            self.s.require_entity(owner)
        # Validate everything (owner, TOC targets) before any write.
        targets = self._toc_targets(source, tocs)
        (self.s.base / uid).mkdir(parents=True)
        self.s.write_desc(uid, {"source": source, "kind": "function", "purpose": purpose})
        _write_lines(self.s.imports_path(uid), [])
        if owner:
            _append_line_unique(self.s.imports_path(owner), uid)
            exp = self.s.exports_dir(uid)
            exp.mkdir(parents=True, exist_ok=True)
            _write_text(exp / owner, "owner: method/member of this object")
        for t in targets:
            _append_line_unique(t, uid)
        self._report_tocs(targets)
        if owner:
            # The owner edge (owner imports this member) is a reverse edge.
            self._rev.ensure_built()
            self._rev.add_edge(uid, owner)
        return uid

    # ── §5.3 createShared ──

    def create_shared(self, exporter: str, shared_uids: list[str]) -> None:
        self.s.ensure_init()
        self.s.require_entity(exporter)
        for sid in shared_uids:
            self.s.require_entity(sid)
        exp_dir = self.s.exports_dir(exporter)
        exp_dir.mkdir(parents=True, exist_ok=True)
        for sid in shared_uids:
            _append_line_unique(self.s.shared_path(exporter), sid)
            shared_sub = exp_dir / sid
            shared_sub.mkdir(parents=True, exist_ok=True)
            desc_path = shared_sub / DESC_FILE
            if not desc_path.exists():
                purpose = self.s.read_desc(sid).get("purpose", "")
                _write_text(desc_path, purpose if purpose else sid)

    # ── §5.4 addImport ──

    def add_import(
        self, importer: str, imported: str, why: str, exporter: str | None = None
    ) -> None:
        self.s.ensure_init()
        self.s.require_entity(importer)
        self.s.require_entity(imported)
        if exporter:
            self.s.require_entity(exporter)
        line = _format_import_line(imported, exporter)
        _append_line_unique(self.s.imports_path(importer), line)
        if exporter:
            rev_dir = self.s.exports_dir(exporter) / imported
            rev_dir.mkdir(parents=True, exist_ok=True)
            _write_text(rev_dir / importer, why)
        else:
            exp = self.s.exports_dir(imported)
            exp.mkdir(parents=True, exist_ok=True)
            _write_text(exp / importer, why)
        # Reverse edge is imported ← importer regardless of the via-exporter
        # (the import line names `imported` as its first token either way).
        self._rev.ensure_built()
        self._rev.add_edge(imported, importer)

    # ── §5.5 updateDescription ──

    def update_description(self, uid: str, fields: dict[str, str]) -> None:
        self.s.ensure_init()
        self.s.require_entity(uid)
        if "kind" in fields:
            k = fields["kind"]
            if k not in _VALID_KINDS:
                _fail(f"invalid kind '{k}' (expected one of: {', '.join(_VALID_KINDS)})")
            # The uid prefix encodes the entity family; kind must stay consistent.
            if uid.startswith("func-") and k != "function":
                _fail(f"{uid} is a function entity — its kind cannot become '{k}'")
            if uid.startswith("obj-") and k == "function":
                _fail(f"{uid} is an object entity — its kind cannot become 'function'")
        if "scope" in fields:
            roots = {self.s.toc_root_uid(t) for t in self.s.all_toc_paths()}
            if uid not in roots:
                _fail(f"{uid} is not a root of any TOC — scope is only meaningful on root entities (TOC[0])")
            fields["scope"] = _normalize_scope(fields["scope"])
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

        # Exact-match removal: without --exporter only a plain line is removed;
        # with --exporter only the matching "via=" line. Removing a via-line by
        # a plain call (or vice versa) would desync imports from exports/.
        imports = self.s.read_imports(importer)
        new_lines: list[str] = []
        line_removed = False
        for imp_uid, imp_via in imports:
            if not line_removed and imp_uid == imported and imp_via == exporter:
                line_removed = True
                continue
            new_lines.append(_format_import_line(imp_uid, imp_via))
        if line_removed:
            _write_lines(self.s.imports_path(importer), new_lines)

        if exporter:
            rev = self.s.exports_dir(exporter) / imported / importer
        else:
            rev = self.s.exports_dir(imported) / importer
        rev_removed = rev.is_file()
        _safe_unlink(rev)
        if exporter:
            sub = self.s.exports_dir(exporter) / imported
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()

        if not line_removed and not rev_removed:
            hint = (
                "hint: this import may have been registered with --exporter; pass the same --exporter"
                if exporter is None
                else "hint: this import may have been registered without --exporter"
            )
            via_s = f" via {exporter}" if exporter else ""
            _fail(f"import {imported}{via_s} not found in {importer} ({hint})")

        # Drop the reverse edge only if `importer` no longer imports `imported`
        # by ANY route (it may have had both a plain and a via-exporter line).
        self._rev.ensure_built()
        if not any(u == imported for u, _ in self.s.read_imports(importer)):
            self._rev.remove_edge(imported, importer)

    # ── §5.9 removeShared ──

    def remove_shared(self, exporter: str, shared_uid: str) -> None:
        self.s.ensure_init()
        self.s.require_entity(exporter)
        _remove_line_value(self.s.shared_path(exporter), shared_uid)
        shared_dir = self.s.exports_dir(exporter) / shared_uid
        affected: list[str] = []
        if shared_dir.is_dir():
            for entry in list(shared_dir.iterdir()):
                if entry.is_file() and entry.name != DESC_FILE:
                    recipient_uid = entry.name
                    affected.append(recipient_uid)
                    if self.s.entity_exists(recipient_uid):
                        imports = self.s.read_imports(recipient_uid)
                        new_lines = [
                            _format_import_line(u, v)
                            for u, v in imports
                            if not (u == shared_uid and v == exporter)
                        ]
                        _write_lines(self.s.imports_path(recipient_uid), new_lines)
            _safe_rmtree(shared_dir)
        # Each recipient lost its `shared_uid via=exporter` line; drop the
        # reverse edge unless it still imports shared_uid by another route.
        self._rev.ensure_built()
        for recipient_uid in affected:
            if not any(u == shared_uid for u, _ in self.s.read_imports(recipient_uid)):
                self._rev.remove_edge(shared_uid, recipient_uid)

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

        # Full reverse-index sweep over every other entity. A targeted cleanup
        # driven by uid's own imports/shared would miss entries that exist
        # without a matching registration (e.g. add-import --exporter without
        # create-shared) and leave dangling references behind.
        for other in all_uids:
            if other == uid:
                continue
            if uid in self.s.read_shared(other):
                _remove_line_value(self.s.shared_path(other), uid)
            exp = self.s.exports_dir(other)
            if not exp.is_dir():
                continue
            entry = exp / uid
            if entry.is_file():
                entry.unlink()  # uid imported `other` as a whole
            elif entry.is_dir():
                shutil.rmtree(entry)  # uid was exported via `other`
            for sub in exp.iterdir():
                if sub.is_dir():
                    _safe_unlink(sub / uid)  # uid imported a shared of `other`
                    if not any(sub.iterdir()):
                        sub.rmdir()

        for toc in self.s.all_toc_paths():
            _remove_line_value(toc, uid)
        # A root's own TOC file has no meaning once the root is gone.
        own_toc = self.s.base / f"{TOC_BASE}-{uid}"
        if own_toc.is_file():
            own_toc.unlink()

        _safe_rmtree(self.s.base / uid)
        # This touches reverse edges across the whole graph (uid as importer,
        # imported, exporter, and shared). Rather than mirror that sweep
        # incrementally, drop the cache; the next reverse/heavy command rebuilds.
        self._rev.invalidate()

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
            neighbors.update(self._all_importer_uids(current))
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

    # ── §5.23 addToToc ──

    def add_to_toc(self, uids: list[str], tocs: list[str]) -> list[str]:
        self.s.ensure_init()
        uids = list(dict.fromkeys(uids))
        for uid in uids:
            self.s.require_entity(uid)
        paths: list[Path] = []
        seen: set[Path] = set()
        for spec in tocs:
            p = self._toc_spec_path(spec)
            if p not in seen:
                seen.add(p)
                paths.append(p)
        report: list[str] = []
        for uid in uids:
            for p in paths:
                if uid in _read_lines(p):
                    report.append(f"{uid}: already in {p.name}")
                else:
                    _append_line_unique(p, uid)
                    report.append(f"{uid}: added to {p.name}")
        return report

    # ── §5.24 moveToToc ──

    def move_to_toc(self, uids: list[str], from_spec: str, to_spec: str) -> list[str]:
        self.s.ensure_init()
        src = self._toc_spec_path(from_spec)
        dst = self._toc_spec_path(to_spec)
        if src == dst:
            _fail("--from and --to point to the same TOC")
        uids = list(dict.fromkeys(uids))
        src_lines = _read_lines(src)
        src_root = src_lines[0] if src_lines else None
        # Validate the whole batch before touching anything — all-or-nothing.
        for uid in uids:
            self.s.require_entity(uid)
            if uid not in src_lines:
                _fail(f"{uid} is not in {src.name} — nothing to move")
            if uid == src_root:
                _fail(f"{uid} is the root of {src.name} and cannot be moved out of its own TOC")
        dst_lines = _read_lines(dst)
        report: list[str] = []
        for uid in uids:
            src_lines = [ln for ln in src_lines if ln != uid]
            if uid in dst_lines:
                report.append(f"{uid}: {src.name} -> {dst.name} (already in target)")
            else:
                dst_lines.append(uid)
                report.append(f"{uid}: {src.name} -> {dst.name}")
        _write_lines(src, src_lines)
        _write_lines(dst, dst_lines)
        return report

    # ── rebuild-cache ──

    def rebuild_cache(self) -> int:
        """Force a full rebuild of the persistent reverse-index cache.

        Run this after the .dsp/ graph was changed OUTSIDE the CLI (git
        checkout/pull, manual edits) — the incremental cache cannot see those.
        """
        self.s.ensure_init()
        return self._rev.rebuild()


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


def _uid_type(value: str) -> str:
    if not _UID_RE.match(value):
        raise argparse.ArgumentTypeError(
            f"invalid uid '{value}' (expected obj-<8hex> or func-<8hex>, e.g. obj-a1b2c3d4)"
        )
    return value


def _toc_spec_type(value: str) -> str:
    if value == _DEFAULT_TOC:
        return value
    if not _UID_RE.match(value):
        raise argparse.ArgumentTypeError(
            f"invalid TOC '{value}' (expected a root uid like obj-a1b2c3d4, or 'default')"
        )
    return value


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
    sp.add_argument("--uid", default=None, metavar="UID", type=_uid_type,
                    help="use this uid instead of generating one (re-indexing a project with existing @dsp markers)")
    grp = sp.add_mutually_exclusive_group()
    grp.add_argument("--toc", default=None, action="append", metavar="TOC", type=_toc_spec_type,
                     help="target TOC: root uid or 'default'; repeatable. Default: auto-detect by root scopes")
    grp.add_argument("--new-root", action="store_true", help="make this object a root with its own TOC-<uid>")
    sp.add_argument("--scope", default=None, metavar="DIR",
                    help="directory subtree covered by this root ('.' = whole repo); requires --new-root")

    # ── create-function ──
    sp = sub.add_parser("create-function", help="§5.2 create a Function entity")
    sp.add_argument("source", help="repo-relative source path (with #symbol if needed)")
    sp.add_argument("purpose", help="1-3 sentences: what and why")
    sp.add_argument("--owner", default=None, metavar="UID", type=_uid_type, help="owner Object uid")
    sp.add_argument("--uid", default=None, metavar="UID", type=_uid_type,
                    help="use this uid instead of generating one (re-indexing a project with existing @dsp markers)")
    sp.add_argument("--toc", default=None, action="append", metavar="TOC", type=_toc_spec_type,
                    help="target TOC: root uid or 'default'; repeatable. Default: auto-detect by root scopes")

    # ── create-shared ──
    sp = sub.add_parser("create-shared", help="§5.3 register shared/exported entities")
    sp.add_argument("exporter", type=_uid_type, help="exporter Object uid")
    sp.add_argument("shared", nargs="+", type=_uid_type, help="uid(s) of shared entities")

    # ── add-import ──
    sp = sub.add_parser("add-import", help="§5.4 add an import relationship")
    sp.add_argument("importer", type=_uid_type, help="importer entity uid")
    sp.add_argument("imported", type=_uid_type, help="imported entity uid")
    sp.add_argument("why", help="1-3 sentences: why this is imported")
    sp.add_argument("--exporter", default=None, metavar="UID", type=_uid_type, help="exporter Object uid (for shared imports)")

    # ── update-description ──
    sp = sub.add_parser("update-description", help="§5.5 update entity description fields")
    sp.add_argument("uid", type=_uid_type, help="entity uid")
    sp.add_argument("--source", default=None, dest="new_source")
    sp.add_argument("--purpose", default=None, dest="new_purpose")
    sp.add_argument("--kind", default=None, dest="new_kind", choices=_VALID_KINDS)
    sp.add_argument("--scope", default=None, dest="new_scope", metavar="DIR",
                    help="directory subtree covered by this root ('.' = whole repo); root entities only")

    # ── update-import-why ──
    sp = sub.add_parser("update-import-why", help="§5.6 update import reason text")
    sp.add_argument("importer", type=_uid_type, help="importer entity uid")
    sp.add_argument("imported", type=_uid_type, help="imported entity uid")
    sp.add_argument("why", help="new reason text")
    sp.add_argument("--exporter", default=None, metavar="UID", type=_uid_type)

    # ── move-entity ──
    sp = sub.add_parser("move-entity", help="§5.7 update source path after rename/move")
    sp.add_argument("uid", type=_uid_type, help="entity uid")
    sp.add_argument("new_source", help="new repo-relative source path")

    # ── add-to-toc ──
    sp = sub.add_parser("add-to-toc", help="§5.23 add existing entities to TOC(s)")
    sp.add_argument("uids", nargs="+", metavar="uid", type=_uid_type, help="entity uid(s) to add")
    sp.add_argument("--toc", required=True, action="append", metavar="TOC", type=_toc_spec_type,
                    help="target TOC: root uid or 'default'; repeatable")

    # ── move-to-toc ──
    sp = sub.add_parser("move-to-toc", help="§5.24 move entities from one TOC to another")
    sp.add_argument("uids", nargs="+", metavar="uid", type=_uid_type, help="entity uid(s) to move")
    sp.add_argument("--from", required=True, dest="from_toc", metavar="TOC", type=_toc_spec_type,
                    help="source TOC: root uid or 'default'")
    sp.add_argument("--to", required=True, dest="to_toc", metavar="TOC", type=_toc_spec_type,
                    help="target TOC: root uid or 'default'")

    # ── remove-import ──
    sp = sub.add_parser("remove-import", help="§5.8 remove an import relationship")
    sp.add_argument("importer", type=_uid_type, help="importer entity uid")
    sp.add_argument("imported", type=_uid_type, help="imported entity uid")
    sp.add_argument("--exporter", default=None, metavar="UID", type=_uid_type)

    # ── remove-shared ──
    sp = sub.add_parser("remove-shared", help="§5.9 unregister a shared entity")
    sp.add_argument("exporter", type=_uid_type, help="exporter Object uid")
    sp.add_argument("shared", type=_uid_type, help="shared entity uid")

    # ── remove-entity ──
    sp = sub.add_parser("remove-entity", help="§5.10 remove entity and all references")
    sp.add_argument("uid", type=_uid_type, help="entity uid to remove")

    # ── get-entity ──
    sp = sub.add_parser("get-entity", help="§5.11 get full entity snapshot")
    sp.add_argument("uid", type=_uid_type, help="entity uid")

    # ── get-shared ──
    sp = sub.add_parser("get-shared", help="§5.12 get public API of entity")
    sp.add_argument("uid", type=_uid_type, help="entity uid")

    # ── get-recipients ──
    sp = sub.add_parser("get-recipients", help="§5.13 get all importers of entity")
    sp.add_argument("uid", type=_uid_type, help="entity uid")

    # ── get-children ──
    sp = sub.add_parser("get-children", help="§5.14 import tree downward")
    sp.add_argument("uid", type=_uid_type, help="entity uid")
    sp.add_argument("--depth", type=_depth_type, default=1, help="traversal depth (default 1, 'inf' for full)")

    # ── get-parents ──
    sp = sub.add_parser("get-parents", help="§5.15 import tree upward")
    sp.add_argument("uid", type=_uid_type, help="entity uid")
    sp.add_argument("--depth", type=_depth_type, default=1, help="traversal depth (default 1, 'inf' for full)")

    # ── get-path ──
    sp = sub.add_parser("get-path", help="§5.16 shortest path between entities")
    sp.add_argument("from_uid", type=_uid_type, help="start entity uid")
    sp.add_argument("to_uid", type=_uid_type, help="end entity uid")

    # ── search ──
    sp = sub.add_parser("search", help="§5.17 full-text search across .dsp")
    sp.add_argument("query", help="search query (case-insensitive substring)")

    # ── find-by-source ──
    sp = sub.add_parser("find-by-source", help="§5.18 find entity by source file path")
    sp.add_argument("source_path", help="repo-relative source path")

    # ── read-toc ──
    sp = sub.add_parser("read-toc", help="§5.19 read table of contents")
    sp.add_argument("--toc", default=None, metavar="ROOT_UID", type=_uid_type, help="TOC root uid (multi-root)")

    # ── detect-cycles ──
    sub.add_parser("detect-cycles", help="§5.20 find circular dependencies")

    # ── get-orphans ──
    sub.add_parser("get-orphans", help="§5.21 find unused entities")

    # ── get-stats ──
    sub.add_parser("get-stats", help="§5.22 project graph statistics")

    # ── rebuild-cache ──
    sub.add_parser(
        "rebuild-cache",
        help="rebuild the persistent reverse-index cache (after non-CLI .dsp edits)",
    )

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
        uid = engine.create_object(
            args.source, args.purpose, args.kind, args.toc, args.new_root, args.uid, args.scope
        )
        print(uid)

    elif cmd == "create-function":
        uid = engine.create_function(args.source, args.purpose, args.owner, args.toc, args.uid)
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
        if args.new_scope is not None:
            fields["scope"] = args.new_scope
        if not fields:
            _fail("provide at least one field to update (--source, --purpose, --kind, --scope)")
        engine.update_description(args.uid, fields)
        print("ok")

    elif cmd == "update-import-why":
        engine.update_import_why(args.importer, args.imported, args.why, args.exporter)
        print("ok")

    elif cmd == "move-entity":
        engine.move_entity(args.uid, args.new_source)
        print("ok")

    elif cmd == "add-to-toc":
        for line in engine.add_to_toc(args.uids, args.toc):
            print(line)

    elif cmd == "move-to-toc":
        for line in engine.move_to_toc(args.uids, args.from_toc, args.to_toc):
            print(line)

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

    elif cmd == "rebuild-cache":
        n = engine.rebuild_cache()
        print(f"rebuilt reverse-index cache: {n} imported entities")


if __name__ == "__main__":
    main()
