"""Verify: every claim in a description must be supported by the moment's events (SPEC §5)."""

import re

from app.contracts import Description, Moment
from app.describer import Context

MAX_FULL_WORDS = 45
MAX_SHORT_WORDS = 15


def _words(text: str) -> int:
    return len(text.split())


class Verifier:
    def __init__(self, ctx: Context):
        self.ctx = ctx

    def check(self, moment: Moment, description: Description) -> list[str]:
        """Issues found in a description; an empty list means it passed."""
        ctx = self.ctx
        issues: list[str] = []
        for ref in description.refs:
            if ref.event_id not in moment.event_ids:
                issues.append(f"event {ref.event_id} is not part of moment {moment.id}")
                continue
            actual = getattr(ctx.by_id[ref.event_id], ref.field)
            if actual != ref.value:
                issues.append(f"event {ref.event_id}: {ref.field} is {actual!r}, not {ref.value!r}")

        involved = ctx.involved(moment)
        text = f"{description.full} {description.short}"
        for name in ctx.all_names:
            if name not in involved and re.search(rf"\b{name}\b", text):
                issues.append(f"{name} is not in this moment")

        last = ctx.by_id[moment.event_ids[-1]]
        allowed = {last.home_score, last.away_score, moment.t // 60}
        allowed |= {ctx.by_id[i].minute for i in moment.event_ids}
        for number in sorted({int(n) for n in re.findall(r"\d+", text)} - allowed):
            issues.append(f"number {number} is not supported by the events")

        if not description.short.strip() or not description.full.strip():
            issues.append("description is empty")
        if _words(description.full) > MAX_FULL_WORDS:
            issues.append(f"full text has more than {MAX_FULL_WORDS} words")
        if _words(description.short) > MAX_SHORT_WORDS:
            issues.append(f"short text has more than {MAX_SHORT_WORDS} words")
        if _words(description.short) > _words(description.full):
            issues.append("short text is longer than the full text")
        return issues
