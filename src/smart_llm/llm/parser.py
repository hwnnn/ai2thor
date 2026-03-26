from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict


class LLMParseError(ValueError):
    pass


def _extract_braced_block(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return text[start:]


def parse_json_robust(raw_text: str) -> Dict[str, Any]:
    candidates = []
    stripped = raw_text.strip()
    candidates.append(stripped)

    fenced = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", stripped)
    candidates.extend(fenced)
    candidates.append(_extract_braced_block(stripped))

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Python dict literal fallback for sloppy model output.
        try:
            parsed = ast.literal_eval(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError):
            pass

        # Common case: single quotes around keys/values.
        normalized = re.sub(r"'([^']*)'", r'"\1"', candidate)
        normalized = re.sub(r",\s*([}\]])", r"\1", normalized)
        try:
            parsed = json.loads(normalized)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise LLMParseError("Unable to parse model output into JSON object")
