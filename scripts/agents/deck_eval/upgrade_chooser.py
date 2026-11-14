"""Which card to upgrade, and whether a rest site should upgrade (smith) or heal: every choice is played on the same sample of upcoming fights.

An upgrade is the deck with that card upgraded (the sim's own upgrade: cost, keywords, numbers); a heal is the deck with the HP back. Both are
scored the same way as a card reward, so their gains compare. Strikes and Defends are not tried unless nothing else can be upgraded (Bash is)."""
from __future__ import annotations
import random
import re
import time

from agents.decision import Decision, Option
from agents.deck_eval.advisor import DeckAdvisor
from agents.deck_eval.card_reward_chooser import paired_gain
from agents.deck_eval.fight_mix import fights_until_next_rest

REST_HEAL_SHARE = 0.30      # a rest site heals this share of max HP when its option does not say how much
PLAIN_PREFIXES = ("STRIKE", "DEFEND")
UPGRADE_FIGHTS = 150        # fights each upgrade is tried on (a card reward uses the advisor's 400)
CHAINS = 150                # simulated walks from this rest site to the next one
SURVIVE_RATE = 0.8          # the upgrade is taken when the deck gets through the fights up to the next rest site at least this often


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
        mix, fights, seed, _ = self.advisor.sample(decision, UPGRADE_FIGHTS)
        ev, start = self.advisor.evaluator, time.perf_counter()
        base = ev.score(deck, player, fights, seed)
        candidates = {}
        for i, card in enumerate(deck):
            if not card.get("is_upgraded") and card.get("can_upgrade", True) and card.get("type") not in ("Curse", "Status"):
                candidates.setdefault(card["id"], i)
        tried = {k: i for k, i in candidates.items() if not _plain(deck[i])} or candidates
        gains = {}
        for card_id, i in tried.items():
            upgraded = [dict(c, _upgrade=True) if j == i else c for j, c in enumerate(deck)]
            gains[card_id] = paired_gain(ev.score(upgraded, player, fights, seed).rewards, base.rewards)[0]
        heal_gain = paired_gain(ev.score(deck, {**player, "hp": player["hp"] + healed}, fights, seed).rewards, base.rewards)[0] if healed else 0.0
        self._gains[_signature(deck)] = gains
        ranked = ", ".join("%s %+.2f" % kv for kv in sorted(gains.items(), key=lambda kv: -kv[1])[:6])
        self.advisor.log("upgrade gains (%d fights, %.1fs): %s%s" % (len(fights), time.perf_counter() - start, ranked, " | heal %d HP %+.2f" % (healed, heal_gain) if healed else ""))
        return gains, heal_gain

    def best_gains(self, decision : Decision) -> dict[str, float]:
        return self._gains.get(_signature(decision.player.get("deck") or [])) or self.analyze(decision)[0]

    def choose_card(self, decision : Decision, picks : list[Option]) -> Option | None:
        """The card screen of an upgrade: the pick with the largest gain; None when no pick could be rated."""
        gains = self.best_gains(decision)
        rated = [(gains[o.data["id"]], o) for o in picks if not (o.data or {}).get("is_upgraded") and (o.data or {}).get("id") in gains]
        return max(rated, key=lambda r: r[0])[1] if rated else None

    def survival(self, decision : Decision, deck : list[dict], fights_seed : int, hp : int | None = None) -> tuple[float, int]:
        """(share of CHAINS walks to the next rest site the deck comes through alive, fights in a walk). A walk draws its fights anew (same draws for every deck)."""
        player, ev, advisor = decision.player, self.advisor.evaluator, self.advisor
        route = advisor.route_provider()
        ctx = decision.state.get("context") or decision.state.get("run") or {}
        act, ascension = ctx.get("act", 1), ctx.get("ascension", 0)
        alive, length = 0, 0
        for i in range(CHAINS):
            fights = fights_until_next_rest(advisor.pool, route, act, ascension, random.Random(fights_seed + i))
            length = max(length, len(fights))
            alive += ev.play_chain(deck, {**player, "hp": player["hp"] if hp is None else hp}, fights, fights_seed + i)[0]
        return alive / CHAINS, length

    def choose_rest(self, decision : Decision) -> Option | None:
        """Heal only when the rest gives its full heal; then upgrade when the upgraded deck survives the way to the next rest site, else heal.
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
        gains, _ = self.analyze(decision)
        if not gains:
            return heal
        deck = player.get("deck") or []
        best = max(gains, key=gains.get)
        i = next(j for j, c in enumerate(deck) if c["id"] == best and not c.get("is_upgraded"))
        upgraded = [dict(c, _upgrade=True) if j == i else c for j, c in enumerate(deck)]
        seed = 7000 + self.advisor._calls
        rate, length = self.survival(decision, upgraded, seed)
        self.advisor.log("rest site: upgrading %s, %.0f%% of walks through the %d fights to the next rest site survive (needs %.0f%%) -> %s" %
                         (best, 100 * rate, length, 100 * SURVIVE_RATE, "smith" if rate >= SURVIVE_RATE else "heal"))
        return smith if rate >= SURVIVE_RATE else heal
