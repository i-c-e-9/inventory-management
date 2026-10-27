#!/usr/bin/env python3
"""Scan Vue 3 single-file components for performance and reuse leads.

Usage:
    python3 scan_vue.py <path> [<path> ...] [--json]

<path> may be a .vue file or a directory (scanned recursively). The client
source root is found by walking up to a directory that contains main.js, so
cross-file checks (shared helpers, router imports, api.js usage) work even
when only one file is passed.

Output is a list of *leads*: heuristics based on regexes, not a parser. Each
lead must be confirmed by reading the code before it is reported.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

INDEX_KEYS = {"index", "i", "idx", "n", "k"}

# Matches the opening tag of any element that carries a v-for.
TAG_WITH_VFOR = re.compile(r"<([a-zA-Z][\w-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?\bv-for=(?:\"[^\"]*\"|'[^']*')(?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.S)
VFOR_ALIAS = re.compile(r"v-for=[\"']\s*\(?\s*([\w$]+)\s*(?:,\s*([\w$]+))?\s*(?:,\s*([\w$]+))?\s*\)?\s+(?:in|of)\s")
KEY_ATTR = re.compile(r"(?::key|v-bind:key)=[\"']([^\"']+)[\"']")
MUSTACHE_CALL = re.compile(r"\{\{[^}]*?\b([a-zA-Z_$][\w$]*)\s*\(")
FUNC_DEF = re.compile(r"^\s*(?:export\s+)?(?:const|let|function)\s+([a-zA-Z_$][\w$]*)\s*(?:=\s*(?:async\s*)?(?:\([^)]*\)|[\w$]+)\s*=>|=\s*(?:async\s+)?function\b|\()", re.M)
INPLACE_MUTATION = re.compile(r"(\.?[\w$\]\)]+)\s*\.(sort|reverse)\(")
API_CALL = re.compile(r"\bapi\.([a-zA-Z_$][\w$]*)\s*\(")
EAGER_VIEW_IMPORT = re.compile(r"^import\s+(\w+)\s+from\s+['\"](\./views/[^'\"]+\.vue)['\"]", re.M)

# Calls inside {{ }} that are cheap built-ins or i18n; not worth flagging.
IGNORED_TEMPLATE_CALLS = {"t", "$t", "String", "Number", "Math", "toFixed", "toLocaleString",
                          "toString", "abs", "round", "floor", "ceil", "min", "max"}


def find_src_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "main.js").exists() or (p / "main.ts").exists():
            return p
    return start


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def split_blocks(text: str):
    """Return (start_line, content) for template, script, style (None when absent)."""
    blocks = {}
    for name in ("template", "script", "style"):
        # Outermost block: first opening tag to last closing tag, so nested
        # <template> slots stay inside the template block.
        start = re.search(rf"<{name}\b[^>]*>", text)
        end = text.rfind(f"</{name}>")
        if start and end > start.end():
            blocks[name] = (line_of(text, start.end()), text[start.end():end])
        else:
            blocks[name] = None
    return blocks


def count_lines(block):
    return 0 if block is None else block[1].strip("\n").count("\n") + 1


def scan_file(path: Path, rel: str, leads: list, defs: dict, api_usage: dict) -> dict:
    text = path.read_text(encoding="utf-8")
    blocks = split_blocks(text)
    tmpl, script = blocks["template"], blocks["script"]

    script_text = script[1] if script else ""
    if script and re.search(r"<script\b[^>]*\bsetup\b", text):
        api_style = "script setup"
    elif "setup(" in script_text:
        api_style = "setup()"
    elif script:
        api_style = "options"
    else:
        api_style = "-"

    def add(kind, line, detail):
        leads.append({"kind": kind, "file": rel, "line": line, "detail": detail})

    if tmpl:
        t_start, t_body = tmpl
        for m in TAG_WITH_VFOR.finditer(t_body):
            attrs = m.group(2)
            line = t_start + t_body.count("\n", 0, m.start())
            alias = VFOR_ALIAS.search(attrs)
            key = KEY_ATTR.search(attrs)
            if not key and m.group(1) != "template":
                add("vfor-missing-key", line, f"<{m.group(1)}> has v-for without :key")
            elif key and alias:
                key_expr = key.group(1).strip()
                index_vars = {v for v in alias.groups()[1:] if v}
                if key_expr in index_vars or (key_expr in INDEX_KEYS and key_expr != alias.group(1)):
                    add("vfor-index-key", line, f':key="{key_expr}" uses the loop index')
            if re.search(r"\bv-if=", attrs):
                add("vif-with-vfor", line, f"<{m.group(1)}> has both v-if and v-for")
        # One summary lead per file: individual formatter calls are usually cheap,
        # so the useful signal is which functions run on every render, and how often.
        calls, first_line = defaultdict(int), None
        for m in MUSTACHE_CALL.finditer(t_body):
            fn = m.group(1)
            if fn not in IGNORED_TEMPLATE_CALLS:
                calls[fn] += 1
                first_line = first_line or t_start + t_body.count("\n", 0, m.start())
        if calls:
            summary = ", ".join(f"{fn} x{n}" for fn, n in sorted(calls.items(), key=lambda kv: -kv[1]))
            add("template-calls", first_line, f"{sum(calls.values())} calls in {{{{ }}}} re-run every render: {summary}")

    if script:
        s_start, s_body = script
        for m in INPLACE_MUTATION.finditer(s_body):
            # Chains on a fresh array (filter/map/slice/spread/concat) are safe.
            before = s_body[max(0, m.start() - 200):m.start() + len(m.group(1))]
            tail = before.rstrip()
            if re.search(r"(\.(filter|map|slice|concat|flatMap)\([^;]*\)|\[\.\.\.[^\]]*\]|Array\.from\([^)]*\)|Object\.(values|keys|entries)\([^)]*\))\s*$", tail, re.S):
                continue
            add("inplace-mutation", s_start + s_body.count("\n", 0, m.start()),
                f"{m.group(1).lstrip('.')}.{m.group(2)}() may mutate reactive data in place")
        for m in re.finditer(r"deep\s*:\s*true", s_body):
            add("deep-watch", s_start + s_body.count("\n", 0, m.start()), "watcher uses deep: true")
        added = len(re.findall(r"\baddEventListener\(", s_body))
        removed = len(re.findall(r"\bremoveEventListener\(", s_body))
        if added > removed:
            m = re.search(r"\baddEventListener\(", s_body)
            add("unpaired-listener", s_start + s_body.count("\n", 0, m.start()),
                f"{added} addEventListener vs {removed} removeEventListener")
        for m in FUNC_DEF.finditer(s_body):
            defs[m.group(1)].append((rel, s_start + s_body.count("\n", 0, m.start())))
        for m in API_CALL.finditer(s_body):
            api_usage[m.group(1)].add(rel)

    return {
        "file": rel,
        "lines": text.count("\n") + 1,
        "template": count_lines(tmpl),
        "script": count_lines(script),
        "style": count_lines(blocks["style"]),
        "api": api_style,
        "watch": len(re.findall(r"\bwatch(?:Effect)?\(", script_text)),
        "computed": len(re.findall(r"\bcomputed\(", script_text)),
    }


def shared_exports(src_root: Path) -> dict:
    """Names exported from utils/ and composables/, mapped to their file."""
    exports = {}
    for sub in ("utils", "composables"):
        for f in sorted((src_root / sub).glob("*.[jt]s")) if (src_root / sub).exists() else []:
            for m in re.finditer(r"export\s+(?:async\s+)?(?:function|const|let)\s+([\w$]+)", f.read_text(encoding="utf-8")):
                exports[m.group(1)] = str(f.relative_to(src_root.parent))
    return exports


def main(argv):
    as_json = "--json" in argv
    paths = [Path(a).resolve() for a in argv if a != "--json"]
    if not paths:
        print(__doc__)
        return 2

    files = []
    for p in paths:
        files += sorted(p.rglob("*.vue")) if p.is_dir() else [p]
    if not files:
        print("No .vue files found", file=sys.stderr)
        return 1

    src_root = find_src_root(paths[0] if paths[0].is_dir() else paths[0].parent)
    base = src_root.parent

    def rel(p: Path) -> str:
        try:
            return str(p.relative_to(base))
        except ValueError:
            return str(p)

    # Cross-file checks need every component, even if only a subset was requested.
    all_files = sorted(src_root.rglob("*.vue"))
    target = {rel(f) for f in files}
    leads, defs, api_usage, stats = [], defaultdict(list), defaultdict(set), []
    for f in all_files:
        file_leads = []
        s = scan_file(f, rel(f), file_leads, defs, api_usage)
        if rel(f) in target:
            stats.append(s)
            leads += file_leads

    exports = shared_exports(src_root)
    for name, sites in sorted(defs.items()):
        local = [(f, l) for f, l in sites if f in target]
        if name in exports:
            for f, l in local:
                leads.append({"kind": "redefines-shared-helper", "file": f, "line": l,
                              "detail": f"{name} is also exported from {exports[name]}"})
        elif len({f for f, _ in sites}) >= 2 and local and not name.startswith(("load", "fetch", "handle", "on")) and len(name) > 3:
            others = ", ".join(sorted({f for f, _ in sites}))
            f, l = local[0]
            leads.append({"kind": "duplicate-function-name", "file": f, "line": l,
                          "detail": f"{name} defined in {len({x for x, _ in sites})} files: {others}"})

    shared_api = {m: sorted(fs) for m, fs in sorted(api_usage.items()) if len(fs) >= 2 and fs & target}

    eager_routes = []
    main_js = src_root / "main.js"
    if main_js.exists():
        mtext = main_js.read_text(encoding="utf-8")
        eager_routes = [{"name": m.group(1), "path": m.group(2), "line": line_of(mtext, m.start())}
                        for m in EAGER_VIEW_IMPORT.finditer(mtext)]

    leads.sort(key=lambda x: (x["file"], x["line"]))
    if as_json:
        print(json.dumps({"files": stats, "leads": leads, "shared_api_calls": shared_api,
                          "eager_route_imports": eager_routes}, indent=2))
        return 0

    print("## Component sizes (largest first)\n")
    print("| File | Lines | Template | Script | Style | API | watch | computed |")
    print("|---|---:|---:|---:|---:|---|---:|---:|")
    for s in sorted(stats, key=lambda s: -s["lines"]):
        print(f"| {s['file']} | {s['lines']} | {s['template']} | {s['script']} | {s['style']} | {s['api']} | {s['watch']} | {s['computed']} |")

    print(f"\n## Leads ({len(leads)}) - verify each by reading the code\n")
    by_kind = defaultdict(list)
    for lead in leads:
        by_kind[lead["kind"]].append(lead)
    for kind, items in by_kind.items():
        print(f"### {kind} ({len(items)})")
        for lead in items:
            print(f"- {lead['file']}:{lead['line']} - {lead['detail']}")
        print()

    if shared_api:
        print("## API methods called from several components (possible refetching or a shared composable)\n")
        for method, fs in shared_api.items():
            print(f"- api.{method}: {', '.join(fs)}")
        print()

    if eager_routes:
        print(f"## Eagerly imported route components in {rel(main_js)} ({len(eager_routes)})\n")
        for r in eager_routes:
            print(f"- line {r['line']}: {r['name']} from {r['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
