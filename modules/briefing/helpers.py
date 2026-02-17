from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def latest(path: Path, pattern: str) -> Path | None:
    files = sorted(path.glob(pattern))
    return files[-1] if files else None


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def to_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def signal_time(signal: dict) -> datetime | None:
    key = str(signal.get("key", ""))
    parts = key.split(":")
    if len(parts) >= 4 and parts[0] == "mf":
        try:
            dt = datetime.fromisoformat(f"{parts[2]}T{parts[3]}")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    for field in ("created_at", "fetched_at"):
        raw = signal.get(field)
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _light_icon(light: str) -> str:
    return {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⚪"}.get(light, "⚪")


def _volume_line(briefing: dict) -> str:
    holdings = briefing.get("volume_lights", {}).get("holdings", [])
    if not holdings:
        return "Volumen: ⚪ n/a"
    parts = []
    for row in holdings[:3]:
        ratio = row.get("ratio")
        ratio_str = f"{ratio}x" if ratio is not None else "n/a"
        parts.append(f"{_light_icon(str(row.get('light')))} {ratio_str}")
    return "Volumen: " + " / ".join(parts)


def _delta_lines(briefing: dict) -> list[str]:
    delta = briefing.get("delta", {})
    if delta.get("status") != "ok":
        return ["Delta: kein Vorbriefing"]

    pos = delta.get("positions_delta", {})
    radar = delta.get("radar_delta", {})
    lines = []
    movers = pos.get("top_movers", [])
    if movers:
        top = movers[0]
        lines.append(f"Top-Move: {top.get('name') or top.get('isin')} ({top.get('delta_pnl_pct')}%)")
    lines.append(f"Neu/Raus Positionen: {len(pos.get('new_positions', []))}/{len(pos.get('removed_positions', []))}")
    lines.append(f"Radar Neu/Raus: {len(radar.get('new_opportunities', []))}/{len(radar.get('dropped_opportunities', []))}")
    return lines[:3]


def briefing_text(briefing: dict) -> str:
    date_str = datetime.now().strftime("%d.%m.%Y")
    lines = [f"📊 MORNING BRIEF - {date_str}", "", "🏦 Portfolio"]
    winners = briefing.get("holdings_block", {}).get("top_winners", [])
    losers = briefing.get("holdings_block", {}).get("top_losers", [])
    total_pnl = briefing.get("holdings_block", {}).get("total_pnl_pct")
    if winners:
        lines.append(f"Top: {winners[0].get('name')} +{winners[0].get('pnl_pct')}%")
    if losers:
        lines.append(f"Weak: {losers[0].get('name')} {losers[0].get('pnl_pct')}%")
    lines.append(f"Gesamt-PnL: {total_pnl}%")
    lines.append(_volume_line(briefing))

    lines.extend(["", "📡 Signale (Bestand)"])
    holdings_signals = briefing.get("holdings_signals", [])
    if holdings_signals:
        for s in holdings_signals[:5]:
            marker = "▲" if s.get("direction") == "up" else "▼" if s.get("direction") == "down" else "•"
            lines.append(f"{marker} {s.get('name') or s.get('isin')} (Score {s.get('factor_score')})")
    else:
        lines.append("Keine relevanten Bestandssignale")

    lines.extend(["", "🚀 Radar-Chancen"])
    opps = briefing.get("top_opportunities", [])
    if opps:
        for idx, opp in enumerate(opps[:3], start=1):
            name = opp.get("name") or opp.get("isin") or "n/a"
            lines.append(f"{idx}) {name} - {opp.get('reason')} (Score {opp.get('opportunity_score')}, {opp.get('confidence')})")
    else:
        lines.append("Keine Radar-Chancen über Schwelle")

    lines.extend(["", "Δ Delta"])
    lines.extend(_delta_lines(briefing))

    regime = briefing.get("regime", {})
    facts = regime.get("facts", {})
    lines.extend(["", "🧭 Regime"])
    lines.append(
        f"{regime.get('regime', 'neutral')} (UpStrong={facts.get('up_strong', 0)}, "
        f"DownStrong={facts.get('down_strong', 0)}, Breite={int(float(facts.get('pct_up', 0)) * 100)}%)"
    )

    lines.append("\nStatus: Monitoring")
    return "\n".join(lines)[:3490]
