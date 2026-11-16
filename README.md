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

(Out of combat) — `scripts/agents/deck_eval/`

Every out-of-combat choice is made by playing the candidates on the same simulated "walks" through the rest of the act (`route_sim.py`: the engine's
run simulator, fights played by the rollout policy, rewards / rest sites / shops / events as the engine does them) and comparing them walk by walk.

- Map: walks the candidate paths and keeps the best (`path_search.py`, ranked first by the node scores in `agents/pathing.py`).
- Card rewards: each card vs skipping (`card_reward_chooser.py`), plus a hand-set bonus for late-paying engine cards (`prospect.py`, `prospective_cards.csv`).
- Rest sites and upgrades (`upgrade_chooser.py`), shops (`shop_chooser.py`), events (`event_chooser.py`), ancients' relics (`ancient_chooser.py`).
- All tuning knobs (time budgets, thresholds, walk scoring) live in `DeckEvalConfig` (`config.py`): `MyAgent(deck_config=DeckEvalConfig().tuned(path_seconds=4))`,
  or `--deck path_seconds=4` on `python -m benchmarks.runs run`.
- The rollout policy's fights are corrected towards what the MCTS would get with a table fitted by `python -m benchmarks.policy_fit fit --write`
  (`policy_correction.json`).

## known issues:

- Enthralled, Splash, and Strategem not implemented.

# TODO :

## sts_lite (slay the spire II headless imitator)

Card pools (multiplayer ignored)
 - [x] Colourless
    Not implemented:
    - Strategem (Sim doesnt have events in between turns)
    - Splash (need other character card pools)
 - [x] Curse
    Not implemented:
    - Enthralled (Enforcing play order not implemented in engine)
 
 - [X] Status
 - [X] Ancient
 - [x] Ironclad
 - [ ] Silent
 - [ ] Necrobinder
 - [ ] Regent
 - [ ] Defect

Other features:
 - [x] In-combat relics
 - [x] Potions
 - [x] Enchantments
 

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

 
 Waiting on engine:
 - [x] Potion use
 - [ ] end of act healing. Not strictly neccesarry. Most hp is still best

 ## Out of combat actions
 - [x] Map, card rewards, rest sites, shops, events, ancients (walk-based, see above)
 - [ ] Value boss survival properly in the walk score (a boss death currently costs only the rooms left in the act + 3 lookahead rooms)
 - [ ] Look further than one act (a learned run-value estimate at the end of a walk)
