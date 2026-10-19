"""S5: the planner fits speech into the gaps, never overlaps, never drops a must-say moment."""

import itertools
import random

from app.contracts import Description, Moment
from app.timing import GAP_MS, LEAD_MS, MAX_LAG_MS, Candidate, estimate_ms, plan


def candidate(moment_id, t, priority, full_words, short_words=2, lang="en"):
    moment = Moment(id=moment_id, t=t, priority=priority, kind="shot", team="home", event_ids=[moment_id])
    description = Description(
        moment_id=moment_id,
        lang=lang,
        full=" ".join(["word"] * full_words),
        short=" ".join(["word"] * short_words),
        refs=[],
    )
    return Candidate(moment, description, "verified", 0.0)


def test_estimate_scales_with_words_rate_and_language():
    text = " ".join(["word"] * 10)
    assert estimate_ms(text, "en", 1.0) == round(10 * 60_000 / 165) + 300
    assert estimate_ms(text, "en", 2.0) < estimate_ms(text, "en", 1.0)
    assert estimate_ms(text, "it", 1.0) > estimate_ms(text, "en", 1.0)
    assert estimate_ms("", "en", 1.0) == 300


def test_a_lone_moment_starts_just_after_the_event():
    cues, dropped = plan([candidate(1, 10, 2, 5)], 0, 1.0)
    assert dropped == [] and cues[0].start_ms == 10_000 + LEAD_MS
    assert cues[0].end_ms - cues[0].start_ms == estimate_ms(cues[0].text, "en", 1.0)


def test_cues_never_overlap_and_keep_a_gap_in_a_crowd():
    rng = random.Random(7)
    crowd = [candidate(i, rng.randint(0, 20), rng.randint(0, 3), rng.randint(4, 25)) for i in range(1, 40)]
    cues, dropped = plan(crowd, 0, 1.0)
    assert cues and dropped
    assert all(b.start_ms >= a.end_ms + GAP_MS for a, b in itertools.pairwise(cues))
    assert len(cues) + len(dropped) == len(crowd)


def test_must_say_moments_are_never_dropped_even_past_the_lag():
    crowd = [candidate(i, 5, 3, 22) for i in range(1, 6)]  # five goals at once
    cues, dropped = plan(crowd, 0, 1.0)
    assert dropped == [] and len(cues) == 5
    lag_limit = 5_000 + MAX_LAG_MS[3]
    assert cues[-1].start_ms > lag_limit  # placed late rather than lost


def test_other_priorities_are_dropped_when_they_cannot_start_in_time():
    blocker = candidate(1, 0, 3, 60)  # a long must-say sentence
    late = candidate(2, 1, 1, 6)
    cues, dropped = plan([blocker, late], 0, 1.0)
    assert [c.moment_id for c in cues] == [1]
    assert [d.moment_id for d in dropped] == [2]


def test_a_higher_priority_moment_is_not_dropped_because_of_lower_ones():
    rng = random.Random(3)
    crowd = [candidate(i, rng.randint(0, 30), rng.randint(0, 3), rng.randint(4, 30)) for i in range(1, 60)]
    _, dropped = plan(crowd, 0, 1.0)
    assert dropped
    for gone in dropped:
        peers = [c for c in crowd if c.moment.priority >= gone.priority]
        _, dropped_again = plan(peers, 0, 1.0)
        assert gone.moment_id in {d.moment_id for d in dropped_again}


def test_the_short_variant_is_used_when_the_full_one_does_not_fit():
    first = candidate(1, 0, 3, 20)  # occupies roughly 0.3 s to 7.9 s
    third = candidate(3, 12, 3, 8)  # starts at 12.3 s
    middle = candidate(2, 8, 2, 14, short_words=2)  # full ~5.5 s does not fit the ~4 s gap
    cues, dropped = plan([first, middle, third], 0, 1.0)
    chosen = next(c for c in cues if c.moment_id == 2)
    assert dropped == [] and chosen.variant == "short"
    assert chosen.end_ms + GAP_MS <= next(c for c in cues if c.moment_id == 3).start_ms


def test_planning_is_deterministic_and_window_relative():
    rng = random.Random(11)
    crowd = [candidate(i, 100 + rng.randint(0, 30), rng.randint(0, 3), rng.randint(4, 25)) for i in range(1, 30)]
    assert plan(crowd, 90, 1.0) == plan(list(reversed(crowd)), 90, 1.0)
    cues, _ = plan([candidate(1, 100, 2, 5)], 90, 1.0)
    assert cues[0].start_ms == 10_000 + LEAD_MS


def test_a_faster_rate_places_more_cues():
    rng = random.Random(5)
    crowd = [candidate(i, rng.randint(0, 25), rng.randint(0, 2), rng.randint(6, 20)) for i in range(1, 50)]
    slow, _ = plan(crowd, 0, 0.8)
    fast, _ = plan(crowd, 0, 1.6)
    assert len(fast) > len(slow)
