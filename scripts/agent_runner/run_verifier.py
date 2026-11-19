"""Checks the run model (sts2_lite and its campaign simulator) against a real run: every screen the game shows out of combat, and what each action did to the run.

    verifier = RunVerifier(log_path="run_mismatches.jsonl", record_path="run_states.jsonl")
    verifier.state(game_state)          # a screen the agent is about to decide on
    verifier.acted(action)              # the action it sent from that screen
    verifier.interrupted()              # a fight (or anything the verifier does not see) came between two screens

Two kinds of check, following the rule that the game's random outcomes are only ever checked for being allowable:
  * a screen is checked on its own (`snapshot`): a shop has the stock and the price ranges the model rolls, a card reward the cards and rarities the model can
    offer, a rest site the options the model lists, the player's numbers add up;
  * an action is checked against the screen it was sent from (`episode`): the screens between two anchors (map, rewards, rest site, shop, treasure, event) are one
    episode. The outcomes that are certain (a rest heals 30%, Smith upgrades one card, a purchase costs its price, a relic does what its pickup says) must
    match exactly; everything an episode does not account for must not have changed.

Nothing here touches the game: `state` and `acted` take what the RunManager already has, and `replay` feeds a recording of them back in, so a recorded run
can be checked again after the model changes. A finding is `error` when the model contradicts a certain outcome, `warn` when the game shows something the
model does not know (an unmodelled relic or event) or an outcome that is unlikely but not ruled out."""
from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sts2_lite.campaign.rewards import treasure_gold_range
from sts2_lite.relic import run_hooks
from sts2_lite.run import RunState
from sts2_lite.run.state import Hidden

DEFAULT_LOG = "run_mismatches.jsonl"
DEFAULT_RECORD = "run_states.jsonl"

ANCHORS = ("map_select", "combat_rewards", "rest_site", "shop", "treasure", "event_choice")      # screens an episode starts and ends on
OVERLAYS = ("card_reward", "card_select", "relic_select")                                       # screens that open from an anchor and return to it
SCREENS = ANCHORS + OVERLAYS
PLAYER_FIELDS = ("hp", "max_hp", "gold")
GOLD_RANGE = {"Monster": (10, 20), "Elite": (35, 45), "Boss": (100, 100)}
REWARD_TYPES = {"gold", "potion", "card", "relic", "special_card", "linked_set", "remove_card"}
ALIASES = {"REST": "HEAL", "SMELT": "SMITH"}
NOT_A_REWARD_RARITY = {"Basic", "Curse", "Status", "Event", "Ancient", "Token", "Quest"}


@dataclass
class Finding:
    rule : str                          # short name of the check: "shop.price", "rest.heal", ...
    severity : str                      # "error" (contradicts the model) or "warn" (unknown to it, or unlikely)
    screen : str
    message : str
    act : int | None = None
    floor : int | None = None
    expected : object = None
    actual : object = None
    action : dict | None = None

    def __str__(self):
        where = f"act {self.act} floor {self.floor} {self.screen}"
        detail = f" (expected {self.expected!r}, got {self.actual!r})" if self.expected is not None or self.actual is not None else ""
        return f"[{self.severity}] {self.rule} at {where}: {self.message}{detail}"


def _context(state : dict) -> tuple:
    context = state.get("context") or state.get("run") or {}
    return context.get("act"), context.get("floor"), context.get("ascension")


def _player(state : dict) -> dict:
    return state.get("player") or {}


def deck_counter(deck : list[dict]) -> Counter:
    return Counter((c.get("id"), bool(c.get("is_upgraded"))) for c in deck or [])


def sozu(player : dict) -> bool:
    """Sozu: no potions can be gained (a potion reward is claimed and nothing arrives)."""
    return "SOZU" in relic_ids(player)


def relic_ids(player : dict) -> list[str]:
    return [r.get("id") for r in player.get("relics") or [] if isinstance(r, dict)]


def mirror(state : dict) -> RunState:
    """The model's RunState for what a real state shows: the engine's own rules (rest heal, gold, prices, pickups) can then be asked what they would do."""
    act, floor, ascension = _context(state)
    run = RunState.from_player(_player(state), _player(state).get("deck") or [], act or 1, floor or 1, ascension or 0)
    run.hidden = Hidden()
    return run


_KNOWN_RELICS : set | None = None


def known_relics() -> set:
    """Every relic id the model has any rule for: the pools, the pickup table, the ancients' offers and the ids the combat sim knows."""
    global _KNOWN_RELICS
    if _KNOWN_RELICS is None:
        from sts2_lite.campaign import ancients
        from sts2_lite.relic import RelicId, ancient_data
        from sts2_lite.relic.bag import RELIC_INFO
        from sts2_lite.relic.pickup import EFFECTS, NOT_MODELLED
        found = set(RelicId.__members__) | set(RELIC_INFO) | set(EFFECTS) | set(NOT_MODELLED)

        def collect(value):
            if isinstance(value, str) and value.isupper() and value.replace("_", "").isalpha():
                found.add(value)
            elif isinstance(value, (tuple, list, set, frozenset)):
                for item in value:
                    collect(item)
            elif isinstance(value, dict):
                for item in list(value) + list(value.values()):
                    collect(item)
        for module in (ancients, ancient_data):
            for name, value in vars(module).items():
                if name.isupper():
                    collect(value)
        from sts2_lite.event.events import FAKE_MERCHANT_RELICS
        found |= set(FAKE_MERCHANT_RELICS)
        import re
        for folder in (Path(ancients.__file__).parent, Path(ancient_data.__file__).parent):      # every relic the model's code names (any quoted id)
            for source in folder.glob("*.py"):
                found |= set(re.findall(r'"([A-Z][A-Z_]{3,})"', source.read_text()))
        _KNOWN_RELICS = found
    return _KNOWN_RELICS


def node_kind(type_name : str | None) -> str | None:
    name = str(type_name or "").lower()
    for key, kind in (("shop", "Shop"), ("rest", "RestSite"), ("treasure", "Treasure"), ("elite", "Elite"), ("boss", "Boss"), ("monster", "Monster"),
                      ("enemy", "Monster"), ("combat", "Monster"), ("unknown", "Unknown"), ("?", "Unknown"), ("event", "Event"), ("ancient", "Event")):
        if key in name:
            return kind
    return None


# What screen a room shows when the agent arrives in it (a fight is not a screen the verifier sees).
SCREEN_OF_ROOM = {"Shop": {"shop"}, "RestSite": {"rest_site"}, "Treasure": {"treasure"}, "Event": {"event_choice", "shop"},
                  "Unknown": {"event_choice", "shop", "treasure"}}


class RunVerifier:
    def __init__(self, log_path : str | None = DEFAULT_LOG, record_path : str | None = None, echo : bool = True):
        self.log_path, self.record_path, self.echo = log_path, record_path, echo
        self.findings : list[Finding] = []
        self.checked = 0                    # screens and episodes looked at
        self.anchor : dict | None = None    # the anchor screen the current episode started on
        self.actions : list[dict] = []      # what was sent since the anchor
        self.seen : list[dict] = []         # the overlay screens that opened since the anchor
        self.room : str | None = None       # the kind of room the last map choice led to
        self.last_dump : str | None = None
        self.reported : set = set()         # (rule, key) pairs reported once already: an unmodelled relic is not reported on every screen
        self.records = 0
        self.known : dict = {}              # the last deck and relics a screen showed: a screen that does not carry them (the shop, say) is checked with these

    # --- what the RunManager calls
    def state(self, state : dict):
        if state.get("type") != "decision" or state.get("decision") not in SCREENS:
            return
        self.record({"state": state})
        state = self.completed(state)
        dump = json.dumps(state, sort_keys=True, default=str)
        if dump == self.last_dump and self.actions:
            self.actions.pop()                  # the same screen again: the last action did nothing
        self.last_dump = dump
        kind = state["decision"]
        self.checked += 1
        self.snapshot(state)
        if kind in OVERLAYS:
            self.seen.append(state)
            return
        if self.anchor is not None and self.actions:
            self.episode(self.anchor, self.actions, self.seen, state)
        self.anchor, self.actions, self.seen = state, [], []

    def completed(self, state : dict) -> dict:
        """A copy of `state` whose player has the deck and relics (from the last screen that showed them) when its own does not; `_filled` names what was borrowed,
        and an episode does not compare what was borrowed."""
        player = state.get("player")
        if not isinstance(player, dict):
            return state
        for key in ("deck", "relics"):
            if key in player:
                self.known[key] = player[key]
        missing = [key for key in ("deck", "relics") if key not in player and key in self.known]
        if not missing:
            return state
        return {**state, "player": {**player, **{key: self.known[key] for key in missing}, "_filled": missing}}

    def acted(self, action : dict):
        self.record({"action": action})
        self.actions.append(dict(action))
        if self.anchor is not None and self.anchor.get("decision") == "map_select" and action.get("action") == "choose_map_node":
            choice = next((c for c in self.anchor.get("choices") or [] if c.get("index") == action.get("index")), None)
            self.room = node_kind(choice.get("type")) if choice else None

    def interrupted(self):
        """A fight, a loading screen or anything else the verifier cannot follow came in between: the episode has no end to compare with."""
        if self.anchor is None and self.last_dump is None:
            return                                  # already apart (the fight lasts many ticks)
        self.record({"interrupted": True})
        self.anchor, self.actions, self.seen, self.last_dump = None, [], [], None

    # --- recording and reporting
    def record(self, entry : dict):
        if not self.record_path:
            return
        try:
            path = Path(self.record_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as file:
                file.write(json.dumps({"n": self.records, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), **entry}, default=str) + "\n")
            self.records += 1
        except OSError as error:
            print(f"could not record the run: {error}")

    def report(self, rule : str, severity : str, state : dict, message : str, expected=None, actual=None, once : object = None, action : dict | None = None):
        if once is not None:
            if (rule, once) in self.reported:
                return
            self.reported.add((rule, once))
        act, floor, _ = _context(state)
        finding = Finding(rule, severity, state.get("decision", "?"), message, act, floor, expected, actual, action)
        self.findings.append(finding)
        if self.echo:
            print(finding)
        if self.log_path:
            try:
                path = Path(self.log_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a") as file:
                    file.write(json.dumps(asdict(finding), default=str) + "\n")
            except OSError as error:
                print(f"could not log the finding: {error}")

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    def summary(self) -> str:
        warns = len(self.findings) - len(self.errors)
        return f"{self.checked} screen(s) checked, {len(self.errors)} error(s), {warns} warning(s)" + (f" (see {self.log_path})" if self.findings and self.log_path else "")

    # --- one screen
    def snapshot(self, state : dict):
        player = _player(state)
        if player:
            self.check_player(state, player)
        {"shop": self.check_shop, "card_reward": self.check_card_reward, "combat_rewards": self.check_rewards, "rest_site": self.check_rest,
         "map_select": self.check_map, "event_choice": self.check_event, "treasure": self.check_treasure, "relic_select": self.check_relic_select,
         }.get(state["decision"], lambda s: None)(state)

    def check_player(self, state : dict, player : dict):
        hp, max_hp, gold = player.get("hp"), player.get("max_hp"), player.get("gold")
        if hp is not None and max_hp is not None and not 0 <= hp <= max_hp:
            self.report("player.hp", "error", state, "hit points outside 0..max", f"0..{max_hp}", hp)
        if gold is not None and gold < 0:
            self.report("player.gold", "error", state, "negative gold", ">= 0", gold)
        potions, slots = [p for p in player.get("potions") or [] if p], player.get("potion_slots")
        if slots is not None and len(potions) > slots:
            self.report("player.potions", "error", state, "more potions than slots", slots, len(potions))
        if slots is not None and player.get("open_potion_slots") is not None and player["open_potion_slots"] != slots - len(potions):
            self.report("player.potions", "error", state, "open potion slots do not match the belt", slots - len(potions), player["open_potion_slots"])
        self.check_known(state, player)

    def check_known(self, state : dict, player : dict):
        """Ids the model has never heard of: a relic, card or potion it would have to be taught before a simulated run could meet it."""
        from sts2_lite.card.tables import CardId
        from sts2_lite.potion import PotionId
        for relic in relic_ids(player):
            if relic and relic not in known_relics():
                self.report("unknown.relic", "warn", state, f"relic {relic} is not modelled", once=relic)
        for card in player.get("deck") or []:
            cid = card.get("id")
            if cid and cid not in CardId.__members__:
                self.report("unknown.card", "warn", state, f"card {cid} is not modelled", once=cid)
        for potion in player.get("potions") or []:
            pid = (potion or {}).get("id")
            if pid and PotionId.from_game_id(pid) is None and pid != "RANDOM_POTION":
                self.report("unknown.potion", "warn", state, f"potion {pid} is not modelled", once=pid)

    def check_map(self, state : dict):
        choices = state.get("choices") or []
        if not choices:
            return
        rows = {c.get("row") for c in choices if c.get("row") is not None}
        if len(rows) > 1:
            self.report("map.choices", "error", state, "the next rooms are not all on one row", None, sorted(rows))
        for choice in choices:
            if node_kind(choice.get("type")) is None:
                self.report("map.node", "warn", state, f"room type {choice.get('type')!r} is not one the model knows", once=choice.get("type"))

    def check_rewards(self, state : dict):
        items = state.get("items") or []
        _, _, ascension = _context(state)
        kinds = Counter(i.get("type") for i in items)
        for kind in kinds:
            if kind not in REWARD_TYPES:
                self.report("rewards.type", "warn", state, f"reward type {kind!r} is not one the model pays out", once=kind)
        room = self.room if self.room in GOLD_RANGE else None
        low, high = GOLD_RANGE.get(room, (min(r[0] for r in GOLD_RANGE.values()), max(r[1] for r in GOLD_RANGE.values())))
        if (ascension or 0) >= 3:                       # Poverty: three quarters of the gold
            low, high = int(low * 0.75), int(high * 0.75)
        fresh = self.anchor is None or self.anchor.get("decision") != "combat_rewards"          # the screen straight after the fight: nothing claimed yet
        for item in items:
            if item.get("type") == "gold":
                amount = _first_int(item.get("description"))
                if amount is not None and amount > int(high * 1.25) + 1:        # Bowler Hat adds a quarter; smaller amounts can be extras (a relic's bonus gold)
                    self.report("rewards.gold", "warn", state, f"gold reward above what a {room or 'fight'} pays", f"<= {high}", amount, once=("gold", amount, room))
        if fresh and room == "Elite" and kinds["relic"] == 0:
            self.report("rewards.elite_relic", "warn", state, "an elite paid no relic")
        if fresh and room == "Monster" and kinds["relic"] > 0 and not {"BLACK_STAR", "WHITE_BEAST_STATUE"} & set(relic_ids(_player(state))):
            self.report("rewards.monster_relic", "warn", state, "a normal fight paid a relic")

    def check_card_reward(self, state : dict):
        from sts2_lite.card.tables import COLORLESS_CARDS
        from sts2_lite.rewards.cards import card_pool_ids
        from sts2_lite.character import character_of_title
        cards = state.get("cards") or []
        ids = [c.get("id") for c in cards]
        if len(set(ids)) != len(ids):
            self.report("card_reward.duplicates", "warn", state, "the same card is offered twice", None, ids)
        player = _player(state)
        character = character_of_title(player.get("character"))
        try:
            pool = {c.name for c in card_pool_ids(character)}
        except NotImplementedError:
            pool = None             # a character the model has no reward cards for: its offers are not checked against a pool
        colorless = {c.name for c in COLORLESS_CARDS} if "DINGY_RUG" in relic_ids(player) else set()
        after_fight = self.anchor is not None and self.anchor.get("decision") == "combat_rewards"          # relics and events offer other pools and counts
        for card in cards:
            if card.get("rarity") in NOT_A_REWARD_RARITY:
                self.report("card_reward.rarity", "error", state, f"{card.get('id')} is {card.get('rarity')}: a card reward never offers that", once=("r", card.get("id")))
            elif after_fight and pool is not None and card.get("id") and card["id"] not in pool | colorless:
                self.report("card_reward.pool", "warn", state, f"{card['id']} is not in the {character.title()} pool the model draws from", once=("p", card["id"]))
        held = relic_ids(player)
        expected = 3 + ("QUESTION_CARD" in held) - 2 * ("BUSTED_CROWN" in held)
        if after_fight and cards and len(cards) not in (expected, expected + 1):          # + 1: Lasting Candy's Power, a reroll
            self.report("card_reward.count", "warn", state, "number of cards offered", expected, len(cards), once=("c", len(cards), expected))

    def check_rest(self, state : dict):
        options = state.get("options") or []
        player = _player(state)
        deck = player.get("deck") or []
        for card in deck:
            from sts2_lite.event.run import can_upgrade
            if "can_upgrade" in card and card.get("type") not in (None, "Curse", "Status") and bool(card["can_upgrade"]) != bool(can_upgrade(dict(card, can_upgrade=True))):
                self.report("rest.can_upgrade", "warn", state, f"{card.get('id')}: the game and the model disagree on whether it can be upgraded",
                            can_upgrade(dict(card, can_upgrade=True)), card["can_upgrade"], once=(card.get("id"), card.get("is_upgraded")))
        if not options or state.get("can_proceed"):
            return
        run = mirror(state)
        expected = {"HEAL", "SMITH"} | set(run_hooks.rest_extra_options(run))
        actual = {_rest_id(o) for o in options}
        if actual != expected and not (expected - {"SMITH"} <= actual <= expected | {"SMITH"}):
            self.report("rest.options", "warn", state, "the options of the rest site", sorted(expected), sorted(actual))

    def check_event(self, state : dict):
        from sts2_lite.event import EVENTS, available
        event_id = state.get("event_id")
        if not event_id or state.get("in_dialogue"):
            return
        if _is_ancient(state) or event_id in ("FAKE_MERCHANT", "SCROLL_BOXES"):           # SCROLL_BOXES: the campaign simulator's screen for a relic's bundle choice
            return
        if event_id not in EVENTS:
            self.report("event.unmodelled", "warn", state, f"event {event_id} is not modelled", once=event_id)
            return
        run = mirror(state)
        if EVENTS[event_id] not in available(run):
            self.report("event.allowed", "warn", state, f"the model would not offer {event_id} here", once=(event_id, run.act))

    def check_treasure(self, state : dict):
        for relic in state.get("relics") or []:
            if relic.get("id") and relic["id"] not in known_relics():
                self.report("unknown.relic", "warn", state, f"treasure relic {relic['id']} is not modelled", once=relic["id"])

    def check_relic_select(self, state : dict):
        for relic in state.get("relics") or []:
            if relic.get("id") and relic["id"] not in known_relics():
                self.report("unknown.relic", "warn", state, f"relic {relic['id']} is not modelled", once=relic["id"])

    # --- the shop
    def check_shop(self, state : dict):
        from sts2_lite.card.tables import CARD_RARITY, COLORLESS_CARDS, CardId
        from sts2_lite.potion import POTION_INFO, PotionId, PotionRarity
        from sts2_lite.relic.bag import MERCHANT_BASE_COST, RELIC_INFO
        from sts2_lite.campaign import shop as model
        items = state.get("items") or []
        if not items:
            return
        run = mirror(state)
        fake = bool(state.get("is_fake_merchant"))
        kinds = Counter(i.get("category") for i in items)
        if fake:
            from sts2_lite.event.events import FAKE_MERCHANT_PRICE, FAKE_MERCHANT_STOCK
            if set(kinds) != {"relic"} or kinds["relic"] != FAKE_MERCHANT_STOCK:
                self.report("fake_merchant.stock", "error", state, "the stock of the Fake Merchant", {"relic": FAKE_MERCHANT_STOCK}, dict(kinds))
        elif (kinds["card"], kinds["relic"], kinds["potion"], kinds["card_removal"]) != (7, 3, 3, 1):
            self.report("shop.stock", "error", state, "the stock of a shop (cards, relics, potions, removal)", (7, 3, 3, 1),
                        (kinds["card"], kinds["relic"], kinds["potion"], kinds["card_removal"]))
        sales = sum(1 for i in items if i.get("on_sale") and i.get("is_stocked", True))
        if sales > 1:
            self.report("shop.sale", "error", state, "more than one card on sale", "<= 1", sales)
        ascension = _context(state)[2] or 0
        for item in items:
            if not item.get("is_stocked", True) or item.get("cost") is None:
                continue
            cost, category = item["cost"], item.get("category")
            bounds = None
            if category == "relic":
                rid = item.get("relic_id")
                info = RELIC_INFO.get(rid)
                if info is None and fake and rid in known_relics():
                    info = {"rarity": "Shop", "shops": True}
                if info is None:
                    self.report("unknown.relic", "warn", state, f"relic {rid} is not in the relic pools", once=rid)
                    continue
                if not info["shops"] and not fake:
                    self.report("shop.relic", "error", state, f"{rid} is on sale but the model never stocks it", once=("s", rid))
                if fake:
                    from sts2_lite.event.events import FAKE_MERCHANT_PRICE
                    bounds = (round(FAKE_MERCHANT_PRICE * model.RELIC_JITTER[0]), round(FAKE_MERCHANT_PRICE * model.RELIC_JITTER[1]), False)
                else:
                    base = MERCHANT_BASE_COST[info["rarity"]]
                    bounds = (round(base * model.RELIC_JITTER[0]), round(base * model.RELIC_JITTER[1]), True)
            elif category == "card":
                cid = item.get("card_id")
                if cid not in CardId.__members__:
                    self.report("unknown.card", "warn", state, f"card {cid} is not modelled", once=cid)
                    continue
                rarity = CARD_RARITY[CardId[cid]].name
                colorless = CardId[cid] in COLORLESS_CARDS
                base = model.CARD_COST.get(rarity, 50)
                if colorless:
                    base = round(base * model.COLORLESS_MARKUP)
                lo, hi = round(base * model.CARD_JITTER[0]), round(base * model.CARD_JITTER[1])
                if item.get("on_sale"):
                    lo, hi = lo // 2, hi // 2
                bounds = (lo, hi, True)
            elif category == "potion":
                pid = item.get("potion_id")
                try:
                    rarity = POTION_INFO[PotionId.from_game_id(pid)].rarity
                except KeyError:
                    self.report("unknown.potion", "warn", state, f"potion {pid} is not modelled", once=pid)
                    continue
                base = model.POTION_COST.get(rarity, 50)
                bounds = (round(base * model.POTION_JITTER[0]), round(base * model.POTION_JITTER[1]), True)
            elif category == "card_removal":
                inflated = ascension >= model.INFLATION_ASCENSION
                base, step = model.REMOVAL_BASE[inflated], model.REMOVAL_STEP[inflated]
                if not any(abs(run_hooks.merchant_price(run, base + step * n) - cost) <= 1 for n in range(0, 20)):
                    self.report("shop.removal", "error", state, f"removal costs {base} + {step} per use at ascension {ascension}", f"{base}+{step}n", cost, once=("rm", cost))
                continue
            if bounds is None:
                continue
            low, high, discounted = bounds
            if discounted:
                low, high = run_hooks.merchant_price(run, low), run_hooks.merchant_price(run, high)
            if not low - 1 <= cost <= high + 1:
                self.report("shop.price", "error", state, f"{category} {item.get('card_id') or item.get('relic_id') or item.get('potion_id')} costs a price the model cannot roll",
                            f"{low}..{high}", cost, once=("price", category, item.get("index"), cost))

    # --- what an episode did
    def episode(self, anchor : dict, actions : list[dict], seen : list[dict], end : dict):
        """The screens from `anchor` to `end` (the next anchor) took `actions`: what the first one chose says what has to have happened."""
        self.checked += 1
        first = actions[0]
        kind = anchor["decision"]
        before, after = _player(anchor), _player(end)
        if not before or not after:
            return
        expect = {}
        {"map_select": self.after_map, "rest_site": self.after_rest, "combat_rewards": self.after_reward, "shop": self.after_shop,
         "treasure": self.after_treasure, "event_choice": self.after_event}[kind](anchor, first, actions, seen, end, expect)
        if expect.pop("skip", False):
            return
        if _is_ancient(end) and kind in ("combat_rewards", "map_select"):
            self.ancient_heal(anchor, end, expect)
        self.compare(anchor, end, first, expect)

    def ancient_heal(self, anchor : dict, end : dict, expect : dict):
        """An ancient heals on arrival: to full, or from Ascension 2 four fifths of what is missing (Neow does not heal: the run starts at full)."""
        if end.get("event_id") == "NEOW":
            return
        from sts2_lite.run.state import WEARY_TRAVELER_ASCENSION, WEARY_TRAVELER_SHARE
        before = _player(anchor)
        hp, max_hp = expect.get("hp", before.get("hp")), expect.get("max_hp", before.get("max_hp"))
        if hp is None or max_hp is None:
            return
        tired = (_context(end)[2] or 0) >= WEARY_TRAVELER_ASCENSION
        healed = {h + (int((m - h) * WEARY_TRAVELER_SHARE) if tired else m - h) for h in (hp if isinstance(hp, frozenset) else {hp}) for m in (max_hp if isinstance(max_hp, frozenset) else {max_hp})}
        expect["hp"] = frozenset(healed) if len(healed) > 1 else next(iter(healed))          # a hp the episode could not pin down stays a set of the values it may be

    def compare(self, anchor : dict, end : dict, action : dict, expect : dict):
        """Every number the episode did not account for stays as it was."""
        before, after = _player(anchor), _player(end)
        for name in PLAYER_FIELDS:
            want = expect.get(name, before.get(name))
            if want is None or after.get(name) is None:
                continue
            if after[name] not in want if isinstance(want, frozenset) else after[name] != want:
                self.report(f"episode.{name}", "error", anchor, f"{name} after {_say(action)}", sorted(want) if isinstance(want, frozenset) else want, after[name], action=action)
        borrowed = set(before.get("_filled", ())) | set(after.get("_filled", ()))
        if "deck" in before and "deck" in after and "deck" not in borrowed:
            want = expect["deck"] if "deck" in expect else deck_counter(before["deck"])
            if want is not None:
                actual = deck_counter(after["deck"])
                if want != actual:
                    self.report("episode.deck", "error", anchor, f"the deck after {_say(action)} differs", _diff(want, actual), _diff(actual, want), action=action)
            elif expect.get("deck_len") is not None and len(after["deck"]) != expect["deck_len"]:
                self.report("episode.deck", "error", anchor, f"deck size after {_say(action)}", expect["deck_len"], len(after["deck"]), action=action)
        if expect.get("deck_ids") is not None and "deck" in after and "deck" not in borrowed and Counter(c.get("id") for c in after["deck"]) != expect["deck_ids"]:
            self.report("episode.deck", "error", anchor, f"the deck after {_say(action)} differs", dict(expect["deck_ids"]), dict(Counter(c.get("id") for c in after["deck"])), action=action)
        want_relics = Counter(expect.get("relics", relic_ids(before)))
        if "relics" in before and "relics" in after and "relics" not in borrowed and want_relics != Counter(relic_ids(after)):
            self.report("episode.relics", "error", anchor, f"the relics after {_say(action)} differ", sorted(want_relics.elements()), sorted(relic_ids(after)), action=action)
        want_potions = expect.get("potions", len([p for p in before.get("potions") or [] if p]))
        have = len([p for p in after.get("potions") or [] if p])
        if "potions" in before and "potions" in after and (have not in want_potions if isinstance(want_potions, frozenset) else have != want_potions):
            self.report("episode.potions", "error", anchor, f"the potions after {_say(action)}", sorted(want_potions) if isinstance(want_potions, frozenset) else want_potions, have, action=action)
        if expect.get("potion_slots") is not None and after.get("potion_slots") is not None and after["potion_slots"] != expect["potion_slots"]:
            self.report("episode.potion_slots", "error", anchor, f"potion slots after {_say(action)}", expect["potion_slots"], after["potion_slots"], action=action)

    def after_map(self, anchor, first, actions, seen, end, expect):
        if first.get("action") != "choose_map_node":
            return
        choice = next((c for c in anchor.get("choices") or [] if c.get("index") == first.get("index")), None)
        a, f, _ = _context(anchor)
        a2, f2, _ = _context(end)
        if f is not None and f2 is not None and a == a2 and f2 != f + 1:
            self.report("map.floor", "error", anchor, "floor after moving to a room", f + 1, f2, action=first)
        kind = node_kind(choice.get("type")) if choice else None
        shown = end["decision"]
        if kind in SCREEN_OF_ROOM and shown not in SCREEN_OF_ROOM[kind]:
            self.report("map.room", "error", anchor, f"a {kind} room led to a {shown} screen", sorted(SCREEN_OF_ROOM[kind]), shown, action=first)
        if kind in ("Shop", "Unknown", "Event") and "LORDS_PARASOL" in relic_ids(_player(anchor)):
            expect["skip"] = True                   # the parasol empties the shop on arrival
            return
        room = {"event_choice": "Event", "shop": "Event" if end.get("is_fake_merchant") else "Shop", "treasure": "Treasure", "rest_site": "RestSite"}.get(shown)
        if room is not None:
            held = set(relic_ids(_player(anchor)))
            presets = tuple({"MAW_BANK": {"bought": b}} for b in (False, True)) if "MAW_BANK" in held else ({},)
            self.merge(self.outcomes(anchor, lambda run: run_hooks.room_entered(run, room, kind == "Unknown"), presets), expect)
            if room == "Treasure":
                self.expect_chest_gold(anchor, expect)

    def expect_chest_gold(self, anchor, expect):
        """The chest pays 42-52 gold as the room opens (x0.75 from Poverty): any of those is allowed."""
        low, high = treasure_gold_range(mirror(anchor).ascension)
        base = expect.get("gold")
        if base is None:
            base = _player(anchor).get("gold")
        bases = base if isinstance(base, frozenset) else {base}
        if any(b is None for b in bases):
            return
        expect["gold"] = frozenset(b + g for b in bases for g in range(low, high + 1))
        if any(c.get("id") == "SPOILS_MAP" for c in (_player(anchor).get("deck") or [])):
            expect["skip"] = True                  # Spoils Map adds more gold when the chest opens

    def after_rest(self, anchor, first, actions, seen, end, expect):
        action = first.get("action")
        if action == "proceed":
            return
        if action != "choose_rest_option":
            expect["skip"] = True
            return
        option = next((o for o in anchor.get("options") or [] if o.get("index") == first.get("index")), {})
        what = _rest_id(option)
        run = mirror(anchor)
        if what == "HEAL":
            run.hp = min(run.max_hp, run.hp + run_hooks.rest_heal(run))
            run_hooks.rest_healed(run)
            expect.update(hp=run.hp, max_hp=run.max_hp)
            if run_hooks.rest_heal_offers(run):
                expect["skip"] = True            # a Dream Catcher card or Tiny Mailbox potions came with it: not tracked here
        elif what == "SMITH":
            chosen = _selected_card(seen, actions)
            want = deck_counter(_player(anchor).get("deck"))
            if chosen is None:
                return                                                   # cancelled: nothing changed
            key = (chosen.get("id"), False)
            if want[key] <= 0:
                expect["skip"] = True
                return
            want[key] -= 1
            want[(chosen.get("id"), True)] += 1
            expect["deck"] = +want
        elif what == "COOK":
            picks = _selected_cards(seen, actions)
            if len(picks) < 2:
                return
            want = deck_counter(_player(anchor).get("deck"))
            for card in picks:
                want[(card.get("id"), bool(card.get("is_upgraded")))] -= 1
            expect.update(deck=+want, max_hp=run.max_hp + 9, hp=run.hp + 9)
        else:
            expect["skip"] = True              # DIG, CLONE ...: a relic or copies: the pickup rules are checked where the relic shows up

    def after_reward(self, anchor, first, actions, seen, end, expect):
        action = first.get("action")
        if action == "proceed":
            return
        if action != "claim_reward":
            expect["skip"] = True
            return
        item = next((i for i in anchor.get("items") or [] if i.get("index") == first.get("index")), {})
        kind = item.get("type")
        run = mirror(anchor)
        if kind == "gold":
            amount = _first_int(item.get("description"))
            if amount is None:
                expect["skip"] = True
                return
            run_hooks.gain_gold(run, amount)
            expect.update(gold=run.gold, hp=run.hp, max_hp=run.max_hp)
        elif kind == "potion":
            expect["potions"] = len([p for p in _player(anchor).get("potions") or [] if p]) + (1 if _player(anchor).get("open_potion_slots", 1) > 0 and not sozu(_player(anchor)) else 0)
        elif kind == "relic":
            self.expect_relic(anchor, end, expect)
        elif kind == "card":
            self.expect_card(anchor, seen, actions, expect)
        else:
            expect["skip"] = True

    def after_treasure(self, anchor, first, actions, seen, end, expect):
        if first.get("action") == "claim_treasure_relic":
            self.expect_relic(anchor, end, expect)
        elif first.get("action") != "proceed":
            expect["skip"] = True

    def after_event(self, anchor, first, actions, seen, end, expect):
        expect["skip"] = True                  # events change what they like; the screens are checked, and the model's events are checked in test_events

    def after_shop(self, anchor, first, actions, seen, end, expect):
        action = first.get("action")
        if action == "proceed":
            return
        if action != "shop_purchase":
            expect["skip"] = True
            return
        item = next((i for i in anchor.get("items") or [] if i.get("index") == first.get("index")), None)
        if item is None or item.get("cost") is None:
            expect["skip"] = True
            return
        player = _player(anchor)
        if item.get("category") == "card_removal" and end["decision"] != "shop":
            expect["skip"] = True
            return
        if item.get("category") == "card_removal" and not _selected_cards(seen, actions):
            return                                                          # cancelled: nothing was bought
        if "LORDS_PARASOL" in relic_ids(player) or item.get("cost") is None:
            expect["skip"] = True
            return
        expect["gold"] = player.get("gold", 0) - item["cost"]
        category = item.get("category")
        want = deck_counter(player.get("deck"))
        if category == "card":
            self.gain_card(anchor, item.get("card_id"), False, expect, paid=item["cost"])
            modelled = expect.get("deck")
            expect["deck"] = None                    # an egg or Fresnel Lens may have changed the card as it joined: compared by id below
            expect["deck_ids"] = Counter(c.get("id") for c in player.get("deck") or []) + Counter([item.get("card_id")])
            if modelled is not None and "BING_BONG" in relic_ids(player):
                expect["deck_ids"] = Counter()           # Bing Bong clones the card as well: the model's own deck says how many
                for (card_id, _), n in modelled.items():
                    expect["deck_ids"][card_id] += n
        elif category == "potion":
            if player.get("open_potion_slots", 1) == 0:
                expect["skip"] = True
                return
            expect["potions"] = len([p for p in player.get("potions") or [] if p]) + (0 if sozu(player) else 1)
        elif category == "relic":
            self.expect_relic(anchor, end, expect, item.get("relic_id"), gold=expect["gold"])
        elif category == "card_removal":
            for card in _selected_cards(seen, actions)[:1]:
                want[(card.get("id"), bool(card.get("is_upgraded")))] -= 1
            expect["deck"] = +want

    def outcomes(self, state : dict, step, presets : tuple = ({},)) -> list[RunState]:
        """What `step` does to the model's copy of the run, once for each way a relic's hidden counter could stand (what the game does not show)."""
        runs = []
        for preset in presets:
            run = mirror(state)
            for relic, values in preset.items():
                run_hooks.state(run, relic).update(values)
            step(run)
            runs.append(run)
        return runs

    @staticmethod
    def merge(runs : list[RunState], expect : dict):
        for name in ("hp", "max_hp", "gold"):
            values = {getattr(r, name) for r in runs}
            expect[name] = next(iter(values)) if len(values) == 1 else frozenset(values)

    def gain_card(self, state : dict, card_id : str, upgraded : bool, expect : dict, paid : int = 0):
        """A card joins the deck (`paid` gold first): the deck and numbers AfterCardChangedPiles leaves (Book of Five Rings, Lucky Fysh, Bing Bong...)."""
        from sts2_lite.card.tables import CardId
        from sts2_lite.event.run import card_entry
        if card_id not in CardId.__members__:
            self.report("unknown.card", "warn", state, f"card {card_id} is not modelled", once=card_id)
            expect["skip"] = True
            return

        def step(run):
            run.gold -= paid
            run_hooks.add_to_deck(run, card_entry(card_id, upgraded))
        held = set(relic_ids(_player(state)))
        presets = tuple({"BOOK_OF_FIVE_RINGS": {"cards": n}} for n in (0, 4)) if "BOOK_OF_FIVE_RINGS" in held else ({},)
        runs = self.outcomes(state, step, presets)
        self.merge(runs, expect)
        expect["deck"] = deck_counter(runs[0].deck)

    # --- the relic a pickup gave: what the model says it does on pickup
    def expect_relic(self, anchor : dict, end : dict, expect : dict, relic_id : str | None = None, gold : int | None = None):
        before, after = _player(anchor), _player(end)
        gained = Counter(relic_ids(after)) - Counter(relic_ids(before))
        if relic_id is not None:
            gained = Counter([relic_id]) if relic_id in relic_ids(after) else Counter()
        if len(gained) != 1 or sum(gained.values()) != 1:
            if "relics" in before and "relics" in after:
                self.report("episode.relics", "error", anchor, "exactly one relic should have been added", relic_id or "one relic", sorted(gained.elements()), action=None)
            expect["skip"] = True
            return
        relic = next(iter(gained))
        expect["relics"] = relic_ids(before) + [relic]
        run = mirror(anchor)
        if gold is not None:
            run.gold = gold
        from sts2_lite.event.core import CardPicker, Ctx
        from sts2_lite.relic.pickup import EFFECTS, NOT_MODELLED, obtain_relic
        if relic in NOT_MODELLED or relic not in EFFECTS:
            expect.update(hp=run.hp, max_hp=run.max_hp)
            if relic in NOT_MODELLED:
                self.report("relic.unmodelled", "warn", anchor, f"{relic} has an effect the model does not play", once=relic)
            return
        run.relics = [dict(r) for r in before.get("relics") or []]
        try:
            obtain_relic(Ctx(run, random.Random(0), CardPicker(random.Random(0))), relic)
        except Exception as error:                                  # a pickup that needs the campaign: leave it to the plain comparison
            self.report("relic.pickup", "warn", anchor, f"{relic}: the model could not play the pickup here ({type(error).__name__}: {error})", once=relic)
            expect["skip"] = True
            return
        expect.update(hp=run.hp, max_hp=run.max_hp, gold=run.gold, potion_slots=run.potion_slots)
        potions = len([p for p in before.get("potions") or [] if p])
        offered = sum(1 for o in run.offers if o.get("kind") == "potion")
        if offered:                                         # random potions, as many as the belt has room for
            expect["potions"] = frozenset(range(potions, min(run.potion_slots, potions + offered) + 1))
        # What the pickup does to the deck is compared exactly only when it does the same whatever the dice say (nothing, or a fixed card); a random upgrade or a
        # queued card reward leaves only the size of the deck to compare.
        unchanged = deck_counter(run.deck) == deck_counter(before.get("deck"))
        if run.offers or not unchanged:
            expect["deck"] = None
            expect["deck_len"] = None if run.offers else len(run.deck)
        else:
            expect["deck"] = deck_counter(run.deck)

    def expect_card(self, anchor : dict, seen : list[dict], actions : list[dict], expect : dict):
        """A card reward: one of the cards it showed joined the deck, or none did."""
        screen = next((s for s in reversed(seen) if s["decision"] == "card_reward"), None)
        pick = next((a for a in reversed(actions) if a.get("action") == "select_card_reward"), None)
        if any(a.get("option_id") == "SACRIFICE" for a in actions):
            expect["skip"] = True                                # Pael's Wing: every second card is a relic, and which one is not shown
            return
        if screen is None or pick is None:
            return                                               # skipped: no card
        card = next((c for c in screen.get("cards") or [] if c.get("index") == pick.get("card_index")), None)
        if card is None:
            expect["skip"] = True
            return
        self.gain_card(anchor, card.get("id"), bool(card.get("is_upgraded")), expect)


# --- helpers
def _is_ancient(state : dict) -> bool:
    if state.get("decision") != "event_choice":
        return False
    from sts2_lite.campaign import ancients
    return bool(state.get("is_ancient")) or state.get("event_id") in (ancients.ACT_ANCIENTS | set(ancients.SHARED) | {"NEOW"})


def _rest_id(option : dict) -> str:
    name = str(option.get("id") or option.get("name") or "").upper().replace(" ", "_")
    return ALIASES.get(name, name)


def _first_int(text) -> int | None:
    digits = "".join(ch if ch.isdigit() else " " for ch in str(text or "")).split()
    return int(digits[0]) if digits else None


def _say(action : dict) -> str:
    return " ".join(f"{k}={v}" for k, v in action.items())


def _selected_cards(seen : list[dict], actions : list[dict]) -> list[dict]:
    """The cards the agent selected on the card_select screens of an episode (by the index the screen listed them under); none when it cancelled.
    The game confirms a one-card pick by itself, so a confirm_selection is not required."""
    screens = [s for s in seen if s["decision"] == "card_select"]
    if not screens:
        return []
    pool = {}
    for screen in screens:
        for card in list(screen.get("cards") or []) + list(screen.get("selected") or []):
            pool.setdefault(card.get("index"), card)
    picks = []
    for action in actions:
        if action.get("action") == "select_card" and action.get("index") in pool:
            picks.append(pool[action["index"]])
        elif action.get("action") == "cancel_selection":
            picks = []
    return picks


def _selected_card(seen : list[dict], actions : list[dict]) -> dict | None:
    cards = _selected_cards(seen, actions)
    return cards[0] if cards else None


def _diff(a : Counter, b : Counter) -> dict:
    return {str(k): v for k, v in (a - b).items()}


# --- recordings
def replay(path : str, verifier : RunVerifier | None = None) -> RunVerifier:
    """Feed a recording (`record_path` of a verifier) through a verifier again: what the model says today about a run the game played yesterday."""
    verifier = verifier or RunVerifier(log_path=None)
    verifier.record_path = None
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if "state" in entry:
            verifier.state(entry["state"])
        elif "action" in entry:
            verifier.acted(entry["action"])
        elif entry.get("interrupted"):
            verifier.interrupted()
    return verifier


def main(argv : list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m agent_runner.run_verifier <recording.jsonl>   (a file written with --verify-run)")
        return 2
    verifier = replay(argv[0])
    print(verifier.summary())
    return 1 if verifier.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
