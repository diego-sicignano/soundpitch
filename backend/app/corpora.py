"""Hand-written commentary used by the evaluation (`app.evaluate`) to measure false rejection.

Placeholders are the fields of `describer.facts`. Every sentence is true for its moment: none of them
tests safety, they test how much valid wording the closed vocabulary of SPEC §5 turns away.

NATURAL was written as a commentator would, without looking at the vocabulary (two authors: the
project author and an independent reviewer). VOCAB_AWARE was written by the independent reviewer
with the per-key word lists in hand. Entries under "goal_assist" without {assist} also serve plain goals.
"""

Corpus = dict[str, dict[str, list[str]]]

NATURAL: Corpus = {
    "en": {
        "goal": ["Goal for {team}! {p} fires it into the net. {score}."],
        "goal_assist": [
            "Goal for {team}! {p} finishes, assisted by {a}. {score}.",
            "Goal! {p} scores for {team}, {assist}. {score}.",
            "What a finish from {p}! {team} score, {assist}. {score}.",
            "{p} slots it home for {team}. {score}.",
            "{p} scores. {score}.",
            "{p}'s goal for {team}, {assist}. {score}.",
        ],
        "shot_on_target": [
            "{p} of {team} strikes the ball {lane_from} and it is on target.",
            "{p} shoots {lane_from} and it's on target.",
            "{p} tests the keeper {lane_from}.",
            "Shot on target from {p}.",
        ],
        "shot_off_target": [
            "{p} of {team} drives a shot {lane_from} that goes wide of the post.",
            "{p} shoots {lane_from} but it goes wide.",
            "{p} fires wide {lane_from}.",
        ],
        "shot_blocked": [
            "{p} of {team} shoots {lane_from} but a defender gets in the way.",
            "{p} shoots {lane_from}, blocked.",
            "{p}'s shot is blocked.",
        ],
        "save": [
            "A save by the goalkeeper, {p}.",
            "{p} makes the save.",
            "Good save by {p}.",
            "{p} dives and saves.",
        ],
        "corner": [
            "{team} win a corner, {p} to take it {lane_from}.",
            "Corner to {team}, taken by {p} {lane_from}.",
            "Corner for {team}.",
        ],
        "free_kick": ["{team} have a free kick and {p} stands over it."],
        "foul": ["{p} of {team} commits a foul.", "Foul by {p} of {team}.", "{p} commits a foul."],
        "throw_in": ["Throw-in for {team} {side}.", "Throw-in to {team} {side}."],
        "turnover": [
            "{p} of {team} wins possession back {zone}.",
            "{p} of {team} wins the ball {zone}.",
            "{p} intercepts {zone}.",
        ],
        "buildup": [
            "{team} are building {lane_down}, with {chain} {zone}.",
            "{team} build {lane_down}: {chain}, {zone}.",
            "{team} pass it through {chain}.",
        ],
        "kickoff": [
            "We are under way, with {team} kicking off and attacking {dir}.",
            "Kick-off. {team} get us under way, attacking {dir}.",
            "We are under way, {team} kick off.",
        ],
        "halftime": ["That is half-time. {score}.", "Half-time. {score}.", "That's half-time. {score}."],
        "fulltime": [
            "That is full-time. {score}.",
            "Full-time. {score}.",
            "The final whistle. {score}.",
        ],
        "score_update": [
            "{minute} and it stands at {score}.",
            "Minute {m}. {score}.",
            "The score at minute {m}: {score}.",
        ],
    },
    "it": {
        "goal": ["Gol per il {team}! {p} la mette in rete. {score}."],
        "goal_assist": [
            "Gol per il {team}! {p} conclude, assistito da {a}. {score}.",
            "Gol! {p} segna per {team}, {assist}. {score}.",
            "Che gol di {p}! {score}.",
            "Rete di {p} per il {team}, {assist}.",
            "{p} segna per {team}. {score}.",
        ],
        "shot_on_target": [
            "{p} del {team} calcia {lane_from} e la palla è nello specchio.",
            "{p} tira {lane_from}, nello specchio.",
            "{p} calcia in porta {lane_from}.",
        ],
        "shot_off_target": [
            "{p} del {team} tira {lane_from} e la palla va a lato.",
            "{p} tira {lane_from} ma la palla finisce fuori.",
            "Tiro di {p} {lane_from}, fuori.",
        ],
        "shot_blocked": [
            "{p} del {team} tira {lane_from} ma un difensore la ferma.",
            "{p} tira {lane_from}, respinto.",
            "Tiro respinto: {p} {lane_from}.",
        ],
        "save": ["Intervento del portiere, {p}.", "Parata di {p}.", "Grande parata di {p}.", "{p} para il tiro."],
        "corner": [
            "Corner per il {team}, lo batte {p} {lane_from}.",
            "Calcio d'angolo per {team}, batte {p} {lane_from}.",
            "Angolo per {team}.",
        ],
        "free_kick": ["Punizione per il {team}, {p} è pronto a batterla."],
        "foul": [
            "{p} del {team} commette un fallo.",
            "Fallo di {p}, {team}.",
            "Fallo di {p} del {team}.",
            "{p} commette fallo.",
        ],
        "throw_in": [
            "Rimessa laterale per il {team} {side}.",
            "Rimessa laterale per {team} {side}.",
            "Rimessa per {team}.",
        ],
        "turnover": [
            "{p} del {team} riprende il possesso {zone}.",
            "{p} del {team} recupera palla {zone}.",
            "{p} intercetta {zone}.",
        ],
        "buildup": [
            "Il {team} costruisce {lane_down}, con {chain} {zone}.",
            "{team} costruisce {lane_down}: {chain}, {zone}.",
            "{team} avanza palla al piede {lane_down}.",
        ],
        "kickoff": [
            "Si parte, il {team} batte il calcio d'inizio e attacca {dir}.",
            "Calcio d'inizio. {team} dà il via, attacca {dir}.",
            "Si parte: {team} calcia il primo pallone.",
        ],
        "halftime": ["Siamo all'intervallo. {score}.", "Fine primo tempo. {score}.", "Siamo al riposo. {score}."],
        "fulltime": ["È finita. {score}.", "Fine partita. {score}.", "Triplice fischio. {score}."],
        "score_update": [
            "{minute} e il punteggio è {score}.",
            "Minuto {m}. {score}.",
            "Al minuto {m} il punteggio e' {score}.",
        ],
    },
}

VOCAB_AWARE: Corpus = {
    "en": {
        "goal_assist": [
            "It's in! {p} scores for {team}, {assist}. {score}.",
            "Goal for {team}! {p} finds the net, {assist}. {score}.",
            "Goal! {p} finishes for {team}, {assist}.",
            "{p} scores for {team}. {score}.",
            "Goal! {p} finds the net for {team}. {score}.",
        ],
        "shot_on_target": ["On target! {p} shoots {lane_from}.", "{p} has a go {lane_from} and it's on target."],
        "shot_off_target": ["{p} shoots {lane_from} but it goes wide.", "Wide! {p} lets fly {lane_from}."],
        "shot_blocked": ["{p} shoots {lane_from} and it's blocked."],
        "save": ["The keeper {p} gathers it.", "{p} makes the save and gathers it."],
        "foul": ["Foul by {p} of {team}.", "A foul by {p}, {team}."],
        "corner": [
            "A corner to {team}, taken by {p} {lane_from}.",
            "Corner to {team}.",
            "Corner for {team}, taken by {p}.",
        ],
        "throw_in": ["A throw-in to {team} {side}."],
        "free_kick": ["Free kick to {team}, {p} to take it.", "Free kick for {team}, taken by {p}."],
        "turnover": ["{team} win the ball back {zone}, through {p}.", "{p} wins it back for {team} {zone}."],
        "buildup": [
            "{team} move forward {lane_down}: {chain}, {zone}.",
            "{team} work the ball {lane_down} through {chain}, {zone}.",
        ],
        "halftime": ["Half-time. {score}."],
        "fulltime": ["Full-time! {score}."],
        "kickoff": ["Kick-off! {team} get us under way.", "Kick-off. {team} get us under way, attacking {dir}."],
        "score_update": ["Minute {m}. {score}.", "The score, minute {m}: {score}."],
    },
    "it": {
        "goal_assist": [
            "Rete! {p} segna per {team}, {assist}. {score}.",
            "Gol per {team}! {p} trova la rete, {assist}. {score}.",
            "Gol! {p} finalizza per {team}, {assist}.",
            "Gol! {p} segna. {score}.",
        ],
        "shot_on_target": ["{p} tira {lane_from}, in porta.", "{p} ci prova {lane_from} e inquadra la porta."],
        "shot_off_target": ["{p} calcia {lane_from}, fuori.", "{p} tira {lane_from} ma la palla finisce fuori."],
        "shot_blocked": ["{p} tira {lane_from} e il tiro e' respinto."],
        "save": ["Il portiere {p} blocca.", "Parata di {p}: il portiere blocca."],
        "foul": ["Fallo di {p}, {team}.", "Fallo di {p} del {team}."],
        "corner": ["Calcio d'angolo per {team}, batte {p} {lane_from}.", "Angolo per {team}, batte {p}."],
        "throw_in": ["Rimessa laterale per {team} {side}."],
        "free_kick": ["Punizione per {team}, batte {p}."],
        "turnover": ["{team} riconquista il possesso {zone}, con {p}.", "{p} recupera palla per {team} {zone}."],
        "buildup": ["{team} manovra {lane_down} con {chain}, {zone}.", "{team} avanza {lane_down}: {chain}, {zone}."],
        "halftime": ["Fine primo tempo. {score}."],
        "fulltime": ["Fine partita. {score}."],
        "kickoff": ["Calcio d'inizio. {team} dà il via."],
        "score_update": ["Minuto {m}. {score}."],
    },
}


def patterns_for(corpus: Corpus, lang: str, key: str) -> list[str]:
    """The sentences of a corpus that apply to a moment of this template key."""
    entries = corpus[lang]
    found = list(entries.get(key, []))
    if key == "goal":
        found += [p for p in entries.get("goal_assist", []) if "{assist}" not in p and "{a}" not in p]
    return found
