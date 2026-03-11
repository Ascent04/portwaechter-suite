from __future__ import annotations

import json
import re
from pathlib import Path
from urllib import parse, request

from modules.common.utils import ensure_dir


def extract_pdf_meta(message: dict) -> dict | None:
    doc = message.get("document")
    if not isinstance(doc, dict):
        return None
    file_id = str(doc.get("file_id") or "").strip()
    file_name = str(doc.get("file_name") or "").strip()
    mime_type = str(doc.get("mime_type") or "").lower()
    if not file_id:
        return None
    if mime_type == "application/pdf" or file_name.lower().endswith(".pdf"):
        return {"file_id": file_id, "file_name": file_name or "upload.pdf", "mime_type": mime_type}
    return None


def _safe_filename(name: str) -> str:
    base = Path(name or "upload.pdf").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    if not cleaned:
        cleaned = "upload.pdf"
    if not cleaned.lower().endswith(".pdf"):
        cleaned = f"{cleaned}.pdf"
    return cleaned


def _portfolio_inbox_path(cfg: dict) -> Path:
    inbox = cfg.get("portfolio", {}).get("source", {}).get("inbox")
    if inbox:
        return Path(str(inbox))
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))
    return root / "data" / "inbox"


def _fetch_file_path(token: str, file_id: str) -> str | None:
    query = parse.urlencode({"file_id": file_id})
    req = request.Request(f"https://api.telegram.org/bot{token}/getFile?{query}", method="GET")
    with request.urlopen(req, timeout=20) as res:
        payload = json.loads(res.read().decode("utf-8"))
    if not payload.get("ok"):
        return None
    file_path = ((payload.get("result") or {}).get("file_path") or "").strip()
    return file_path or None


def save_pdf_to_inbox(token: str, cfg: dict, file_id: str, file_name: str, update_id: int | str) -> dict:
    try:
        file_path = _fetch_file_path(token, file_id)
        if not file_path:
            return {"ok": False, "error": "telegram_getfile_failed"}
        download_req = request.Request(f"https://api.telegram.org/file/bot{token}/{file_path}", method="GET")
        with request.urlopen(download_req, timeout=40) as res:
            blob = res.read()

        inbox = _portfolio_inbox_path(cfg)
        ensure_dir(inbox)
        out_name = f"tg_{update_id}_{_safe_filename(file_name)}"
        out_path = inbox / out_name
        out_path.write_bytes(blob)
        return {"ok": True, "path": str(out_path)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
