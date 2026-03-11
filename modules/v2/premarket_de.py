from __future__ import annotations

import argparse

from modules.performance.notifier import send_performance_text
from modules.v2.telegram.copy import candidate_name, classification_label, display_name, market_label, premarket_priority, premarket_section_title, short_name
from modules.v2.telegram.help import load_latest_recommendations as _load_latest_recommendations

EU_COUNTRIES = {
    "AT",
    "BE",
    "CH",
    "DE",
    "DK",
    "ES",
    "FI",
    "FR",
    "IE",
    "IT",
    "LU",
    "NL",
    "NO",
    "PT",
    "SE",
}
EU_SYMBOL_SUFFIXES = (".DE", ".AS", ".PA", ".MI", ".MC", ".BR", ".LS", ".SW", ".VI", ".CO", ".ST", ".HE", ".OL")
ALLOWED_LABELS = {"KAUFEN PRUEFEN", "VERKAUFEN PRUEFEN", "RISIKO REDUZIEREN"}


def load_latest_recommendations(cfg: dict) -> list[dict]:
    return _load_latest_recommendations(cfg)


def _score_value(candidate: dict) -> float:
    label = classification_label(candidate.get("classification"), candidate)
    raw = (candidate.get("defense_score") or {}).get("defense_score") if label in {"RISIKO REDUZIEREN", "VERKAUFEN PRUEFEN"} else (candidate.get("opportunity_score") or {}).get("total_score")
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _de_relevant(candidate: dict) -> bool:
    country = str(candidate.get("country") or "").strip().upper()
    symbol = str(candidate.get("symbol") or "").strip().upper()
    isin = str(candidate.get("isin") or "").strip().upper()
    if country in EU_COUNTRIES:
        return True
    if isin[:2] in EU_COUNTRIES:
        return True
    return symbol.endswith(EU_SYMBOL_SUFFIXES)


def _line(candidate: dict) -> str:
    return f"- {short_name(candidate, max_len=56)}"


def build_premarket_summary_de(recommendations: list[dict], cfg: dict) -> str:
    rows = [
        row
        for row in recommendations
        if str(row.get("classification") or "").upper() != "IGNORE"
        and _de_relevant(row)
        and classification_label(row.get("classification"), row) in ALLOWED_LABELS
    ]
    rows.sort(
        key=lambda row: (
            premarket_priority(row.get("classification"), row),
            -_score_value(row),
            candidate_name(row).lower(),
        )
    )
    top_rows = rows[:5]
    regime = market_label(next((row.get("regime") for row in rows if row.get("regime")), "neutral"))
    if not top_rows:
        return (
            f"{display_name(cfg)} – Voreröffnung Deutschland\n\n"
            "Heute kein klarer Schwerpunkt.\n\n"
            f"Marktlage: {regime}\n\n"
            "Nächster Schritt:\n"
            "Nur bestehende Positionen aufmerksam verfolgen."
        )[:1000]

    lines = [f"{display_name(cfg)} – Voreröffnung Deutschland", "", "Heute wichtig:", ""]
    for label in ("VERKAUFEN PRUEFEN", "RISIKO REDUZIEREN", "KAUFEN PRUEFEN"):
        subset = [row for row in top_rows if classification_label(row.get("classification"), row) == label]
        if not subset:
            continue
        lines.append(f"{premarket_section_title(label)}:")
        lines.extend(_line(row) for row in subset)
        lines.append("")
    lines.extend([f"Marktlage: {regime}", "", "Nächster Schritt:", "Vor Xetra-Start prüfen."])
    return "\n".join(lines).strip()[:1000]


def send_premarket_summary_de(cfg: dict) -> bool:
    text = build_premarket_summary_de(load_latest_recommendations(cfg), cfg)
    return send_performance_text(text, cfg)


def _cli() -> None:
    from modules.v2.config import load_v2_config

    parser = argparse.ArgumentParser(description="CB Fund Desk premarket briefing Germany")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        cfg = load_v2_config()
        text = build_premarket_summary_de(load_latest_recommendations(cfg), cfg)
        print(text)
        send_performance_text(text, cfg)


if __name__ == "__main__":
    _cli()
