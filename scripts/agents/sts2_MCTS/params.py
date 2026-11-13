"""Everything that tunes the search, in one place.

`SearchConfig` is what a search is given. Besides its own fields it holds four groups of numbers, each a frozen dataclass:
  reward      how a finished rollout is scored            (RewardParams)
  uct         the exploration term and the information bonus (UctParams)
  confidence  when the search may stop and when moves count as tied (ConfidenceParams)
  heuristic   how the rollout policies weigh cards         (HeuristicParams)
Nothing here is changed at runtime: to try another value make another config, e.g. `SearchConfig().tuned(p_random_action=0.0)`
(`tuned` takes the name of any field of the config or of its groups). The sweeps and tests do this instead of patching modules.
Rollout policy functions take a HeuristicParams; asked for none they use `DEFAULT_HEURISTIC`."""
from __future__ import annotations
import dataclasses
from dataclasses import dataclass, field
from enum import Enum, auto

from sts2_lite.card import CardRarity
from sts2_lite.potion import PotionId


class RolloutPolicy(Enum):
    FirstAction = auto()            # just play first action (works surprisingly well)
    RandomAction = auto()           # random choice from all abailable actions
    RandomPlayble = auto()          # random choice that prefers playable cards first, then end turn
    RandomPlayblePEndTurn = auto()  # random playable, with p_end_turn

    # Bias towards playing higher rarity cards first.
    # Prefer block when being attacked.
    # Exceptions for certain cards that perform better when played later (i.e. body slam)
    RarityPreference = auto()

    # Situation-aware weighted choice (Powers and draw first, Vulnerable before attacks, block only while damage is unblocked)
    ClaudeHeuristic = auto()

    # ClaudeHeuristic with the dice taken out: always plays the highest-weighted card (ties go to the first in hand), never rolls the random
    # action. The same position plays out the same way every rollout, so moves are compared on the draws and not on the policy's luck.
    ClaudeHeuristicGreedy = auto()


@dataclass(frozen=True)
class RewardParams:
    """How a finished rollout is rated (MCTS._rate_outcome): a win is win_base + the HP kept (as a share of the starting HP), a loss is
    minus the share of the enemies' HP still left."""
    win_base : float = 20.0
    turn_cost : float = 0.1                 # a win loses this much HP of score per turn it took
    loss_turn_bonus : float = 0.02          # a loss gains this much (a share of the enemies' HP) per turn lasted: dying later leaves more chances to find a win
    max_hp_scaling : float = 2.0
    default_potion_bonus : int = 16
    potion_bonus : dict[PotionId, int] = field(default_factory=lambda: {
        PotionId.BLOOD_POTION : 18,
        PotionId.FORTIFIER : 15,
        PotionId.HEART_OF_IRON : 15,
        PotionId.FRUIT_JUICE : 16,
        PotionId.LUCKY_TONIC : 18,
        PotionId.OROBIC_ACID : 20,
        PotionId.SHACKLING_POTION : 18,
        PotionId.SHIP_IN_A_BOTTLE : 20,
        PotionId.GIGANTIFICATION_POTION : 20,
        PotionId.SOLDIERS_STEW : 15,
        PotionId.AMBERGRIS : 45,
        PotionId.POTION_SHAPED_ROCK : 2,
    })


@dataclass(frozen=True)
class UctParams:
    """The exploration term is sized by the spread of the rewards the search has seen (the lowest to the highest rollout): half that spread,
    to the exploration_power. Before any win it is a fraction of a point (losses are -1..0), so the search can tell moves apart by their
    enemy HP; once a win has been found it is ~21 points wide and the scale is what a fixed one of that size gave. Fully scaling made the
    search over-explore on short budgets, none made it miss rare wins (tested on whole fights)."""
    exploration_power : float = 0.75
    min_reward_span : float = 0.2           # the span is never taken smaller than this (the first rollouts have seen almost nothing)
    exploration_scale : float | None = None # a number fixes the scale (the benchmark's reference searches set one); None sizes it from the rewards seen
    # information bonus: see sts2_MCTS._information_value
    info_sigma : float = 0.05               # spread of the outcomes' values (reward units) at which a chance node earns 76% of the largest bonus (tanh(1))
    info_min_visits : int = 2               # a sampled outcome's value counts once it has been visited this often


@dataclass(frozen=True)
class ConfidenceParams:
    """When the search may stop on its own (MCTS._check_statistical_exit) and when the top moves count as tied (MCTS._pick_root_child)."""
    epsilon : float = 0.005
    tie_min_visits : int = 30               # the top move needs this many visits before a tie is considered
    tie_visit_fraction : float = 0.5        # a tied move needs this share of the top move's visits: a thin estimate is within the margin by luck


@dataclass(frozen=True)
class HeuristicParams:
    """The numbers of the rollout policies (the functions are in MCTS.py)."""
    p_end_turn : float = 0.02               # RandomPlayblePEndTurn: chance to end the turn instead of playing a card
    rarity_weights : dict[CardRarity, float] = field(default_factory=lambda: {
        CardRarity.Ancient : 4,         # Note: usually ancient cards are very good. Right now we only have neow's fury, which is about an uncommn.
        CardRarity.Rare : 8,
        CardRarity.Uncommon : 4,
        CardRarity.Token : 4,           # Note : Token and event cards seem to be about the same as uncommon, in terms of strength.
        CardRarity.Event : 4,
        CardRarity.Common : 2,
        CardRarity.Basic : 1,           # baseline: a basic card is value 1. Model other weights around that value
        CardRarity.Status : 0.1,        # only playable status is slimed
        CardRarity.Curse : 0.01,
    })
    p_random_action : float = 0.05          # chance a heuristic rollout plays a uniformly random action (end_turn included)
    block_mult : float = 24.0               # a block card's weight grows to (1 + block_mult)x as the unblocked incoming damage reaches block_cap
    block_cap : int = 15
    draw_first : float = 4.0                # draw / energy cards
    no_room : float = 0.1                   # ... when the hand has no room for what they draw
    draw_room : int = 3                     # needs len(hand) <= MAX_HAND_SIZE - draw_room
    vuln_first : float = 4.0                # a card that applies Vulnerable, while some enemy lacks it
    attack_before_vuln : float = 0.1        # an attack on a non-vulnerable target while a Vulnerable card can be played
    power_first : float = 3.0               # Heuristic policy only
    upgrade_weight : float = 1.5            # Heuristic policy only: an upgraded card is worth about half as much again (Strike 6 -> 9), and was likely upgraded because the deck wants it played
    # Which enemy the targeted cards of the weighted policies go at, so damage is not spread over several:
    #   "none" any enemy | "first" the first living one | "lowest_hp" the lowest HP | "lowest_hp_block" the lowest HP + block (minions last)
    focus : str = "lowest_hp"


DEFAULT_HEURISTIC = HeuristicParams()       # what a rollout policy uses when it is called without parameters


@dataclass(frozen=True)
class SearchConfig:
    max_sims : int = 20000
    min_sims : int = 100                 # always searches at least this many simulations
    time_budget : float | None = None    # None = sim-count mode
    exploration : float = 1.0
    outcome_c : float = 2.0
    outcome_alpha : float = 0.5          # a chance node keeps at most outcome_c * visits ** outcome_alpha distinct sampled outcomes
    max_rollout_turns : int = 50
    early_exit : bool = True             # allows the sim to exit early
    prefer_info : bool = True            # among tied root moves, play the one whose outcome is not yet known (a draw) first
    rollout : RolloutPolicy = RolloutPolicy.ClaudeHeuristic
    info_bonus : float = 0.0             # largest bonus for resolving a draw / random effect early, in HP of the final score (0 = off; the idea is <= 0.5)
    reuse_tree : bool = True             # keep the part of the previous search the game actually went into (needs the same sts2_MCTS object)
    paired_scenarios : int = 300         # after the search, replay the picked move and its close rivals under the same random scenarios and keep the picked move unless a rival is significantly ahead (0 = off)
    order_check : bool = True            # after the search, try the turn's plain plays (no random outcome) in every order under the same scenarios and play first what the best order starts with (needs paired_scenarios > 0)
    reward : RewardParams = field(default_factory=RewardParams)
    uct : UctParams = field(default_factory=UctParams)
    confidence : ConfidenceParams = field(default_factory=ConfidenceParams)
    heuristic : HeuristicParams = field(default_factory=HeuristicParams)

    def tuned(self, **values) -> SearchConfig:
        """A copy with the named fields changed. A name is a field of the config itself or of one of its groups (they never share one):
        `config.tuned(max_sims=500, p_random_action=0.0, win_base=10)`."""
        own, groups = {}, {}
        for name, value in values.items():
            if name in GROUPS:
                own[name] = value
            elif name in _OWN_FIELDS:
                own[name] = value
            else:
                group = _FIELD_GROUP.get(name)
                if group is None:
                    raise KeyError(f"unknown search parameter {name!r}")
                groups.setdefault(group, {})[name] = value
        for group, changes in groups.items():
            if group in own:
                raise ValueError(f"both {group!r} and one of its fields were given")
            own[group] = dataclasses.replace(getattr(self, group), **changes)
        return dataclasses.replace(self, **own)

    def to_dict(self) -> dict:
        """Plain JSON-able form (enum keys and values by name); `from_dict` is its inverse."""
        d = {}
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if f.name in GROUPS:
                value = {g.name: _plain(getattr(value, g.name)) for g in dataclasses.fields(value)}
            else:
                value = _plain(value)
            d[f.name] = value
        return d

    @classmethod
    def from_dict(cls, d : dict) -> SearchConfig:
        d = dict(d)
        d["rollout"] = RolloutPolicy[d["rollout"]]
        base = cls()
        for group, group_class in GROUPS.items():
            if group in d:
                d[group] = _group_from_dict(getattr(base, group), group_class, d[group])
        return cls(**d)


DEFAULT_CONFIG = SearchConfig()           # the shipped defaults, for reading (tests compare against them)
GROUPS = {"reward" : RewardParams, "uct" : UctParams, "confidence" : ConfidenceParams, "heuristic" : HeuristicParams}
_OWN_FIELDS = {f.name for f in dataclasses.fields(SearchConfig)} - set(GROUPS)
_FIELD_GROUP = {f.name : group for group, cls in GROUPS.items() for f in dataclasses.fields(cls)}

def _plain(value):
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, dict):
        return {(k.name if isinstance(k, Enum) else k) : v for k, v in value.items()}
    return value

def _group_from_dict(default, group_class, d : dict):
    out = {}
    for name, value in d.items():
        current = getattr(default, name)
        if isinstance(current, dict):         # keys are enum members: look them up by the type of the default's keys
            key_type = type(next(iter(current)))
            value = {key_type[k] if isinstance(k, str) else k : v for k, v in value.items()}
        out[name] = value
    return group_class(**out)
