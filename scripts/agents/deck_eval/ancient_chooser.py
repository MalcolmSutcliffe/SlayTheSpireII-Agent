"""Which relic to take from an ancient (Neow at the start of the run, then each act's Orobas, Pael, Tezcatara, Nonupeipe, Tanx, Vakuu or Darv).

Each relic on offer is taken by the engine's own pickup (its effect, its setup, the card or reward screens it queues: RunSimulator.take_ancient_relic) at the start of
every walk, and the walks go through a whole act from there (a new act: no rest sites, the fights an act is expected to hold; route_sim). All three are played on the same
walks, so the dice, the monsters and the relic draws are the same for each; the relic with the best mean reward is taken. At the start of the run that is the whole of act 1.

The screen gives the relics' names; the chooser finds the relic each one is (Sea Glass with the character in its title, Dusty Tome with a Corruption card). A name it does not know
leaves the choice to the caller (`choose` returns None). The analysis takes at most DeckEvalConfig.ancient_seconds."""
from __future__ import annotations
import re

from agents import unknowns

from sts2_lite.campaign import ancients
from sts2_lite.relic.ancient_data import NEOW_CURSES, NEOW_POSITIVE
from sts2_lite.relic.bag import relic_name

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor
from agents.deck_eval.route_sim import AncientPlan

EXTRA_RELICS = ("SEA_GLASS", "PRISMATIC_GEM", "TOUCH_OF_OROBAS", "ARCHAIC_TOOTH", "PAELS_WING", "PAELS_CLAW", "PAELS_TOOTH", "PAELS_GROWTH", "PAELS_LEGION", "LAVA_ROCK", "SMALL_CAPSULE",
                "NUTRITIOUS_OYSTER", "STONE_HUMIDIFIER", "NEOWS_TALISMAN", "POMANDER", "NUTRITIOUS_SOUP", "BEAUTIFUL_BRACELET", "TRI_BOOMERANG", "DUSTY_TOME", "LARGE_CAPSULE")
ID = re.compile(r"^[A-Z][A-Z0-9_]+$")


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(x, (tuple, list, set, frozenset)):
        for v in x:
            yield from _strings(v)


def plain(name : str) -> str:
    """A relic's name as it is compared: the game writes "Pael's Tears" where the engine's table has "Paels Tears"."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def known_relics() -> dict[str, str]:
    """{the name the screen shows, plain (see `plain`): relic id} for every relic an ancient can offer."""
    ids = set(EXTRA_RELICS) | set(_strings(NEOW_CURSES)) | set(_strings(NEOW_POSITIVE))
    for value in vars(ancients).values():
        if isinstance(value, (tuple, list, dict)):
            ids |= {x for x in _strings(value) if ID.match(x)}
    return {plain(relic_name(i)): i for i in ids}


def resolve(title : str, ancient_id : str, names : dict[str, str]) -> AncientPlan | None:
    """The plan for an option's title ("Sea Glass (Silent)" -> Sea Glass with its character); None for a title that is not a known relic."""
    match = re.match(r"^(.*?)(?: \(([^)]+)\))?$", title)
    name, character = match.group(1), match.group(2)
    relic = names.get(plain(name))
    if relic is None:
        return None
    setup = {"character": character.upper()} if character else {}
    if relic == "DUSTY_TOME":
        setup["card"] = "CORRUPTION"        # the card is rolled when the relic is offered and the title does not show it: the Ironclad's other Ancient card
    return AncientPlan(ancient_id, relic, setup)


class AncientChooser:
    def __init__(self, advisor : DeckAdvisor):
        self.advisor = advisor
        self.names = known_relics()

    def choose(self, decision : Decision) -> Option | None:
        ancient_id = decision.state.get("event_id")
        if ancient_id not in ancients.GENERATORS:
            return None
        options = decision.options_named("choose_event_option")
        if options and all(o.label.strip().lower() == "proceed" for o in options):
            return options[0]               # the relic is taken: only the way on is left, which is not a relic on offer
        plans = [resolve(o.label, ancient_id, self.names) for o in options]
        if not options or None in plans:
            for o, p in zip(options, plans):
                if p is None:
                    unknowns.note("ancient_relic", f"{ancient_id}:{o.label}", f"{ancient_id} offered {o.label!r}, which the engine does not know")
            self.advisor.log("ancient %s: a relic on offer is not one the engine knows (%s) -> left to the default" % (ancient_id, ", ".join(o.label for o, p in zip(options, plans) if p is None)))
            return None
        if len(options) == 1:
            return options[0]
        deck, player, ev = decision.player.get("deck") or [], decision.player, self.advisor.evaluator
        plays = {i: (lambda walks, plan=plan: ev.score_walks(deck, player, walks, plan).rewards) for i, plan in enumerate(plans)}
        rewards, count, seconds = self.advisor.race(decision, plays, self.advisor.config.ancient_seconds, route=None)
        means = {i: sum(r) / len(r) for i, r in rewards.items()}
        best = max(means, key=lambda i: (means[i], -i))
        self.advisor.log("ancient %s (%d walks, %.1fs of %.0fs): " % (ancient_id, count, seconds, self.advisor.config.ancient_seconds) +
                         ", ".join("%s %.2f" % (options[i].label, means[i]) for i in sorted(means, key=lambda i: -means[i])) + " -> " + options[best].label)
        return options[best]
