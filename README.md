

# Agent for Slay the Spire 2.

### DISCLAIMER : Claude Sonnet 5.5 and Opus 5.5 were used for bug-fixing, writing sts2_lite (from decompiled sts2 code), and Test suites.

## REFERENCES:

https://github.com/HKUDS/CLI-Anything/blob/main/skills/cli-anything-slay-the-spire-ii/SKILL.md -> Used for command line interface with STS2
    changes: 
    - added relic "status" field to state ouput
    - changed draw pile, discard pile, and exhaust pile to have full card information
    - expose various extra fields such as active, spent, cardsPlayedThisTurn, etc, for important relic functionality
    - reads and exposes the enemy move id, on top of the intent.

https://github.com/zhiyue/sts2-rl-agent -> headless sts2_env used for cross-referencing game behaviour

https://int8.io/monte-carlo-tree-search-beginners-guide/ -> used as reference for initial MCTS implementation

# Potential resources:

https://simthespire.wordpress.com/ -> Massive dataset of fights (expected damage, good cards to take, etc.. )



## Current functionality:

(In combat)

- Runs a monte-carlo-tree-search on card actions determining the best current action, using a sts2_lite simulator. 
- Uses deterministic and sampled non-deterministic nodes. 
- Uses rollout of play first card in hand
- Uses current_hp as rollout score

(Out of combat)

No functionality

## known issues:

- Enthralled, Splash, Strategem, and Alchemize not implemented.
- Ovicopter crash (unreproducable)

# TODO :

## STS2_Lite

Add Enemy Ais (Currently assumes enemy will make the same move when looking ahead)
 - [x] Act 1 Overgrowth
 - [ ] Act 1 Underdocks
 - [x] Act 2
 - [ ] Act 3

Card pools (multiplayer ignored)
 - [x] Colourless
    Not implemented:
    - [ ] Strategem (Sim doesnt have events in between turns)
    - [ ] Splash (need other character card pools)
    - [ ] Alchemize (potions not modeled yet)
 - [x] Curse
    Not implemented:
    - [ ] Enthralled (Enforcing play order not implemented in engine)
 
 - [ ] Status
 - [ ] Ancient
 - [x] Ironclad
 - [ ] Silent
 - [ ] Necrobinder
 - [ ] Regent
 - [ ] Defect


Add In-combat relics
 - [x]
    - Missing:
    - Potion relics

Add potions
 - [ ]

Add enchantments
 - [ ]

 ## MCTS :

 - [x] Rollout policies
 - [x] Enhanced rollout policies
 - [x] Time based max search rather than branch limit
 - [x] Optimize outcome scoring function
 - [x] Confidence exit (If the agent is confident enough in a move, finish the search)
 - [x] Transposition table
 - [x] Information preference (The agent should prioritize learning the outcome of random events e.g. draws, to perform subsequent moves with more information)
 - [x] Better outcome scoring 
 - [X] Concurrent search caching
 - [x] Identical move culling
 - [x] Benchmark harness. Create a fixed set of fights to play, use this to fine tune constants.
 - [ ] Improve sim speed
 - [ ] Root parallelization
 - [ ] Neural network rollout policy

 
 Waiting on engine:
 - [ ] Potion use
 - [ ] end of act healing

 ## Out of combat actions
 - Needs to be addressed
