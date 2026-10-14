# Schridinger's Maze

**A maze that watches you, guesses where you're going, and moves its own walls to stop you.**

Uses a few algorithms and Python.

---

## How it works

You're in a maze with 3 doors. One is real, two are fake, and they all look the same.
The maze tracks how you move, guesses which door you want, and seals the path to it.

The paths are sealed in a way that there is still exactly one route you can take to beat it. 
But that route wont be comfortable.
---

## How it thinks: four characters

| Name | What it does | One-liner |
|---|---|---|
| **Mind Reader** | Guesses which door you want | "Where is this player going?" |
| **Counterplanner** | Finds the wall that hurts that route most | "What do I block?" |
| **Reality Bender** | Rejects any unfair change | "Is that block allowed?" |
| **Patient One** | Decides when to act | "Is now the moment to block?" |

Every time you take a step, they run in that order. Then, a warning tile shows
up, and the wall lands.

---

## What is BFS

BFS = "breadth-first search". Imagine pouring water into the maze at one tile. It
spreads one step at a time, so the first time it hits any tile is the shortest route.

```
distance(start) = 0
every tile touching a tile at distance d  ->  distance d + 1
```

That gives us real walking distance (through corridors, not walls).

---

## 1. Mind Reader: "which door?"

For each door, every step you take gets you either closer or farther from a certain door:

```
delta = (distance to door before your step) - (distance to door after)      always +1 or -1
```

Add up your last 30 steps, newest counting most:
```
score(door) = sum of  0.85^age x delta          (age 0 = your latest step)
```

the ^age part makes sure that your most recent steps contribute a lot more than what step you took, say
20 moves ago. You couldve targeted a different door in move 20, that change matters.

Turn scores into percentages (softmax):

```
belief(door) = e^(0.8 x score) / (sum of the same over all doors)
```

Softmax returns an array of the raw scores converted into a probability. all the values in that array
after softmax sums up to 1.

Highest belief = **top** = the door it thinks you want.

> **Why 0.85?** It's the weakness on purpose. The maze forgets slowly, so if you walk
> toward a door for 8 steps, it's ~100% sure. 

**How sure is it?** (confidence)

```
target_conf = (belief_top - 1/k) / (1 - 1/k)        k = doors left; this makes "just guessing" = 0
habit_conf  = (times you did the usual follow-up / times it saw this pattern) x min(1, times seen / 4)
confidence  = 0.65 x target_conf + 0.35 x habit_conf
```

So: 65% "I know your door", 35% "you're predictable".

I made the "knowing which door" part matter more because in a real life scenario, if you were someone blocking another person in a maze you created, even you'd think of trying to figure out which door theyre gonna be headed towards first before anything.

### The habit part (a tiny Markov chain)

A markov chain, simply put, is a mathematical function that takes the last "n" moves to predict what your n+1th move would be

I am using a 2 order Markov chain here. Lets say we want to predict a specific outcome "X" at time "t".
A 2nd order markov chains predicts by looking back at the states X(t-1) and X(t-2)

This one ignores doors completely. It only looks at your **move letters**: `U D L R`,
for your last 30 steps. The idea: *what you did last time in this situation is what you'll
probably do again.*

1. Take your last **two** moves, like `R R`.
2. Look back through your last 30 moves for other times you did `R R`.
3. Count what came right after each one.

Example: your moves are `R R D R R D R R`. You just did `R R` again. Last two times you
did `R R`, you went `D` both times, so it expects `D`:

```
habit_conf = (2 / 2) x min(1, 2 / 4) = 0.5
```

- The `(2 / 2)` part is "how consistent you are".
- The `min(1, seen / 4)` part is a **small-sample penalty**. Two examples isn't enough
  to be sure, so it can't hit full confidence until it has seen the pattern 4 times.
- Unlike the door score, there's **no fading** here. A habit from 25 moves ago counts the
  same as one from 3 moves ago. Moves just fall off the end after 30.

**Why only 35% of confidence?** Habits tell the maze *how* you walk, not *where* you're
going, so the door guess matters more. But it's the part you can beat for free: just
mix up your moves and it stays low.

Honest detail: the model also guesses your next move (`D` above), but nothing uses that
guess. Only the confidence number matters.

## 2. Counterplanner: "what to block?"

Think of it as a bruteforce mechanism that tries every single potential block on your path to find the best fit.

1. **Get your route.** one BFS runs from your tile to `top` (the door Mind Reader picked, which
   is not necessarily the real exit). That gives the route tile by tile, and its length, lets 
   call it `old`.
2. **List the candidates.** Every **doorway tile** on that route (the gap between two
   rooms, the only kind of tile it's allowed to seal, so the maze stays tidy and still solvable). Skip any
   that are within 3 steps of you, a door, changed in the last 10 turns, or already pending to be changed.
3. **Simulate each one.** Seal it fr (in memory), run **two** BFS searches, undo it:
   - **BFS #1: you -> `top`.** This is the score:
     ```
     gain = (new BFS distance to top) - old        (20 if the seal cuts top off completely)
     ```
   - **BFS #2: you -> the real exit.** Not for scoring, only so the referee can check the
     seal is fair (exit still reachable, not too far).
4. **Sort the results.** gain of 0 or less gets dropped immediately. Positive gain seals get put in a santa's good list, while the ones that cut you off completely get put in the bad list.
5. **Rescue the blocked ones.** For up to 4 blocked seals in the bad list, pick up to 20 nearby walls to
   **open at the same time**. That's a *reroute*: block your path, but give you a longer way
   around. The walls are picked **at random** from a box 8 tiles around the seal, so BFS
   doesn't *find* the openings, it only **scores** them: the same two searches as step 3,
   and the pair must be legal with positive gain. (Worst case: 4 x 20 x 2 = 160 BFS runs.)
6. **Pick one.** Highest gain wins, ties broken randomly (seeded, so it's repeatable). Only
   that single change goes back to Patient One.

Tiny example: your route to `top` is 40 steps.

| Try | New route | Gain | Verdict |
|---|---|---|---|
| Seal tile A (corridor, no alternative) | 70 | 30 | great, but it'd trap you, so it goes to the blocked pile |
| Seal tile B (right next to a loop) | 44 | 4 | legal, small hit |
| Seal A + open a wall nearby (reroute) | 62 | 22 | legal, exit still reachable, wins |

## 3. Reality Bender: the "never unfair" rules

A change is rejected if it would:

- make the real exit **unreachable**
- push the real exit past **3x** the original shortest path
- leave the exit farther than **(moves left - 12)**
- touch a tile within **3 steps of you**, or one changed in the last **10 turns**
- touch a **door**

Checked once when chosen, and **again right before it lands**.

## 4. Patient One: "is now the moment?"

It hoards. First it's only allowed to act if: turn 15+, it has a charge, nothing is
already pending, and 8+ turns since the last change. Then:

```
bonus       = clamp(1 + (1 - dist_to_top_now / dist_to_top_at_start), 1, 2)
opportunity = confidence x gain x bonus
threshold   = max(2, 10 - 0.2 x turns_since_last_change)
fire if opportunity > threshold
```

Sure + big hit + you're close to a door = fire. The bar drops while it waits, so it
gets impatient. After firing, it resets.

---

## Charges (the maze's ammo)

Charges are the maze's stamina to close walls. Depending on the difficulty, charges are replenished.

The maze gets a fixed bonus charge if you step on a fake door, too.

---

## Why it's always beatable (the part judges like)

**On a clock** (default). A change is only allowed if your real route still fits in
`moves_left - 12`. Walk the shortest route and you lose one move *and* the route gets
one shorter, so that margin never shrinks. No number of changes can run you out of time.

**No clock** (`--infmoves`). Regen alone could stall you forever, so there's a credit
system. Each turn the maze earns some credit. A change costs credit equal
to how many steps longer it makes your route, and it can't overspend:

```
total setback by turn T  <=  starting credit + creds x T
you walk 1 step per turn, it claws back < 1 per turn, so you arrive by:

turns  <=  base_len x (1 + 1.0) / (1 - creds)
```

**Fake doors shimmer** - Randomly, doors that are fake shimmer. They first shimmer at 50 moves, then shimmer after a certain number of moves is completed. this is controlled by a multiplier that increases the moves value. So if you look hard enough, you can identify which doors are fake. Not available in hard or brutal difficulty.

---

## How you beat it

- **Bluff.** Walk toward a door for a while, then double back. The maze wastes charges.
- **Watch for tells.** On easy and normal, a fake door occasionally **shimmers** (the
  gaps grow: 50, 65, 84, 110... steps). The real door never does.

---

## Run it

```
python game.py                                 # menu picks difficulty
python game.py --difficulty hard               # easy | normal | hard | brutal
python game.py --nofog --infmoves              # see everything, no move limit
python game.py --seed 1234                     # replay a maze
```

Python 3.8+, a terminal at least 80x24. On Windows: `pip install windows-curses`.
Move with WASD or arrows, `q` to quit.

---

Thats it!!