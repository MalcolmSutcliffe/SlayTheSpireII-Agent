"""One fight of a run: build it from the run's deck, relics and potions, then let the agent play it while the engine rules it.

The engine's state is the truth. The agent is handed a copy in which the order of the draw pile is hidden (the game never shows it), and what it
chooses is carried out on the truth. Everything the engine rolls while ruling (shuffles, enemy moves, random targets) comes from the game's own rng."""
from __future__ import annotations

from sts2_lite.datacopy import deepcopy_data

from sts2_lite.status import StatusId
from dataclasses import dataclass

from sts2_lite.card import Card, CardId
from sts2_lite.combat import CombatSimulator, CombatState
from sts2_lite.encounters import build_combat
from sts2_lite.player import Player
from sts2_lite.potion import PotionId
from sts2_lite.relic.combat_start import Opening
from sts2_lite.run import RunState

BASE_ENERGY = 3
UNPLAYABLE_TYPES = ("Curse", "Status")
MAX_ACTIONS = 3000          # a fight longer than this is a stalled agent, not a fight
MAX_ROUNDS = 150


class StalledFight(RuntimeError):
    pass


@dataclass
class FightResult:
    won : bool
    rounds : int
    actions : int
    hp_lost : int


def card_dict(card : dict) -> dict:
    ctype = card.get("type", "Skill")
    target = card.get("target_type") or ("AnyEnemy" if ctype == "Attack" else "Self")
    return {"id": card["id"], "name": card.get("name", card["id"]), "type": ctype, "cost": card.get("cost", 1), "star_cost": card.get("star_cost"),
            "description": card.get("description", ""), "target_type": target, "can_play": ctype not in UNPLAYABLE_TYPES, "unplayable_reason": None,
            "is_upgraded": bool(card.get("is_upgraded")), "generated": False, "enchantment": card.get("enchantment"), "keywords": [],
            "_upgrade": bool(card.get("_upgrade")), **({"rider": card["rider"]} if card.get("rider") else {})}


def _combat_start_potions(run : RunState, game):
    """BeforeCombatStart: Petrified Toad brings a Potion-Shaped Rock, Delicate Frond fills every open slot with a random potion (they stay on the belt after the fight)."""
    from sts2_lite.campaign.rewards import random_potion
    def add(potion_id : str):
        if len(run.potions) < run.potion_slots:
            run.potions.append({"id": potion_id, "name": potion_id.replace("_", " ").title()})
    if run.has_relic("PETRIFIED_TOAD"):
        add("POTION_SHAPED_ROCK")
    if run.has_relic("DELICATE_FROND"):
        while len(run.potions) < run.potion_slots:
            add(random_potion(game.stream("potion_rewards")))


def start_fight(run : RunState, encounter_id : str, room_type : str, game, final_fight : bool = False, one_hp : bool = False, variant : int | None = None) -> CombatSimulator:
    """Round 1 of `encounter_id` with the run's deck shuffled, the opening hand drawn and the start-of-combat relics applied."""
    cards = [card_dict(c) for c in run.deck]
    relics = deepcopy_data(run.relics)
    _combat_start_potions(run, game)
    opening = Opening(relics, room_type, room_type == "boss", interactive=True)
    for relic in run.relics:            # the tea set's stored energy is spent by this fight
        if relic["id"] in ("VENERABLE_TEA_SET", "FAKE_VENERABLE_TEA_SET") and relic.get("status") == "Active":
            relic["status"] = "Normal"
    energy = BASE_ENERGY + opening.energy_bonus()
    me = {"character": run.character, "hp": run.hp, "max_hp": run.max_hp, "block": 0, "gold": run.gold, "status": [], "hand": [], "draw_pile": cards, "discard_pile": [], "exhaust_pile": [],
          "relics": relics, "potions": [dict(p, slot=i) for i, p in enumerate(run.potions)], "potion_slots": run.potion_slots, "energy": energy, "max_energy": energy}
    with game.scope("combat"):
        player = Player.from_dict(me)
        for i, raw in enumerate(cards):
            if raw["_upgrade"] and player.draw_pile[i].is_upgradable:
                player.draw_pile[i] = player.draw_pile[i].upgraded_copy()
        for i, raw in enumerate(cards):
            if player.draw_pile[i].card_id in (CardId.THE_SCYTHE, CardId.GENETIC_ALGORITHM):       # their growth is kept by the deck's version
                scythe = Card.create_copy(player.draw_pile[i])
                scythe.bonus_damage, scythe.deck_index = run.deck[i].get("scythe_bonus", 0), i
                player.draw_pile[i] = scythe
        player.shuffle_draw_pile()
        cs = build_combat(encounter_id, run.ascension, player, game.stream("monster_ai"), max_energy=energy, final_fight=final_fight, variant=variant)
        if one_hp:          # Fur Coat: a marked fight
            for enemy in cs.enemies:
                enemy.current_hp = 1
        opening.before_combat(cs)
        opening.before_turn(cs)
        player.opening_hook = opening.before_draw
        sim = CombatSimulator(cs)
        sim._start_player_turn(enemies_start=False)
        player.opening_hook = None
        opening.after_draw(sim)
    return sim


def agent_view(cs : CombatState, search) -> CombatState:
    """What the agent may see of the fight: everything but the order of the unknown part of the draw pile (`known_top` cards on top are known)."""
    view = CombatState.deepcopy(cs)
    pile = view.player.draw_pile
    unknown = len(pile) - view.player.known_top
    if unknown > 1:
        hidden = pile[:unknown]
        search.random.shuffle(hidden)
        pile[:unknown] = hidden
    return view


def play_fight(sim : CombatSimulator, agent, game, search, time_budget : float | None = None, turn_limit : int | None = None) -> FightResult:
    """Plays the fight out. `turn_limit` (the Battleworn Dummy's time limit) ends it after that many turns, won or not."""
    start_hp = sim.combat_state.player.current_hp
    actions = 0
    while not sim.is_over:
        cs = sim.combat_state
        if turn_limit is not None and cs.turn_number > turn_limit:
            break
        if turn_limit is not None:                  # the time limit power counts the turns left
            for enemy in cs.enemies:
                if StatusId.BATTLEWORN_DUMMY_TIME_LIMIT in enemy.status:
                    enemy.status[StatusId.BATTLEWORN_DUMMY_TIME_LIMIT].amount = turn_limit - cs.turn_number + 1
        if actions >= MAX_ACTIONS or cs.turn_number > MAX_ROUNDS:
            raise StalledFight(f"{actions} actions, round {cs.turn_number}")
        with search.scope():
            action = agent.get_combat_action(agent_view(cs, search), time_budget)
        with game.scope("combat"):
            sim.perform_action(action)
        actions += 1
    cs = sim.combat_state
    return FightResult(cs.player.current_hp > 0, cs.turn_number, actions, max(0, start_hp - cs.player.current_hp))


def carry_back(run : RunState, sim : CombatSimulator):
    """What a fight leaves on the run: hit points, maximum hit points and the potions that were not used."""
    player = sim.combat_state.player
    run.hp = max(0, player.current_hp)
    run.max_hp = player.max_hp
    left = {p.slot for p in player.potions}
    run.potions = [p for i, p in enumerate(run.potions) if i in left or PotionId.from_game_id(p.get("id")) is None]      # one the sim does not know cannot have been used
    run.dead = run.hp <= 0
    for i, bonus in player.deck_buffs.items():
        if i < len(run.deck) and run.deck[i]["id"] in ("THE_SCYTHE", "GENETIC_ALGORITHM"):
            run.deck[i] = dict(run.deck[i], scythe_bonus=bonus)
    return 0 if run.dead else player.status_amount(StatusId.FORBIDDEN_GRIMOIRE)       # ForbiddenGrimoirePower.AfterCombatEnd: a card removal reward each
