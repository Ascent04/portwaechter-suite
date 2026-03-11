from __future__ import annotations

import argparse
import json
from datetime import datetime
import logging

from modules.common.utils import ensure_dir, read_json, write_json
from modules.decision_engine.expectancy import load_latest_expectancy
from modules.integration.pw_to_virus import export_action_candidates_to_bridge
from modules.marketdata_watcher.volume_baseline import load_volume_baseline, save_volume_baseline, update_volume_baseline
from modules.v2.config import data_dir, load_v2_config, resolve_env_value, root_dir
from modules.v2.marketdata.api_governor import (
    current_mode,
    load_governor_state,
    reset_minute_if_needed,
    save_governor_state,
)
from modules.v2.marketdata.batch_quotes import fetch_quotes_for_instruments
from modules.v2.recommendations.classify import classify_candidate
from modules.v2.recommendations.render import render_recommendation
from modules.v2.scanner.orchestrator import run_scanner
from modules.v2.scoring.defense_score import compute_defense_score
from modules.v2.scoring.opportunity_score import compute_opportunity_score
from modules.v2.scoring.portfolio_priority import compute_portfolio_priority
from modules.v2.symbols import build_missing_mapping_report
from modules.v2.telegram.notifier import send_action, send_defense, send_watch_bundle
from modules.v2.universe.holdings_universe import load_current_holdings
from modules.v2.universe.scanner_universe import load_scanner_universe, merge_universes
from modules.v2.universe.scheduling import select_assets_for_run

log = logging.getLogger(__name__)


def _latest_regime(cfg: dict) -> str:
    briefings = sorted((root_dir(cfg) / "data" / "briefings").glob("morning_*.json"))
    if not briefings:
        return "neutral"
    briefing = read_json(briefings[-1])
    return str((briefing.get("regime") or {}).get("regime") or "neutral")


def _persist(cfg: dict, candidates: list[dict], recommendations: list[dict]) -> dict:
    out_dir = data_dir(cfg)
    ensure_dir(out_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    candidates_path = out_dir / f"candidates_{stamp}.json"
    recommendations_path = out_dir / f"recommendations_{stamp}.json"
    write_json(candidates_path, {"generated_at": datetime.now().isoformat(), "candidates": candidates})
    write_json(recommendations_path, {"generated_at": datetime.now().isoformat(), "recommendations": recommendations})
    return {"candidates_path": str(candidates_path), "recommendations_path": str(recommendations_path)}


def _update_baseline(cfg: dict, candidates: list[dict]) -> None:
    baseline_path = root_dir(cfg) / "data" / "marketdata" / "volume_baseline.json"
    baseline = load_volume_baseline(baseline_path)
    for candidate in candidates:
        quote = candidate.get("quote", {})
        if quote.get("status") != "ok":
            continue
        key = str(candidate.get("isin") or candidate.get("symbol") or "")
        update_volume_baseline(baseline, key, quote.get("volume"))
    save_volume_baseline(baseline_path, baseline)


def _notify(cfg: dict, recommendations: list[dict]) -> None:
    watches = [row for row in recommendations if row.get("classification") == "WATCH"]
    if watches:
        send_watch_bundle(watches, cfg)
    for row in recommendations:
        text = row.get("telegram_text")
        if not text:
            continue
        if row.get("classification") == "ACTION":
            send_action(row, text, cfg)
        elif row.get("classification") == "DEFENSE":
            send_defense(row, text, cfg)


def run(cfg: dict | None = None) -> dict:
    active_cfg = cfg or load_v2_config()
    holdings = load_current_holdings(active_cfg)
    scanner = load_scanner_universe(active_cfg)
    universe = merge_universes(holdings, scanner)
    governor_state = reset_minute_if_needed(load_governor_state(active_cfg), datetime.now())
    selected_universe = select_assets_for_run(universe, governor_state, active_cfg)
    save_governor_state(governor_state, active_cfg)
    selected_holdings = [row for row in selected_universe if row.get("group") == "holding"]
    selected_scanner = [row for row in selected_universe if row.get("group") != "holding"]
    mapping_report = build_missing_mapping_report(holdings, cfg=active_cfg)

    quotes = fetch_quotes_for_instruments(selected_universe, active_cfg, api_key=resolve_env_value(active_cfg, "TWELVEDATA_API_KEY"))
    candidates = run_scanner(active_cfg, holdings=selected_holdings, scanner=selected_scanner, quotes=quotes)
    regime = _latest_regime(active_cfg)
    expectancy = load_latest_expectancy(active_cfg)

    recommendations: list[dict] = []
    for candidate in candidates:
        candidate["regime"] = regime
        candidate["portfolio_priority"] = compute_portfolio_priority(candidate, holdings)
        opp_score = compute_opportunity_score(candidate, regime, expectancy)
        defense_score = compute_defense_score(candidate, regime, float(candidate.get("weight_pct", 0) or 0))
        classification = classify_candidate(candidate, opp_score, defense_score)
        candidate["opportunity_score"] = opp_score
        candidate["defense_score"] = defense_score
        candidate["classification"] = classification
        rendered = render_recommendation(
            candidate,
            classification,
            {"opportunity": opp_score, "defense": defense_score, "regime": regime},
            cfg=active_cfg,
        )
        recommendations.append({**rendered["json"], "telegram_text": rendered["telegram_text"]})

    bridge_paths = export_action_candidates_to_bridge(recommendations, active_cfg)
    _update_baseline(active_cfg, candidates)
    persisted = _persist(active_cfg, candidates, recommendations)
    _notify(active_cfg, [row for row in recommendations if row.get("classification") != "IGNORE"])
    governor_runtime = active_cfg.get("_api_governor_runtime", {}) if isinstance(active_cfg.get("_api_governor_runtime"), dict) else {}
    governor_summary = {
        "selected_assets": len(selected_universe),
        "holdings_count": sum(1 for row in selected_universe if row.get("group") == "holding"),
        "scanner_count": sum(1 for row in selected_universe if row.get("group") != "holding"),
        "api_cost": int(governor_runtime.get("api_cost", 0) or 0),
        "minute_used": int(governor_runtime.get("minute_used", governor_state.get("used_in_current_minute", 0)) or 0),
        "mode": str(governor_runtime.get("mode") or current_mode(governor_state, active_cfg)),
    }
    log.warning(
        "v2_governor_summary: selected_assets=%s holdings_count=%s scanner_count=%s api_cost=%s minute_used=%s mode=%s",
        governor_summary["selected_assets"],
        governor_summary["holdings_count"],
        governor_summary["scanner_count"],
        governor_summary["api_cost"],
        governor_summary["minute_used"],
        governor_summary["mode"],
    )
    return {
        "status": "ok",
        "mapping_report": mapping_report,
        "persisted": persisted,
        "candidates": candidates,
        "recommendations": recommendations,
        "bridge_exported": bridge_paths,
        "governor_summary": governor_summary,
    }


def _cli() -> None:
    parser = argparse.ArgumentParser(description="PortWächter V2 runner")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    if args.command == "run":
        result = run()
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "persisted": result["persisted"],
                    "mapping_report": result["mapping_report"],
                    "governor_summary": result["governor_summary"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    _cli()
