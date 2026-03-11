from __future__ import annotations

from typing import Iterable


WARNING_LABELS = {
    "UNVOLLSTAENDIG": "UNVOLLSTAENDIG",
    "VERALTET": "VERALTET",
    "KOSTEN_NICHT_GEDECKT": "KOSTEN NICHT GEDECKT",
    "MARKT_GESCHLOSSEN": "MARKT GESCHLOSSEN",
    "NOCH_NICHT_BEWERTBAR": "NOCH NICHT BEWERTBAR",
    "API_DRUCK": "API-DRUCK / BETRIEBSSTRESS",
}


def warning_label(code: object) -> str:
    key = str(code or "").strip().upper()
    return WARNING_LABELS.get(key, key.replace("_", " "))


def warning_line(code: object, detail: object | None = None) -> str:
    label = warning_label(code)
    text = str(detail or "").strip().rstrip(".")
    return f"{label}: {text}." if text else label


def warning_lines(items: Iterable[object]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, tuple) and len(item) >= 2:
            line = warning_line(item[0], item[1])
        else:
            line = str(item or "").strip()
        if not line or line in seen:
            continue
        lines.append(line)
        seen.add(line)
    return lines
