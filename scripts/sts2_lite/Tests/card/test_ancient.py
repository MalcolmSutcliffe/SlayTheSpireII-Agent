from sts2_lite.card import Card, CardId, CardType, INNATE_CARDS, TargetType
from sts2_lite.combat import CombatSimulator
from sts2_lite.status import StatusId
from sts2_lite.Tests.enemies.test_glory_simple import at
from sts2_lite.Tests.card.test_card import make_card, make_state, play, hps
from sts2_lite.Tests.card.test_powers import strike, defend, skill, power, one_enemy


def ancient(card_id, upgraded=False, kind=CardType.Skill, target=TargetType.Self):
    cost = Card.create_generated(card_id).energy_cost
    c = make_card(card_id, card_id.name.title(), kind, cost, target)
    return c.upgraded_copy() if upgraded else c

def attack_card(card_id, upgraded=False):
    return ancient(card_id, upgraded, CardType.Attack, TargetType.AnyEnemy)

def ids(pile):
    return [c.card_id for c in pile]


# ---------------------------------------------------------------- Apotheosis
def test_apotheosis_upgrades_every_pile_and_exhausts():
    cs = one_enemy([ancient(CardId.APOTHEOSIS), strike()])
    p = cs.player
    p.draw_pile, p.discard_pile, p.exhaust_pile = [defend()], [strike()], [strike()]
    play(cs)
    assert all(c.is_upgraded for c in p.hand + p.draw_pile + p.discard_pile + p.exhaust_pile if c.card_id != CardId.APOTHEOSIS)
    assert ids(p.exhaust_pile).count(CardId.APOTHEOSIS) == 1 and cs.energy == 1

def test_apotheosis_upgraded_costs_one_and_is_innate_exhaust():
    c = ancient(CardId.APOTHEOSIS, True)
    assert c.energy_cost == 1 and c.exhausts and CardId.APOTHEOSIS in INNATE_CARDS

# ---------------------------------------------------------------- Brightest Flame
def test_brightest_flame_energy_cards_and_max_hp():
    cs = one_enemy([ancient(CardId.BRIGHTEST_FLAME)])
    cs.player.draw_pile = [defend() for _ in range(5)]
    play(cs)
    assert cs.energy == 5 and len(cs.player.hand) == 2 and cs.player.max_hp == 49 and cs.player.current_hp == 49

def test_brightest_flame_upgraded():
    cs = one_enemy([ancient(CardId.BRIGHTEST_FLAME, True)])
    cs.player.draw_pile = [defend() for _ in range(5)]
    play(cs)
    assert cs.energy == 6 and len(cs.player.hand) == 3

# ---------------------------------------------------------------- Wish
def test_wish_takes_the_chosen_card_from_the_draw_pile_and_exhausts():
    cs = one_enemy([ancient(CardId.WISH)])
    cs.player.draw_pile = [strike(), defend(), power(CardId.INFERNO)]
    sim = play(cs)
    cs.player.draw_pile[:] = cs.player.draw_pile
    assert cs.pending_choice is not None
    sim.choose_card(2)
    assert ids(cs.player.hand) == [CardId.INFERNO] and len(cs.player.draw_pile) == 2
    assert ids(cs.player.exhaust_pile) == [CardId.WISH]

def test_wish_upgraded_retains_and_with_an_empty_pile_does_nothing():
    c = ancient(CardId.WISH, True)
    assert c.retains and c.exhausts
    cs = one_enemy([ancient(CardId.WISH)])
    play(cs)
    assert cs.pending_choice is None and cs.player.hand == []

# ---------------------------------------------------------------- Whistle
def test_whistle_hits_and_stuns_the_move_it_interrupts():
    cs = at("PHANTASMAL_GARDENER", "FLAIL", hp=100, max_hp=100)
    cs.player.hand = [attack_card(CardId.WHISTLE)]
    cs.energy = cs.max_energy = 3
    CombatSimulator(cs).play_card(0, 0)
    e = cs.enemies[0]
    assert e.current_hp == 67 and e.move_id == "STUNNED" and e.after_stun == "FLAIL"
    hp = cs.player.current_hp
    CombatSimulator(cs)._play_enemy_turn()
    assert cs.player.current_hp == hp and cs.enemies[0].move_id == "FLAIL"
    assert ids(cs.player.exhaust_pile) == [CardId.WHISTLE]

def test_whistle_upgraded_damage():
    cs = one_enemy([attack_card(CardId.WHISTLE, True)], hp=100)
    play(cs)
    assert hps(cs) == [56]

# ---------------------------------------------------------------- Relax
def test_relax_blocks_now_and_pays_energy_and_cards_next_turn():
    cs = one_enemy([ancient(CardId.RELAX)])
    cs.player.draw_pile = [defend() for _ in range(20)]
    sim = play(cs)
    assert cs.player.block == 16 and cs.player.status_amount(StatusId.ENERGY_NEXT_TURN) == 2
    sim.end_turn()
    assert cs.energy == 3 + 2 and len(cs.player.hand) == 5 + 2
    assert StatusId.ENERGY_NEXT_TURN not in cs.player.status and StatusId.DRAW_CARDS_NEXT_TURN not in cs.player.status
    sim.end_turn()
    assert cs.energy == 3 and len(cs.player.hand) == 5

def test_relax_upgraded():
    cs = one_enemy([ancient(CardId.RELAX, True)])
    cs.player.draw_pile = [defend() for _ in range(20)]
    sim = play(cs)
    assert cs.player.block == 18
    sim.end_turn()
    assert cs.energy == 6 and len(cs.player.hand) == 8

# ---------------------------------------------------------------- Maul
def test_maul_hits_twice_and_grows_every_maul():
    cs = one_enemy([attack_card(CardId.MAUL), attack_card(CardId.MAUL)], hp=100)
    cs.player.draw_pile = [attack_card(CardId.MAUL)]
    play(cs)
    assert hps(cs) == [90]
    other, drawn = cs.player.hand[0], cs.player.draw_pile[0]
    assert other.bonus_damage == drawn.bonus_damage == 2
    CombatSimulator(cs).play_card(0, 0)
    assert hps(cs) == [90 - 14]             # (5 + 2) x 2

def test_maul_upgraded_grows_by_three():
    cs = one_enemy([attack_card(CardId.MAUL, True), attack_card(CardId.MAUL)], hp=100)
    play(cs)
    assert hps(cs) == [88] and cs.player.hand[0].bonus_damage == 3

def test_maul_bonus_is_read_from_the_shown_damage():
    from sts2_lite.player import Player
    hand = [attack_card(CardId.MAUL)]
    hand[0].shown_damage = 9
    pl = Player()
    pl.hand = hand
    pl.draw_pile = pl.discard_pile = pl.exhaust_pile = []
    pl.status = {}
    pl._read_growing_cards()
    assert hand[0].bonus_damage == 4

# ---------------------------------------------------------------- Apparition
def test_apparition_gives_intangible_through_the_enemy_turn():
    cs = one_enemy([ancient(CardId.APPARITION)])
    e = cs.enemies[0]
    e.attack_damage, e.num_attacks = 20, 1
    sim = play(cs)
    assert cs.player.status_amount(StatusId.INTANGIBLE) == 1
    sim.end_turn()
    assert cs.player.current_hp == 49 and StatusId.INTANGIBLE not in cs.player.status

def test_apparition_is_ethereal_until_upgraded():
    assert ancient(CardId.APPARITION).ethereal
    up = ancient(CardId.APPARITION, True)
    assert not up.ethereal and up.exhausts

# ---------------------------------------------------------------- Abundance
def test_abundance_offers_three_upgraded_powers_for_free():
    cs = one_enemy([ancient(CardId.ABUNDANCE)])
    sim = play(cs)
    offers = cs.pending_choice.offers
    assert len(offers) == 3 and all(o.type == CardType.Power and o.is_upgraded for o in offers)
    sim.choose_card(1)
    assert len(cs.player.hand) == 1 and cs.player.hand[0].energy_cost == 0
    assert ids(cs.player.exhaust_pile) == [CardId.ABUNDANCE]

def test_abundance_upgraded_costs_nothing():
    assert ancient(CardId.ABUNDANCE, True).energy_cost == 0
