"""frontmatter: a small, forgiving YAML-subset reader/writer. Stdlib only.

Frontmatter is the block of `key: value` lines between two `---` lines at the top of a
markdown file. This reader handles the shapes ICM contracts and dagr tickets use:
scalars, inline lists `[a, b]` (also across lines), block lists (`- a`), and comments.
Keys are normalised: `blocked-by` is read as `blocked_by`.
"""
from __future__ import annotations

import os
import re

_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")


def strip_comment(s: str) -> str:
    if s.lstrip().startswith("#"):
        return ""
    i = s.find(" #")
    return (s[:i] if i >= 0 else s).rstrip()


def unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    return s


def split_frontmatter(text: str):
    """-> (frontmatter_lines, body, state). state is "none" (no block), "ok", or
    "unterminated" (opening --- but no closing one)."""
    text = text.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], text, "none"
    for j in range(1, len(lines)):
        if lines[j].strip() == "---":
            return lines[1:j], "\n".join(lines[j + 1:]), "ok"
    return [], text, "unterminated"


def parse_lines(lines):
    """-> (dict, errors). A line that is not a key, list item, comment or indented
    continuation is reported in errors (it is skipped, never fatal)."""
    out, errors = {}, []
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = _KEY.match(raw)
        if not m:
            if raw[:1] in (" ", "\t") or raw.lstrip().startswith("- "):
                continue   # stray continuation of something we do not model
            errors.append(f"line {i}: not a `key: value` line: {raw.strip()[:60]}")
            continue
        key, rest = m.group(1).replace("-", "_"), strip_comment(m.group(2))
        if rest.startswith("["):
            buf = rest
            while buf.count("[") > buf.count("]") and i < len(lines):
                buf += " " + strip_comment(lines[i].strip())
                i += 1
            if buf.count("[") > buf.count("]"):
                errors.append(f"key {key}: unclosed [")
            end = buf.rfind("]")
            inner = buf.strip()[1:end] if end > 0 else buf.strip()[1:]
            out[key] = [unquote(x) for x in inner.split(",") if x.strip()]
        elif rest == "":
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(unquote(strip_comment(lines[i].strip()[2:])))
                i += 1
            if items:
                out[key] = items
            else:
                while i < len(lines) and lines[i][:1] in (" ", "\t"):
                    i += 1   # nested mapping: not modelled, skipped
                out[key] = ""
        else:
            out[key] = unquote(rest)
    return out, errors


def parse_text(text: str):
    """-> (dict, errors, state)"""
    lines, _body, state = split_frontmatter(text)
    fm, errs = parse_lines(lines)
    if state == "unterminated":
        errs = ["frontmatter opens with --- but never closes"] + errs
    return fm, errs, state


def as_list(v) -> list:
    if v is None or v == "":
        return []
    return list(v) if isinstance(v, list) else [v]


def sections(body: str) -> dict:
    """`## Heading` -> text below it, up to the next `## `."""
    secs, cur, buf = {}, None, []
    for line in body.splitlines():
        if line.startswith("## "):
            if cur is not None:
                secs[cur] = "\n".join(buf).strip()
            cur, buf = line[3:].strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        secs[cur] = "\n".join(buf).strip()
    return secs


def set_frontmatter(path, key, value) -> None:
    """Rewrite only the `key:` line of the frontmatter (insert before the closing --- if
    absent). Preserves line endings and every other byte."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: no frontmatter")
    end = None
    for j in range(1, len(lines)):
        if lines[j].strip() == "---":
            end = j
            break
    if end is None:
        raise ValueError(f"{path}: unterminated frontmatter")
    newline = f"{key}: {value}".rstrip() if value != "" else f"{key}:"
    pat = re.compile(rf"^{re.escape(key)}\s*:")
    for j in range(1, end):
        if pat.match(lines[j]):
            lines[j] = newline
            break
    else:
        lines.insert(end, newline)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(nl.join(lines))
    os.replace(tmp, path)
