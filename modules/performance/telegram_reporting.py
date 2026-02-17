from __future__ import annotations

from modules.performance.notifier import send_performance_text


def _perf_cfg(cfg: dict) -> dict:
    perf = cfg.get("performance", {}) if isinstance(cfg, dict) else {}
    return {
        "telegram_enabled": bool(perf.get("telegram_enabled", True)),
        "telegram_min_n": int(perf.get("telegram_min_n", 30)),
        "telegram_min_n_regime": int(perf.get("telegram_min_n_regime", 20)),
        "telegram_min_n_bucket": int(perf.get("telegram_min_n_bucket", 15)),
    }


def is_statistically_relevant(report: dict, cfg: dict) -> bool:
    c = _perf_cfg(cfg)
    by_h = report.get("by_horizon", {}) if isinstance(report, dict) else {}

    valid = []
    for h in ("1d", "3d", "5d"):
        row = by_h.get(h, {})
        n = int(row.get("n", 0) or 0)
        exp = row.get("expectancy")
        if n >= c["telegram_min_n"] and exp is not None and float(exp) != 0.0:
            valid.append(h)

    return bool(valid)


def _line_h(h: str, row: dict) -> str:
    n = int(row.get("n", 0) or 0)
    wr = round(float(row.get("win_rate", 0) or 0) * 100)
    avg_win = float(row.get("avg_win", 0) or 0)
    avg_loss = abs(float(row.get("avg_loss", 0) or 0))
    exp = float(row.get("expectancy", 0) or 0)
    return (
        f"{h}:\n"
        f"n={n} | WR={wr}%\n"
        f"AvgWin=+{avg_win:.2f}% | AvgLoss=-{avg_loss:.2f}%\n"
        f"Expectancy={exp:+.2f}%"
    )


def build_telegram_summary(report: dict, cfg: dict) -> str:
    c = _perf_cfg(cfg)
    lines = ["📊 PERFORMANCE WEEKLY (stat. valid)"]

    by_h = report.get("by_horizon", {})
    valid_h = []
    for h in ("1d", "3d", "5d"):
        row = by_h.get(h, {})
        n = int(row.get("n", 0) or 0)
        exp = row.get("expectancy")
        if n >= c["telegram_min_n"] and exp is not None and float(exp) != 0.0:
            valid_h.append(h)
            lines.extend(["", _line_h(h, row)])

    by_regime = report.get("by_regime", {})
    regime_rows = []
    for reg, data in by_regime.items():
        k3 = (data or {}).get("3d", {})
        if int(k3.get("n", 0) or 0) >= c["telegram_min_n_regime"]:
            regime_rows.append((reg, k3))
    if regime_rows:
        lines.append(f"\nRegime (n≥{c['telegram_min_n_regime']}):")
        for reg, row in regime_rows[:4]:
            lines.append(f"{reg} → Exp={float(row.get('expectancy',0) or 0):+.2f}%")

    by_bucket = report.get("by_bucket", {})
    bucket_rows = []
    for key, row in by_bucket.items():
        if "factor_score>=" not in key:
            continue
        if int(row.get("n", 0) or 0) >= c["telegram_min_n_bucket"]:
            bucket_rows.append((key, row))
    if bucket_rows:
        lines.append(f"\nScore (n≥{c['telegram_min_n_bucket']}):")
        for key, row in bucket_rows[:4]:
            label = key.replace("factor_score>=", "≥")
            lines.append(f"{label} → Exp={float(row.get('expectancy',0) or 0):+.2f}%")

    best_regime = max(regime_rows, key=lambda x: float(x[1].get("expectancy", 0)), default=None)
    best_bucket = max(bucket_rows, key=lambda x: float(x[1].get("expectancy", 0)), default=None)
    lines.append("\nFazit:")
    if best_regime:
        lines.append(f"Signale performen klar besser im {best_regime[0]}-Umfeld.")
    else:
        lines.append("Keine statistisch relevanten Regime-Daten.")
    if best_bucket:
        lines.append(f"Bester Score-Bucket: {best_bucket[0].replace('factor_score>=', '≥')}.")

    return "\n".join(lines)[:2490]


def send_if_relevant(report: dict, cfg: dict) -> None:
    c = _perf_cfg(cfg)
    if not c["telegram_enabled"]:
        print("performance_telegram_disabled")
        return

    if not is_statistically_relevant(report, cfg):
        print("performance_not_statistically_relevant")
        return

    try:
        text = build_telegram_summary(report, cfg)
        sent = send_performance_text(text, cfg)
        print("performance_telegram_sent" if sent else "performance_telegram_send_failed")
    except Exception as exc:
        print(f"performance_telegram_error:{type(exc).__name__}")
