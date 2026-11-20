"""What a won fight pays out (RewardsSet.GenerateRewardsFor): gold, maybe a potion, a card reward and, from an elite, a relic."""
from __future__ import annotations

from dataclasses import dataclass

from sts2_lite.encounters import Encounter
from sts2_lite.potion import POTION_INFO, PotionId, PotionRarity
from sts2_lite.relic.bag import pull_relic, relic_name
from sts2_lite.relic.run_hooks import candy_adds_power, forces_potion_reward, reward_extras
from sts2_lite.rewards import CardRarityOdds, create_reward_for_room
from sts2_lite.run import RunState

GOLD_RANGE = {"Monster": (10, 20), "Elite": (35, 45), "Boss": (100, 100)}
POVERTY_ASCENSION = 3
POVERTY_GOLD = 0.75         # AscensionHelper.PovertyAscensionGoldMultiplier: not in the decompile, 0.75 assumed
POTION_ELITE_BONUS = 0.25   # PotionRewardOdds: the roll adds half of it
POTION_STEP = 0.1


@dataclass
class Reward:
    kind : str              # "gold" | "potion" | "card" | "relic" | "card_removal"
    amount : int = 0        # gold
    potion : str | None = None
    cards : list | None = None     # the cards of a card reward (CardOffer)
    relic : str | None = None      # the relic of a relic reward
    room : str | None = None       # a card reward: the room type whose odds made it

    def description(self) -> str:
        return {"card_removal": "Remove a card from your deck", "gold": f"{self.amount} gold", "potion": "Add a potion to your belt", "card": "Add a card to your deck", "relic": "Obtain " + (relic_name(self.relic) if self.relic else "a relic")}[self.kind]


def gold_range(encounter : Encounter, ascension : int) -> tuple[int, int]:
    low, high = encounter.gold or GOLD_RANGE[encounter.room]
    if ascension >= POVERTY_ASCENSION and encounter.gold is None:
        low, high = int(low * POVERTY_GOLD), int(high * POVERTY_GOLD)
    return low, high


TREASURE_GOLD = (42, 52)    # OneOffSynchronizer.DoTreasureRoomRewards: NextInt(42, 53), times the Poverty multiplier


def treasure_gold_range(ascension : int) -> tuple[int, int]:
    low, high = TREASURE_GOLD
    if ascension >= POVERTY_ASCENSION:
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


def random_potion(rng, character : str = "IRONCLAD") -> str:
    """PotionFactory.CreateRandomPotionOutOfCombat: rarity roll (10% rare, 25% uncommon, else common), the character's + shared pools."""
    from sts2_lite.potion_pool import random_potion_id
    return random_potion_id(rng, character).name


def generate_rewards(run : RunState, encounter : Encounter, last_act_boss : bool, game) -> list[Reward]:
    """The rewards of a won fight. The last boss of the run pays nothing; an encounter flagged `rewards=False` (some event fights) pays nothing."""
    if not encounter.rewards or (encounter.room == "Boss" and last_act_boss):
        return []
    room = encounter.room
    out = []
    low, high = gold_range(encounter, run.ascension)
    out.append(Reward("gold", amount=game.stream("gold").randint(low, high)))
    rolled = roll_potion_reward(run, room, game.stream("potion_rewards"))
    if rolled or forces_potion_reward(run, room):
        out.append(Reward("potion", potion=random_potion(game.stream("potion_rewards"), run.character)))
    rng = game.stream("card_rewards")
    odds = CardRarityOdds(rng, run.ascension, run.hidden.rarity_offset)
    act_index = max(0, run.act - 1)
    cards = create_reward_for_room(rng, odds, room, act_index, **_pool_options(run))
    if candy_adds_power(run):
        cards += _candy_power(rng, odds, act_index, cards, run.character)
    out.append(Reward("card", cards=cards, room=room))
    if room == "Elite":
        out.append(Reward("relic", relic=_pull(run)))
    for extra in reward_extras(run, room, last_act_boss):
        if extra[0] == "gold":
            out.append(Reward("gold", amount=extra[1]))
        elif extra[0] == "relic":
            out.append(Reward("relic", relic=_pull(run)))
        else:
            out.append(Reward("card", cards=create_reward_for_room(rng, odds, extra[1], act_index, **_pool_options(run)), room=extra[1]))
    run.hidden.rarity_offset = odds.current_value
    return out


def _pull(run) -> str | None:
    return pull_relic(run) if run.hidden.relic_bag else None


def _pool_options(run) -> dict:
    """The character's pool; with Dingy Rug the colorless cards join it."""
    if not run.has_relic("DINGY_RUG"):
        return {"character": run.character}
    from sts2_lite.card.tables import COLORLESS_CARDS
    from sts2_lite.rewards.cards import card_pool_ids
    return {"pool": card_pool_ids(run.character) + list(COLORLESS_CARDS)}


def _candy_power(rng, odds, act_index : int, cards : list, character : str = "IRONCLAD") -> list:
    """Lasting Candy's extra option: a Power the reward does not hold yet (any Power when it holds them all)."""
    from sts2_lite.event.run import card_entry
    from sts2_lite.rewards import create_card_reward
    from sts2_lite.rewards.cards import card_pool_ids
    powers = [c for c in card_pool_ids(character) if card_entry(c)["type"] == "Power"]
    held = {o.card_id for o in cards}
    fresh = [c for c in powers if c not in held] or powers
    return create_card_reward(rng, odds, act_index, 1, pool=fresh) if fresh else []
