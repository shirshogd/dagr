"""scan: a deterministic inventory of a user's ICM tree. Stdlib only.

Writes `.dagr/scan.json` and `.dagr/scan.md`. It only reports what is on disk (no model, no
guessing about meaning, no timestamps), so the same tree always gives the same output. The
agent doing the integration adds judgment on top.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import contracts as ct
from . import frontmatter as fmt

L0_NAMES = ["CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules", ".windsurfrules",
            ".github/copilot-instructions.md"]
KNOWLEDGE_NAMES = {"knowledge", "reference", "references", "refs", "resources", "library",
                   "wiki", "kb", "notes", "_context", "context", "brand", "research",
                   "shared", "memory", "glossary", "playbooks", "templates", "examples"}
# "Inputs" in the languages people write ICM in; a table under it is the Inputs table.
INPUT_HEADINGS = ("input", "inputs", "entrada", "entradas", "entrée", "entrées", "eingabe",
                  "eingaben", "ingresso", "ingressi", "入力", "输入", "輸入", "ввод", "входные данные")
_HEADING = re.compile(r"^#{1,6}\s*(.+?)\s*#*\s*$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


def _head(path, limit=200_000) -> str:
    try:
        with open(path, "rb") as f:
            return f.read(limit).decode("utf-8", "replace")
    except OSError:
        return ""


def headings(text, level=None):
    out = []
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m and (level is None or line.startswith("#" * level + " ")):
            out.append(m.group(1))
    return out


def has_inputs_table(text) -> bool:
    """True when a heading that means "Inputs" is followed (before the next heading) by a
    markdown table."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if not m or m.group(1).strip().strip("*_ ").lower() not in INPUT_HEADINGS:
            continue
        for nxt in lines[i + 1:]:
            if _HEADING.match(nxt):
                break
            if _TABLE_ROW.match(nxt):
                return True
    return False


def _has_section(text, names) -> bool:
    return any(h.strip().strip("*_ ").lower() in names for h in headings(text))


def _file_info(path, root) -> dict:
    text = _head(path)
    fm, errs, state = fmt.parse_text(text)
    _l, body, _s = fmt.split_frontmatter(text)
    return {
        "path": ct.rel(path, root),
        "bytes": Path(path).stat().st_size if Path(path).exists() else 0,
        "frontmatter": state,
        "frontmatter_keys": sorted(fm),
        "frontmatter_errors": errs,
        "id": fm.get("id") or "",
        "consumes": fmt.as_list(fm.get("consumes")),
        "produces": fmt.as_list(fm.get("produces")),
        "inputs_table": has_inputs_table(body),
        "has_process": _has_section(body, ("process", "proceso", "prozess", "processus")),
        "has_outputs": _has_section(body, ("output", "outputs", "salida", "salidas",
                                           "ausgabe", "sortie", "sorties")),
        "headings": headings(body, 2)[:12],
    }


def _count_files(d, cap=2000) -> int:
    n = 0
    for _dp, _dns, fns in ct.iter_dirs(d, skip_output=False):
        n += len(fns)
        if n >= cap:
            return cap
    return n


def scan(root) -> dict:
    root = Path(root).resolve()
    outputs_found: list = []
    l0 = []
    for name in L0_NAMES:
        p = root / name
        if p.is_file():
            l0.append({"path": name, "bytes": p.stat().st_size,
                       "frontmatter_keys": sorted(fmt.parse_text(_head(p))[0])})
    cur = root / ".cursor" / "rules"
    if cur.is_dir():
        for p in sorted(cur.glob("*.mdc")) + sorted(cur.glob("*.md")):
            l0.append({"path": ct.rel(p, root), "bytes": p.stat().st_size,
                       "frontmatter_keys": sorted(fmt.parse_text(_head(p))[0])})

    context_files, readmes, knowledge, wf_dirs = [], [], [], {}
    root_context = None
    dir_count = 0
    for dp, dns, fns in ct.iter_dirs(root, skip_output=True, outputs=outputs_found):
        dir_count += 1
        d = Path(dp)
        for fn in fns:
            if fn.lower() == "context.md":
                info = _file_info(d / fn, root)
                context_files.append(info)
                if d == root:
                    root_context = info["path"]
            elif fn.lower() == "readme.md" and ct.stage_dirs(d):
                readmes.append(_file_info(d / fn, root))
        if d != root and d.name.lower() in KNOWLEDGE_NAMES:
            knowledge.append({"path": ct.rel(d, root), "files": _count_files(d)})
        stages = [] if d.name.lower() in ct.STAGE_CONTAINERS else ct.stage_dirs(d)
        ctx = ct.context_file(d)
        reasons = []
        if len(stages) >= 2:
            reasons.append("two or more numbered or stages/ subfolders")
        elif stages:
            reasons.append("one numbered or stages/ subfolder")
        has_contract = False
        if ctx is not None:
            fm, _e, state = fmt.parse_text(ct.read(ctx))
            has_contract = ct.is_contract_fm(fm)
            if has_contract:
                reasons.append("contract frontmatter (id + consumes/produces)")
        elif (d / "README.md").is_file() and stages:
            fm, _e, state = fmt.parse_text(ct.read(d / "README.md"))
            if ct.is_contract_fm(fm):
                has_contract = True
                reasons.append("README.md with contract frontmatter")
        if (stages and (ctx is not None or len(stages) >= 2)) or has_contract:
            if d != root:
                wf_dirs[d] = (reasons, stages, ctx, has_contract)

    # stage folders are not workflows themselves (a numbered folder inside a stages/ dir)
    stage_set = {s for (_r, st, _c, _h) in wf_dirs.values() for s in st}
    workflows = []
    for d in sorted(wf_dirs, key=lambda p: ct.rel(p, root)):
        reasons, stages, ctx, has_contract = wf_dirs[d]
        if d in stage_set and not has_contract:
            continue
        st_info = []
        for s in stages:
            sc = ct.context_file(s)
            text = _head(sc) if sc else ""
            st_info.append({"path": ct.rel(s, root), "context": ct.rel(sc, root) if sc else None,
                            "inputs_table": has_inputs_table(text) if sc else False,
                            "own_output_dir": (s / "output").is_dir() or (s / "outputs").is_dir()})
        workflows.append({
            "path": ct.rel(d, root), "reasons": reasons,
            "contract": ct.rel(ctx, root) if ctx else None,
            "contract_declared": has_contract,
            "stages": st_info,
            "stages_missing_inputs_table": [s["path"] for s in st_info
                                            if s["context"] and not s["inputs_table"]],
            "stages_without_context": [s["path"] for s in st_info if not s["context"]],
        })

    outputs = [{"path": ct.rel(p, root), "files": _count_files(p)}
               for p in sorted(outputs_found, key=lambda p: ct.rel(p, root))]
    units, issues = ct.discover(root)
    knowledge.sort(key=lambda k: k["path"])
    context_files.sort(key=lambda c: c["path"])
    fm_files = [{"path": c["path"], "keys": c["frontmatter_keys"]}
                for c in context_files + readmes if c["frontmatter"] != "none"]
    fm_files += [{"path": f["path"], "keys": f["frontmatter_keys"]} for f in l0
                 if f["frontmatter_keys"]]
    return {
        "root": root.as_posix(),
        "l0_files": l0,
        "root_context": root_context,
        "context_files": context_files,
        "readme_contracts": readmes,
        "workflow_candidates": workflows,
        "declared_contracts": [{"id": u.id, "path": u.file_rel, "consumes": u.consumes,
                                "produces": u.produces} for u in sorted(units.values(),
                                                                       key=lambda u: u.id)],
        "contract_issues": issues,
        "output_folders": outputs,
        "knowledge_folders": knowledge,
        "existing_frontmatter": sorted(fm_files, key=lambda f: f["path"]),
        "stats": {"folders_walked": dir_count, "context_files": len(context_files),
                  "workflow_candidates": len(workflows),
                  "stages_missing_inputs_table": sum(
                      len(w["stages_missing_inputs_table"]) for w in workflows),
                  "contracts_declared": len(units)},
    }


def render_md(s: dict) -> str:
    L = ["# dagr scan", "", f"Root: `{s['root']}`", "",
         "A deterministic inventory of your folders: what is there, not what it means. The "
         "agent reads this and adds judgment.", ""]
    st = s["stats"]
    L += ["## Summary", "",
          f"- folders walked: {st['folders_walked']}",
          f"- CONTEXT.md files: {st['context_files']}",
          f"- workflow-looking folders: {st['workflow_candidates']}",
          f"- contracts already declared (id + consumes/produces): {st['contracts_declared']}",
          f"- stages with no Inputs table: {st['stages_missing_inputs_table']}", ""]
    L += ["## L0 files (the root agent instructions)", ""]
    L += [f"- `{f['path']}` ({f['bytes']} bytes)" for f in s["l0_files"]] or [
        "- none found (CLAUDE.md, AGENTS.md, GEMINI.md, .cursorrules, ...)"]
    L += ["", "## L1 (root CONTEXT.md)", "",
          f"- `{s['root_context']}`" if s["root_context"] else "- no root CONTEXT.md", ""]
    L += ["## Workflow-looking folders", ""]
    if not s["workflow_candidates"]:
        L.append("- none found")
    for w in s["workflow_candidates"]:
        c = f"`{w['contract']}`" if w["contract"] else "no CONTEXT.md"
        decl = "declared" if w["contract_declared"] else "no port frontmatter yet"
        L.append(f"- `{w['path']}`: {c} ({decl}); {len(w['stages'])} stage folder(s); "
                 + "; ".join(w["reasons"]))
        for sg in w["stages"]:
            L.append(f"  - `{sg['path']}`: context "
                     + ("yes" if sg["context"] else "MISSING")
                     + ", Inputs table " + ("yes" if sg["inputs_table"] else "no"))
    L += ["", "## Declared contracts", ""]
    L += [f"- `{c['id']}` ({c['path']}): consumes {c['consumes'] or '-'}; "
          f"produces {c['produces'] or '-'}" for c in s["declared_contracts"]] or ["- none"]
    if s["contract_issues"]:
        L += ["", "## Contract problems", ""]
        L += [f"- `{i['path']}`: {i['kind']}: {i['message']}" for i in s["contract_issues"]]
    L += ["", "## CONTEXT.md files", ""]
    for c in s["context_files"]:
        flags = ["frontmatter" if c["frontmatter"] == "ok" else "no frontmatter"]
        flags.append("Inputs table" if c["inputs_table"] else "no Inputs table")
        L.append(f"- `{c['path']}`: " + ", ".join(flags))
    if not s["context_files"]:
        L.append("- none")
    L += ["", "## Output folders", ""]
    L += [f"- `{o['path']}` ({o['files']} files)" for o in s["output_folders"]] or ["- none"]
    L += ["", "## Knowledge / reference-looking folders", ""]
    L += [f"- `{k['path']}` ({k['files']} files)" for k in s["knowledge_folders"]] or ["- none"]
    L += ["", "## Existing frontmatter", ""]
    L += [f"- `{f['path']}`: {', '.join(f['keys']) or '(empty)'}"
          for f in s["existing_frontmatter"]] or ["- none"]
    return "\n".join(L) + "\n"


def run_scan(root) -> dict:
    root = Path(root)
    s = scan(root)
    d = root / ".dagr"
    d.mkdir(parents=True, exist_ok=True)
    (d / "scan.json").write_bytes((json.dumps(s, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    (d / "scan.md").write_bytes((render_md(s)).encode("utf-8"))
    return s
