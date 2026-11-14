"""What a won fight pays out (RewardsSet.GenerateRewardsFor): gold, maybe a potion, a card reward and, from an elite, a relic."""
from __future__ import annotations

from dataclasses import dataclass

from sts2_lite.encounters import Encounter
from sts2_lite.potion import POTION_INFO, PotionId, PotionRarity
from sts2_lite.rewards import CardRarityOdds, create_reward_for_room
from sts2_lite.run import RunState

GOLD_RANGE = {"Monster": (10, 20), "Elite": (35, 45), "Boss": (100, 100)}
POVERTY_ASCENSION = 3
POVERTY_GOLD = 0.75         # AscensionHelper.PovertyAscensionGoldMultiplier: not in the decompile, 0.75 assumed
POTION_ELITE_BONUS = 0.25   # PotionRewardOdds: the roll adds half of it
POTION_STEP = 0.1
POTION_RARITY_ODDS = ((PotionRarity.COMMON, 0.65), (PotionRarity.UNCOMMON, 0.25), (PotionRarity.RARE, 0.10))      # assumed (Slay the Spire 1's)


@dataclass
class Reward:
    kind : str              # "gold" | "potion" | "card" | "relic"
    amount : int = 0        # gold
    potion : str | None = None
    cards : list | None = None     # the cards of a card reward (CardOffer)

    def description(self) -> str:
        return {"gold": f"{self.amount} gold", "potion": "Add a potion to your belt", "card": "Add a card to your deck", "relic": "Obtain a relic"}[self.kind]


def gold_range(encounter : Encounter, ascension : int) -> tuple[int, int]:
    low, high = encounter.gold or GOLD_RANGE[encounter.room]
    if ascension >= POVERTY_ASCENSION and encounter.gold is None:
        low, high = int(low * POVERTY_GOLD), int(high * POVERTY_GOLD)
    return low, high


def roll_potion_reward(run : RunState, room : str, rng) -> bool:
    """PotionRewardOdds.Roll: a pity system that moves 10% each way."""
    bonus = POTION_ELITE_BONUS if room == "Elite" else 0.0
    chance = run.hidden.potion_odds + bonus * 0.5
    if rng.random() < chance:
        run.hidden.potion_odds -= POTION_STEP
        return True
    run.hidden.potion_odds += POTION_STEP
    return False


def random_potion(rng) -> str:
    """A potion by rarity (the sim's own list: the game's drop table is not in the decompile)."""
    x, rarity = rng.random(), PotionRarity.COMMON
    for kind, share in POTION_RARITY_ODDS:
        rarity = kind
        x -= share
        if x < 0:
            break
    return rng.choice([p.name for p, info in POTION_INFO.items() if info.rarity == rarity])


def generate_rewards(run : RunState, encounter : Encounter, last_act_boss : bool, game) -> list[Reward]:
    """The rewards of a won fight. The last boss of the run pays nothing; an encounter flagged `rewards=False` (some event fights) pays nothing."""
    if not encounter.rewards or (encounter.room == "Boss" and last_act_boss):
        return []
    room = encounter.room
    out = []
    low, high = gold_range(encounter, run.ascension)
    out.append(Reward("gold", amount=game.stream("gold").randint(low, high)))
    if roll_potion_reward(run, room, game.stream("potion_rewards")):
        out.append(Reward("potion", potion=random_potion(game.stream("potion_rewards"))))
    rng = game.stream("card_rewards")
    odds = CardRarityOdds(rng, run.ascension, run.hidden.rarity_offset)
    cards = create_reward_for_room(rng, odds, room, max(0, run.act - 1))
    run.hidden.rarity_offset = odds.current_value
    out.append(Reward("card", cards=cards))
    if room == "Elite":
        out.append(Reward("relic"))
    return out
