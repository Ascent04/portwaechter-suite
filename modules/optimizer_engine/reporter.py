from __future__ import annotations


def render_optimizer_md(proposal: dict) -> str:
    lines = [
        "# Optimizer Proposal",
        "",
        f"- Generated: {proposal.get('generated_at')}",
        f"- Max Position: {proposal.get('limits', {}).get('max_position_weight_pct')}%",
        f"- Max Top3: {proposal.get('limits', {}).get('max_top3_weight_pct')}%",
        "",
        "## Actions",
    ]

    for action in proposal.get("actions", []):
        lines.append(
            f"- {action.get('type').upper()} {action.get('name')} ({action.get('isin')}) -> "
            f"{action.get('target_weight_pct')}% ({action.get('reason')})"
        )

    lines.append("")
    lines.append("## Rationale")
    for item in proposal.get("rationale", []):
        lines.append(f"- {item}")

    return "\n".join(lines) + "\n"
