"""The Italian commentary agrees in number with a club name, and nothing recorded can say otherwise.

A club name is one subject in Italian sports prose ("Northgate passa in vantaggio", see test_stakes). The first
templates gave it the plural verb of its players ("Northgate danno il via") and put "del" before every name,
which is wrong before "Harbour" ("del Harbour"). The replies recorded from the model had copied those sentences,
so the check below runs on what a listener can hear, from the templates and from the replay.
"""

import re

import pytest

from app.contracts import Profile
from app.describer import Context, TemplateDescriber
from app.match_gen import SEED, generate_match
from app.moments import detect_moments
from app.pipeline import build_presets, build_session, describer_from_env

MATCH = generate_match(SEED)
TEAMS = "|".join(re.escape(t.short) for t in (MATCH.home, MATCH.away))
PLURAL_WITH_A_CLUB = re.compile(
    rf"\b(?:{TEAMS}) (?:danno|attaccano|riconquistano|costruiscono|manovrano|avanzano|recuperano)\b"
)
ARTICLE_BEFORE_A_CLUB = re.compile(rf"\bdel (?:{TEAMS})\b")


def wrong_italian(text: str) -> list[str]:
    return [m.group(0) for rx in (PLURAL_WITH_A_CLUB, ARTICLE_BEFORE_A_CLUB) for m in rx.finditer(text)]


def test_the_templates_give_a_club_name_a_singular_verb_and_no_article():
    ctx = Context(MATCH, "it")
    described = TemplateDescriber().describe(detect_moments(MATCH.events, "full"), ctx, {}, 1)
    texts = [t for d in described.values() for t in (d.full, d.short)]
    assert any("Northgate" in t or "Harbour" in t for t in texts)
    assert [bad for t in texts for bad in wrong_italian(t)] == []


@pytest.mark.parametrize("detail", ["essential", "standard", "full"])
def test_a_recorded_reply_with_the_old_wording_is_never_spoken(monkeypatch, detail):
    monkeypatch.setenv("SOUNDPITCH_LLM", "replay")
    describer = describer_from_env()
    for preset in build_presets(MATCH):
        session = build_session(MATCH, preset, Profile(detail=detail, lang="it"), describer)
        heard = [c.text for c in session.cues]
        assert [bad for t in heard for bad in wrong_italian(t)] == [], preset.id
        assert session.report.fallback == 0 and session.report.verified == session.report.moments
