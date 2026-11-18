"""Card rarity odds and card rewards (CardRarityOdds, CardFactory.CreateForReward). Run from scripts/: python -m pytest sts2_lite/Tests"""
import random
import re

import pytest

from data_paths import DECOMPILED
from sts2_lite.card.ids import CardId, CardType
from sts2_lite.card.tables import CARD_RARITY, GENERATABLE_CARDS
from sts2_lite.rewards import CardRarityOdds, IRONCLAD_POOL, OddsType, Rarity, Source, base_odds, create_card_reward, create_for_merchant, create_reward_for_room
from sts2_lite.rewards.cards import next_allowed_rarity, rarity_of, roll_for_upgrade


class Fixed:
    """An rng that gives the numbers it is given, and picks the first item."""
    def __init__(self, *numbers):
        self.numbers = list(numbers)

    def random(self):
        return self.numbers.pop(0)

    def choice(self, items):
        return items[0]


def test_base_odds_of_the_game():
    assert [base_odds(OddsType.REGULAR_ENCOUNTER, r) for r in (Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE)] == [0.6, 0.37, 0.03]
    assert [base_odds(OddsType.ELITE_ENCOUNTER, r) for r in (Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE)] == [0.5, 0.4, 0.1]
    assert [base_odds(OddsType.SHOP, r) for r in (Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE)] == [0.54, 0.37, 0.09]
    assert [base_odds(OddsType.BOSS_ENCOUNTER, r) for r in (Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE)] == [0.0, 0.0, 1.0]
    assert base_odds(OddsType.REGULAR_ENCOUNTER, Rarity.RARE, 7) == 0.0149 and base_odds(OddsType.ELITE_ENCOUNTER, Rarity.RARE, 7) == 0.05
    assert base_odds(OddsType.SHOP, Rarity.RARE, 7) == 0.045 and base_odds(OddsType.REGULAR_ENCOUNTER, Rarity.RARE, 6) == 0.03


def test_the_offset_starts_below_zero_so_a_first_roll_cannot_be_rare():
    odds = CardRarityOdds(Fixed(0.0, 0.34, 0.38))
    assert odds.current_value == -0.05
    assert odds.roll(OddsType.REGULAR_ENCOUNTER) == Rarity.UNCOMMON         # 0.03 - 0.05 < 0: nothing below it, the uncommon band is [-0.02, 0.35)
    assert odds.roll(OddsType.REGULAR_ENCOUNTER) == Rarity.UNCOMMON          # 0.34 < 0.03 - 0.04 + 0.37
    assert odds.roll(OddsType.REGULAR_ENCOUNTER) == Rarity.COMMON            # 0.38 >= 0.03 - 0.03 + 0.37


def test_every_roll_grows_the_offset_up_to_the_cap_and_a_rare_resets_it():
    odds = CardRarityOdds(Fixed(*[0.99] * 100))
    for _ in range(100):
        odds.roll(OddsType.REGULAR_ENCOUNTER)
    assert odds.current_value == pytest.approx(0.4)
    odds.rng = Fixed(0.0)
    assert odds.roll(OddsType.REGULAR_ENCOUNTER) == Rarity.RARE and odds.current_value == -0.05
    scarce = CardRarityOdds(Fixed(0.99, 0.99), ascension=7)
    scarce.roll(OddsType.REGULAR_ENCOUNTER)
    scarce.roll(OddsType.REGULAR_ENCOUNTER)
    assert scarce.current_value == pytest.approx(-0.04)


def test_a_boss_reward_is_always_rare_and_resets_the_offset():
    odds = CardRarityOdds(Fixed(0.999), current_value=0.3)
    assert odds.roll(OddsType.BOSS_ENCOUNTER) == Rarity.RARE and odds.current_value == -0.05


def test_rolling_with_base_odds_puts_the_uncommon_band_after_the_rare_one():
    odds = CardRarityOdds(Fixed(0.029, 0.03, 0.399, 0.40), current_value=0.3)
    assert [odds.roll_with_base_odds(OddsType.REGULAR_ENCOUNTER) for _ in range(4)] == [Rarity.RARE, Rarity.UNCOMMON, Rarity.UNCOMMON, Rarity.COMMON]
    assert odds.current_value == 0.3
    shop = CardRarityOdds(Fixed(0.0), current_value=0.2)
    assert shop.roll_without_changing_future_odds(OddsType.SHOP) == Rarity.RARE and shop.current_value == 0.2


def test_a_rarity_the_pool_lacks_moves_up_and_wraps():
    assert next_allowed_rarity(Rarity.COMMON, {Rarity.RARE}.__contains__) == Rarity.RARE
    assert next_allowed_rarity(Rarity.RARE, {Rarity.COMMON}.__contains__) == Rarity.COMMON
    assert next_allowed_rarity(Rarity.UNCOMMON, {Rarity.COMMON}.__contains__) == Rarity.COMMON
    assert next_allowed_rarity(Rarity.UNCOMMON, set().__contains__) == Rarity.NONE


def test_the_upgrade_roll_grows_with_the_act_and_never_helps_rare_cards():
    common, rare = CardId.ANGER, CardId.DEMON_FORM
    assert rarity_of(common) == Rarity.COMMON and rarity_of(rare) == Rarity.RARE
    assert not roll_for_upgrade(Fixed(0.01), common, 0, 0) and roll_for_upgrade(Fixed(0.24), common, 0, 1) and not roll_for_upgrade(Fixed(0.26), common, 0, 1)
    assert roll_for_upgrade(Fixed(0.5), common, 0, 2) and not roll_for_upgrade(Fixed(0.5), rare, 0, 2)
    assert roll_for_upgrade(Fixed(0.12), common, 0, 1, ascension=7) and not roll_for_upgrade(Fixed(0.13), common, 0, 1, ascension=7)
    rng = Fixed(0.1)
    roll_for_upgrade(rng, common, 0, 0, upgradable=False)
    assert rng.numbers == []        # the number is drawn all the same


def test_a_reward_is_three_different_cards_from_the_pool():
    rng = random.Random(1)
    odds = CardRarityOdds(rng)
    pool = {cid for cards in IRONCLAD_POOL.values() for cid in cards}
    for _ in range(300):
        cards = [o.card_id for o in create_card_reward(rng, odds, 0)]
        assert len(cards) == 3 == len(set(cards)) and set(cards) <= pool


def test_card_rewards_move_the_odds_once_per_card_and_events_do_not():
    rng = random.Random(2)
    odds = CardRarityOdds(rng)
    create_card_reward(rng, odds, 0, 3, OddsType.REGULAR_ENCOUNTER, Source.ENCOUNTER)
    assert odds.current_value in (pytest.approx(-0.02), -0.05) or odds.current_value > -0.05
    before = odds.current_value
    create_card_reward(rng, odds, 0, 3, OddsType.REGULAR_ENCOUNTER, Source.OTHER)
    assert odds.current_value == before
    create_card_reward(rng, odds, 0, 3, OddsType.REGULAR_ENCOUNTER, Source.OTHER, force_odds_change=True)
    assert odds.current_value != before


def test_rarity_shares_of_a_regular_reward_follow_the_odds():
    rng = random.Random(3)
    counts = {Rarity.COMMON: 0, Rarity.UNCOMMON: 0, Rarity.RARE: 0}
    for _ in range(3000):
        odds = CardRarityOdds(rng)
        for offer in create_card_reward(rng, odds, 0, 1, source=Source.OTHER, no_upgrade_roll=True):        # base odds: 3% rare, 37% uncommon, 60% common
            counts[rarity_of(offer.card_id)] += 1
    shares = {r: n / 3000 for r, n in counts.items()}
    assert shares[Rarity.RARE] == pytest.approx(0.03, abs=0.015) and shares[Rarity.UNCOMMON] == pytest.approx(0.37, abs=0.04)


def test_boss_rewards_are_three_rares():
    rng = random.Random(4)
    for _ in range(50):
        offers = create_reward_for_room(rng, CardRarityOdds(rng), "Boss", 2)
        assert {rarity_of(o.card_id) for o in offers} == {Rarity.RARE}


def test_upgrades_in_rewards_depend_on_the_act():
    rng = random.Random(5)
    first = sum(o.upgraded for _ in range(500) for o in create_reward_for_room(rng, CardRarityOdds(rng), "Monster", 0))
    third = sum(o.upgraded for _ in range(500) for o in create_reward_for_room(rng, CardRarityOdds(rng), "Monster", 2))
    assert first < 5 and third > 300        # 0% in act 1, 50% of the common and uncommon cards in act 3


def test_a_single_rarity_pool_needs_uniform_odds_and_may_not_repeat():
    rng = random.Random(6)
    odds = CardRarityOdds(rng)
    rares = list(IRONCLAD_POOL["Rare"])
    offers = create_card_reward(rng, odds, 0, 3, OddsType.UNIFORM, Source.OTHER, pool=rares, no_upgrade_roll=True)
    assert len({o.card_id for o in offers}) == 3
    commons = create_card_reward(rng, odds, 0, 3, OddsType.REGULAR_ENCOUNTER, Source.OTHER, pool=rares, no_upgrade_roll=True)        # the rarity moves up to what the pool has
    assert {rarity_of(o.card_id) for o in commons} == {Rarity.RARE}


def test_the_merchant_sells_the_type_asked_for_and_never_upgrades():
    rng = random.Random(7)
    odds = CardRarityOdds(rng)
    types = {cid: info[1] for cid, info in GENERATABLE_CARDS.items()}
    pool = list(types)
    for _ in range(100):
        offer = create_for_merchant(rng, odds, pool, CardType.Power, types.get)
        assert types[offer.card_id] == CardType.Power and not offer.upgraded
    assert odds.current_value == -0.05


def test_the_reward_pool_is_the_ironclad_pool_of_the_game():
    names = {a: [] for a in ("Common", "Uncommon", "Rare")}
    path = DECOMPILED / "Core" / "Models" / "CardPools" / "IroncladCardPool.cs"
    if not path.exists():
        pytest.skip("the decompiled game is not here")
    in_pool = {re.sub(r"(?<!^)(?=[A-Z])", "_", n).upper() for n in re.findall(r"ModelDb\.Card<(\w+)>", path.read_text())}
    for cid, rarity in CARD_RARITY.items():
        if rarity.name in names and cid.name in in_pool:
            names[rarity.name].append(cid)
    assert {r: set(c) for r, c in names.items()} == {r: set(c) for r, c in IRONCLAD_POOL.items()}
    assert [len(IRONCLAD_POOL[r]) for r in ("Common", "Uncommon", "Rare")] == [20, 35, 25]
