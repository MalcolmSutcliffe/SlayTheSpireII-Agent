# Agent for Slay the Spire 2.

### DISCLAIMER : Claude Sonnet 5.5 and Opus 5.5 were used for writing sts2_lite (from decompiled sts2 code), Test suites, bug-fixing, and code refactoring.

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
- Various rollout policies
- Outcome score based on current HP for a win, prefering less turns. + large bonus for win (agent should always prefer win over loss)
- On a loss, the outcoume is scored based on how close the enemy was to dying.
- All enemy attack patterns modeled in engine.

(Out of combat)

 - Pathing: Heuristic node score, finds maximal path
 - Card choice: simulates from upcoming act pool of fights with mutated deck to decide which card has highest value
 - Events: random choice
 - Shops: buys relics first, then potions (if elite is coming up), then cards using mutated simulator
 - Rest sites: If above 80% hp: upgrade, otherwise simulate combats until next rest site. If it survives 80%+ of the time, upgrade, otherwise rest.

## known issues:

- Enthralled, Splash, and Strategem not implemented.
- Kaleidoscope, sea Glass, Prismatic gem, Question card, Busted crown not implemented fully
- the divine event

# TODO :

## sts_lite (slay the spire II headless imitator)

 - [X] Status
 - [X] Ancient
 - [x] Ironclad
 - [ ] Silent
 - [ ] Necrobinder
 - [ ] Regent
 - [ ] Defect


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
 - [x] Tied move paired RNG rollout decision (if two moves are tied at the end of search, use seeded rng to minimize noise between them)
 - [x] Check card order permuatations under stricter bounds to differentiate small differences in turn order
 - [ ] Improve sim speed
 - [ ] Root parallelization
 - [ ] Neural network rollout policy
 - [x] Seeded rollouts to reduce noise
