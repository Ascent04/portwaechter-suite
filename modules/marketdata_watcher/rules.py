from __future__ import annotations

from modules.marketdata_watcher.adaptive import compute_adaptive_floor, load_recent_quotes


def direction(pct: float) -> str:
    if pct > 0:
        return "up"
    if pct < 0:
        return "down"
    return "flat"


def group_thresholds(cfg: dict, group: str) -> dict:
    mcfg = cfg.get("marketdata_alerts", {})
    defaults = mcfg.get("group_defaults", {}) if isinstance(mcfg.get("group_defaults"), dict) else {}
    group_cfg = defaults.get(group, {}) if isinstance(defaults.get(group), dict) else {}

    min_delta = float(group_cfg.get("min_delta_pct", mcfg.get("min_delta_pct", 0.7)))
    min_direction = float(group_cfg.get("min_direction_pct", mcfg.get("min_direction_pct", 0.9)))
    threshold = float(group_cfg.get("threshold_pct", mcfg.get("threshold_pct", 5.0)))

    ad_cfg = mcfg.get("adaptive", {}) if isinstance(mcfg.get("adaptive"), dict) else {}
    group_floor = float(group_cfg.get("min_floor_pct", ad_cfg.get("min_floor_pct", 0.6)))

    return {
        "min_delta_pct": min_delta,
        "min_direction_pct": min_direction,
        "threshold_pct": threshold,
        "min_floor_pct": group_floor,
    }


def effective_thresholds(cfg: dict, group: str, isin: str, cache: dict[str, list[float]]) -> dict:
    static = group_thresholds(cfg, group)
    mcfg = cfg.get("marketdata_alerts", {})
    ad_cfg = mcfg.get("adaptive", {}) if isinstance(mcfg.get("adaptive"), dict) else {}

    eff_delta = static["min_delta_pct"]
    eff_direction = static["min_direction_pct"]
    adaptive_floor = None

    if ad_cfg.get("enabled", False):
        if isin not in cache:
            cache[isin] = load_recent_quotes(cfg, isin)
        points = cache.get(isin, [])
        if len(points) >= 5:
            adaptive_floor = compute_adaptive_floor(
                points,
                k_multiplier=float(ad_cfg.get("k_multiplier", 1.2)),
                min_floor_pct=float(ad_cfg.get("min_floor_pct", 0.6)),
                max_floor_pct=float(ad_cfg.get("max_floor_pct", 2.5)),
            )
            apply_to = {str(x) for x in ad_cfg.get("apply_to", [])}
            if "min_delta_pct" in apply_to:
                eff_delta = max(eff_delta, adaptive_floor)
            if "min_direction_pct" in apply_to:
                eff_direction = max(eff_direction, adaptive_floor)

    return {
        "effective_min_delta": float(eff_delta),
        "effective_min_direction": float(eff_direction),
        "threshold_pct": float(static["threshold_pct"]),
        "min_floor_global": float(max(static["min_floor_pct"], eff_delta)),
        "adaptive_floor": adaptive_floor,
    }


def evaluate_triggers(current_pct: float, prev: dict, thresholds: dict, cfg: dict) -> tuple[list[str], float, str, str | None]:
    mcfg = cfg.get("marketdata_alerts", {})
    last_pct = prev.get("last_pct")
    last_val = float(last_pct) if last_pct is not None else None

    delta_pct = round(current_pct - last_val, 2) if last_val is not None else round(current_pct, 2)
    cur_dir = direction(current_pct)
    last_dir = str(prev.get("last_dir", direction(last_val or 0.0)))

    abs_current = abs(current_pct)
    abs_last = abs(last_val) if last_val is not None else None
    threshold = float(thresholds["threshold_pct"])
    threshold_cross = abs_last is not None and abs_last < threshold and abs_current >= threshold

    if abs_current < float(thresholds["min_floor_global"]) and not threshold_cross:
        if abs_current < float(thresholds["effective_min_delta"]):
            return [], delta_pct, cur_dir, "below_min_delta"
        return [], delta_pct, cur_dir, "below_threshold_pct"

    if last_val is None:
        if abs_current >= threshold:
            return ["initial_threshold"], delta_pct, cur_dir, None
        return [], delta_pct, cur_dir, "below_threshold_pct"

    triggers: list[str] = []
    if mcfg.get("send_on_delta", True) and abs(delta_pct) >= float(thresholds["effective_min_delta"]):
        triggers.append("delta")
    if (
        mcfg.get("send_on_direction_change", True)
        and cur_dir != last_dir
        and abs_current >= float(thresholds["effective_min_direction"])
    ):
        triggers.append("direction_change")
    if mcfg.get("send_on_threshold_cross", True) and threshold_cross:
        triggers.append("threshold_cross")

    if triggers:
        return triggers, delta_pct, cur_dir, None

    if abs_current < threshold:
        return [], delta_pct, cur_dir, "below_threshold_pct"
    return [], delta_pct, cur_dir, "below_min_delta"
