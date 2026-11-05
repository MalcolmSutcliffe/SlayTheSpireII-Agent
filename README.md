

# Agent for Slay the Spire 2.

### DISCLAIMER : Claude Sonnet 5.5 was used for bug-fixing, writing sts2_lite (from decompiled sts2 code), and Test suites.

## REFERENCES:

https://github.com/zhiyue/sts2-rl-agent -> headless sts2_env was used for cross-referencing
https://int8.io/monte-carlo-tree-search-beginners-guide/ -> used as reference for initial MCTS implementation
https://github.com/HKUDS/CLI-Anything/blob/main/skills/cli-anything-slay-the-spire-ii/SKILL.md -> Used for command line interface with STS2 (updated for newest version)


## Current functionality:

(In combat)

- Runs a monte-carlo-tree-search on card actions determining the best current action, using a sts2_lite simulator. 
- Uses deterministic and sampled non-deterministic nodes. 
- Uses rollout of play first card in hand
- Uses current_hp as rollout score

(Out of combat)

No functionality

# TODO :

## STS2_Lite

Add Enemy Ais (Currently assumes enemy will make the same move when looking ahead)
 - [x] Act 1 Overgrowth
 - [ ] Act 1 Underdocks
 - [ ] Act 2
 - [ ] Act 3
 - + Many more

Card pools (multiplayer ignored)
 - [ ] Colourless
 - [ ] Status
 - [ ] Ancient
 - [x] Ironclad
 - [ ] Silent
 - [ ] Necrobinder
 - [ ] Regent
 - [ ] Defect


Add In-combat relics
 - [ ]

Add potions
 - [ ]

 ## MCTS :

 - Better rollout policy 
 - Better outcome scoring 
 - Concurrent search caching
 - Identical move culling
 - Better node traversal heuristics (i.e. powers/non-starter cards first,)
 - Gimme move culling (i.e if fight ends with one card play dont waste time searching deep : consider meta-scaling)
 - Potion use
 - end of act healing

 ## Out of combat actions
 - Needs to be addressed
