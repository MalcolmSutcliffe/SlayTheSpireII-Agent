"""The rollout policies: how the simulated rest of a fight is played, from the cheapest (first action) to the situation-aware
heuristic. A policy is `policy(combat_simulator, actions, params) -> action`; `rollout_policy` picks one by RolloutPolicy and
leaves out potions. The numbers they weigh cards by are HeuristicParams (params.py); a policy called without params uses
`params.DEFAULT_HEURISTIC`."""
from __future__ import annotations

from sts2_lite import rng
from sts2_lite.card import CARD_RARITY, CardId, CardRarity, CardType, MAX_HAND_SIZE, ETHEREAL_CARDS, UPGRADE_COST_CHANGE, UPGRADE_KEYWORD, UPGRADE_REMOVED_KEYWORD
from sts2_lite.combat import CombatState, CombatSimulator
from sts2_lite.status import StatusId

from agents.sts2_MCTS import params as P
from agents.sts2_MCTS.params import HeuristicParams, RolloutPolicy

# ... except when the upgrade only lowers the cost (the energy saved already lets the policy play more) or only adds / removes a keyword (no number goes up)
UPGRADE_UNSCALED = frozenset(UPGRADE_COST_CHANGE) | frozenset(UPGRADE_KEYWORD) | frozenset(UPGRADE_REMOVED_KEYWORD)


DRAW_ENERGY_CARDS = frozenset(CardId[n] for n in (
    "BATTLE_TRANCE BURNING_PACT DRUM_OF_BATTLE FINESSE FLASH_OF_STEEL IMPATIENCE MASTER_OF_STRATEGY OFFERING PILLAGE POMMEL_STRIKE "
    "RESTLESSNESS SCRAWL SHRUG_IT_OFF THINKING_AHEAD BLOODLETTING EXPECT_A_FIGHT FORGOTTEN_RITUAL PRODUCTION").split())
VULNERABLE_CARDS = frozenset(CardId[n] for n in "BASH BREAK SHOCKWAVE SQUASH TAUNT THUNDERCLAP TREMBLE UPPERCUT".split())
BLOCK_CARDS = frozenset(CardId[n] for n in (
    "DEFEND_IRONCLAD SHRUG_IT_OFF BLOOD_WALL IRON_WAVE TRUE_GRIT FLAME_BARRIER IMPERVIOUS SECOND_WIND ULTIMATE_DEFEND EQUILIBRIUM "
    "ARMAMENTS EVIL_EYE PANIC_BUTTON TAUNT FINESSE TORIC_TOUGHNESS").split())


def rollout_policy(c : CombatSimulator, actions, policy : RolloutPolicy, params : HeuristicParams | None = None):
    # rollouts never drink potions (every policy): a potion is only used by a move the tree chose, so a kept one keeps its bonus
    actions = [a for a in actions if a["action"] != "use_potion"] or actions
    if len(actions) == 0:
        return None
    if len(actions) == 1:   
        return actions[0]
    return ROLLOUT_POLICY_DICT[policy](c, actions, params)

###
### Rollout Poliocy helpers
###

def _params(p : HeuristicParams | None) -> HeuristicParams:
    """The parameters a rollout policy was given, or the defaults (read here, not at import, so a test can swap them)."""
    return P.DEFAULT_HEURISTIC if p is None else p

def _incoming_damage(cs : CombatState) -> int:
    """Damage the enemies' next moves deal before block (no Strength, Weak or Vulnerable applied)."""
    return sum(e.attack_damage * e.num_attacks for e in cs.enemies if e.current_hp > 0 and not e.is_minion)

def _rarity_weight(card, p : HeuristicParams) -> float:
    rarity = CardRarity.Common if card.card_id == CardId.BASH else CARD_RARITY[card.card_id]     # Bash plays like a Common
    return p.rarity_weights[rarity]

def _focus_fire(c : CombatSimulator, plays : list[dict], p : HeuristicParams) -> list[dict]:
    """Restricts the targeted plays to the focus enemy; plays that take no target are untouched."""
    if p.focus == "none":
        return plays
    enemies = c.combat_state.enemies
    targeted = [a for a in plays if "target_name" in a]
    candidates = list(dict.fromkeys(a["target"] for a in targeted))
    if len(candidates) < 2:
        return plays
    pool = [i for i in candidates if not enemies[i].is_minion] or candidates
    if p.focus == "first":
        focus = pool[0]
    elif p.focus == "lowest_hp":
        focus = min(pool, key=lambda i: enemies[i].current_hp)
    else:
        focus = min(pool, key=lambda i: enemies[i].current_hp + enemies[i].block)
    return [a for a in plays if "target_name" not in a or a["target"] == focus]

def _weighted_play(c : CombatSimulator, actions : list[dict], weight, p : HeuristicParams, greedy : bool = False) -> dict:
    """p_random_action: any action. Otherwise a card play drawn with weight(card, action); end_turn only when nothing else can be done.
    greedy: no random action, and the heaviest play every time (the first of equals). Pending choices (choose_card etc.) are uniform."""
    plays = [a for a in actions if a["action"] == "play_card"]
    if not plays or (not greedy and rng.random_float() < p.p_random_action):
        return rng.choice(actions)
    plays = _focus_fire(c, plays, p)
    hand = c.combat_state.player.hand
    weights = [weight(hand[a["card_index"]], a) for a in plays]
    if greedy:
        return plays[max(range(len(plays)), key=weights.__getitem__)]
    return rng.choices(plays, weights=weights)[0]

def _situation(c : CombatSimulator, actions : list[dict], p : HeuristicParams):
    """(unblocked incoming damage, can a Vulnerable card be played, hand has room to draw)"""
    cs = c.combat_state
    hand = cs.player.hand
    can_vuln = any(a["action"] == "play_card" and hand[a["card_index"]].card_id in VULNERABLE_CARDS for a in actions) \
        and any(e.current_hp > 0 and not e.is_minion and e.status_amount(StatusId.VULNERABLE) == 0 for e in cs.enemies)
    return max(0, _incoming_damage(cs) - cs.player.block), can_vuln, len(hand) <= MAX_HAND_SIZE - p.draw_room

def _common_factors(c : CombatSimulator, card, action : dict, unblocked : int, can_vuln : bool, room : bool, p : HeuristicParams) -> float:
    """Draw / Vulnerable / block factors shared by both weighted policies."""
    w = 1.0
    if card.card_id in DRAW_ENERGY_CARDS:
        w *= p.draw_first if room else p.no_room
    if card.card_id in VULNERABLE_CARDS and can_vuln:
        w *= p.vuln_first
    if card.type == CardType.Attack and can_vuln and card.card_id not in VULNERABLE_CARDS:
        enemies = c.combat_state.enemies
        target = enemies[action["target"]] if action["target"] < len(enemies) else None
        if target is None or target.status_amount(StatusId.VULNERABLE) == 0:       # (an attack on all enemies counts as unvulnerable too)
            w *= p.attack_before_vuln
    if card.card_id in BLOCK_CARDS and unblocked > 0:
        w *= 1.0 + p.block_mult * min(1.0, unblocked / p.block_cap)
    return w


### 
### Rollout Policy functions
###

def first_action(c : CombatSimulator, actions : list[dict], p : HeuristicParams | None = None) -> dict:
    return actions[0]

def random_action(c : CombatSimulator, actions : list[dict], p : HeuristicParams | None = None) -> dict:
    return rng.choice(actions)

def random_playable(c : CombatSimulator, actions : list[dict], p : HeuristicParams | None = None) -> dict:
    playable_actions = [a for a in actions if a["action"] != "end_turn"] or actions
    return rng.choice(playable_actions)

def random_playable_p_end_turn(c : CombatSimulator, actions : list[dict], p : HeuristicParams | None = None) -> dict:
    p = _params(p)
    end_turn = next((a for a in actions if a["action"] == "end_turn"), None)
    if end_turn is not None and rng.random_float() < p.p_end_turn:
        return end_turn
    return random_playable(c, actions, p)

def rarity_preference(c : CombatSimulator, actions : list[dict], p : HeuristicParams | None = None) -> dict:
    """Weighted by rarity of card"""
    p = _params(p)
    unblocked, can_vuln, room = _situation(c, actions, p)
    return _weighted_play(c, actions, lambda card, a: _rarity_weight(card, p) * _common_factors(c, card, a, unblocked, can_vuln, room, p), p)

def _claude_weight(c : CombatSimulator, actions : list[dict], p : HeuristicParams):
    unblocked, can_vuln, room = _situation(c, actions, p)
    def weight(card, a):
        w = _common_factors(c, card, a, unblocked, can_vuln, room, p)
        if card.type == CardType.Power:
            w *= p.power_first
        elif card.card_id in BLOCK_CARDS and unblocked == 0:
            w *= 0.25                                                                # already safe: spend the energy on offence
        if card.is_upgraded and card.card_id not in UPGRADE_UNSCALED:
            w *= p.upgrade_weight
        return w
    return weight

### The pick of a pending card choice (True Grit's card, Armaments' card, Ashwater's cards)
REMOVING_CHOICES = ("exhaust", "exhaust_any", "discard_any")      # a card leaves the hand: the least wanted one goes

def _pick_for_choice(c : CombatSimulator, actions : list[dict], greedy : bool, p : HeuristicParams) -> dict:
    """The heuristic's answer to a pending card choice, with the weights it plays cards by (as if each card of the hand were playable now):
      - a card leaves the hand (exhaust, discard): unplayable cards first (those that stay in the deck, then ethereal ones), then the rest with
        probability proportional to 1 / weight, so the card the policy would play most is the one least likely to go.
        A choice of "any number" takes the unplayable cards only, and then stops.
      - Armaments: probability proportional to the weight of playing the card; an unplayable card is not upgraded while another can be.
      - anything else: uniform."""
    pending = c.combat_state.pending_choice
    kind = pending.kind if pending is not None else None
    picks = [a for a in actions if a["action"] == "choose_card"]
    if kind not in REMOVING_CHOICES + ("upgrade",) or not picks:
        return rng.choice(actions)
    cs = c.combat_state
    hand = cs.player.hand
    focus = next((i for i, e in enumerate(cs.enemies) if e.current_hp > 0 and not e.is_minion), 0)
    as_plays = [{"action" : "play_card", "card_index" : i, "target" : focus} for i, card in enumerate(hand) if not card.is_unplayable]
    weight = _claude_weight(c, as_plays, p)
    cards = [c._pile(a["pile"])[a["card_index"]] for a in picks]
    w = [max(1e-9, weight(card, {"action" : "play_card", "target" : focus})) for card in cards]
    def choose(indices, wanted):
        if greedy:
            return picks[max(indices, key=lambda i: wanted[i])]
        return rng.choices([picks[i] for i in indices], weights=[wanted[i] for i in indices])[0]

    if kind == "upgrade":
        playable = [i for i, card in enumerate(cards) if not card.is_unplayable]
        return choose(playable or list(range(len(picks))), w)

    inverse = [1.0 / x for x in w]
    stays = [i for i, card in enumerate(cards) if card.is_unplayable and card.card_id not in ETHEREAL_CARDS]
    fades = [i for i, card in enumerate(cards) if card.is_unplayable and card.card_id in ETHEREAL_CARDS]
    confirm = next((a for a in actions if a["action"] == "confirm_choice"), None)
    if pending.optional and confirm is not None:
        junk = stays + fades
        return choose(junk, inverse) if junk else confirm
    for group in (stays, fades, list(range(len(picks)))):
        if group:
            return choose(group, inverse)
    return rng.choice(actions)

def _claude_pick(c : CombatSimulator, actions : list[dict], greedy : bool, p : HeuristicParams | None) -> dict:
    p = _params(p)
    if c.combat_state.pending_choice is not None:
        return _pick_for_choice(c, actions, greedy, p)
    return _weighted_play(c, actions, _claude_weight(c, actions, p), p, greedy=greedy)

def claude_heuristic(c : CombatSimulator, actions : list[dict], p : HeuristicParams | None = None) -> dict:
    """Same shape as rarity_preference, but rarity is replaced by what the card does: Powers first (they pay off for the rest of
    the fight, which the rollout plays out), then draw/energy, Vulnerable, other Skills and Attacks equal, block only while damage
    is unblocked."""
    return _claude_pick(c, actions, False, p)

def claude_heuristic_greedy(c : CombatSimulator, actions : list[dict], p : HeuristicParams | None = None) -> dict:
    """claude_heuristic, taking the heaviest play instead of drawing one, and without the random action."""
    return _claude_pick(c, actions, True, p)

ROLLOUT_POLICY_DICT = {
    RolloutPolicy.FirstAction : first_action,
    RolloutPolicy.RandomAction : random_action,
    RolloutPolicy.RandomPlayble : random_playable,
    RolloutPolicy.RandomPlayblePEndTurn : random_playable_p_end_turn,
    RolloutPolicy.RarityPreference : rarity_preference,
    RolloutPolicy.ClaudeHeuristic : claude_heuristic,
    RolloutPolicy.ClaudeHeuristicGreedy : claude_heuristic_greedy,
}
