from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def now_iso_tz(tz: str = "Europe/Berlin") -> str:
    return datetime.now(ZoneInfo(tz)).isoformat()


def parse_de_number(s: str) -> float:
    if s is None:
        raise ValueError("Cannot parse number from None")

    text = str(s).replace("\xa0", " ").strip()
    match = re.search(r"[-+]?\d[\d\.,]*", text)
    if not match:
        raise ValueError(f"No number found in: {s!r}")

    number = match.group(0)
    normalized = number.replace(".", "").replace(",", ".")
    return float(normalized)


def write_json(path: str | Path, obj: object) -> None:
    out_path = Path(path)
    ensure_dir(out_path.parent)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def read_json(path: str | Path) -> object:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def append_jsonl(path: str | Path, obj: object) -> None:
    out_path = Path(path)
    ensure_dir(out_path.parent)
    line = json.dumps(obj, ensure_ascii=False)
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
