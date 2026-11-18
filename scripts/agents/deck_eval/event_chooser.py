"""Which option of an event room to take: every option is played out by the engine's own event model (sts2_lite.event) and the walks through the rest of the act
are then walked from the run it leaves (route_sim: the fights with the HP carried over, rest sites, rewards, relics). The option with the best mean reward wins.

All options are played on the same walks, so what differs is only the option: the same rolled numbers (the event's gold, its damage), the same relic draws, the same
monsters and dice. An option that kills the agent, or one that starts a fight, is rated by the walk like any other room. The card choices inside an option are the
agent's usual ones (a curse, Strike, Defend first for a removal or a transform; the rarest card to upgrade or take: route_sim.PlanPicker).

Gold counts only through the shops a walk meets (it is spent there: route_sim), so an option that pays gold is worth nothing on a route without a shop.

A page after the first is played by replaying the options chosen so far (the numbers the game rolled for this visit are redrawn, not known). An event the engine does not model,
or whose option names are not the model's, is left to the caller (`choose` returns None). The analysis takes at most DeckEvalConfig.event_seconds."""
from __future__ import annotations

from agents import unknowns
from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor
from agents.deck_eval.route_sim import EventMismatch, EventPlan, event_option_key
from sts2_lite.event import EVENTS


class EventChooser:
    def __init__(self, advisor : DeckAdvisor):
        self.advisor = advisor
        self.visit : str | None = None          # the event being played, and the keys chosen on its pages so far
        self.path : list[str] = []

    def _remember(self, event_id : str, option : Option) -> Option:
        self.path.append(event_option_key(option))
        return option

    def choose(self, decision : Decision) -> Option | None:
        event_id = decision.state.get("event_id")
        if event_id != self.visit:
            self.visit, self.path = event_id, []
        options = decision.options_named("choose_event_option")
        if not options or event_id not in EVENTS:
            return None
        if len(options) == 1:
            return self._remember(event_id, options[0])
        deck, player = decision.player.get("deck") or [], decision.player
        ev = self.advisor.evaluator
        plays = {i: (lambda walks, key=event_option_key(o): ev.score_walks(deck, player, walks, EventPlan(event_id, list(self.path), key)).rewards) for i, o in enumerate(options)}
        try:
            rewards, count, seconds = self.advisor.race(decision, plays, self.advisor.config.event_seconds)
        except EventMismatch as e:
            unknowns.note("event", f"{event_id}:{e}", f"event {event_id}: the options do not match the engine's model ({e}); options {[o.label for o in options]}")
            self.advisor.log("event %s: the options do not match the engine's model (%s) -> left to the default" % (event_id, e))
            return None
        means = {i: sum(r) / len(r) for i, r in rewards.items()}
        best = max(means, key=lambda i: (means[i], -i))
        self.advisor.log("event %s (%d walks, %.1fs of %.0fs): " % (event_id, count, seconds, self.advisor.config.event_seconds) +
                         ", ".join("%s %.2f" % (options[i].label, means[i]) for i in sorted(means, key=lambda i: -means[i])) + " -> " + options[best].label)
        return self._remember(event_id, options[best])
