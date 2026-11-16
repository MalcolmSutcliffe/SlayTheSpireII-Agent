"""Which card to upgrade, and whether a rest site should upgrade (smith) or heal: every choice is played on the same walks through the route ahead
(the engine's run simulator over the rest of the act: route_sim, DeckEvaluator.score_walks).

An upgrade is the deck with that card upgraded (the sim's own upgrade: cost, keywords, numbers); a heal is the deck with the HP back. Both are
scored the same way as a card reward, so their gains compare: the rest site takes the bigger one. Strikes and Defends are not tried unless nothing else can be upgraded (Bash is)."""
from __future__ import annotations
import re

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor, paired_gain

REST_HEAL_SHARE = 0.30      # a rest site heals this share of max HP when its option does not say how much
PLAIN_PREFIXES = ("STRIKE", "DEFEND")


def _plain(card : dict) -> bool:
    return str(card.get("id", "")).startswith(PLAIN_PREFIXES)


def _signature(deck : list[dict]) -> tuple:
    return tuple(sorted((c.get("id"), bool(c.get("is_upgraded"))) for c in deck))


def full_heal(option : Option | None, player : dict) -> int:
    """What the rest option heals before the max HP caps it."""
    text = ((option.data or {}).get("description") if option else "") or ""
    match = re.search(r"(\d+)\s*(?:HP|health)", text, re.I)
    return int(match.group(1)) if match else round(REST_HEAL_SHARE * player.get("max_hp", 0))


def heal_amount(option : Option | None, player : dict) -> int:
    return max(0, min(full_heal(option, player), player.get("max_hp", 0) - player.get("hp", 0)))


class UpgradeChooser:
    def __init__(self, advisor : DeckAdvisor):
        self.advisor = advisor
        self._gains : dict[tuple, dict[str, float]] = {}     # deck -> its upgrade gains: the smith choice and the card screen after it share them

    def analyze(self, decision : Decision, healed : int = 0) -> tuple[dict[str, float], float]:
        """({card id: gain of upgrading one copy}, gain of `healed` more HP), all on the same fights and dice. Only cards that can be upgraded."""
        player = decision.player
        deck = player.get("deck") or []
        ev = self.advisor.evaluator
        candidates = {}
        for i, card in enumerate(deck):
            if not card.get("is_upgraded") and card.get("can_upgrade", True) and card.get("type") not in ("Curse", "Status"):
                candidates.setdefault(card["id"], i)
        tried = {k: i for k, i in candidates.items() if not _plain(deck[i])} or candidates
        plays = {"base": lambda walks: ev.score_walks(deck, player, walks).rewards}
        for card_id, i in tried.items():
            upgraded = [dict(c, _upgrade=True) if j == i else c for j, c in enumerate(deck)]
            plays[card_id] = lambda walks, d=upgraded: ev.score_walks(d, player, walks).rewards
        if healed:
            plays["heal"] = lambda walks: ev.score_walks(deck, {**player, "hp": player["hp"] + healed}, walks).rewards
        budget = self.advisor.config.upgrade_seconds
        rewards, count, seconds = self.advisor.race(decision, plays, budget)
        gains = {card_id: paired_gain(rewards[card_id], rewards["base"])[0] for card_id in tried}
        heal_gain = paired_gain(rewards["heal"], rewards["base"])[0] if healed else 0.0
        self._gains[_signature(deck)] = gains
        ranked = ", ".join("%s %+.2f" % kv for kv in sorted(gains.items(), key=lambda kv: -kv[1])[:6])
        self.advisor.log("upgrade gains (%d walks through the route ahead, %.1fs of %.0fs): %s%s" % (count, seconds, budget, ranked, " | heal %d HP %+.2f" % (healed, heal_gain) if healed else ""))
        return gains, heal_gain

    def best_gains(self, decision : Decision) -> dict[str, float]:
        return self._gains.get(_signature(decision.player.get("deck") or [])) or self.analyze(decision)[0]

    def choose_card(self, decision : Decision, picks : list[Option]) -> Option | None:
        """The card screen of an upgrade: the pick with the largest gain; None when no pick could be rated."""
        gains = self.best_gains(decision)
        rated = [(gains[o.data["id"]], o) for o in picks if not (o.data or {}).get("is_upgraded") and (o.data or {}).get("id") in gains]
        return max(rated, key=lambda r: r[0])[1] if rated else None

    def choose_rest(self, decision : Decision) -> Option | None:
        """Heal only when the rest gives its full heal; then take what is worth more on the walks through the route ahead: the best upgrade, or the HP.
        None when the screen has no heal / smith pair."""
        by_id = {(o.data or {}).get("id"): o for o in decision.options_named("choose_rest_option")}
        heal, smith = by_id.get("HEAL"), by_id.get("SMITH")
        if heal is None or smith is None:
            return None
        player = decision.player
        missing = player.get("max_hp", 0) - player.get("hp", 0)
        if missing < full_heal(heal, player):
            self.advisor.log("rest site: %d HP missing, a rest heals %d -> smith" % (missing, full_heal(heal, player)))
            return smith
        gains, heal_gain = self.analyze(decision, heal_amount(heal, player))
        if not gains:
            return heal
        best = max(gains, key=gains.get)
        take_smith = gains[best] >= heal_gain
        self.advisor.log("rest site: upgrading %s %+.2f vs healing %d HP %+.2f -> %s" % (best, gains[best], heal_amount(heal, player), heal_gain, "smith" if take_smith else "heal"))
        return smith if take_smith else heal
