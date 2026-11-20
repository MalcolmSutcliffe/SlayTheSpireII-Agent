from __future__ import annotations

from sts2_lite.relic import RelicId

from sts2_lite.card.ids import CardId, EnchantmentId, TargetType

# Energy cost and target of every Ironclad, colorless, ancient, event and token card, read from the base() call of each class in the
# decompiled Models.Cards (cost "X" is a card that spends all its energy). The shop lists only the gold price, so this is where a
# card's energy cost comes from before it is in the deck. tables.py builds from the same numbers: test_card_constants keeps them equal.
_S, _A, _ALL, _RAND, _NONE = TargetType.Self, TargetType.AnyEnemy, TargetType.AllEnemies, TargetType.RandomEnemy, TargetType.NONE
CARD_ENERGY_COST_AND_TARGET : dict[CardId, tuple[int | str, TargetType]] = {
    CardId.ABUNDANCE : (1, _S),
    CardId.BREAK : (1, _A),
    CardId.CORRUPTION : (3, _S),
    CardId.NEOWS_FURY : (1, _A),
    CardId.AGGRESSION : (1, _S),
    CardId.ALCHEMIZE : (1, _S),
    CardId.ANGER : (0, _A),
    CardId.ANOINTED : (1, _S),
    CardId.APOTHEOSIS : (2, _S),
    CardId.APPARITION : (1, _S),
    CardId.ARMAMENTS : (1, _S),
    CardId.ASHEN_STRIKE : (1, _A),
    CardId.AUTOMATION : (1, _S),
    CardId.BARRICADE : (3, _S),
    CardId.BASH : (2, _A),
    CardId.BATTLE_TRANCE : (0, _S),
    CardId.BEAT_DOWN : (3, _RAND),
    CardId.BLOODLETTING : (0, _S),
    CardId.BLOOD_WALL : (2, _S),
    CardId.BLUDGEON : (3, _A),
    CardId.BODY_SLAM : (1, _A),
    CardId.BOLAS : (0, _A),
    CardId.BRAND : (0, _S),
    CardId.BREAKTHROUGH : (1, _ALL),
    CardId.BRIGHTEST_FLAME : (0, _S),
    CardId.BULLY : (0, _A),
    CardId.BURNING_PACT : (1, _S),
    CardId.BYRD_SWOOP : (0, _A),
    CardId.CALAMITY : (3, _S),
    CardId.CASCADE : ('X', _S),
    CardId.CATASTROPHE : (2, _S),
    CardId.CINDER : (2, _A),
    CardId.COLOSSUS : (1, _S),
    CardId.CONFLAGRATION : (1, _ALL),
    CardId.CRIMSON_MANTLE : (1, _S),
    CardId.CRUELTY : (1, _S),
    CardId.DARK_EMBRACE : (2, _S),
    CardId.DARK_SHACKLES : (0, _A),
    CardId.DEFEND_IRONCLAD : (1, _S),
    CardId.DEFEND_SILENT : (1, _S),
    CardId.NEUTRALIZE : (0, _A),
    CardId.SHIV : (0, _A),
    CardId.STRIKE_SILENT : (1, _A),
    CardId.SURVIVOR : (1, _S),
    CardId.STRIKE_REGENT : (1, _A),
    CardId.DEFEND_REGENT : (1, _S),
    CardId.FALLING_STAR : (0, _A),
    CardId.VENERATE : (1, _S),
    CardId.SOVEREIGN_BLADE : (2, _A),
    CardId.MINION_STRIKE : (0, _A),
    CardId.DEBRIS : (1, _NONE),
    CardId.ASTRAL_PULSE : (0, _ALL),
    CardId.BEGONE : (1, _S),
    CardId.CELESTIAL_MIGHT : (2, _A),
    CardId.CLOAK_OF_STARS : (0, _S),
    CardId.COLLISION_COURSE : (0, _A),
    CardId.COSMIC_INDIFFERENCE : (1, _S),
    CardId.CRESCENT_SPEAR : (1, _A),
    CardId.CRUSH_UNDER : (1, _ALL),
    CardId.GATHER_LIGHT : (1, _S),
    CardId.GLITTERSTREAM : (2, _S),
    CardId.GLOW : (1, _S),
    CardId.GUIDING_STAR : (1, _A),
    CardId.HIDDEN_CACHE : (1, _S),
    CardId.KNOW_THY_PLACE : (0, _A),
    CardId.PATTER : (1, _S),
    CardId.PHOTON_CUT : (1, _A),
    CardId.REFINE_BLADE : (1, _S),
    CardId.SOLAR_STRIKE : (1, _A),
    CardId.SPOILS_OF_BATTLE : (1, _S),
    CardId.WROUGHT_IN_WAR : (1, _A),
    CardId.MINION_DIVE_BOMB : (0, _A),
    CardId.ALIGNMENT : (0, _S),
    CardId.BLACK_HOLE : (1, _S),
    CardId.BULWARK : (2, _S),
    CardId.CHARGE : (1, _S),
    CardId.CHILD_OF_THE_STARS : (1, _S),
    CardId.CONQUEROR : (1, _A),
    CardId.CONVERGENCE : (1, _S),
    CardId.DEVASTATE : (1, _A),
    CardId.FURNACE : (1, _S),
    CardId.GAMMA_BLAST : (0, _A),
    CardId.GLIMMER : (1, _S),
    CardId.HEGEMONY : (2, _A),
    CardId.KINGLY_KICK : (4, _A),
    CardId.KINGLY_PUNCH : (1, _A),
    CardId.LUNAR_BLAST : (0, _A),
    CardId.MANIFEST_AUTHORITY : (1, _S),
    CardId.MONOLOGUE : (0, _S),
    CardId.ORBIT : (2, _S),
    CardId.PALE_BLUE_DOT : (1, _S),
    CardId.PARRY : (1, _S),
    CardId.PARTICLE_WALL : (0, _S),
    CardId.PILLAR_OF_CREATION : (1, _S),
    CardId.PROPHESIZE : (2, _S),
    CardId.QUASAR : (0, _S),
    CardId.RADIATE : (0, _ALL),
    CardId.REFLECT : (1, _S),
    CardId.RESONANCE : (1, _ALL),
    CardId.ROYAL_GAMBLE : (0, _S),
    CardId.SHINING_STRIKE : (1, _A),
    CardId.SPECTRUM_SHIFT : (2, _S),
    CardId.STARDUST : (0, _RAND),
    CardId.SUMMON_FORTH : (1, _S),
    CardId.SUPERMASSIVE : (1, _A),
    CardId.TERRAFORMING : (1, _S),
    CardId.MINION_SACRIFICE : (0, _S),
    CardId.KNOCKOUT_BLOW : (3, _A),
    CardId.ARSENAL : (1, _S),
    CardId.BEAT_INTO_SHAPE : (1, _A),
    CardId.BIG_BANG : (0, _S),
    CardId.BOMBARDMENT : (3, _A),
    CardId.BUNDLE_OF_JOY : (1, _S),
    CardId.COMET : (0, _A),
    CardId.CRASH_LANDING : (1, _ALL),
    CardId.DECISIONS_DECISIONS : (0, _S),
    CardId.DYING_STAR : (1, _ALL),
    CardId.FOREGONE_CONCLUSION : (1, _S),
    CardId.GENESIS : (2, _S),
    CardId.GUARDS : (2, _S),
    CardId.HEAVENLY_DRILL : ('X', _A),
    CardId.HEIRLOOM_HAMMER : (2, _A),
    CardId.I_AM_INVINCIBLE : (1, _S),
    CardId.MAKE_IT_SO : (0, _A),
    CardId.MONARCHS_GAZE : (2, _S),
    CardId.NEUTRON_AEGIS : (1, _S),
    CardId.ROYALTIES : (1, _S),
    CardId.SEEKING_EDGE : (1, _S),
    CardId.SEVEN_STARS : (2, _ALL),
    CardId.SWORD_SAGE : (2, _S),
    CardId.THE_SMITH : (1, _S),
    CardId.TYRANNY : (1, _S),
    CardId.VOID_FORM : (3, _S),
    CardId.ANTICIPATE : (0, _S),
    CardId.BACKFLIP : (1, _S),
    CardId.BLADE_DANCE : (1, _S),
    CardId.CLOAK_AND_DAGGER : (1, _S),
    CardId.DAGGER_SPRAY : (1, _ALL),
    CardId.DAGGER_THROW : (1, _A),
    CardId.DEADLY_POISON : (1, _A),
    CardId.DEFLECT : (0, _S),
    CardId.DODGE_AND_ROLL : (1, _S),
    CardId.FLICK_FLACK : (1, _ALL),
    CardId.LEADING_STRIKE : (1, _A),
    CardId.PIERCING_WAIL : (1, _ALL),
    CardId.POISONED_STAB : (1, _A),
    CardId.PREDATOR : (2, _A),
    CardId.PREPARED : (0, _S),
    CardId.RICOCHET : (2, _RAND),
    CardId.SLICE : (0, _A),
    CardId.SNAKEBITE : (2, _A),
    CardId.SUCKER_PUNCH : (1, _A),
    CardId.UNTOUCHABLE : (2, _S),
    CardId.ACCELERANT : (1, _S),
    CardId.ACCURACY : (1, _S),
    CardId.ACROBATICS : (1, _S),
    CardId.BACKSTAB : (0, _A),
    CardId.BLUR : (1, _S),
    CardId.BOUNCING_FLASK : (2, _RAND),
    CardId.BUBBLE_BUBBLE : (1, _A),
    CardId.CALCULATED_GAMBLE : (0, _S),
    CardId.DASH : (2, _A),
    CardId.ECHOING_SLASH : (1, _ALL),
    CardId.ESCAPE_PLAN : (0, _S),
    CardId.EXPERTISE : (1, _S),
    CardId.EXPOSE : (0, _A),
    CardId.FINISHER : (1, _A),
    CardId.FLECHETTES : (1, _A),
    CardId.SIDESTEP : (0, _S),
    CardId.FOOTWORK : (1, _S),
    CardId.HAND_TRICK : (1, _S),
    CardId.HAZE : (2, _ALL),
    CardId.HIDDEN_DAGGERS : (0, _S),
    CardId.INFINITE_BLADES : (1, _S),
    CardId.LEG_SWEEP : (2, _A),
    CardId.MEMENTO_MORI : (1, _A),
    CardId.MIRAGE : (1, _S),
    CardId.NOXIOUS_FUMES : (1, _S),
    CardId.PHANTOM_BLADES : (1, _S),
    CardId.PINPOINT : (3, _A),
    CardId.POUNCE : (2, _A),
    CardId.PRECISE_CUT : (0, _A),
    CardId.REFLEX : (3, _S),
    CardId.SKEWER : ('X', _A),
    CardId.SPEEDSTER : (2, _S),
    CardId.STRANGLE : (1, _A),
    CardId.TACTICIAN : (3, _S),
    CardId.UP_MY_SLEEVE : (2, _S),
    CardId.ABRASIVE : (3, _S),
    CardId.ADRENALINE : (0, _S),
    CardId.AFTERIMAGE : (1, _S),
    CardId.ASSASSINATE : (0, _A),
    CardId.BLADE_OF_INK : (1, _S),
    CardId.BULLET_TIME : (3, _S),
    CardId.BURST : (1, _S),
    CardId.CORROSIVE_WAVE : (1, _S),
    CardId.ENVENOM : (2, _S),
    CardId.FAN_OF_KNIVES : (2, _S),
    CardId.GRAND_FINALE : (0, _ALL),
    CardId.KNIFE_TRAP : (2, _A),
    CardId.MALAISE : ('X', _A),
    CardId.MASTER_PLANNER : (2, _S),
    CardId.MURDER : (3, _A),
    CardId.NIGHTMARE : (3, _S),
    CardId.OUTBREAK : (3, _ALL),
    CardId.SERPENT_FORM : (3, _S),
    CardId.SHADOW_STEP : (1, _S),
    CardId.SHADOWMELD : (1, _S),
    CardId.STORM_OF_STEEL : (1, _S),
    CardId.THE_HUNT : (1, _A),
    CardId.TOOLS_OF_THE_TRADE : (1, _S),
    CardId.TRACKING : (2, _S),
    CardId.WELL_LAID_PLANS : (2, _S),
    CardId.DEMON_FORM : (3, _S),
    CardId.DISCOVERY : (1, _S), CardId.SPLASH : (1, _S),
    CardId.DISMANTLE : (1, _A),
    CardId.DOMINATE : (1, _A),
    CardId.DRAMATIC_ENTRANCE : (0, _ALL),
    CardId.DRUM_OF_BATTLE : (1, _S),
    CardId.ENLIGHTENMENT : (0, _S),
    CardId.ENTROPY : (1, _S),
    CardId.EQUILIBRIUM : (2, _S),
    CardId.ETERNAL_ARMOR : (3, _S),
    CardId.EVIL_EYE : (1, _S),
    CardId.EXPECT_A_FIGHT : (3, _S),
    CardId.EXTERMINATE : (1, _ALL),
    CardId.FASTEN : (1, _S),
    CardId.FEED : (1, _A),
    CardId.FEEL_NO_PAIN : (1, _S),
    CardId.FIEND_FIRE : (2, _A),
    CardId.FIGHT_ME : (2, _A),
    CardId.FINESSE : (0, _S),
    CardId.FISTICUFFS : (1, _A),
    CardId.FLAME_BARRIER : (2, _S),
    CardId.FLASH_OF_STEEL : (0, _A),
    CardId.FORGOTTEN_RITUAL : (1, _S),
    CardId.GIANT_ROCK : (1, _A),
    CardId.GOLD_AXE : (1, _A),
    CardId.HAND_OF_GREED : (2, _A),
    CardId.HAVOC : (1, _S),
    CardId.HEADBUTT : (1, _A),
    CardId.HELLRAISER : (2, _S),
    CardId.HEMOKINESIS : (1, _A),
    CardId.HIDDEN_GEM : (1, _S),
    CardId.HOWL_FROM_BEYOND : (3, _ALL),
    CardId.IMPATIENCE : (0, _S),
    CardId.IMPERVIOUS : (2, _S),
    CardId.INFERNAL_BLADE : (1, _S),
    CardId.INFERNO : (1, _S),
    CardId.INFLAME : (1, _S),
    CardId.IRON_WAVE : (1, _A),
    CardId.JACKPOT : (3, _A),
    CardId.JACK_OF_ALL_TRADES : (0, _S),
    CardId.JUGGERNAUT : (2, _S),
    CardId.JUGGLING : (1, _S),
    CardId.LUMINESCE : (0, _S),
    CardId.MANGLE : (3, _A),
    CardId.MASTER_OF_STRATEGY : (0, _S),
    CardId.MAUL : (1, _A),
    CardId.MAYHEM : (2, _S),
    CardId.STRATAGEM : (1, _S),
    CardId.METAMORPHOSIS : (2, _S),
    CardId.MIND_BLAST : (1, _A),
    CardId.MOLTEN_FIST : (1, _A),
    CardId.NOSTALGIA : (1, _S),
    CardId.NOT_YET : (2, _S),
    CardId.OFFERING : (0, _S),
    CardId.OMNISLICE : (0, _A),
    CardId.ONE_TWO_PUNCH : (1, _S),
    CardId.PACTS_END : (0, _ALL),
    CardId.PANACHE : (0, _S),
    CardId.PANIC_BUTTON : (0, _S),
    CardId.PECK : (1, _A),
    CardId.PERFECTED_STRIKE : (2, _A),
    CardId.PILLAGE : (1, _A),
    CardId.POMMEL_STRIKE : (1, _A),
    CardId.PREP_TIME : (1, _S),
    CardId.PRIMAL_FORCE : (0, _S),
    CardId.PRODUCTION : (0, _S),
    CardId.PROLONG : (0, _S),
    CardId.PROWESS : (1, _S),
    CardId.PURITY : (0, _S),
    CardId.PYRE : (2, _S),
    CardId.RAGE : (0, _S),
    CardId.RAMPAGE : (1, _A),
    CardId.RELAX : (3, _S),
    CardId.REND : (1, _A),
    CardId.RESTLESSNESS : (0, _S),
    CardId.ROLLING_BOULDER : (3, _S),
    CardId.RUPTURE : (1, _S),
    CardId.SALVO : (1, _A),
    CardId.SCRAWL : (1, _S),
    CardId.SECOND_WIND : (1, _S),
    CardId.SECRET_TECHNIQUE : (0, _S),
    CardId.SECRET_WEAPON : (0, _S),
    CardId.SEEKER_STRIKE : (1, _A),
    CardId.SETUP_STRIKE : (1, _A),
    CardId.SHOCKWAVE : (2, _ALL),
    CardId.SHRUG_IT_OFF : (1, _S),
    CardId.SPITE : (0, _A),
    CardId.SQUASH : (1, _A),
    CardId.STAMPEDE : (2, _S),
    CardId.STOKE : (1, _S),
    CardId.STOMP : (3, _ALL),
    CardId.STONE_ARMOR : (1, _S),
    CardId.STRIKE_IRONCLAD : (1, _A),
    CardId.SWORD_BOOMERANG : (1, _RAND),
    CardId.TAUNT : (1, _A),
    CardId.TEAR_ASUNDER : (2, _A),
    CardId.THE_BOMB : (2, _S),
    CardId.THE_GAMBIT : (0, _S),
    CardId.THINKING_AHEAD : (0, _S),
    CardId.THRASH : (1, _A),
    CardId.THRUMMING_HATCHET : (1, _A),
    CardId.THUNDERCLAP : (1, _ALL),
    CardId.TORIC_TOUGHNESS : (2, _S),
    CardId.FEEDING_FRENZY : (0, _S),
    CardId.MAD_SCIENCE : (1, _A),
    CardId.CLASH : (0, _A), CardId.DUAL_WIELD : (1, _S), CardId.ENTRENCH : (2, _S), CardId.CALTROPS : (1, _S), CardId.DISTRACTION : (1, _S),
    CardId.OUTMANEUVER : (1, _S), CardId.HELLO_WORLD : (1, _S), CardId.REBOUND : (1, _A), CardId.RIP_AND_TEAR : (1, _RAND), CardId.STACK : (1, _S),
    CardId.TREMBLE : (1, _A),
    CardId.TRUE_GRIT : (1, _S),
    CardId.TWIN_STRIKE : (1, _A),
    CardId.ULTIMATE_DEFEND : (1, _S),
    CardId.ULTIMATE_STRIKE : (1, _A),
    CardId.UNMOVABLE : (2, _S),
    CardId.UNRELENTING : (2, _A),
    CardId.UPPERCUT : (2, _A),
    CardId.VICIOUS : (1, _S),
    CardId.VOLLEY : ('X', _RAND),
    CardId.WHIRLWIND : ('X', _ALL),
    CardId.WHISTLE : (2, _A),
    CardId.WISH : (0, _S),
    CardId.METEOR_SHOWER : (0, _ALL),
    CardId.SUPPRESS : (0, _A),
    CardId.WRAITH_FORM : (3, _S),
    CardId.THE_SEALED_THRONE : (1, _S),
    CardId.BODYGUARD : (1, _S),
    CardId.DEFEND_NECROBINDER : (1, _S),
    CardId.FORBIDDEN_GRIMOIRE : (2, _S),
    CardId.PROTECTOR : (1, _A),
    CardId.STRIKE_NECROBINDER : (1, _A),
    CardId.UNLEASH : (1, _A),
    CardId.SOUL : (0, _S),
    CardId.SWEEPING_GAZE : (0, _RAND),
    # the Necrobinder's
    CardId.AFTERLIFE : (1, _S),
    CardId.BANSHEES_CRY : (9, _ALL),
    CardId.BLIGHT_STRIKE : (1, _A),
    CardId.BONE_SHARDS : (1, _ALL),
    CardId.BORROWED_TIME : (1, _S),
    CardId.BURY : (4, _A),
    CardId.CALCIFY : (1, _S),
    CardId.CALL_OF_THE_VOID : (1, _S),
    CardId.CAPTURE_SPIRIT : (1, _A),
    CardId.CLEANSE : (1, _S),
    CardId.COUNTDOWN : (1, _S),
    CardId.DANSE_MACABRE : (1, _S),
    CardId.DEATH_MARCH : (1, _A),
    CardId.DEATHBRINGER : (2, _ALL),
    CardId.DEATHS_DOOR : (1, _S),
    CardId.DEBILITATE : (1, _A),
    CardId.DEFILE : (1, _A),
    CardId.DEFY : (1, _A),
    CardId.DELAY : (2, _S),
    CardId.DEMESNE : (3, _S),
    CardId.DEVOUR_LIFE : (1, _S),
    CardId.DIRGE : ("X", _S),
    CardId.DRAIN_POWER : (1, _A),
    CardId.DREDGE : (1, _S),
    CardId.EIDOLON : (2, _S),
    CardId.END_OF_DAYS : (3, _ALL),
    CardId.ENFEEBLING_TOUCH : (1, _A),
    CardId.ERADICATE : ("X", _A),
    CardId.FEAR : (1, _A),
    CardId.FETCH : (0, _A),
    CardId.FLATTEN : (2, _A),
    CardId.FRIENDSHIP : (1, _S),
    CardId.GRAVE_WARDEN : (1, _S),
    CardId.GRAVEBLAST : (1, _A),
    CardId.HANG : (1, _A),
    CardId.HAUNT : (1, _S),
    CardId.HIGH_FIVE : (2, _ALL),
    CardId.INVOKE : (1, _S),
    CardId.LETHALITY : (1, _S),
    CardId.MELANCHOLY : (3, _S),
    CardId.MISERY : (0, _A),
    CardId.NECRO_MASTERY : (2, _S),
    CardId.NEGATIVE_PULSE : (1, _ALL),
    CardId.NEUROSURGE : (0, _S),
    CardId.NO_ESCAPE : (1, _A),
    CardId.OBLIVION : (0, _A),
    CardId.PAGESTORM : (1, _S),
    CardId.PARSE : (1, _S),
    CardId.POKE : (0, _A),
    CardId.PULL_AGGRO : (2, _S),
    CardId.PULL_FROM_BELOW : (1, _A),
    CardId.PUTREFY : (1, _A),
    CardId.RATTLE : (1, _A),
    CardId.REANIMATE : (3, _S),
    CardId.REAP : (3, _A),
    CardId.REAPER_FORM : (3, _S),
    CardId.REAVE : (1, _A),
    CardId.RIGHT_HAND_HAND : (0, _A),
    CardId.SACRIFICE : (1, _S),
    CardId.SCOURGE : (1, _A),
    CardId.SCULPTING_STRIKE : (1, _A),
    CardId.SEANCE : (1, _S),
    CardId.SENTRY_MODE : (2, _S),
    CardId.SEVERANCE : (2, _A),
    CardId.SHARED_FATE : (0, _A),
    CardId.SHROUD : (1, _S),
    CardId.SIC_EM : (1, _A),
    CardId.SLEIGHT_OF_FLESH : (2, _S),
    CardId.SNAP : (1, _A),
    CardId.SOUL_STORM : (1, _A),
    CardId.SOW : (1, _ALL),
    CardId.SPIRIT_OF_ASH : (1, _S),
    CardId.SPUR : (1, _S),
    CardId.SQUEEZE : (3, _A),
    CardId.THE_SCYTHE : (2, _A),
    CardId.TIMES_UP : (2, _A),
    CardId.TRANSFIGURE : (1, _S),
    CardId.UNDEATH : (0, _S),
    CardId.VEILPIERCER : (1, _A),
    CardId.WISP : (0, _S),
    # the Defect's
    CardId.ADAPTIVE_STRIKE : (2, _A),
    CardId.ALL_FOR_ONE : (2, _A),
    CardId.BALL_LIGHTNING : (1, _A),
    CardId.BARRAGE : (1, _A),
    CardId.BEAM_CELL : (0, _A),
    CardId.BIASED_COGNITION : (1, _S),
    CardId.BOOST_AWAY : (0, _S),
    CardId.BOOT_SEQUENCE : (0, _S),
    CardId.BUFFER : (2, _S),
    CardId.BULK_UP : (2, _S),
    CardId.CAPACITOR : (1, _S),
    CardId.CHAOS : (1, _S),
    CardId.CHARGE_BATTERY : (1, _S),
    CardId.CHILL : (0, _S),
    CardId.CLAW : (0, _A),
    CardId.COLD_SNAP : (1, _A),
    CardId.COMPACT : (1, _S),
    CardId.COMPILE_DRIVER : (1, _A),
    CardId.CONSUMING_SHADOW : (2, _S),
    CardId.COOLANT : (1, _S),
    CardId.COOLHEADED : (1, _S),
    CardId.CREATIVE_AI : (3, _S),
    CardId.DARKNESS : (1, _S),
    CardId.DEFEND_DEFECT : (1, _S),
    CardId.DEFRAGMENT : (1, _S),
    CardId.DOUBLE_ENERGY : (1, _S),
    CardId.DUALCAST : (1, _S),
    CardId.ECHO_FORM : (3, _S),
    CardId.FERAL : (2, _S),
    CardId.FIGHT_THROUGH : (1, _S),
    CardId.FLAK_CANNON : (2, _RAND),
    CardId.FOCUSED_STRIKE : (1, _A),
    CardId.FTL : (0, _A),
    CardId.FUSION : (1, _S),
    CardId.GENETIC_ALGORITHM : (1, _S),
    CardId.GLACIER : (2, _S),
    CardId.GLASSWORK : (1, _S),
    CardId.GO_FOR_THE_EYES : (0, _A),
    CardId.GUNK_UP : (1, _A),
    CardId.HAILSTORM : (1, _S),
    CardId.HELIX_DRILL : (0, _A),
    CardId.HOLOGRAM : (1, _S),
    CardId.HOTFIX : (0, _S),
    CardId.HYPERBEAM : (2, _ALL),
    CardId.ICE_LANCE : (3, _A),
    CardId.ITERATION : (1, _S),
    CardId.LEAP : (1, _S),
    CardId.LIGHTNING_ROD : (1, _S),
    CardId.LOOP : (1, _S),
    CardId.MACHINE_LEARNING : (1, _S),
    CardId.METEOR_STRIKE : (5, _A),
    CardId.MODDED : (0, _S),
    CardId.MOMENTUM_STRIKE : (1, _A),
    CardId.MULTI_CAST : ("X", _S),
    CardId.NULL : (2, _A),
    CardId.OVERCLOCK : (0, _S),
    CardId.QUADCAST : (1, _S),
    CardId.RAINBOW : (2, _S),
    CardId.REBOOT : (0, _S),
    CardId.REFRACT : (3, _A),
    CardId.ROCKET_PUNCH : (2, _A),
    CardId.SCAVENGE : (1, _S),
    CardId.SCRAPE : (1, _A),
    CardId.SHADOW_SHIELD : (2, _S),
    CardId.SHATTER : (1, _ALL),
    CardId.SIGNAL_BOOST : (1, _S),
    CardId.SKIM : (1, _S),
    CardId.SMOKESTACK : (1, _S),
    CardId.SPINNER : (1, _S),
    CardId.STORM : (1, _S),
    CardId.STRIKE_DEFECT : (1, _A),
    CardId.SUBROUTINE : (1, _S),
    CardId.SUNDER : (3, _A),
    CardId.SUPERCRITICAL : (0, _S),
    CardId.SWEEPING_BEAM : (1, _ALL),
    CardId.SYNCHRONIZE : (1, _S),
    CardId.SYNTHESIS : (2, _A),
    CardId.TEMPEST : ("X", _S),
    CardId.TESLA_COIL : (0, _A),
    CardId.THUNDER : (1, _S),
    CardId.TRASH_TO_TREASURE : (1, _S),
    CardId.TURBO : (0, _S),
    CardId.UPROAR : (2, _A),
    CardId.VOLTAIC : (3, _S),
    CardId.WHITE_NOISE : (1, _S),
    CardId.ZAP : (1, _S),
    CardId.FUEL : (0, _S),
}

INFECTION_DAMAGE = 3

BURN_DAMAGE = 2

BECKON_HP_LOSS = 6      # Soul Fysh's Beckon: a status that can be played for 1 Energy, else costs this at the end of the turn

WITHER_DAMAGE = 3       # and 3 more for each time Aeonglass has upgraded it

TOXIC_DAMAGE = 5

# energy cost change when upgraded (the rest of an upgrade is read from is_upgraded when the card is played)
UPGRADE_COST_CHANGE = {
    CardId.BANSHEES_CRY : -2, CardId.DEMESNE : -1, CardId.EIDOLON : -1, CardId.FORBIDDEN_GRIMOIRE : -1, CardId.PAGESTORM : -1, CardId.PROTECTOR : -1, CardId.SACRIFICE : -1, CardId.SEANCE : -1, CardId.SENTRY_MODE : -1,
    CardId.SOVEREIGN_BLADE : -1, CardId.THE_SEALED_THRONE : -1, CardId.ORBIT : -1, CardId.SPECTRUM_SHIFT : -1, CardId.MONARCHS_GAZE : -1, CardId.SEVEN_STARS : -1, CardId.SWORD_SAGE : -1,
    CardId.BARRICADE : -1, CardId.CORRUPTION : -1, CardId.DARK_EMBRACE : -1, CardId.STAMPEDE : -1,
    CardId.UNMOVABLE : -1, CardId.HAVOC : -1, CardId.INFERNAL_BLADE : -1,
    CardId.BODY_SLAM : -1, CardId.HELLRAISER : -1, CardId.MIND_BLAST : -1,
    CardId.AUTOMATION : -1, CardId.MAYHEM : -1, CardId.NOSTALGIA : -1, CardId.CALAMITY : -1,
    CardId.APOTHEOSIS : -1, CardId.ABUNDANCE : -1, CardId.ALCHEMIZE : -1, CardId.ENTRENCH : -1, CardId.DISTRACTION : -1,
    CardId.STRATAGEM : -1,
    CardId.BULLET_TIME : -1,
    CardId.MASTER_PLANNER : -1,
    CardId.MURDER : -1,
    CardId.NIGHTMARE : -1,
    CardId.SHADOW_STEP : -1,
    CardId.SHADOWMELD : -1,
    CardId.TOOLS_OF_THE_TRADE : -1,
    CardId.TRACKING : -1,
    CardId.WELL_LAID_PLANS : -1,

}

# CardModel base cost of the cards above (an upgrade caps a rolled Confused cost at base + change)
# the Regent's Star costs (CanonicalStarCost; "X" spends every Star): what a card costs in Stars before upgrades
STAR_COST : dict[CardId, int | str] = {
    CardId.FALLING_STAR : 2, CardId.ASTRAL_PULSE : 3, CardId.CLOAK_OF_STARS : 1, CardId.CRESCENT_SPEAR : 1, CardId.GUIDING_STAR : 1,
    CardId.ALIGNMENT : 2, CardId.DEVASTATE : 4, CardId.GAMMA_BLAST : 3, CardId.PARTICLE_WALL : 2, CardId.QUASAR : 2, CardId.REFLECT : 3,
    CardId.RESONANCE : 2, CardId.ROYAL_GAMBLE : 5, CardId.STARDUST : "X",
    CardId.METEOR_SHOWER : 2, CardId.THE_SEALED_THRONE : 3, CardId.COMET : 5, CardId.DECISIONS_DECISIONS : 6, CardId.DYING_STAR : 3, CardId.NEUTRON_AEGIS : 5, CardId.SEVEN_STARS : 7, CardId.THE_SMITH : 4,
}
# Star cost an upgrade changes: (new Star cost upgraded) for the cards whose upgrade does it
UPGRADE_STAR_COST : dict[CardId, int] = {}

UPGRADE_BASE_COST = {
    CardId.BANSHEES_CRY : 9, CardId.DEMESNE : 3, CardId.EIDOLON : 2, CardId.FORBIDDEN_GRIMOIRE : 2, CardId.PAGESTORM : 1, CardId.PROTECTOR : 1, CardId.SACRIFICE : 1, CardId.SEANCE : 1, CardId.SENTRY_MODE : 2,
    CardId.SOVEREIGN_BLADE : 2, CardId.THE_SEALED_THRONE : 1, CardId.ORBIT : 2, CardId.SPECTRUM_SHIFT : 2, CardId.MONARCHS_GAZE : 2, CardId.SEVEN_STARS : 2, CardId.SWORD_SAGE : 2,
    CardId.BARRICADE : 3, CardId.CORRUPTION : 3, CardId.DARK_EMBRACE : 2, CardId.STAMPEDE : 2,
    CardId.UNMOVABLE : 2, CardId.HAVOC : 1, CardId.INFERNAL_BLADE : 1,
    CardId.BODY_SLAM : 1, CardId.HELLRAISER : 2, CardId.MIND_BLAST : 1,
    CardId.AUTOMATION : 1, CardId.MAYHEM : 2, CardId.NOSTALGIA : 1, CardId.CALAMITY : 3,
    CardId.APOTHEOSIS : 2, CardId.ABUNDANCE : 1, CardId.ALCHEMIZE : 1, CardId.ENTRENCH : 2, CardId.DISTRACTION : 1,
    CardId.STRATAGEM : 1,
    CardId.BULLET_TIME : 3,
    CardId.MASTER_PLANNER : 2,
    CardId.MURDER : 3,
    CardId.NIGHTMARE : 3,
    CardId.SHADOW_STEP : 1,
    CardId.SHADOWMELD : 1,
    CardId.TOOLS_OF_THE_TRADE : 1,
    CardId.TRACKING : 2,
    CardId.WELL_LAID_PLANS : 2,

}

# keyword an upgrade removes (Exhaust)
UPGRADE_REMOVED_KEYWORD = {CardId.GRAVEBLAST : 1, CardId.TRANSFIGURE : 1, CardId.VOID_FORM : 2, CardId.KNOW_THY_PLACE : 1, CardId.SECRET_TECHNIQUE : 1, CardId.SECRET_WEAPON : 1, CardId.THINKING_AHEAD : 1, CardId.PROLONG : 1, CardId.DISCOVERY : 1, CardId.APPARITION : 2, CardId.MIRAGE : 1}      # Exhaust x5, Ethereal for Apparition

# keyword an upgrade adds
UPGRADE_KEYWORD = {CardId.CALL_OF_THE_VOID : 4, CardId.DREDGE : 16, CardId.MISERY : 16, CardId.REAPER_FORM : 16, CardId.TIMES_UP : 16, CardId.WISP : 16, CardId.ARSENAL : 4, CardId.BIG_BANG : 4, CardId.TYRANNY : 4, CardId.MONOLOGUE : 16, CardId.ROYAL_GAMBLE : 16, CardId.HELLO_WORLD : 4, CardId.MAD_SCIENCE : 4, CardId.SCRAWL : 16, CardId.GOLD_AXE : 16, CardId.ANOINTED : 16, CardId.ENTROPY : 4, CardId.WISH : 16, CardId.AGGRESSION : 4, CardId.JUGGLING : 4, CardId.CALCULATED_GAMBLE : 16, CardId.INFINITE_BLADES : 4, CardId.SPEEDSTER : 4, CardId.AFTERIMAGE : 4}       # Retain, Retain, Retain, Innate (Entropy, Aggression, Juggling), Retain

CONFUSED_MAX_COST = 3

_EXHAUST, _ETHEREAL, _INNATE, _UNPLAYABLE, _RETAIN, _SLY, _ETERNAL, _REPLAY = 1, 2, 4, 8, 16, 32, 64, 128

# cards with the Exhaust keyword
EXHAUSTING_CARDS = frozenset({CardId.MINION_SACRIFICE, CardId.BIG_BANG, CardId.BOMBARDMENT, CardId.BUNDLE_OF_JOY, CardId.GUARDS, CardId.MINION_DIVE_BOMB, CardId.ROYAL_GAMBLE, CardId.KNOW_THY_PLACE, CardId.MINION_STRIKE, CardId.DEBRIS, CardId.ADRENALINE, CardId.ASSASSINATE, CardId.MALAISE, CardId.NIGHTMARE, CardId.THE_HUNT, CardId.BACKSTAB, CardId.CALCULATED_GAMBLE, CardId.EXPOSE, CardId.MIRAGE, CardId.SLIMED, CardId.TREMBLE, CardId.IMPERVIOUS, CardId.MOLTEN_FIST,
                              CardId.TOXIC, CardId.FEED, CardId.DOMINATE, CardId.FIEND_FIRE, CardId.FORGOTTEN_RITUAL,
                              CardId.INFERNAL_BLADE, CardId.NOT_YET, CardId.OFFERING, CardId.SPORE_MIND,
                              CardId.PRODUCTION, CardId.MASTER_OF_STRATEGY, CardId.DRAMATIC_ENTRANCE, CardId.SHOCKWAVE,
                              CardId.SCRAWL, CardId.PURITY, CardId.SECRET_TECHNIQUE, CardId.SECRET_WEAPON, CardId.THINKING_AHEAD,
                              CardId.PANIC_BUTTON, CardId.PROLONG, CardId.DARK_SHACKLES, CardId.JACK_OF_ALL_TRADES, CardId.ANOINTED, CardId.DISCOVERY, CardId.ALCHEMIZE, CardId.LUMINESCE,
                              CardId.ENLIGHTENMENT, CardId.METAMORPHOSIS, CardId.DISTRACTION, CardId.NEOWS_FURY,
                              CardId.ABUNDANCE, CardId.APOTHEOSIS, CardId.APPARITION, CardId.RELAX, CardId.WHISTLE, CardId.WISH, CardId.SHIV,
                              CardId.BLADE_DANCE, CardId.PIERCING_WAIL})

# curses (Debt's gold loss is not modelled: the sim does not track gold)
CURSE_CARDS = frozenset({CardId.BAD_LUCK, CardId.DEBT, CardId.REGRET, CardId.DECAY, CardId.SHAME, CardId.DOUBT, CardId.NORMALITY, CardId.INJURY,
                         CardId.POOR_SLEEP, CardId.GREED, CardId.CLUMSY, CardId.CURSE_OF_THE_BELL, CardId.WRITHE,
                         CardId.FOLLY, CardId.GUILTY, CardId.SPORE_MIND, CardId.ASCENDERS_BANE, CardId.ENTHRALLED})

PLAYABLE_CURSES = {CardId.SPORE_MIND : 1, CardId.ENTHRALLED : 2}      # energy cost of the curses that can be played

# cards with the Unplayable keyword
UNPLAYABLE_CARDS = frozenset({CardId.VOID, CardId.SPOILS_MAP, CardId.LANTERN_KEY, CardId.BYRDONIS_EGG, CardId.DOWSING, CardId.DAZED, CardId.WOUND, CardId.NOT_IMPLEMENTED, CardId.INFECTION, CardId.BURN, CardId.WITHER, CardId.SOOT,
                              CardId.DISINTEGRATION, CardId.MIND_ROT, CardId.SLOTH, CardId.WASTE_AWAY}
                             | (CURSE_CARDS - PLAYABLE_CURSES.keys()))

# cards with the Ethereal keyword: exhausted instead of discarded if still in hand at end of turn
ETHEREAL_CARDS = frozenset({CardId.VOID, CardId.ECHO_FORM, CardId.DYING_STAR, CardId.VOID_FORM, CardId.APPARITION, CardId.DAZED, CardId.CLUMSY, CardId.FOLLY, CardId.ASCENDERS_BANE})

# Retain / Innate / Eternal: only Retain acts in combat (Innate and Eternal are deck-level)
RETAINING_CARDS = frozenset({CardId.SOVEREIGN_BLADE, CardId.POOR_SLEEP, CardId.RESTLESSNESS, CardId.PURITY, CardId.LUMINESCE, CardId.SNAKEBITE})

# cards with the Sly keyword: discarded by an effect, they play themselves for free (CardCmd.DiscardAndDraw)
SLY_CARDS = frozenset({CardId.FLICK_FLACK, CardId.RICOCHET, CardId.UNTOUCHABLE, CardId.REFLEX, CardId.TACTICIAN, CardId.ABRASIVE})

INNATE_CARDS = frozenset({CardId.SUPPRESS, CardId.ASSASSINATE, CardId.BACKSTAB, CardId.APOTHEOSIS, CardId.WRITHE, CardId.FOLLY, CardId.DRAMATIC_ENTRANCE, CardId.MIND_BLAST})

ETERNAL_CARDS = frozenset({CardId.BAD_LUCK, CardId.ASCENDERS_BANE, CardId.CURSE_OF_THE_BELL, CardId.GREED, CardId.FOLLY, CardId.ENTHRALLED})

NORMALITY_CARD_LIMIT = 3

NEOWS_FURY_CARDS = (2, 3)       # cards returned to the hand, by upgrade

DECAY_DAMAGE = 2

BAD_LUCK_HP_LOSS = 13

CURSE_STATUS_AMOUNT = 1         # Shame (Frail), Doubt (Weak)

# the Necrobinder's keywords
EXHAUSTING_CARDS = EXHAUSTING_CARDS | frozenset({CardId.AFTERLIFE, CardId.DIRGE, CardId.DREDGE, CardId.EIDOLON, CardId.GRAVEBLAST, CardId.PUTREFY, CardId.REANIMATE, CardId.SHARED_FATE, CardId.SOUL, CardId.SWEEPING_GAZE, CardId.THE_SCYTHE, CardId.TRANSFIGURE, CardId.WISP})
ETHEREAL_CARDS = ETHEREAL_CARDS | frozenset({CardId.DEFILE, CardId.DEFY, CardId.DEMESNE, CardId.ENFEEBLING_TOUCH, CardId.FEAR, CardId.LETHALITY, CardId.PARSE, CardId.SEANCE, CardId.SWEEPING_GAZE})
RETAINING_CARDS = RETAINING_CARDS | frozenset({CardId.ERADICATE, CardId.REAP, CardId.SACRIFICE, CardId.SOW, CardId.SPUR})
INNATE_CARDS = INNATE_CARDS | frozenset({})
ETERNAL_CARDS = ETERNAL_CARDS | frozenset({CardId.FORBIDDEN_GRIMOIRE})
OSTY_ATTACK_CARDS = frozenset({CardId.BONE_SHARDS, CardId.FETCH, CardId.FLATTEN, CardId.HIGH_FIVE, CardId.POKE, CardId.PROTECTOR, CardId.RATTLE, CardId.RIGHT_HAND_HAND, CardId.SIC_EM, CardId.SNAP, CardId.SQUEEZE, CardId.UNLEASH, CardId.SWEEPING_GAZE})      # CardTag.OstyAttack

UPGRADE_COST_CHANGE.update({CardId.CREATIVE_AI : -1, CardId.DOUBLE_ENERGY : -1, CardId.DUALCAST : -1, CardId.FERAL : -1, CardId.QUADCAST : -1, CardId.SIGNAL_BOOST : -1, CardId.SUBROUTINE : -1, CardId.TRASH_TO_TREASURE : -1, CardId.WHITE_NOISE : -1, CardId.ZAP : -1})
UPGRADE_BASE_COST.update({CardId.CREATIVE_AI : 3, CardId.DOUBLE_ENERGY : 1, CardId.DUALCAST : 1, CardId.FERAL : 2, CardId.QUADCAST : 1, CardId.SIGNAL_BOOST : 1, CardId.SUBROUTINE : 1, CardId.TRASH_TO_TREASURE : 1, CardId.WHITE_NOISE : 1, CardId.ZAP : 1})
# the Defect's keywords
EXHAUSTING_CARDS = EXHAUSTING_CARDS | frozenset({CardId.BOOT_SEQUENCE, CardId.CHILL, CardId.DOUBLE_ENERGY, CardId.FUSION, CardId.GENETIC_ALGORITHM, CardId.HOLOGRAM, CardId.HOTFIX, CardId.RAINBOW, CardId.REBOOT, CardId.SHATTER, CardId.SIGNAL_BOOST, CardId.SUPERCRITICAL, CardId.VOLTAIC, CardId.WHITE_NOISE, CardId.FUEL})
ETHEREAL_CARDS = ETHEREAL_CARDS | frozenset({CardId.ECHO_FORM, CardId.VOID})
INNATE_CARDS = INNATE_CARDS | frozenset({CardId.BOOT_SEQUENCE})
UNPLAYABLE_CARDS = UNPLAYABLE_CARDS | frozenset({CardId.VOID})
UPGRADE_REMOVED_KEYWORD.update({CardId.CHILL : 1, CardId.FUSION : 1, CardId.HOLOGRAM : 1, CardId.HOTFIX : 1, CardId.RAINBOW : 1, CardId.VOLTAIC : 1, CardId.ECHO_FORM : 2})
UPGRADE_KEYWORD.update({CardId.MACHINE_LEARNING : 4})

def _set_canonical_keywords():
    """CardModel.CanonicalKeywords, stored as a mask on each CardId member."""
    for card_id in CardId:
        card_id.keyword_mask = ((_EXHAUST if card_id in EXHAUSTING_CARDS else 0) | (_ETHEREAL if card_id in ETHEREAL_CARDS else 0)
                                | (_UNPLAYABLE if card_id in UNPLAYABLE_CARDS else 0) | (_RETAIN if card_id in RETAINING_CARDS else 0)
                                | (_INNATE if card_id in INNATE_CARDS else 0) | (_ETERNAL if card_id in ETERNAL_CARDS else 0)
                                | (_SLY if card_id in SLY_CARDS else 0))

_set_canonical_keywords()

ENCHANT_CORRUPTED_DAMAGE = 1.5

ENCHANT_INSTINCT_DAMAGE = 2.0

ENCHANT_CORRUPTED_HP_LOSS = 2

ENCHANT_SOWN_ENERGY = 1

ENCHANT_EMBER_DAMAGE = 3

SLITHER_MAX_COST = 3

# enchantments a play changes on the card: the card is played as a private copy (Card.create_copy shares nothing mutable)
CONSUMED_ON_PLAY = frozenset({EnchantmentId.SWIFT, EnchantmentId.SOWN, EnchantmentId.VIGOROUS})

CHANGED_ON_PLAY = CONSUMED_ON_PLAY | {EnchantmentId.MOMENTUM, EnchantmentId.GLAM, EnchantmentId.GOOPY}

_unknown_enchantments : set[str] = set()

_unknown_cards : set[str] = set()

# Quest cards (CardType.Quest, cost -1, Unplayable, MaxUpgradeLevel 0): in combat they do nothing, like a Wound (Spoils Map, Lantern Key, Byrdonis Egg
# and Dowsing act on the map, at events and at rest sites, which the campaign simulator models). They load as themselves (Card.create_quest).
QUEST_NAMES = {CardId.SPOILS_MAP: "Spoils Map", CardId.LANTERN_KEY: "Lantern Key", CardId.BYRDONIS_EGG: "Byrdonis Egg", CardId.DOWSING: "Dowsing"}
QUEST_CARDS = frozenset(cid.name for cid in QUEST_NAMES)
DOWSING_ROOMS = 5         # Dowsing.maxRooms: ? rooms entered with it in the deck before it becomes Abundance

# Mad Science: the riders Tinker Time offers for each card type, and (damage / block, rider numbers) the sim plays them with
MAD_SCIENCE_RIDERS = {"Attack": ("SAPPING", "VIOLENCE", "CHOKING"), "Skill": ("ENERGIZED", "WISDOM", "CHAOS"), "Power": ("EXPERTISE", "CURIOUS", "IMPROVEMENT")}
MAD_SCIENCE_DAMAGE, MAD_SCIENCE_BLOCK = 12, 8
MAD_SCIENCE_TEXT = (("weak", "SAPPING"), ("times", "VIOLENCE"), ("lose", "CHOKING"), ("strangle", "CHOKING"), ("energy", "ENERGIZED"), ("draw", "WISDOM"),
                    ("random", "CHAOS"), ("strength", "EXPERTISE"), ("dexterity", "EXPERTISE"), ("upgrade", "IMPROVEMENT"), ("cost", "CURIOUS"))


def mad_science_rider(description : str) -> str | None:
    """The rider of a Mad Science card the bridge showed, read from its text (the bridge has no field for it)."""
    text = description.lower()
    return next((rider for word, rider in MAD_SCIENCE_TEXT if word in text), None)


def keyword_mask(keywords) -> int:
    mask = 0
    for k in keywords:
        mask |= k.value
    return mask

CURSE_NAMES = {CardId.CURSE_OF_THE_BELL: "Curse of the Bell", CardId.ASCENDERS_BANE: "Ascender's Bane", CardId.POOR_SLEEP: "Poor Sleep",
               CardId.SPORE_MIND: "Spore Mind"}

_SCARF, _CHOKER, _AXE = RelicId.BRILLIANT_SCARF, RelicId.VELVET_CHOKER, RelicId.THROWING_AXE

###
### Helpers
###
