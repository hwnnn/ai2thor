from __future__ import annotations

from typing import Any, Dict, List


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Parse a constrained YAML subset used by prompt spec files.

    Supported forms:
    - top-level `key: value`
    - top-level `key:` + nested 2-space map
    - top-level `key:` + nested 2-space scalar list (`- item`)
    - top-level `key: |` literal block with 2-space indentation
    """

    lines = text.splitlines()
    out: Dict[str, Any] = {}
    i = 0

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if raw.startswith(" "):
            i += 1
            continue

        if ":" not in raw:
            i += 1
            continue

        key, rest = raw.split(":", 1)
        key = key.strip()
        rest_value = rest.strip()

        if rest_value == "|":
            i += 1
            block: List[str] = []
            while i < len(lines):
                ln = lines[i]
                if ln.startswith("  "):
                    block.append(ln[2:])
                    i += 1
                    continue
                if not ln.strip():
                    block.append("")
                    i += 1
                    continue
                break
            out[key] = "\n".join(block).rstrip("\n")
            continue

        if rest_value == "":
            i += 1

            if i < len(lines) and lines[i].startswith("  - "):
                arr: List[str] = []
                while i < len(lines) and lines[i].startswith("  - "):
                    arr.append(lines[i][4:].strip())
                    i += 1
                out[key] = arr
                continue

            if i < len(lines) and lines[i].startswith("  "):
                nested: Dict[str, str] = {}
                while i < len(lines) and lines[i].startswith("  "):
                    nested_line = lines[i][2:]
                    if ":" in nested_line:
                        nk, nv = nested_line.split(":", 1)
                        nested[nk.strip()] = nv.strip()
                    i += 1
                out[key] = nested
                continue

            out[key] = ""
            continue

        out[key] = rest_value
        i += 1

    return out
