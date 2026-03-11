from __future__ import annotations


def score_relative_strength(quote: dict, peer_group: list[float] | None = None) -> dict:
    if quote.get("status") != "ok" or quote.get("percent_change") is None:
        return {"score": 0, "status": "unavailable", "percentile": None}
    peers = sorted(float(value) for value in (peer_group or []) if value is not None)
    if len(peers) < 5:
        return {"score": 0, "status": "unavailable", "percentile": None}

    current = float(quote["percent_change"])
    rank = sum(1 for value in peers if value <= current) / len(peers)
    if rank >= 0.8:
        score = 2
    elif rank >= 0.6:
        score = 1
    else:
        score = 0
    return {"score": score, "status": "ok", "percentile": round(rank, 2)}

