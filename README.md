

# Agent for Slay the Spire 2.

## Current functionality:

(In combat)

Runs a monte-carlo-tree-search on card actions determining the best current action, using a sts2_lite simulator

(Out of combat)

No functionality

# TODO:

## STS2_Lite

Refactor code with event manager "hooks"
 - Make sure when copied, the event system is distinct

Hooks:
 - [ ] HP lost
 - [ ] HP lost on turn
 - [ ] Creature killed
 - [ ] Creature attacked
 - [ ] Card played
 - [ ] Skill played
 - [ ] Power played
 - [ ] Attack played
 - ... 

Add Enemy Ais (Currently assumes enemy will make the same move when looking ahead)
 - [ ] FUZZY_WURM_CRAWLER
 - [ ]SHRINKER_BEETLE
 - [ ] NIBBIT
 - [ ] TWIG_SLIME_(S)
 - [ ] TWIG_SLIME_(M)
 - [ ] ACID_SLIME_(S)
 - [ ] ACID_SLIME_(M)
 - + Many more

Add full Ironclad card pool
 - [ ] AGGRESSION
 - [x] ANGER
 - [ ] ARMAMENTS
 - [ ] ASHEN_STRIKE
 - [ ] BARRICADE
 - [x] BASH
 - [ ] BATTLE_TRANCE
 - [x] BLOOD_WALL
 - [ ] BLOODLETTING
 - [x] BLUDGEON
 - [x] BODY_SLAM
 - [ ] BRAND
 - [ ] BREAK
 - [x] BREAKTHROUGH
 - [ ] BULLY
 - + ...


Add In-combat relics
- ...