"""Everything that tunes the deck choosers (cards, rest sites, shops, events, ancients, the map) and the walks they are judged on, in one place.

`DeckEvalConfig` is frozen; to try another value make another config: `DeckEvalConfig().tuned(path_seconds=4, card_z=1.0)`. The DeckAdvisor holds the
config and hands it to the evaluator and the walks (route_sim), so every chooser of an agent reads the same numbers: `MyAgent(deck_config=...)`.
The benchmarks set fields from the command line with `--deck name=value` (benchmarks/runs.py).

What is a fact of the game (a rest heals 30%, the rarity odds of a card reward) stays a constant of its module; only what is a choice of ours is here."""
from __future__ import annotations
import dataclasses
from dataclasses import dataclass


@dataclass(frozen=True)
class DeckEvalConfig:
    # ---- thinking time of one decision, in seconds (every candidate is played on as many walks as fit)
    card_seconds : float = 8.0          # an ordinary card reward (the number of fights is set from it: a pilot of `pilot_fights` measures the speed)
    card_big_seconds : float = 15.0     # the first `early_rewards` picks and the boss reward shape the whole run: they get longer
    upgrade_seconds : float = 10.0      # a rest site's smith-or-heal analysis, and which card to upgrade
    shop_seconds : float = 15.0         # one shop screen (relics, cards and the removal are all played)
    event_seconds : float = 10.0
    ancient_seconds : float = 10.0
    path_seconds : float = 10.0         # a map decision

    # ---- card rewards (card_reward_chooser)
    card_z : float = 1.5                # standard errors a card's gain over skipping has to clear
    card_floor : float = 0.02           # reward points: the smallest gain worth a card ...
    attack_bonus : float = 1.0         # card rewards: rooms added to an Attack's gain when the deck has no other (non-starter) Attack; each one it has scales it by attack_decay
    attack_decay : float = 0.5
    skill_bonus : float = 1.5          # the same for a Skill
    skill_decay : float = 0.5
    power_bonus : float = 2.0          # ... and a Power (the walks see the first few Powers of a deck badly: the policy plays them poorly and the fights are too short to pay them off)
    power_decay : float = 0.5
    uncommon_bonus_factor : float = 1.5    # the bonus of an Uncommon card is multiplied by this
    rare_bonus_factor : float = 2.0        # ... and of a Rare card by this
    card_early_floor : float = 0.01     # ... and for the first `early_rewards` rewards of a run (a starter deck nearly always takes a card)
    early_rewards : int = 3
    full_floor_win_rate : float = 0.8   # the floor applies in full from this win rate on the walks ahead; a weaker deck needs help, so the floor shrinks with it
    pilot_fights : int = 100
    min_fights : int = 400              # bounds on the fights a card reward is decided on
    max_fights : int = 12000

    # ---- shops (shop_chooser)
    shop_z : float = 1.5                # the Z-score a purchase has to clear
    last_shop_z : float = 0.1          # the Z-score asked for in the last shop the agent plans to visit in act 3 (no later shop for the gold)
    potion_lookahead : int = 3          # an elite or the boss within this many rooms of the planned route is a reason to buy potions

    # ---- the map (path_search)
    max_candidates : int = 24           # paths walked at most
    per_option : int = 5                # ... of which at most this many start with the same option
    round_walks : int = 2               # walks every candidate plays in a round
    rounds_per_cut : int = 3            # every this many rounds the worse half of the candidates is dropped ...
    min_keep : int = 4                  # ... down to this many
    elite_bonus : float = 2.0          # rooms of progress added to a path for each elite on it at the end of the act (the walks see an elite's risk in full, its reward only in part)
    path_tie_z : float = 1.0           # when hurt, a path whose walks are within this many standard errors of the best counts as tied with it ...
    path_tie_hp : float = 0.5          # ... (hurt: HP below this share of the max) and the tied path that reaches a rest site or a shop soonest is taken
    shop_gold_per_floor : float = 15.0 # a shop's bonus: the gold expected there (the gold held now, plus this much for each room before it) ...
    shop_gold_scale : float = 200.0    # ... divided by this, in rooms. The walks see a shop's purchases only through the fights after it, not their long-term worth
    shop_gold_min : float = 200.0      # a shop earns the bonus only when the gold expected there is at least this much
    elite_act_step : float = 0.5       # the elite bonus falls by this much in each act after the first (2.0 -> 1.5 -> 1.0)
    elite_early : float = 1.0          # an elite at the start of the act gets this share of elite_bonus; the share grows linearly with the row to 1 at the boss

    # ---- the walks (advisor, route_sim): how many, and how a walk is scored in rooms of progress
    min_walks : int = 6                 # fewest walks a decision is played on
    max_walks : int = 800               # most walks a time-boxed decision plays, whatever its time
    batch_walks : int = 2               # walks played at a time by DeckAdvisor.race (the clock is checked between batches)
    default_fights : int = 400          # fights a decision is played on when its chooser does not say
    max_turns : int = 25                # a rollout fight that lasts longer is stopped there
    lookahead_rooms : int = 3           # rooms of the next act a walk that clears its act goes on to play
    min_walk_rooms : int = 8            # a walk is at least this many rooms long: with fewer left in the act it plays more of the next one (scaling cards pay off after the boss)
    clear_bonus : float = 8.0           # a cleared last act: the run is won (the same share of an act as a surviving walk gets for the acts still ahead)
    act_rooms : int = 16                # rooms in an act, for what a walk that survives has still ahead of it
    continuation_share : float = 0.5    # the share of the rooms still ahead (after the lookahead) a walk that survives is credited with: dying before the end of the walk forfeits them (0: a death costs only the act)
    potion_credit : float = 0.1         # rooms' worth of progress each potion held at the end of the walk
    max_hp_credit : float = 0.02        # rooms' worth for each point of max HP gained during the walk
    correct : bool = True               # turn the rollout policy's fights into what the MCTS would get (route_sim.CORRECTION)

    def tuned(self, **values) -> DeckEvalConfig:
        """A copy with the named fields changed: `config.tuned(path_seconds=4)`. An unknown name is an error."""
        unknown = set(values) - set(FIELDS)
        if unknown:
            raise KeyError("unknown deck-eval parameter(s): %s" % ", ".join(sorted(unknown)))
        return dataclasses.replace(self, **values)


FIELDS = {f.name: f.type for f in dataclasses.fields(DeckEvalConfig)}
DEFAULT = DeckEvalConfig()
