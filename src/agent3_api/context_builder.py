from __future__ import annotations

from agent3_api.contracts import ConversationContext


def render_context_for_model(context: ConversationContext) -> str:
    """Render a bounded, program-owned dsh handoff context.

    Authorization details are deliberately reduced to a generic notice. Never
    place roles, scopes, tokens or principal identifiers in this model-visible
    representation.
    """

    lines = [
        "[DataAgent Conversation Context]",
        f"Objective: {context.user_objective}",
    ]
    if context.confirmed_metrics:
        lines.append("Confirmed metrics: " + ", ".join(context.confirmed_metrics))
    if context.confirmed_dimensions:
        lines.append("Confirmed dimensions: " + ", ".join(context.confirmed_dimensions))
    if context.previous_results_summary:
        lines.append("Previous result summary: " + context.previous_results_summary)
    if context.caveats:
        lines.append("Caveats: " + " | ".join(context.caveats))
    lines.append("Authorization: " + context.authz_summary)
    if context.unresolved:
        lines.append("Unresolved: " + " | ".join(context.unresolved))
    if context.page_context:
        lines.append("Page context: " + context.page_context)
    return "\n".join(lines)
