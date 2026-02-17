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
    avg_loss = row.get("avg_loss", 0)
    return (
        f"Horizont {h}:\n"
        f"n={row.get('n', 0)}\n"
        f"WinRate={row.get('win_rate', 0)}\n"
        f"AvgWin=+{row.get('avg_win', 0)}%\n"
        f"AvgLoss=-{avg_loss}%\n"
        f"Expectancy={row.get('expectancy', 0):+}%"
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
        lines.append("\nRegime:")
        for reg, row in regime_rows[:4]:
            lines.append(f"{reg}: n={row.get('n',0)} exp={row.get('expectancy',0):+}%")

    by_bucket = report.get("by_bucket", {})
    bucket_rows = []
    for key, row in by_bucket.items():
        if "factor_score>=" not in key:
            continue
        if int(row.get("n", 0) or 0) >= c["telegram_min_n_bucket"]:
            bucket_rows.append((key, row))
    if bucket_rows:
        lines.append("\nScore Buckets:")
        for key, row in bucket_rows[:4]:
            lines.append(f"{key}: n={row.get('n',0)} exp={row.get('expectancy',0):+}%")

    best_regime = max(regime_rows, key=lambda x: float(x[1].get("expectancy", 0)), default=None)
    best_bucket = max(bucket_rows, key=lambda x: float(x[1].get("expectancy", 0)), default=None)
    lines.append("\nFazit:")
    lines.append(f"best regime: {best_regime[0] if best_regime else 'n/a'}")
    lines.append(f"best bucket: {best_bucket[0] if best_bucket else 'n/a'}")

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
