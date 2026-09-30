# AGENT NOTES: DumbBot (CITS3011)

Tested

Scenarios 1 and 2, 70 games each

## What it is (explained in my code as well)

A reflex agent. No search, no lookahead, no opponent modelling.

Three steps: score every province, blur those scores across the map, send each unit to the best square it can reach.

Overall, a simple agent that doesn't try anything clever but does the basics properly. Picked it because the simplicity fits the one second / 512MB / no-GPU restrictions, and because every decision it makes is explainable in the report.

## How it works 

Step 1 – `province_scores()`

Scores every province. Attack value if someone else holds a supply centre there. Defence value if it's ours and a big power is next door.

Power size is `c² + 4c + 16`, so a 17-centre leader scores 373 and a 1-centre straggler scores 21. Stealing from the strong is the whole idea.

Step 2 – `destination_values()`

Blurs those scores outward across the map graph, nine times.

This is what gives an agent with no lookahead a sense of direction. A unit sitting in dead space still feels a pull from a centre nine provinces away.

Note: armies and fleets move on different graphs, so `build_adjacency()` builds both. 6ms, once per game.

Note: Spring and Fall use different weights. Supply centres only change hands in Fall, so Fall wants to be ON a valuable province and Spring wants to be NEXT TO one. Two numbers swapped gives the bot a two-phase plan for free.

Step 3 – `movement_orders()`

Each unit takes the best destination it can reach, one unit per destination. Then two repair passes: add supports, redirect attacks that are going nowhere.

Note: retreats and builds are handled properly, not randomly. Forfeiting builds is a silent way to bleed units all game.

## Basic technique and citation

DumbBot. David Norman wrote it in two days in 2002 and twenty years of research papers still benchmark against it.

Formalised in: D. de Jonge, *Optimizing a Diplomacy Bot Using Genetic Algorithms*, MSc thesis, IIIA-CSIC / Universitat Autònoma de Barcelona, 2010.

**This citation has to be in the report.** Rubric Note [4] allows existing techniques but demands references. Implemented from the published description — no existing code reused.

## The flags

Every improvement sits behind a constructor flag so it can be switched off for ablation.

StudentAgent(use_diffusion=True, use_supports=True, use_redirect=True)

`use_diffusion` – proximity diffusion. A unit with nothing valuable next to it has no reason to prefer any direction. Blurring value outward gives it one, with no search.

`use_supports` – support coordination. Every unit has strength 1, so an unsupported attack on an occupied province can never win. Pairing an attacker with a supporter is the only way to dislodge anyone.

`use_redirect` – attack redirection. An unsupported attack on a defended province bounces every single turn. Without this, units lock into the same failed order for the entire game. This was the big one.

Note: do not delete any of these, even the ones we don't end up using. Rubric Note [7] requires all techniques to stay implemented in the submitted code.

Running an ablation:

from functools import partial
from agent_groupnumber import StudentAgent

no_diffusion = partial(StudentAgent, use_diffusion=False)
experiment(player_agent=no_diffusion, opponent_agent_pool=[StaticAgent], repeat_nums=20)


## What's still missing

A third new technique. The spec wants three, i only made two.

The obvious candidate is opponent modelling. `update_game(all_power_orders)` receives every power's orders every turn, so hostility is inferable from observation alone. Track who's been attacking our centres, decay it over time, scale the attack and defence values by it. Should be directly measurable against AttitudeAgent since its attitudes genuinely change mid-game.

## Weak spots

No convoy logic at all. Convoy orders get filtered out in `movement_orders()`. England and Italy suffer most.

Turkey is the weakest power in Scenario 1 (90% wins against 100% for everyone else). Worth a look at what it's doing differently.

Austria is the weakest in Scenario 2 (9.77 SCs). Probably just the natural shit position rather than a bug. Austria borders four hostile powers and has an indefensible home triangle.

No stalemate-line awareness. The agent evaluates on centre count and proximity only, so it can't tell a winnable position from an unwinnable one.

## Todo list ->

- Update the imports in `test.py` **and** `visualize.py`
- All four `@timeout_decorator.timeout(1)` decorators present and uncommented. They work on WSL/Linux, they don't work on native Windows
- Agent file under 100KB (currently 16KB i think)
- Report is PDF, four pages max, group number and every member's full name and student number with DumbBot / de Jonge citation in the report

## Overall

Full marks on both testable scenarios from an agent that never thinks ahead.

Knowing what you want and knowing what you can get are separate problems. Heuristic agents almost always fail at the second one.
