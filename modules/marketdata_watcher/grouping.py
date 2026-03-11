from __future__ import annotations

from pathlib import Path

from modules.common.utils import read_json


def _latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def load_holdings_isins(cfg: dict) -> set[str]:
    root = Path(cfg.get("app", {}).get("root_dir", Path.cwd()))

    candidates = [
        _latest(root / "data" / "portfolio", "latest*.json"),
        _latest(root / "data" / "snapshots", "portfolio_*.json"),
    ]

    for path in candidates:
        if not path or not path.exists():
            continue
        try:
            data = read_json(path)
        except Exception:
            continue
        positions = data.get("positions", []) if isinstance(data, dict) else []
        out = {str(p.get("isin")) for p in positions if isinstance(p, dict) and p.get("isin")}
        if out:
            return out

    return set()


def classify_isin(isin: str, holdings_set: set[str]) -> str:
    if isin and isin in holdings_set:
        return "holdings"
    return "radar"
