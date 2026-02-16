from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from modules.common.utils import ensure_dir, now_iso_tz, sha256_file, write_json


def _latest_pdf(inbox_dir: Path) -> Path:
    pdfs = list(inbox_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found in {inbox_dir}")
    return max(pdfs, key=lambda p: p.stat().st_mtime)


def collect_latest_pdf(inbox_dir: str | Path, raw_dir: str | Path) -> dict:
    inbox_path = Path(inbox_dir)
    raw_path = Path(raw_dir)
    ensure_dir(raw_path)

    src_pdf = _latest_pdf(inbox_path)
    run_id = str(uuid.uuid4())
    dst_pdf = raw_path / f"tr_depotauszug_{run_id}.pdf"
    shutil.copy2(src_pdf, dst_pdf)

    src_stat = src_pdf.stat()
    mtime = datetime.fromtimestamp(src_stat.st_mtime, ZoneInfo("Europe/Berlin")).isoformat()

    fingerprint = {
        "run_id": run_id,
        "sha256": sha256_file(dst_pdf),
        "size": src_stat.st_size,
        "mtime": mtime,
        "src": str(src_pdf),
        "dst": str(dst_pdf),
        "src_path": str(src_pdf),
        "dst_path": str(dst_pdf),
        "collected_at": now_iso_tz(),
    }

    fingerprint_path = raw_path / f"tr_depotauszug_{run_id}.fingerprint.json"
    write_json(fingerprint_path, fingerprint)

    # Prevent endless PathExistsGlob triggers by consuming the inbox file.
    processed_dir = raw_path / "processed_inbox"
    ensure_dir(processed_dir)
    consumed_path = processed_dir / f"{src_pdf.stem}_{run_id}.pdf"
    shutil.move(str(src_pdf), consumed_path)
    fingerprint["src_consumed_path"] = str(consumed_path)
    return fingerprint
