from __future__ import annotations
from typing import TYPE_CHECKING

from enum import Enum, auto
from sts2_lite.status import StatusId

from sts2_lite.card.constants import BAD_LUCK_HP_LOSS, CURSE_STATUS_AMOUNT, DECAY_DAMAGE
from sts2_lite.card.ids import CardId, CardType, TargetType

if TYPE_CHECKING:
    from sts2_lite.card.card import Card

# the Ironclad cards that card effects can add to the player's piles (no Basic or Ancient cards, Feed and Not Yet
# can't be generated, Tank and Demonic Shield are multiplayer only): (name, type, cost, target)
S, A, ALL, RAND = TargetType.Self, TargetType.AnyEnemy, TargetType.AllEnemies, TargetType.RandomEnemy

GENERATABLE_CARDS = {
    CardId.AGGRESSION : ("Aggression", CardType.Power, 1, S),
    CardId.ANGER : ("Anger", CardType.Attack, 0, A),
    CardId.ARMAMENTS : ("Armaments", CardType.Skill, 1, S),
    CardId.ASHEN_STRIKE : ("Ashen Strike", CardType.Attack, 1, A),
    CardId.BARRICADE : ("Barricade", CardType.Power, 3, S),
    CardId.BATTLE_TRANCE : ("Battle Trance", CardType.Skill, 0, S),
    CardId.BLOOD_WALL : ("Blood Wall", CardType.Skill, 2, S),
    CardId.BLOODLETTING : ("Bloodletting", CardType.Skill, 0, S),
    CardId.BLUDGEON : ("Bludgeon", CardType.Attack, 3, A),
    CardId.BODY_SLAM : ("Body Slam", CardType.Attack, 1, A),
    CardId.BRAND : ("Brand", CardType.Skill, 0, S),
    CardId.BREAKTHROUGH : ("Breakthrough", CardType.Attack, 1, ALL),
    CardId.BULLY : ("Bully", CardType.Attack, 0, A),
    CardId.BURNING_PACT : ("Burning Pact", CardType.Skill, 1, S),
    CardId.CASCADE : ("Cascade", CardType.Skill, "X", S),
    CardId.CINDER : ("Cinder", CardType.Attack, 2, A),
    CardId.COLOSSUS : ("Colossus", CardType.Skill, 1, S),
    CardId.CONFLAGRATION : ("Conflagration", CardType.Attack, 1, ALL),
    CardId.CRIMSON_MANTLE : ("Crimson Mantle", CardType.Power, 1, S),
    CardId.CRUELTY : ("Cruelty", CardType.Power, 1, S),
    CardId.DARK_EMBRACE : ("Dark Embrace", CardType.Power, 2, S),
    CardId.DEMON_FORM : ("Demon Form", CardType.Power, 3, S),
    CardId.DISMANTLE : ("Dismantle", CardType.Attack, 1, A),
    CardId.DOMINATE : ("Dominate", CardType.Skill, 1, A),
    CardId.DRUM_OF_BATTLE : ("Drum of Battle", CardType.Skill, 1, S),
    CardId.EVIL_EYE : ("Evil Eye", CardType.Skill, 1, S),
    CardId.EXPECT_A_FIGHT : ("Expect a Fight", CardType.Skill, 3, S),
    CardId.FEEL_NO_PAIN : ("Feel No Pain", CardType.Power, 1, S),
    CardId.FIEND_FIRE : ("Fiend Fire", CardType.Attack, 2, A),
    CardId.FIGHT_ME : ("Fight Me", CardType.Attack, 2, A),
    CardId.FLAME_BARRIER : ("Flame Barrier", CardType.Skill, 2, S),
    CardId.FORGOTTEN_RITUAL : ("Forgotten Ritual", CardType.Skill, 1, S),
    CardId.HAVOC : ("Havoc", CardType.Skill, 1, S),
    CardId.HEADBUTT : ("Headbutt", CardType.Attack, 1, A),
    CardId.HELLRAISER : ("Hellraiser", CardType.Power, 2, S),
    CardId.HEMOKINESIS : ("Hemokinesis", CardType.Attack, 1, A),
    CardId.HOWL_FROM_BEYOND : ("Howl from Beyond", CardType.Attack, 3, ALL),
    CardId.IMPERVIOUS : ("Impervious", CardType.Skill, 2, S),
    CardId.INFERNAL_BLADE : ("Infernal Blade", CardType.Skill, 1, S),
    CardId.INFERNO : ("Inferno", CardType.Power, 1, S),
    CardId.INFLAME : ("Inflame", CardType.Power, 1, S),
    CardId.IRON_WAVE : ("Iron Wave", CardType.Attack, 1, A),
    CardId.JUGGERNAUT : ("Juggernaut", CardType.Power, 2, S),
    CardId.JUGGLING : ("Juggling", CardType.Power, 1, S),
    CardId.MANGLE : ("Mangle", CardType.Attack, 3, A),
    CardId.MOLTEN_FIST : ("Molten Fist", CardType.Attack, 1, A),
    CardId.OFFERING : ("Offering", CardType.Skill, 0, S),
    CardId.ONE_TWO_PUNCH : ("One-Two Punch", CardType.Skill, 1, S),
    CardId.PACTS_END : ("Pact's End", CardType.Attack, 0, ALL),
    CardId.PERFECTED_STRIKE : ("Perfected Strike", CardType.Attack, 2, A),
    CardId.PILLAGE : ("Pillage", CardType.Attack, 1, A),
    CardId.POMMEL_STRIKE : ("Pommel Strike", CardType.Attack, 1, A),
    CardId.PRIMAL_FORCE : ("Primal Force", CardType.Skill, 0, S),
    CardId.PYRE : ("Pyre", CardType.Power, 2, S),
    CardId.RAGE : ("Rage", CardType.Skill, 0, S),
    CardId.RAMPAGE : ("Rampage", CardType.Attack, 1, A),
    CardId.RUPTURE : ("Rupture", CardType.Power, 1, S),
    CardId.SECOND_WIND : ("Second Wind", CardType.Skill, 1, S),
    CardId.SETUP_STRIKE : ("Setup Strike", CardType.Attack, 1, A),
    CardId.SHRUG_IT_OFF : ("Shrug It Off", CardType.Skill, 1, S),
    CardId.SPITE : ("Spite", CardType.Attack, 0, A),
    CardId.STAMPEDE : ("Stampede", CardType.Power, 2, S),
    CardId.STOKE : ("Stoke", CardType.Skill, 1, S),
    CardId.STOMP : ("Stomp", CardType.Attack, 3, ALL),
    CardId.STONE_ARMOR : ("Stone Armor", CardType.Power, 1, S),
    CardId.SWORD_BOOMERANG : ("Sword Boomerang", CardType.Attack, 1, RAND),
    CardId.TAUNT : ("Taunt", CardType.Skill, 1, A),
    CardId.TEAR_ASUNDER : ("Tear Asunder", CardType.Attack, 2, A),
    CardId.THRASH : ("Thrash", CardType.Attack, 1, A),
    CardId.THUNDERCLAP : ("Thunderclap", CardType.Attack, 1, ALL),
    CardId.TREMBLE : ("Tremble", CardType.Skill, 1, A),
    CardId.TRUE_GRIT : ("True Grit", CardType.Skill, 1, S),
    CardId.TWIN_STRIKE : ("Twin Strike", CardType.Attack, 1, A),
    CardId.UNMOVABLE : ("Unmovable", CardType.Power, 2, S),
    CardId.UNRELENTING : ("Unrelenting", CardType.Attack, 2, A),
    CardId.UPPERCUT : ("Uppercut", CardType.Attack, 2, A),
    CardId.VICIOUS : ("Vicious", CardType.Power, 1, S),
    CardId.WHIRLWIND : ("Whirlwind", CardType.Attack, "X", ALL),
}

TOKEN_CARDS = {CardId.GIANT_ROCK : ("Giant Rock", CardType.Attack, 1, A),      # made by Primal Force
               CardId.SHIV : ("Shiv", CardType.Attack, 0, A),                 # the Silent's Blade Dance, Cloak and Dagger, Cunning Potion...
               CardId.LUMINESCE : ("Luminesce", CardType.Skill, 0, S),
               CardId.SOVEREIGN_BLADE : ("Sovereign Blade", CardType.Attack, 2, A),
               CardId.MINION_STRIKE : ("Minion Strike", CardType.Attack, 0, A),
               CardId.MINION_DIVE_BOMB : ("Minion Dive Bomb", CardType.Attack, 0, A),
               CardId.MINION_SACRIFICE : ("Minion Sacrifice", CardType.Skill, 0, S),
               CardId.SOUL : ("Soul", CardType.Skill, 0, S),
               CardId.SWEEPING_GAZE : ("Sweeping Gaze", CardType.Attack, 0, RAND),
               CardId.FUEL : ("Fuel", CardType.Skill, 0, S)}      # Charge's transform      # the Regent's Forge makes it          # Radiant Pearl: Retain. Gain 2 Energy (3 upgraded). Exhaust.

# event cards (CardRarity.Event): never generated in combat; listed so tests and transforms can build them
EVENT_CARDS = {
    CardId.BYRD_SWOOP : ("Swoop", CardType.Attack, 0, A), CardId.PECK : ("Peck", CardType.Attack, 1, A),
    CardId.EXTERMINATE : ("Exterminate", CardType.Attack, 1, ALL), CardId.SQUASH : ("Squash", CardType.Attack, 1, A),
    CardId.ENLIGHTENMENT : ("Enlightenment", CardType.Skill, 0, S), CardId.METAMORPHOSIS : ("Metamorphosis", CardType.Skill, 2, S),
    CardId.TORIC_TOUGHNESS : ("Toric Toughness", CardType.Skill, 2, S),
    CardId.FEEDING_FRENZY : ("Feeding Frenzy", CardType.Skill, 0, S),
    CardId.MAD_SCIENCE : ("Mad Science", CardType.Attack, 1, A),
    CardId.CLASH : ("Clash", CardType.Attack, 0, A), CardId.DUAL_WIELD : ("Dual Wield", CardType.Skill, 1, S), CardId.ENTRENCH : ("Entrench", CardType.Skill, 2, S),
    CardId.CALTROPS : ("Caltrops", CardType.Power, 1, S), CardId.DISTRACTION : ("Distraction", CardType.Skill, 1, S),
    CardId.OUTMANEUVER : ("Outmaneuver", CardType.Skill, 1, S), CardId.HELLO_WORLD : ("Hello World", CardType.Power, 1, S),
    CardId.REBOUND : ("Rebound", CardType.Attack, 1, A), CardId.RIP_AND_TEAR : ("Rip and Tear", CardType.Attack, 1, RAND),
    CardId.STACK : ("Stack", CardType.Skill, 1, S),
}

# colorless cards that card effects can add (Jack of All Trades, Toolbox): (name, type, cost, target). Multiplayer-only
# cards are left out; Splash is not modelled; Alchemize, Hand of Greed and Hidden Gem are never generated in combat.
COLORLESS_CARDS = {
    CardId.FINESSE : ("Finesse", CardType.Skill, 0, S), CardId.FLASH_OF_STEEL : ("Flash of Steel", CardType.Attack, 0, A),
    CardId.ULTIMATE_STRIKE : ("Ultimate Strike", CardType.Attack, 1, A), CardId.ULTIMATE_DEFEND : ("Ultimate Defend", CardType.Skill, 1, S),
    CardId.PRODUCTION : ("Production", CardType.Skill, 0, S), CardId.MASTER_OF_STRATEGY : ("Master of Strategy", CardType.Skill, 0, S),
    CardId.DRAMATIC_ENTRANCE : ("Dramatic Entrance", CardType.Attack, 0, ALL), CardId.SHOCKWAVE : ("Shockwave", CardType.Skill, 2, ALL),
    CardId.PROWESS : ("Prowess", CardType.Power, 1, S), CardId.IMPATIENCE : ("Impatience", CardType.Skill, 0, S),
    CardId.RESTLESSNESS : ("Restlessness", CardType.Skill, 0, S), CardId.SCRAWL : ("Scrawl", CardType.Skill, 1, S),
    CardId.FISTICUFFS : ("Fisticuffs", CardType.Attack, 1, A), CardId.MIND_BLAST : ("Mind Blast", CardType.Attack, 1, A),
    CardId.GOLD_AXE : ("Gold Axe", CardType.Attack, 1, A), CardId.REND : ("Rend", CardType.Attack, 1, A),
    CardId.OMNISLICE : ("Omnislice", CardType.Attack, 0, A), CardId.VOLLEY : ("Volley", CardType.Attack, "X", RAND),
    CardId.ETERNAL_ARMOR : ("Eternal Armor", CardType.Power, 3, S), CardId.HAND_OF_GREED : ("Hand of Greed", CardType.Attack, 2, A),
    CardId.PURITY : ("Purity", CardType.Skill, 0, S),
    CardId.SECRET_TECHNIQUE : ("Secret Technique", CardType.Skill, 0, S), CardId.SECRET_WEAPON : ("Secret Weapon", CardType.Skill, 0, S),
    CardId.SEEKER_STRIKE : ("Seeker Strike", CardType.Attack, 1, A), CardId.THINKING_AHEAD : ("Thinking Ahead", CardType.Skill, 0, S),
    CardId.EQUILIBRIUM : ("Equilibrium", CardType.Skill, 2, S), CardId.SALVO : ("Salvo", CardType.Attack, 1, A),
    CardId.PANIC_BUTTON : ("Panic Button", CardType.Skill, 0, S), CardId.PROLONG : ("Prolong", CardType.Skill, 0, S),
    CardId.FASTEN : ("Fasten", CardType.Power, 1, S), CardId.PREP_TIME : ("Prep Time", CardType.Power, 1, S),
    CardId.DARK_SHACKLES : ("Dark Shackles", CardType.Skill, 0, A), CardId.AUTOMATION : ("Automation", CardType.Power, 1, S),
    CardId.PANACHE : ("Panache", CardType.Power, 0, S), CardId.ROLLING_BOULDER : ("Rolling Boulder", CardType.Power, 3, S),
    CardId.THE_BOMB : ("The Bomb", CardType.Skill, 2, S), CardId.THE_GAMBIT : ("The Gambit", CardType.Skill, 0, S),
    CardId.MAYHEM : ("Mayhem", CardType.Power, 2, S), CardId.NOSTALGIA : ("Nostalgia", CardType.Power, 1, S),
    CardId.BOLAS : ("Bolas", CardType.Attack, 0, A), CardId.THRUMMING_HATCHET : ("Thrumming Hatchet", CardType.Attack, 1, A),
    CardId.JACKPOT : ("Jackpot", CardType.Attack, 3, A), CardId.CALAMITY : ("Calamity", CardType.Power, 3, S),
    CardId.JACK_OF_ALL_TRADES : ("Jack of All Trades", CardType.Skill, 0, S), CardId.CATASTROPHE : ("Catastrophe", CardType.Skill, 2, S),
    CardId.BEAT_DOWN : ("Beat Down", CardType.Skill, 3, RAND), CardId.ANOINTED : ("Anointed", CardType.Skill, 1, S),
    CardId.DISCOVERY : ("Discovery", CardType.Skill, 1, S), CardId.SPLASH : ("Splash", CardType.Skill, 1, S), CardId.ENTROPY : ("Entropy", CardType.Power, 1, S),
    CardId.HIDDEN_GEM : ("Hidden Gem", CardType.Skill, 1, S), CardId.ALCHEMIZE : ("Alchemize", CardType.Skill, 1, S),
    CardId.STRATAGEM : ("Stratagem", CardType.Power, 1, S),
}

# the Silent's cards (SilentCardPool), Basic ones included: the reward pool is the Common / Uncommon / Rare ones (rewards.cards.card_pool)
SILENT_CARDS = {
    CardId.STRIKE_SILENT : ("Strike", CardType.Attack, 1, A), CardId.DEFEND_SILENT : ("Defend", CardType.Skill, 1, S),
    CardId.NEUTRALIZE : ("Neutralize", CardType.Attack, 0, A), CardId.SURVIVOR : ("Survivor", CardType.Skill, 1, S),
    # Common
    CardId.ANTICIPATE : ("Anticipate", CardType.Skill, 0, S),
    CardId.BACKFLIP : ("Backflip", CardType.Skill, 1, S),
    CardId.BLADE_DANCE : ("Blade Dance", CardType.Skill, 1, S),
    CardId.CLOAK_AND_DAGGER : ("Cloak and Dagger", CardType.Skill, 1, S),
    CardId.DAGGER_SPRAY : ("Dagger Spray", CardType.Attack, 1, ALL),
    CardId.DAGGER_THROW : ("Dagger Throw", CardType.Attack, 1, A),
    CardId.DEADLY_POISON : ("Deadly Poison", CardType.Skill, 1, A),
    CardId.DEFLECT : ("Deflect", CardType.Skill, 0, S),
    CardId.DODGE_AND_ROLL : ("Dodge and Roll", CardType.Skill, 1, S),
    CardId.FLICK_FLACK : ("Flick-Flack", CardType.Attack, 1, ALL),
    CardId.LEADING_STRIKE : ("Leading Strike", CardType.Attack, 1, A),
    CardId.PIERCING_WAIL : ("Piercing Wail", CardType.Skill, 1, ALL),
    CardId.POISONED_STAB : ("Poisoned Stab", CardType.Attack, 1, A),
    CardId.PREDATOR : ("Predator", CardType.Attack, 2, A),
    CardId.PREPARED : ("Prepared", CardType.Skill, 0, S),
    CardId.RICOCHET : ("Ricochet", CardType.Attack, 2, RAND),
    CardId.SLICE : ("Slice", CardType.Attack, 0, A),
    CardId.SNAKEBITE : ("Snakebite", CardType.Skill, 2, A),
    CardId.SUCKER_PUNCH : ("Sucker Punch", CardType.Attack, 1, A),
    CardId.UNTOUCHABLE : ("Untouchable", CardType.Skill, 2, S),
    CardId.ACCELERANT : ("Accelerant", CardType.Power, 1, S),
    CardId.ACCURACY : ("Accuracy", CardType.Power, 1, S),
    CardId.ACROBATICS : ("Acrobatics", CardType.Skill, 1, S),
    CardId.BACKSTAB : ("Backstab", CardType.Attack, 0, A),
    CardId.BLUR : ("Blur", CardType.Skill, 1, S),
    CardId.BOUNCING_FLASK : ("Bouncing Flask", CardType.Skill, 2, RAND),
    CardId.BUBBLE_BUBBLE : ("Bubble Bubble", CardType.Skill, 1, A),
    CardId.CALCULATED_GAMBLE : ("Calculated Gamble", CardType.Skill, 0, S),
    CardId.DASH : ("Dash", CardType.Attack, 2, A),
    CardId.ECHOING_SLASH : ("Echoing Slash", CardType.Attack, 1, ALL),
    CardId.ESCAPE_PLAN : ("Escape Plan", CardType.Skill, 0, S),
    CardId.EXPERTISE : ("Expertise", CardType.Skill, 1, S),
    CardId.EXPOSE : ("Expose", CardType.Skill, 0, A),
    CardId.FINISHER : ("Finisher", CardType.Attack, 1, A),
    CardId.FLECHETTES : ("Flechettes", CardType.Attack, 1, A),
    CardId.SIDESTEP : ("Sidestep", CardType.Skill, 0, S),
    CardId.FOOTWORK : ("Footwork", CardType.Power, 1, S),
    CardId.HAND_TRICK : ("Hand Trick", CardType.Skill, 1, S),
    CardId.HAZE : ("Haze", CardType.Skill, 2, ALL),
    CardId.HIDDEN_DAGGERS : ("Hidden Daggers", CardType.Skill, 0, S),
    CardId.INFINITE_BLADES : ("Infinite Blades", CardType.Power, 1, S),
    CardId.LEG_SWEEP : ("Leg Sweep", CardType.Skill, 2, A),
    CardId.MEMENTO_MORI : ("Memento Mori", CardType.Attack, 1, A),
    CardId.MIRAGE : ("Mirage", CardType.Skill, 1, S),
    CardId.NOXIOUS_FUMES : ("Noxious Fumes", CardType.Power, 1, S),
    CardId.PHANTOM_BLADES : ("Phantom Blades", CardType.Power, 1, S),
    CardId.PINPOINT : ("Pinpoint", CardType.Attack, 3, A),
    CardId.POUNCE : ("Pounce", CardType.Attack, 2, A),
    CardId.PRECISE_CUT : ("Precise Cut", CardType.Attack, 0, A),
    CardId.REFLEX : ("Reflex", CardType.Skill, 3, S),
    CardId.SKEWER : ("Skewer", CardType.Attack, 'X', A),
    CardId.SPEEDSTER : ("Speedster", CardType.Power, 2, S),
    CardId.STRANGLE : ("Strangle", CardType.Attack, 1, A),
    CardId.TACTICIAN : ("Tactician", CardType.Skill, 3, S),
    CardId.UP_MY_SLEEVE : ("Up My Sleeve", CardType.Skill, 2, S),
    CardId.ABRASIVE : ("Abrasive", CardType.Power, 3, S),
    CardId.ADRENALINE : ("Adrenaline", CardType.Skill, 0, S),
    CardId.AFTERIMAGE : ("Afterimage", CardType.Power, 1, S),
    CardId.ASSASSINATE : ("Assassinate", CardType.Attack, 0, A),
    CardId.BLADE_OF_INK : ("Blade of Ink", CardType.Skill, 1, S),
    CardId.BULLET_TIME : ("Bullet Time", CardType.Skill, 3, S),
    CardId.BURST : ("Burst", CardType.Skill, 1, S),
    CardId.CORROSIVE_WAVE : ("Corrosive Wave", CardType.Skill, 1, S),
    CardId.ENVENOM : ("Envenom", CardType.Power, 2, S),
    CardId.FAN_OF_KNIVES : ("Fan of Knives", CardType.Power, 2, S),
    CardId.GRAND_FINALE : ("Grand Finale", CardType.Attack, 0, ALL),
    CardId.KNIFE_TRAP : ("Knife Trap", CardType.Skill, 2, A),
    CardId.MALAISE : ("Malaise", CardType.Skill, 'X', A),
    CardId.MASTER_PLANNER : ("Master Planner", CardType.Power, 2, S),
    CardId.MURDER : ("Murder", CardType.Attack, 3, A),
    CardId.NIGHTMARE : ("Nightmare", CardType.Skill, 3, S),
    CardId.OUTBREAK : ("Outbreak", CardType.Skill, 3, ALL),
    CardId.SERPENT_FORM : ("Serpent Form", CardType.Power, 3, S),
    CardId.SHADOW_STEP : ("Shadow Step", CardType.Skill, 1, S),
    CardId.SHADOWMELD : ("Shadowmeld", CardType.Skill, 1, S),
    CardId.STORM_OF_STEEL : ("Storm of Steel", CardType.Skill, 1, S),
    CardId.THE_HUNT : ("The Hunt", CardType.Attack, 1, A),
    CardId.TOOLS_OF_THE_TRADE : ("Tools of the Trade", CardType.Power, 1, S),
    CardId.TRACKING : ("Tracking", CardType.Power, 2, S),
    CardId.WELL_LAID_PLANS : ("Well-Laid Plans", CardType.Power, 2, S),
}

# Ancient cards the sim could not read from the decompiled source (name, type, cost, target)
ANCIENT_CARDS = {
    CardId.ABUNDANCE : ("Abundance", CardType.Skill, 1, S), CardId.APOTHEOSIS : ("Apotheosis", CardType.Skill, 2, S),
    CardId.APPARITION : ("Apparition", CardType.Skill, 1, S), CardId.BRIGHTEST_FLAME : ("Brightest Flame", CardType.Skill, 0, S),
    CardId.MAUL : ("Maul", CardType.Attack, 1, A), CardId.RELAX : ("Relax", CardType.Skill, 3, S),
    CardId.WHISTLE : ("Whistle", CardType.Attack, 2, A), CardId.WISH : ("Wish", CardType.Skill, 0, S),
    CardId.SUPPRESS : ("Suppress", CardType.Attack, 0, A), CardId.WRAITH_FORM : ("Wraith Form", CardType.Power, 3, S),
    CardId.METEOR_SHOWER : ("Meteor Shower", CardType.Attack, 0, ALL), CardId.THE_SEALED_THRONE : ("The Sealed Throne", CardType.Power, 1, S),
    CardId.FORBIDDEN_GRIMOIRE : ("Forbidden Grimoire", CardType.Power, 2, S),
    CardId.PROTECTOR : ("Protector", CardType.Attack, 1, A),
    CardId.BIASED_COGNITION : ("Biased Cognition", CardType.Power, 1, S),
    CardId.QUADCAST : ("Quadcast", CardType.Skill, 1, S),
}

# the Regent's cards (RegentCardPool), Basic ones included; the Star cost of each is in constants.STAR_COST
REGENT_CARDS = {
    CardId.STRIKE_REGENT : ("Strike", CardType.Attack, 1, A), CardId.DEFEND_REGENT : ("Defend", CardType.Skill, 1, S),
    CardId.FALLING_STAR : ("Falling Star", CardType.Attack, 0, A), CardId.VENERATE : ("Venerate", CardType.Skill, 1, S),
    # Common
    CardId.ASTRAL_PULSE : ("Astral Pulse", CardType.Attack, 0, ALL),
    CardId.BEGONE : ("Begone!", CardType.Skill, 1, S),
    CardId.CELESTIAL_MIGHT : ("Celestial Might", CardType.Attack, 2, A),
    CardId.CLOAK_OF_STARS : ("Cloak of Stars", CardType.Skill, 0, S),
    CardId.COLLISION_COURSE : ("Collision Course", CardType.Attack, 0, A),
    CardId.COSMIC_INDIFFERENCE : ("Cosmic Indifference", CardType.Skill, 1, S),
    CardId.CRESCENT_SPEAR : ("Crescent Spear", CardType.Attack, 1, A),
    CardId.CRUSH_UNDER : ("Crush Under", CardType.Attack, 1, ALL),
    CardId.GATHER_LIGHT : ("Gather Light", CardType.Skill, 1, S),
    CardId.GLITTERSTREAM : ("Glitterstream", CardType.Skill, 2, S),
    CardId.GLOW : ("Glow", CardType.Skill, 1, S),
    CardId.GUIDING_STAR : ("Guiding Star", CardType.Attack, 1, A),
    CardId.HIDDEN_CACHE : ("Hidden Cache", CardType.Skill, 1, S),
    CardId.KNOW_THY_PLACE : ("Know Thy Place", CardType.Skill, 0, A),
    CardId.PATTER : ("Patter", CardType.Skill, 1, S),
    CardId.PHOTON_CUT : ("Photon Cut", CardType.Attack, 1, A),
    CardId.REFINE_BLADE : ("Refine Blade", CardType.Skill, 1, S),
    CardId.SOLAR_STRIKE : ("Solar Strike", CardType.Attack, 1, A),
    CardId.SPOILS_OF_BATTLE : ("Spoils of Battle", CardType.Skill, 1, S),
    CardId.WROUGHT_IN_WAR : ("Wrought in War", CardType.Attack, 1, A),
    # Uncommon (Constellation, Largesse and Plot are multiplayer only)
    CardId.ALIGNMENT : ("Alignment", CardType.Skill, 0, S),
    CardId.BLACK_HOLE : ("Black Hole", CardType.Power, 1, S),
    CardId.BULWARK : ("Bulwark", CardType.Skill, 2, S),
    CardId.CHARGE : ("Charge", CardType.Skill, 1, S),
    CardId.CHILD_OF_THE_STARS : ("Child of the Stars", CardType.Power, 1, S),
    CardId.CONQUEROR : ("Conqueror", CardType.Skill, 1, A),
    CardId.CONVERGENCE : ("Convergence", CardType.Skill, 1, S),
    CardId.DEVASTATE : ("Devastate", CardType.Attack, 1, A),
    CardId.FURNACE : ("Furnace", CardType.Power, 1, S),
    CardId.GAMMA_BLAST : ("Gamma Blast", CardType.Attack, 0, A),
    CardId.GLIMMER : ("Glimmer", CardType.Skill, 1, S),
    CardId.HEGEMONY : ("Hegemony", CardType.Attack, 2, A),
    CardId.KINGLY_KICK : ("Kingly Kick", CardType.Attack, 4, A),
    CardId.KINGLY_PUNCH : ("Kingly Punch", CardType.Attack, 1, A),
    CardId.LUNAR_BLAST : ("Lunar Blast", CardType.Attack, 0, A),
    CardId.MANIFEST_AUTHORITY : ("Manifest Authority", CardType.Skill, 1, S),
    CardId.MONOLOGUE : ("Monologue", CardType.Skill, 0, S),
    CardId.ORBIT : ("Orbit", CardType.Power, 2, S),
    CardId.PALE_BLUE_DOT : ("Pale Blue Dot", CardType.Power, 1, S),
    CardId.PARRY : ("Parry", CardType.Power, 1, S),
    CardId.PARTICLE_WALL : ("Particle Wall", CardType.Skill, 0, S),
    CardId.PILLAR_OF_CREATION : ("Pillar of Creation", CardType.Power, 1, S),
    CardId.PROPHESIZE : ("Prophesize", CardType.Skill, 2, S),
    CardId.QUASAR : ("Quasar", CardType.Skill, 0, S),
    CardId.RADIATE : ("Radiate", CardType.Attack, 0, ALL),
    CardId.REFLECT : ("Reflect", CardType.Skill, 1, S),
    CardId.RESONANCE : ("Resonance", CardType.Skill, 1, ALL),
    CardId.ROYAL_GAMBLE : ("Royal Gamble", CardType.Skill, 0, S),
    CardId.SHINING_STRIKE : ("Shining Strike", CardType.Attack, 1, A),
    CardId.SPECTRUM_SHIFT : ("Spectrum Shift", CardType.Power, 2, S),
    CardId.STARDUST : ("Stardust", CardType.Attack, 0, RAND),
    CardId.SUMMON_FORTH : ("Summon Forth", CardType.Skill, 1, S),
    CardId.SUPERMASSIVE : ("Supermassive", CardType.Attack, 1, A),
    CardId.TERRAFORMING : ("Terraforming", CardType.Skill, 1, S),
    CardId.KNOCKOUT_BLOW : ("Knockout Blow", CardType.Attack, 3, A),
    # Rare (Hammer Time and Tutor are multiplayer only)
    CardId.ARSENAL : ("Arsenal", CardType.Power, 1, S),
    CardId.BEAT_INTO_SHAPE : ("Beat into Shape", CardType.Attack, 1, A),
    CardId.BIG_BANG : ("Big Bang", CardType.Skill, 0, S),
    CardId.BOMBARDMENT : ("Bombardment", CardType.Attack, 3, A),
    CardId.BUNDLE_OF_JOY : ("Bundle of Joy", CardType.Skill, 1, S),
    CardId.COMET : ("Comet", CardType.Attack, 0, A),
    CardId.CRASH_LANDING : ("Crash Landing", CardType.Attack, 1, ALL),
    CardId.DECISIONS_DECISIONS : ("Decisions, Decisions", CardType.Skill, 0, S),
    CardId.DYING_STAR : ("Dying Star", CardType.Attack, 1, ALL),
    CardId.FOREGONE_CONCLUSION : ("Foregone Conclusion", CardType.Skill, 1, S),
    CardId.GENESIS : ("Genesis", CardType.Power, 2, S),
    CardId.GUARDS : ("Guards", CardType.Skill, 2, S),
    CardId.HEAVENLY_DRILL : ("Heavenly Drill", CardType.Attack, "X", A),
    CardId.HEIRLOOM_HAMMER : ("Heirloom Hammer", CardType.Attack, 2, A),
    CardId.I_AM_INVINCIBLE : ("I Am Invincible", CardType.Skill, 1, S),
    CardId.MAKE_IT_SO : ("Make It So", CardType.Attack, 0, A),
    CardId.MONARCHS_GAZE : ("Monarch's Gaze", CardType.Power, 2, S),
    CardId.NEUTRON_AEGIS : ("Neutron Aegis", CardType.Power, 1, S),
    CardId.ROYALTIES : ("Royalties", CardType.Power, 1, S),
    CardId.SEEKING_EDGE : ("Seeking Edge", CardType.Power, 1, S),
    CardId.SEVEN_STARS : ("Seven Stars", CardType.Attack, 2, ALL),
    CardId.SWORD_SAGE : ("Sword Sage", CardType.Power, 2, S),
    CardId.THE_SMITH : ("The Smith", CardType.Skill, 1, S),
    CardId.TYRANNY : ("Tyranny", CardType.Power, 1, S),
    CardId.VOID_FORM : ("Void Form", CardType.Power, 3, S),
}

# the Necrobinder's cards (NecrobinderCardPool), Basic ones included
NECROBINDER_CARDS = {
    CardId.AFTERLIFE : ("Afterlife", CardType.Skill, 1, S),
    CardId.BANSHEES_CRY : ("Banshee's Cry", CardType.Attack, 9, ALL),
    CardId.BLIGHT_STRIKE : ("Blight Strike", CardType.Attack, 1, A),
    CardId.BODYGUARD : ("Bodyguard", CardType.Skill, 1, S),
    CardId.BONE_SHARDS : ("Bone Shards", CardType.Attack, 1, ALL),
    CardId.BORROWED_TIME : ("Borrowed Time", CardType.Skill, 1, S),
    CardId.BURY : ("Bury", CardType.Attack, 4, A),
    CardId.CALCIFY : ("Calcify", CardType.Power, 1, S),
    CardId.CALL_OF_THE_VOID : ("Call Of The Void", CardType.Power, 1, S),
    CardId.CAPTURE_SPIRIT : ("Capture Spirit", CardType.Skill, 1, A),
    CardId.CLEANSE : ("Cleanse", CardType.Skill, 1, S),
    CardId.COUNTDOWN : ("Countdown", CardType.Power, 1, S),
    CardId.DANSE_MACABRE : ("Danse Macabre", CardType.Power, 1, S),
    CardId.DEATH_MARCH : ("Death March", CardType.Attack, 1, A),
    CardId.DEATHBRINGER : ("Deathbringer", CardType.Skill, 2, ALL),
    CardId.DEATHS_DOOR : ("Death's Door", CardType.Skill, 1, S),
    CardId.DEBILITATE : ("Debilitate", CardType.Attack, 1, A),
    CardId.DEFEND_NECROBINDER : ("Defend", CardType.Skill, 1, S),
    CardId.DEFILE : ("Defile", CardType.Attack, 1, A),
    CardId.DEFY : ("Defy", CardType.Skill, 1, A),
    CardId.DELAY : ("Delay", CardType.Skill, 2, S),
    CardId.DEMESNE : ("Demesne", CardType.Power, 3, S),
    CardId.DEVOUR_LIFE : ("Devour Life", CardType.Power, 1, S),
    CardId.DIRGE : ("Dirge", CardType.Skill, "X", S),
    CardId.DRAIN_POWER : ("Drain Power", CardType.Attack, 1, A),
    CardId.DREDGE : ("Dredge", CardType.Skill, 1, S),
    CardId.EIDOLON : ("Eidolon", CardType.Skill, 2, S),
    CardId.END_OF_DAYS : ("End Of Days", CardType.Skill, 3, ALL),
    CardId.ENFEEBLING_TOUCH : ("Enfeebling Touch", CardType.Skill, 1, A),
    CardId.ERADICATE : ("Eradicate", CardType.Attack, "X", A),
    CardId.FEAR : ("Fear", CardType.Attack, 1, A),
    CardId.FETCH : ("Fetch", CardType.Attack, 0, A),
    CardId.FLATTEN : ("Flatten", CardType.Attack, 2, A),
    CardId.FRIENDSHIP : ("Friendship", CardType.Power, 1, S),
    CardId.GRAVE_WARDEN : ("Grave Warden", CardType.Skill, 1, S),
    CardId.GRAVEBLAST : ("Graveblast", CardType.Attack, 1, A),
    CardId.HANG : ("Hang", CardType.Attack, 1, A),
    CardId.HAUNT : ("Haunt", CardType.Power, 1, S),
    CardId.HIGH_FIVE : ("High Five", CardType.Attack, 2, ALL),
    CardId.INVOKE : ("Invoke", CardType.Skill, 1, S),
    CardId.LETHALITY : ("Lethality", CardType.Power, 1, S),
    CardId.MELANCHOLY : ("Melancholy", CardType.Skill, 3, S),
    CardId.MISERY : ("Misery", CardType.Attack, 0, A),
    CardId.NECRO_MASTERY : ("Necro Mastery", CardType.Power, 2, S),
    CardId.NEGATIVE_PULSE : ("Negative Pulse", CardType.Skill, 1, ALL),
    CardId.NEUROSURGE : ("Neurosurge", CardType.Power, 0, S),
    CardId.NO_ESCAPE : ("No Escape", CardType.Skill, 1, A),
    CardId.OBLIVION : ("Oblivion", CardType.Skill, 0, A),
    CardId.PAGESTORM : ("Pagestorm", CardType.Power, 1, S),
    CardId.PARSE : ("Parse", CardType.Skill, 1, S),
    CardId.POKE : ("Poke", CardType.Attack, 0, A),
    CardId.PULL_AGGRO : ("Pull Aggro", CardType.Skill, 2, S),
    CardId.PULL_FROM_BELOW : ("Pull From Below", CardType.Attack, 1, A),
    CardId.PUTREFY : ("Putrefy", CardType.Skill, 1, A),
    CardId.RATTLE : ("Rattle", CardType.Attack, 1, A),
    CardId.REANIMATE : ("Reanimate", CardType.Skill, 3, S),
    CardId.REAP : ("Reap", CardType.Attack, 3, A),
    CardId.REAPER_FORM : ("Reaper Form", CardType.Power, 3, S),
    CardId.REAVE : ("Reave", CardType.Attack, 1, A),
    CardId.RIGHT_HAND_HAND : ("Right Hand Hand", CardType.Attack, 0, A),
    CardId.SACRIFICE : ("Sacrifice", CardType.Skill, 1, S),
    CardId.SCOURGE : ("Scourge", CardType.Skill, 1, A),
    CardId.SCULPTING_STRIKE : ("Sculpting Strike", CardType.Attack, 1, A),
    CardId.SEANCE : ("Seance", CardType.Skill, 1, S),
    CardId.SENTRY_MODE : ("Sentry Mode", CardType.Power, 2, S),
    CardId.SEVERANCE : ("Severance", CardType.Attack, 2, A),
    CardId.SHARED_FATE : ("Shared Fate", CardType.Skill, 0, A),
    CardId.SHROUD : ("Shroud", CardType.Power, 1, S),
    CardId.SIC_EM : ("Sic 'Em", CardType.Attack, 1, A),
    CardId.SLEIGHT_OF_FLESH : ("Sleight Of Flesh", CardType.Power, 2, S),
    CardId.SNAP : ("Snap", CardType.Attack, 1, A),
    CardId.SOUL_STORM : ("Soul Storm", CardType.Attack, 1, A),
    CardId.SOW : ("Sow", CardType.Attack, 1, ALL),
    CardId.SPIRIT_OF_ASH : ("Spirit Of Ash", CardType.Power, 1, S),
    CardId.SPUR : ("Spur", CardType.Skill, 1, S),
    CardId.SQUEEZE : ("Squeeze", CardType.Attack, 3, A),
    CardId.STRIKE_NECROBINDER : ("Strike", CardType.Attack, 1, A),
    CardId.THE_SCYTHE : ("The Scythe", CardType.Attack, 2, A),
    CardId.TIMES_UP : ("Time's Up", CardType.Attack, 2, A),
    CardId.TRANSFIGURE : ("Transfigure", CardType.Skill, 1, S),
    CardId.UNDEATH : ("Undeath", CardType.Skill, 0, S),
    CardId.UNLEASH : ("Unleash", CardType.Attack, 1, A),
    CardId.VEILPIERCER : ("Veilpiercer", CardType.Attack, 1, A),
    CardId.WISP : ("Wisp", CardType.Skill, 0, S),
}

# the Defect's cards (DefectCardPool), Basic ones included; the multiplayer-only ones (Energy Surge, Hibernate, Ignition, Imitation Learning, One for All) are left out
DEFECT_CARDS = {
    CardId.ADAPTIVE_STRIKE : ("Adaptive Strike", CardType.Attack, 2, A),
    CardId.ALL_FOR_ONE : ("All for One", CardType.Attack, 2, A),
    CardId.BALL_LIGHTNING : ("Ball Lightning", CardType.Attack, 1, A),
    CardId.BARRAGE : ("Barrage", CardType.Attack, 1, A),
    CardId.BEAM_CELL : ("Beam Cell", CardType.Attack, 0, A),
    CardId.BOOST_AWAY : ("Boost Away", CardType.Skill, 0, S),
    CardId.BOOT_SEQUENCE : ("Boot Sequence", CardType.Skill, 0, S),
    CardId.BUFFER : ("Buffer", CardType.Power, 2, S),
    CardId.BULK_UP : ("Bulk Up", CardType.Power, 2, S),
    CardId.CAPACITOR : ("Capacitor", CardType.Power, 1, S),
    CardId.CHAOS : ("Chaos", CardType.Skill, 1, S),
    CardId.CHARGE_BATTERY : ("Charge Battery", CardType.Skill, 1, S),
    CardId.CHILL : ("Chill", CardType.Skill, 0, S),
    CardId.CLAW : ("Claw", CardType.Attack, 0, A),
    CardId.COLD_SNAP : ("Cold Snap", CardType.Attack, 1, A),
    CardId.COMPACT : ("Compact", CardType.Skill, 1, S),
    CardId.COMPILE_DRIVER : ("Compile Driver", CardType.Attack, 1, A),
    CardId.CONSUMING_SHADOW : ("Consuming Shadow", CardType.Power, 2, S),
    CardId.COOLANT : ("Coolant", CardType.Power, 1, S),
    CardId.COOLHEADED : ("Coolheaded", CardType.Skill, 1, S),
    CardId.CREATIVE_AI : ("Creative AI", CardType.Power, 3, S),
    CardId.DARKNESS : ("Darkness", CardType.Skill, 1, S),
    CardId.DEFEND_DEFECT : ("Defend", CardType.Skill, 1, S),
    CardId.DEFRAGMENT : ("Defragment", CardType.Power, 1, S),
    CardId.DOUBLE_ENERGY : ("Double Energy", CardType.Skill, 1, S),
    CardId.DUALCAST : ("Dualcast", CardType.Skill, 1, S),
    CardId.ECHO_FORM : ("Echo Form", CardType.Power, 3, S),
    CardId.FERAL : ("Feral", CardType.Power, 2, S),
    CardId.FIGHT_THROUGH : ("Fight Through", CardType.Skill, 1, S),
    CardId.FLAK_CANNON : ("Flak Cannon", CardType.Attack, 2, RAND),
    CardId.FOCUSED_STRIKE : ("Focused Strike", CardType.Attack, 1, A),
    CardId.FTL : ("FTL", CardType.Attack, 0, A),
    CardId.FUSION : ("Fusion", CardType.Skill, 1, S),
    CardId.GENETIC_ALGORITHM : ("Genetic Algorithm", CardType.Skill, 1, S),
    CardId.GLACIER : ("Glacier", CardType.Skill, 2, S),
    CardId.GLASSWORK : ("Glasswork", CardType.Skill, 1, S),
    CardId.GO_FOR_THE_EYES : ("Go for the Eyes", CardType.Attack, 0, A),
    CardId.GUNK_UP : ("Gunk Up", CardType.Attack, 1, A),
    CardId.HAILSTORM : ("Hailstorm", CardType.Power, 1, S),
    CardId.HELIX_DRILL : ("Helix Drill", CardType.Attack, 0, A),
    CardId.HOLOGRAM : ("Hologram", CardType.Skill, 1, S),
    CardId.HOTFIX : ("Hotfix", CardType.Skill, 0, S),
    CardId.HYPERBEAM : ("Hyperbeam", CardType.Attack, 2, ALL),
    CardId.ICE_LANCE : ("Ice Lance", CardType.Attack, 3, A),
    CardId.ITERATION : ("Iteration", CardType.Power, 1, S),
    CardId.LEAP : ("Leap", CardType.Skill, 1, S),
    CardId.LIGHTNING_ROD : ("Lightning Rod", CardType.Skill, 1, S),
    CardId.LOOP : ("Loop", CardType.Power, 1, S),
    CardId.MACHINE_LEARNING : ("Machine Learning", CardType.Power, 1, S),
    CardId.METEOR_STRIKE : ("Meteor Strike", CardType.Attack, 5, A),
    CardId.MODDED : ("Modded", CardType.Skill, 0, S),
    CardId.MOMENTUM_STRIKE : ("Momentum Strike", CardType.Attack, 1, A),
    CardId.MULTI_CAST : ("Multi-Cast", CardType.Skill, "X", S),
    CardId.NULL : ("Null", CardType.Attack, 2, A),
    CardId.OVERCLOCK : ("Overclock", CardType.Skill, 0, S),
    CardId.RAINBOW : ("Rainbow", CardType.Skill, 2, S),
    CardId.REBOOT : ("Reboot", CardType.Skill, 0, S),
    CardId.REFRACT : ("Refract", CardType.Attack, 3, A),
    CardId.ROCKET_PUNCH : ("Rocket Punch", CardType.Attack, 2, A),
    CardId.SCAVENGE : ("Scavenge", CardType.Skill, 1, S),
    CardId.SCRAPE : ("Scrape", CardType.Attack, 1, A),
    CardId.SHADOW_SHIELD : ("Shadow Shield", CardType.Skill, 2, S),
    CardId.SHATTER : ("Shatter", CardType.Attack, 1, ALL),
    CardId.SIGNAL_BOOST : ("Signal Boost", CardType.Skill, 1, S),
    CardId.SKIM : ("Skim", CardType.Skill, 1, S),
    CardId.SMOKESTACK : ("Smokestack", CardType.Power, 1, S),
    CardId.SPINNER : ("Spinner", CardType.Power, 1, S),
    CardId.STORM : ("Storm", CardType.Power, 1, S),
    CardId.STRIKE_DEFECT : ("Strike", CardType.Attack, 1, A),
    CardId.SUBROUTINE : ("Subroutine", CardType.Power, 1, S),
    CardId.SUNDER : ("Sunder", CardType.Attack, 3, A),
    CardId.SUPERCRITICAL : ("Supercritical", CardType.Skill, 0, S),
    CardId.SWEEPING_BEAM : ("Sweeping Beam", CardType.Attack, 1, ALL),
    CardId.SYNCHRONIZE : ("Synchronize", CardType.Skill, 1, S),
    CardId.SYNTHESIS : ("Synthesis", CardType.Attack, 2, A),
    CardId.TEMPEST : ("Tempest", CardType.Skill, "X", S),
    CardId.TESLA_COIL : ("Tesla Coil", CardType.Attack, 0, A),
    CardId.THUNDER : ("Thunder", CardType.Power, 1, S),
    CardId.TRASH_TO_TREASURE : ("Trash to Treasure", CardType.Power, 1, S),
    CardId.TURBO : ("Turbo", CardType.Skill, 0, S),
    CardId.UPROAR : ("Uproar", CardType.Attack, 2, A),
    CardId.VOLTAIC : ("Voltaic", CardType.Skill, 3, S),
    CardId.WHITE_NOISE : ("White Noise", CardType.Skill, 1, S),
    CardId.ZAP : ("Zap", CardType.Skill, 1, S),
}

CHARACTER_CARDS = {"DEFECT": DEFECT_CARDS, "IRONCLAD": GENERATABLE_CARDS, "SILENT": SILENT_CARDS, "REGENT": REGENT_CARDS, "NECROBINDER": NECROBINDER_CARDS}      # each character's card table (its pool, Basic cards included for the Silent)

# what Jack of All Trades can make: Hand of Greed (and Alchemize and Hidden Gem) cannot be generated in combat, and it makes no Jack of All Trades
NOT_GENERATED_COLORLESS = frozenset({CardId.HAND_OF_GREED, CardId.HIDDEN_GEM, CardId.JACK_OF_ALL_TRADES, CardId.ALCHEMIZE})

JACK_POOL = [cid for cid in COLORLESS_CARDS if cid not in NOT_GENERATED_COLORLESS]

# what a card can be transformed into: generatable colorless cards (Jack of All Trades included), or generatable Ironclad cards
TRANSFORM_COLORLESS = [cid for cid in COLORLESS_CARDS if cid not in (CardId.HAND_OF_GREED, CardId.HIDDEN_GEM, CardId.ALCHEMIZE)]

def transform_options(card : Card) -> list[CardId]:
    """CardFactory.GetFilteredTransformationOptions: Common to Rare cards of the card's own pool (Neow's Fury is colorless), never the same card.
    Empty for Statuses, Curses and Quest cards, which cannot be transformed here."""
    if card.type in (CardType.Status, CardType.Curse, CardType.Quest):
        return []
    colorless = card.card_id in COLORLESS_CARDS or card.card_id == CardId.NEOWS_FURY or card.card_id in ANCIENT_CARDS
    if colorless:
        pool = TRANSFORM_COLORLESS
    else:
        pool = TRANSFORM_POOLS[CARD_POOL_OF.get(card.card_id, "IRONCLAD")]
    return [cid for cid in pool if cid != card.card_id]

class CardRarity(Enum):
    """CardRarity of the game. Basic / Ancient / Event / Token / Status / Curse cards are never in a card reward pool."""
    Basic = auto()
    Common = auto()
    Uncommon = auto()
    Rare = auto()
    Ancient = auto()
    Event = auto()
    Token = auto()
    Status = auto()
    Curse = auto()
    Quest = auto()

# The rarity of every card, read from the `CardRarity` of each class in the decompiled Models.Cards (test_card_rarity checks the
# table is complete). The true game rarity is stored: a policy that treats Bash like a Common does that itself.
_RARITY_NAMES = {
    CardRarity.Basic : (
        "STRIKE_IRONCLAD DEFEND_IRONCLAD BASH STRIKE_SILENT DEFEND_SILENT NEUTRALIZE SURVIVOR STRIKE_REGENT DEFEND_REGENT FALLING_STAR VENERATE"
        " BODYGUARD DEFEND_NECROBINDER STRIKE_NECROBINDER UNLEASH"
    ),
    CardRarity.Common : (
        "ASTRAL_PULSE BEGONE CELESTIAL_MIGHT CLOAK_OF_STARS COLLISION_COURSE COSMIC_INDIFFERENCE CRESCENT_SPEAR CRUSH_UNDER GATHER_LIGHT GLITTERSTREAM GLOW GUIDING_STAR "
        "HIDDEN_CACHE KNOW_THY_PLACE PATTER PHOTON_CUT REFINE_BLADE SOLAR_STRIKE SPOILS_OF_BATTLE WROUGHT_IN_WAR "
        "BLOOD_WALL PERFECTED_STRIKE BREAKTHROUGH SHRUG_IT_OFF POMMEL_STRIKE IRON_WAVE THUNDERCLAP TREMBLE ANGER BODY_SLAM TWIN_STRIKE "
        "MOLTEN_FIST SWORD_BOOMERANG CINDER TAUNT ARMAMENTS HEADBUTT TRUE_GRIT HAVOC SETUP_STRIKE "
        "ANTICIPATE BACKFLIP BLADE_DANCE CLOAK_AND_DAGGER DAGGER_SPRAY DAGGER_THROW DEADLY_POISON DEFLECT DODGE_AND_ROLL FLICK_FLACK LEADING_STRIKE PIERCING_WAIL POISONED_STAB PREDATOR PREPARED RICOCHET SLICE SNAKEBITE SUCKER_PUNCH UNTOUCHABLE"
        " AFTERLIFE BLIGHT_STRIKE DEFILE DEFY DRAIN_POWER FEAR FLATTEN GRAVE_WARDEN GRAVEBLAST INVOKE NEGATIVE_PULSE POKE PULL_AGGRO REAP REAVE SCOURGE SCULPTING_STRIKE SNAP SOW WISP"
    ),
    CardRarity.Uncommon : (
        "KNOCKOUT_BLOW ALIGNMENT BLACK_HOLE BULWARK CHARGE CHILD_OF_THE_STARS CONQUEROR CONVERGENCE DEVASTATE FURNACE GAMMA_BLAST GLIMMER HEGEMONY KINGLY_KICK KINGLY_PUNCH LUNAR_BLAST MANIFEST_AUTHORITY MONOLOGUE ORBIT PALE_BLUE_DOT PARRY PARTICLE_WALL PILLAR_OF_CREATION PROPHESIZE QUASAR RADIATE REFLECT RESONANCE ROYAL_GAMBLE SHINING_STRIKE SPECTRUM_SHIFT STARDUST SUMMON_FORTH SUPERMASSIVE TERRAFORMING"
        " "
        "ACCELERANT ACCURACY ACROBATICS BACKSTAB BLUR BOUNCING_FLASK BUBBLE_BUBBLE CALCULATED_GAMBLE DASH ECHOING_SLASH ESCAPE_PLAN EXPERTISE EXPOSE FINISHER FLECHETTES SIDESTEP FOOTWORK HAND_TRICK HAZE HIDDEN_DAGGERS INFINITE_BLADES LEG_SWEEP MEMENTO_MORI MIRAGE NOXIOUS_FUMES PHANTOM_BLADES PINPOINT POUNCE PRECISE_CUT REFLEX SKEWER SPEEDSTER STRANGLE TACTICIAN UP_MY_SLEEVE "
        "INFLAME FIGHT_ME BLUDGEON UNRELENTING HEMOKINESIS DISMANTLE BULLY ASHEN_STRIKE UPPERCUT WHIRLWIND SPITE EVIL_EYE SECOND_WIND "
        "BLOODLETTING FINESSE FLASH_OF_STEEL ULTIMATE_STRIKE ULTIMATE_DEFEND PRODUCTION DRAMATIC_ENTRANCE SHOCKWAVE PROWESS IMPATIENCE "
        "RESTLESSNESS FISTICUFFS MIND_BLAST OMNISLICE VOLLEY PURITY SEEKER_STRIKE THINKING_AHEAD EQUILIBRIUM PANIC_BUTTON PROLONG FASTEN "
        "PREP_TIME DARK_SHACKLES AUTOMATION PANACHE THE_BOMB THRUMMING_HATCHET JACK_OF_ALL_TRADES CATASTROPHE DISCOVERY BURNING_PACT "
        "COLOSSUS FEEL_NO_PAIN FLAME_BARRIER JUGGLING RAGE RUPTURE STAMPEDE STONE_ARMOR VICIOUS BATTLE_TRANCE DRUM_OF_BATTLE EXPECT_A_FIGHT "
        "FORGOTTEN_RITUAL HOWL_FROM_BEYOND INFERNAL_BLADE INFERNO PILLAGE RAMPAGE STOMP SALVO CRUELTY STRATAGEM"
        " BONE_SHARDS BORROWED_TIME BURY CALCIFY CAPTURE_SPIRIT CLEANSE COUNTDOWN DANSE_MACABRE DEATH_MARCH DEATHBRINGER DEATHS_DOOR DEBILITATE DELAY DIRGE DREDGE ENFEEBLING_TOUCH FETCH FRIENDSHIP HAUNT HIGH_FIVE LETHALITY MELANCHOLY NO_ESCAPE PAGESTORM PARSE PULL_FROM_BELOW PUTREFY RATTLE RIGHT_HAND_HAND SEVERANCE SHROUD SIC_EM SLEIGHT_OF_FLESH SPUR VEILPIERCER"
    ),
    CardRarity.Rare : (
        "ARSENAL BEAT_INTO_SHAPE BIG_BANG BOMBARDMENT BUNDLE_OF_JOY COMET CRASH_LANDING DECISIONS_DECISIONS DYING_STAR FOREGONE_CONCLUSION GENESIS GUARDS HEAVENLY_DRILL HEIRLOOM_HAMMER I_AM_INVINCIBLE MAKE_IT_SO MONARCHS_GAZE NEUTRON_AEGIS ROYALTIES SEEKING_EDGE SEVEN_STARS SWORD_SAGE THE_SMITH TYRANNY VOID_FORM"
        " "
        "ABRASIVE ADRENALINE AFTERIMAGE ASSASSINATE BLADE_OF_INK BULLET_TIME BURST CORROSIVE_WAVE ENVENOM FAN_OF_KNIVES GRAND_FINALE KNIFE_TRAP MALAISE MASTER_PLANNER MURDER NIGHTMARE OUTBREAK SERPENT_FORM SHADOW_STEP SHADOWMELD STORM_OF_STEEL THE_HUNT TOOLS_OF_THE_TRADE TRACKING WELL_LAID_PLANS SPLASH "
        "CRIMSON_MANTLE IMPERVIOUS FEED AGGRESSION MASTER_OF_STRATEGY SCRAWL GOLD_AXE REND ETERNAL_ARMOR HAND_OF_GREED SECRET_TECHNIQUE "
        "SECRET_WEAPON ROLLING_BOULDER THE_GAMBIT MAYHEM NOSTALGIA BOLAS JACKPOT CALAMITY BEAT_DOWN ANOINTED ENTROPY HIDDEN_GEM ALCHEMIZE "
        "BARRICADE DOMINATE DARK_EMBRACE DEMON_FORM JUGGERNAUT ONE_TWO_PUNCH PYRE UNMOVABLE CASCADE CONFLAGRATION FIEND_FIRE NOT_YET "
        "OFFERING PACTS_END BRAND HELLRAISER MANGLE PRIMAL_FORCE STOKE TEAR_ASUNDER THRASH"
        " BANSHEES_CRY CALL_OF_THE_VOID DEMESNE DEVOUR_LIFE EIDOLON END_OF_DAYS ERADICATE HANG MISERY NECRO_MASTERY NEUROSURGE OBLIVION REANIMATE REAPER_FORM SACRIFICE SEANCE SENTRY_MODE SHARED_FATE SOUL_STORM SPIRIT_OF_ASH SQUEEZE THE_SCYTHE TIMES_UP TRANSFIGURE UNDEATH"
    ),
    CardRarity.Ancient : (
        "BREAK NEOWS_FURY CORRUPTION ABUNDANCE APOTHEOSIS APPARITION BRIGHTEST_FLAME MAUL RELAX WHISTLE WISH METEOR_SHOWER THE_SEALED_THRONE SUPPRESS WRAITH_FORM"
        " FORBIDDEN_GRIMOIRE PROTECTOR"
    ),
    CardRarity.Event : (
        "BYRD_SWOOP EXTERMINATE PECK SQUASH ENLIGHTENMENT METAMORPHOSIS TORIC_TOUGHNESS FEEDING_FRENZY MAD_SCIENCE "
        "CLASH DUAL_WIELD ENTRENCH CALTROPS DISTRACTION OUTMANEUVER HELLO_WORLD REBOUND RIP_AND_TEAR STACK"
    ),
    CardRarity.Token : (
        "GIANT_ROCK LUMINESCE SHIV SOVEREIGN_BLADE MINION_STRIKE MINION_DIVE_BOMB MINION_SACRIFICE"
        " SOUL SWEEPING_GAZE"
    ),
    CardRarity.Status : (
        "SLIMED INFECTION BURN BECKON WITHER DAZED WOUND SOOT TOXIC FRANTIC_ESCAPE DISINTEGRATION MIND_ROT SLOTH WASTE_AWAY DEBRIS"
    ),
    CardRarity.Curse : (
        "REGRET DECAY SHAME DOUBT NORMALITY INJURY POOR_SLEEP GREED CLUMSY CURSE_OF_THE_BELL WRITHE FOLLY BAD_LUCK DEBT GUILTY SPORE_MIND "
        "ASCENDERS_BANE ENTHRALLED"
    ),
    CardRarity.Quest : (
        "SPOILS_MAP LANTERN_KEY BYRDONIS_EGG DOWSING"
    ),
}

# the Defect's rarities
_RARITY_NAMES[CardRarity.Basic] += " DEFEND_DEFECT  DUALCAST  STRIKE_DEFECT  ZAP"
_RARITY_NAMES[CardRarity.Common] += " BALL_LIGHTNING  BARRAGE  BEAM_CELL  BOOST_AWAY  CHARGE_BATTERY  CLAW  COLD_SNAP  COMPILE_DRIVER  COOLHEADED  FOCUSED_STRIKE  GO_FOR_THE_EYES  GUNK_UP  HOLOGRAM  HOTFIX  LEAP  LIGHTNING_ROD  MOMENTUM_STRIKE  SWEEPING_BEAM  TURBO  UPROAR"
_RARITY_NAMES[CardRarity.Uncommon] += " BOOT_SEQUENCE  BULK_UP  CAPACITOR  CHAOS  CHILL  COMPACT  DARKNESS  DOUBLE_ENERGY  FERAL  FIGHT_THROUGH  FTL  FUSION  GLACIER  GLASSWORK  HAILSTORM  ITERATION  LOOP  NULL  OVERCLOCK  REFRACT  ROCKET_PUNCH  SCAVENGE  SCRAPE  SHADOW_SHIELD  SKIM  SMOKESTACK  STORM  SUBROUTINE  SUNDER  SYNCHRONIZE  SYNTHESIS  TEMPEST  TESLA_COIL  THUNDER  WHITE_NOISE"
_RARITY_NAMES[CardRarity.Rare] += " ADAPTIVE_STRIKE  ALL_FOR_ONE  BUFFER  CONSUMING_SHADOW  COOLANT  CREATIVE_AI  DEFRAGMENT  ECHO_FORM  FLAK_CANNON  GENETIC_ALGORITHM  HELIX_DRILL  HYPERBEAM  ICE_LANCE  MACHINE_LEARNING  METEOR_STRIKE  MODDED  MULTI_CAST  RAINBOW  REBOOT  SHATTER  SIGNAL_BOOST  SPINNER  SUPERCRITICAL  TRASH_TO_TREASURE  VOLTAIC"
_RARITY_NAMES[CardRarity.Ancient] += " BIASED_COGNITION  QUADCAST"
_RARITY_NAMES[CardRarity.Token] += " FUEL"
_RARITY_NAMES[CardRarity.Status] += " VOID"

CARD_RARITY : dict[CardId, CardRarity] = {CardId[name] : rarity for rarity, names in _RARITY_NAMES.items() for name in names.split()}

CARD_RARITY[CardId.NOT_IMPLEMENTED] = CardRarity.Status       # placeholder, not a real card

# Rare cards (Anointed takes them from the draw pile)
RARE_CARDS = frozenset(cid for cid, rarity in CARD_RARITY.items() if rarity == CardRarity.Rare)

INFERNAL_BLADE_POOL = [cid for cid, (_, card_type, _, _) in GENERATABLE_CARDS.items() if card_type == CardType.Attack]

STOKE_POOL = list(GENERATABLE_CARDS)

ZERO_COST_POOL = [cid for cid, (_, _, cost, _) in GENERATABLE_CARDS.items() if cost == 0]       # Jackpot: canonical cost 0, not X

# CardFactory.FilterForCombat over Character.CardPool: what card effects generate in combat (Discovery, Attack Potion, Infernal Blade, Crossbow...).
# Common to Rare cards of the character's pool, minus the ones with CanBeGeneratedInCombat => false.
NOT_GENERATED_IN_COMBAT = frozenset({CardId.FEED, CardId.NOT_YET, CardId.NIGHTMARE, CardId.THE_HUNT, CardId.EIDOLON, CardId.TRANSFIGURE})
_GENERATED_RARITIES = (CardRarity.Common, CardRarity.Uncommon, CardRarity.Rare)
COMBAT_CARDS = {
    "IRONCLAD": GENERATABLE_CARDS,
    "SILENT": {cid: v for cid, v in SILENT_CARDS.items() if CARD_RARITY[cid] in _GENERATED_RARITIES and cid not in NOT_GENERATED_IN_COMBAT},
    "NECROBINDER": {cid: v for cid, v in NECROBINDER_CARDS.items() if CARD_RARITY[cid] in _GENERATED_RARITIES and cid not in NOT_GENERATED_IN_COMBAT},
    "DEFECT": {cid: v for cid, v in DEFECT_CARDS.items() if CARD_RARITY[cid] in _GENERATED_RARITIES and cid not in NOT_GENERATED_IN_COMBAT},
    "REGENT": {cid: v for cid, v in REGENT_CARDS.items() if CARD_RARITY[cid] in _GENERATED_RARITIES and cid not in NOT_GENERATED_IN_COMBAT},
}


def combat_cards(character : str = "IRONCLAD") -> dict:
    """The character's combat-generatable cards (name, type, cost, target); the Ironclad's for a character the engine does not model."""
    return COMBAT_CARDS.get(character.upper(), GENERATABLE_CARDS)


def combat_pool(character : str = "IRONCLAD", card_type : CardType | None = None, rarity : CardRarity | None = None) -> list[CardId]:
    return [cid for cid, (_, kind, _, _) in combat_cards(character).items()
            if (card_type is None or kind == card_type) and (rarity is None or CARD_RARITY[cid] == rarity)]


def zero_cost_pool(character : str = "IRONCLAD") -> list[CardId]:
    """Jackpot: canonical cost 0, not X."""
    return [cid for cid, (_, _, cost, _) in combat_cards(character).items() if cost == 0]


# the character pool each card belongs to (CardModel.Pool), for transforms
CARD_POOL_OF = {cid: name for name, table in CHARACTER_CARDS.items() for cid in table}
TRANSFORM_POOLS = {name: [cid for cid in table if CARD_RARITY[cid] in _GENERATED_RARITIES] for name, table in CHARACTER_CARDS.items()}

# Splash: Attacks of every character pool but the owner's (only the modelled characters' pools)
def splash_pool(character : str = "IRONCLAD") -> list[CardId]:
    others = [name for name in COMBAT_CARDS if name != character.upper()] or list(COMBAT_CARDS)
    return [cid for name in others for cid in combat_pool(name, CardType.Attack)]

# cards that return to the hand at the start of the next turn if they were played this one (BeforeHandDraw)
RETURNING_CARDS = frozenset({CardId.BOLAS, CardId.THRUMMING_HATCHET})

# cards with the Defend tag (Fasten)
DEFEND_CARDS = frozenset({CardId.DEFEND_DEFECT, CardId.DEFEND_NECROBINDER, CardId.DEFEND_IRONCLAD, CardId.ULTIMATE_DEFEND, CardId.DEFEND_SILENT, CardId.DEFEND_REGENT})

# cards with the Strike tag (Hellraiser plays them when they are drawn)
STRIKE_CARDS = frozenset({CardId.STRIKE_DEFECT, CardId.ADAPTIVE_STRIKE, CardId.FOCUSED_STRIKE, CardId.METEOR_STRIKE, CardId.MOMENTUM_STRIKE, CardId.STRIKE_NECROBINDER, CardId.BLIGHT_STRIKE, CardId.SCULPTING_STRIKE, CardId.SHINING_STRIKE, CardId.STRIKE_SILENT, CardId.STRIKE_REGENT, CardId.SOLAR_STRIKE, CardId.MINION_STRIKE, CardId.LEADING_STRIKE, CardId.ULTIMATE_STRIKE, CardId.SEEKER_STRIKE, CardId.STRIKE_IRONCLAD, CardId.PERFECTED_STRIKE, CardId.POMMEL_STRIKE, CardId.TWIN_STRIKE,
                          CardId.ASHEN_STRIKE, CardId.SETUP_STRIKE})

def _curse_debuff(player, status : StatusId):
    """Shame and Doubt: 2 stacks if the player lacks the debuff, else 1. Hack: the sim ticks it at the end of the enemy turn,
    so a single stack would never reach the next player turn."""
    player.apply_status(status, CURSE_STATUS_AMOUNT if status in player.status else CURSE_STATUS_AMOUNT + 1)

HAND_CURSE_EFFECTS = {
    CardId.REGRET : lambda player: player.lose_hp(len(player.hand)),        # 1 HP per card in hand, itself included
    CardId.DECAY : lambda player: player.apply_damage(DECAY_DAMAGE),
    CardId.BAD_LUCK : lambda player: player.lose_hp(BAD_LUCK_HP_LOSS),     # Unblockable | Unpowered
    CardId.SHAME : lambda player: _curse_debuff(player, StatusId.FRAIL),
    CardId.DOUBT : lambda player: _curse_debuff(player, StatusId.WEAK),
}
