# --- World ---
MAZE_W = 19            # rooms across  (grid is 2*W+1 wide)
MAZE_H = 9             # rooms down    (grid is 2*H+1 tall)
LOOP_DENSITY = 0.10    # fraction of remaining walls knocked out to create loops
DECOY_SHIMMER = True   # slow-burn hint: a random live decoy shimmers now and then (easy/normal only)
SHIMMER_START = 50     # first shimmer after this many steps
SHIMMER_GROWTH = 1.3   # each gap is this many times longer than the last (50, 65, 84, 110, ...)
SHIMMER_DURATION = 8   # how many turns a shimmer lasts
NUM_DOORS = 3          # one real, the rest decoys
FOG_OF_WAR = True      # False = whole maze always visible (also: python game.py --nofog)
VISION_RADIUS = 6      # in grid tiles, with line of sight
INFINITE_MOVES = False # True = no move limit (also: python game.py --infmoves)
MOVE_LIMIT_MULT = 4.5  # move limit = this * starting shortest path (2.5 is brutal in fog; see simulate.py)

# --- Mind Reader ---
HISTORY_LEN = 30       # moves remembered
RECENCY_DECAY = 0.85   # weight = decay ** age  (this is the exploitable bit)
SOFTMAX_BETA = 0.8     # sharpness of target belief

# --- Reality Bender (hard rules) ---
RACE_CHANCE = 0.35     # chance the maze's next change is a close "race" strike you can beat
                       # by running (0 = never). The real share is a bit lower, see README.
MIN_PLAYER_DIST = 3    # never alter cells within this Manhattan distance of player
CELL_COOLDOWN = 10     # turns before a cell can be mutated again
DETOUR_CAP_MULT = 3.0  # real-exit path may never exceed this * original shortest
MOVE_MARGIN = 12       # real exit must stay reachable within (moves left - this)
UNREACHABLE_GAIN = 20  # gain credited when a mutation fully cuts off the predicted target

# --- Patient One ---
MUTATION_BUDGET = 10   # starting charges (regen refills up to this, never beyond)
REGEN_INTERVAL = 20    # +1 charge every this many turns while below budget (0 = off)
SETBACK_RATE = 0.5     # infinite-moves guarantee: the maze earns this many steps of
                       # "setback credit" per turn (must be < 1 so you out-walk it)
SETBACK_START = 1.0    # starting credit, in multiples of the shortest path
SETBACK_CAP = 1.5      # most credit it can bank, in multiples of the shortest path
DECOY_CHARGE = 1       # charges the maze gains when you trip a decoy
COOLDOWN = 8           # min turns between mutations
GRACE = 15             # no mutations before this turn
TELEGRAPH_DELAY = 2    # turns of warning before a mutation lands
THRESH_START = 10.0    # opportunity needed right after firing (or at game start)
THRESH_DECAY = 0.2     # threshold drops this much per turn of waiting (impatience)
THRESH_MIN = 2.0       # impatience floor

# --- Taunts ---
TAUNT_COOLDOWN = 30


# --- Difficulty presets ---
# Each preset overrides the constants above. "normal" is the tuned default.
DIFFICULTIES = {
    "easy": dict(DECOY_SHIMMER=True, SETBACK_RATE=0.3, REGEN_INTERVAL=30, MOVE_LIMIT_MULT=6.0, VISION_RADIUS=8, MUTATION_BUDGET=6, DECOY_CHARGE=0,
                 GRACE=25, COOLDOWN=12, TELEGRAPH_DELAY=3,
                 THRESH_START=14.0, THRESH_DECAY=0.15, THRESH_MIN=3.0,
                 RECENCY_DECAY=0.80),
    "normal": dict(DECOY_SHIMMER=True, SETBACK_RATE=0.5, REGEN_INTERVAL=20, MOVE_LIMIT_MULT=4.5, VISION_RADIUS=6, MUTATION_BUDGET=10, DECOY_CHARGE=1,
                   GRACE=15, COOLDOWN=8, TELEGRAPH_DELAY=2,
                   THRESH_START=10.0, THRESH_DECAY=0.2, THRESH_MIN=2.0,
                   RECENCY_DECAY=0.85),
    "hard": dict(DECOY_SHIMMER=False, SETBACK_RATE=0.6, REGEN_INTERVAL=15, MOVE_LIMIT_MULT=3.5, VISION_RADIUS=5, MUTATION_BUDGET=12, DECOY_CHARGE=1,
                 GRACE=10, COOLDOWN=6, TELEGRAPH_DELAY=2,
                 THRESH_START=8.0, THRESH_DECAY=0.25, THRESH_MIN=1.5,
                 RECENCY_DECAY=0.90),
    "brutal": dict(DECOY_SHIMMER=False, SETBACK_RATE=0.7, REGEN_INTERVAL=10, MOVE_LIMIT_MULT=3.0, VISION_RADIUS=4, MUTATION_BUDGET=14, DECOY_CHARGE=2,
                   GRACE=8, COOLDOWN=5, TELEGRAPH_DELAY=1,
                   THRESH_START=6.0, THRESH_DECAY=0.3, THRESH_MIN=1.0,
                   RECENCY_DECAY=0.92),
}
DIFFICULTY_BLURBS = {
    "easy":   "long clock, wide vision, shimmering decoys, a slow and forgetful maze",
    "normal": "the tuned default, with the occasional shimmering decoy",
    "hard":   "short clock, narrow vision, a faster maze that remembers more",
    "brutal": "1-turn warnings, tiny vision, +2 per decoy, a long-memory maze",
}


def apply_difficulty(name):
    """Override the constants above with a preset. Call before creating a Game."""
    globals().update(DIFFICULTIES[name])