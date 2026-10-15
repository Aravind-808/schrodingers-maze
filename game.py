import argparse
import curses
import datetime
import locale
import math
import time

import config as cfg
from engine import Game

UNI = dict(wall="██", floor="· ", blank="  ", door="E ", me="@ ", tele="▒▒",
           walked="●", thought="○", both="◆", on="■", off="□", shimmer="≈ ")
ASC = dict(wall="##", floor=". ", blank="  ", door="E ", me="@ ", tele="%%",
           walked="*", thought="+", both="X", on="#", off="-", shimmer="~ ")

KEYS = {
    ord("w"): "U", ord("W"): "U", curses.KEY_UP: "U",
    ord("s"): "D", ord("S"): "D", curses.KEY_DOWN: "D",
    ord("a"): "L", ord("A"): "L", curses.KEY_LEFT: "L",
    ord("d"): "R", ord("D"): "R", curses.KEY_RIGHT: "R",
}

INTRO = [
    "S C H R O D I N G E R ' S   M A Z E",
    "",
    "You are lost in a maze that is watching you.",
    "",
    "  - Three doors marked E. One is real. Two are decoys.",
    "  - The maze predicts where you're headed and rewrites itself to block you. Good luck :3",
    "",
    "Move: WASD / arrows      Quit: q",
    "",
    "Press any key.",
]


def put(win, y, x, s, attr=0):
    try:
        win.addstr(y, x, s, attr)
    except curses.error:
        pass


def init_attrs():
    a = dict(wall=0, floor=0, door=curses.A_BOLD, me=curses.A_BOLD, tele=curses.A_BOLD,
             mem=0, taunt=curses.A_BOLD, hud=0)
    if not curses.has_colors():
        return a
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = 0
    for i, fg in enumerate([curses.COLOR_WHITE, curses.COLOR_YELLOW, curses.COLOR_GREEN,
                            curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_BLUE,
                            curses.COLOR_MAGENTA], 1):
        curses.init_pair(i, fg, bg)
    cp = curses.color_pair
    a.update(wall=cp(1), floor=cp(2), door=cp(3) | curses.A_BOLD, me=cp(4) | curses.A_BOLD,
             tele=cp(5) | curses.A_BOLD, mem=cp(6), taunt=cp(7) | curses.A_BOLD)
    return a


def draw(scr, g, gl, at):
    scr.erase()
    H, W = scr.getmaxyx()
    gh, gw = len(g.grid), len(g.grid[0])
    if H < gh + 4 or W < gw * 2 + 1:
        put(scr, 0, 0, "Terminal too small: need %dx%d (have %dx%d). Resize..." % (gw * 2 + 1, gh + 4, W, H))
        scr.refresh()
        return
    put(scr, 0, 1, "SCHRODINGER'S MAZE  [%s]" % getattr(g, "difficulty", "normal").upper(), at["taunt"])
    put(scr, 0, W - 27 if W > 60 else 30, "WASD/arrows move   q quit"[:26], at["hud"])
    tele = g.visible_telegraphs()
    shim = g.shimmering_pos()
    phase = int(time.time() * 4) % 2      # flips 4x a second
    for y in range(gh):
        for x in range(gw):
            p = (x, y)
            if p == g.player:
                s, a = gl["me"], at["me"]
            elif p in tele:
                s, a = gl["tele"], at["tele"]
            elif p in g.visible:
                if g.grid[y][x]:
                    s, a = gl["wall"], at["wall"]
                elif g.door_at(p):
                    if p == shim and phase:
                        s, a = gl["shimmer"], at["taunt"]   # decoy tell: flickers E <-> ~
                    else:
                        s, a = gl["door"], at["door"]
                else:
                    s, a = gl["floor"], at["floor"]
            else:
                k = g.known[y][x]
                if k is None:
                    continue
                s = gl["wall"] if k == "#" else gl["door"] if k == "E" else gl["floor"]
                a = at["mem"]
            put(scr, 1 + y, x * 2, s, a)

    base = 1 + gh
    c = g.charges
    energy = gl["on"] * min(c, 14) + gl["off"] * max(0, cfg.MUTATION_BUDGET - c)
    conf = g.mind.pred.confidence if g.mind.pred else 0.0
    n = int(round(conf * 10))
    susp = gl["on"] * n + gl["off"] * (10 - n)
    moves = "inf" if math.isinf(g.moves_left) else "%3d" % g.moves_left
    put(scr, base, 1, "Moves %3s   Doors %d   Maze energy %s (%d)   Suspicion %s" % (
        moves, len(g.alive_doors()), energy, c, susp), at["hud"])
    if tele:
        put(scr, base + 1, 1, "the walls are shifting...", at["tele"])
    msg = g.current_message()
    if msg:
        put(scr, base + 2, 1, '"%s"' % msg, at["taunt"])
    scr.refresh()


def banner(scr, lines, at):
    H, W = scr.getmaxyx()
    top = max(0, H // 2 - len(lines) // 2)
    for i, line in enumerate(lines):
        put(scr, top + i, max(0, (W - len(line)) // 2), line, at["taunt"])
    scr.refresh()


LEVELS = ["easy", "normal", "hard", "brutal"]

SETUP_ROWS = [
    ("Difficulty", "difficulty"),
    ("Move limit", "infmoves"),
    ("Fog of war", "fog_off"),
    ("Maze", "daily"),
    ("Characters", "ascii"),
]
ENTER_KEYS = (10, 13, curses.KEY_ENTER)
QUIT_KEYS = (ord("q"), ord("Q"), 27)


def setup_value(st, key):
    if key == "difficulty":
        return st["difficulty"].upper()
    if key == "infmoves":
        return "UNLIMITED" if st["infmoves"] else "LIMITED (clock)"
    if key == "fog_off":
        return "OFF" if st["fog_off"] else "ON"
    if key == "daily":
        return "DAILY" if st["daily"] else "RANDOM"
    return "ASCII (safe)" if st["ascii"] else "UNICODE"


def setup_help(st, key):
    if key == "difficulty":
        p = cfg.DIFFICULTIES[st["difficulty"]]
        return ["%s." % cfg.DIFFICULTY_BLURBS[st["difficulty"]].capitalize(),
                "Move limit %.1fx the shortest path, sight %d tiles, maze starts with %d charges."
                % (p["MOVE_LIMIT_MULT"], p["VISION_RADIUS"], p["MUTATION_BUDGET"])]
    return {
        "infmoves": ["LIMITED: you lose if you run out of moves.",
                     "UNLIMITED: no clock. The only way to lose is quitting."],
        "fog_off": ["ON: you only see nearby tiles, and your map can go stale.",
                    "OFF: you see the whole maze (the doors still look identical)."],
        "daily": ["RANDOM: a fresh maze every game.",
                  "DAILY: everyone who plays today gets the same maze."],
        "ascii": ["UNICODE: nicer blocks and symbols.",
                  "ASCII: pick this if the blocks look like garbage."],
    }[key]


def cycle(st, key, step):
    if key == "difficulty":
        st["difficulty"] = LEVELS[(LEVELS.index(st["difficulty"]) + step) % len(LEVELS)]
    else:
        st[key] = not st[key]


def setup_menu(scr, at, st):
    """Arrow-key settings screen. Returns the chosen settings, or None to quit."""
    sel = 0
    while True:
        scr.erase()
        H, W = scr.getmaxyx()
        x0 = max(0, (W - 56) // 2)
        y = max(0, (H - 17) // 2)
        put(scr, y, x0, "S E T U P", at["taunt"])
        for i, (label, key) in enumerate(SETUP_ROWS):
            marker = "> " if i == sel else "  "
            line = "%s%-12s < %s >" % (marker, label, setup_value(st, key))
            put(scr, y + 2 + i, x0, line.ljust(56), curses.A_REVERSE if i == sel else at["hud"])
        for j, text in enumerate(setup_help(st, SETUP_ROWS[sel][1])):
            put(scr, y + 9 + j, x0, text[:W - x0 - 1], at["floor"])
        put(scr, y + 12, x0, "ENTER = start the game", at["taunt"])
        put(scr, y + 14, x0, "Up/Down: choose   Left/Right: change   1-4: difficulty   q: quit"[:W - x0 - 1], at["hud"])
        scr.refresh()
        k = scr.getch()
        if k in QUIT_KEYS:
            return None
        if k in ENTER_KEYS:
            return st
        if k in (curses.KEY_UP, ord("w"), ord("W")):
            sel = (sel - 1) % len(SETUP_ROWS)
        elif k in (curses.KEY_DOWN, ord("s"), ord("S")):
            sel = (sel + 1) % len(SETUP_ROWS)
        elif k in (curses.KEY_LEFT, ord("a"), ord("A")):
            cycle(st, SETUP_ROWS[sel][1], -1)
        elif k in (curses.KEY_RIGHT, ord("d"), ord("D"), ord(" ")):
            cycle(st, SETUP_ROWS[sel][1], +1)
        elif ord("1") <= k <= ord("4"):
            st["difficulty"] = LEVELS[k - ord("1")]


def describe(st):
    return "%s, %s moves, fog %s%s" % (
        st["difficulty"], "unlimited" if st["infmoves"] else "limited",
        "off" if st["fog_off"] else "on", ", daily maze" if st["daily"] else "")


def start_game(st, args):
    """Apply the chosen settings to the config and create the game."""
    cfg.apply_difficulty(st["difficulty"])
    cfg.INFINITE_MOVES = st["infmoves"]
    cfg.FOG_OF_WAR = not st["fog_off"]
    seed = int(datetime.date.today().strftime("%Y%m%d")) if st["daily"] else args.seed
    g = Game(seed, args.w, args.h)
    g.difficulty = st["difficulty"]
    g.settings = describe(st)
    return g


def play(scr, g, gl, at):
    """One game. Returns "again" if the player wants another, else "done"."""
    while True:
        draw(scr, g, gl, at)
        scr.timeout(250 if g.shimmering_pos() else -1)   # keep redrawing only while something shimmers
        k = scr.getch()
        if k == -1:
            continue
        if k in QUIT_KEYS:
            g.status = "quit"
            return "done"
        if k in KEYS:
            g.step(KEYS[k])
            if g.status in ("won", "lost"):
                scr.timeout(-1)
                draw(scr, g, gl, at)
                if g.status == "won":
                    lines = ["  YOU ESCAPED  ", "  the maze never saw it coming  "]
                else:
                    lines = ["  THE MAZE WINS  ", "  you ran out of moves  "]
                banner(scr, lines + ["", "  R = play again    any other key = see your results  "], at)
                return "again" if scr.getch() in (ord("r"), ord("R")) else "done"


def run(scr, args, out):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    scr.keypad(True)
    at = init_attrs()
    scr.erase()
    banner(scr, INTRO, at)
    scr.getch()
    st = dict(difficulty=args.difficulty or "normal", infmoves=args.infmoves,
              fog_off=args.nofog, daily=args.daily, ascii=args.ascii)
    while True:
        if not args.difficulty:                  # --difficulty skips the menu
            st = setup_menu(scr, at, st)
            if st is None:
                return
        g = start_game(st, args)
        gl = ASC if st["ascii"] else UNI
        out["g"], out["gl"] = g, gl
        if play(scr, g, gl, at) != "again":
            return


def report(g, gl):
    heading = {"won": "YOU ESCAPED", "lost": "THE MAZE WINS (out of moves)",
               "quit": "You walked away."}.get(g.status, "")
    out = ["", heading, ""]
    if g.status != "quit":
        out += ["Seed %d. Heatmap: %s you walked   %s the maze expected   %s it read you correctly   E real exit   x decoy"
                % (g.seed, gl["walked"], gl["thought"], gl["both"]), ""]
        for y, row in enumerate(g.grid):
            line = ""
            for x, wall in enumerate(row):
                p = (x, y)
                d = g.door_at(p, alive_only=False)
                w, t = g.walked[p] > 0, g.thought[p] > 0
                if d:
                    line += ("E " if d.real else "x ")
                elif p == g.player and g.status == "won":
                    line += "@ "
                elif w and t:
                    line += gl["both"] + " "
                elif w:
                    line += gl["walked"] + " "
                elif t:
                    line += gl["thought"] + " "
                elif wall:
                    line += gl["wall"]
                else:
                    line += "  "
            out.append(line.rstrip())
        out.append("")
    out += [
        "Settings:          %s" % getattr(g, "settings", getattr(g, "difficulty", "normal")),
        "Difficulty:        %s" % getattr(g, "difficulty", "normal"),
        "Moves used:        %d / %s" % (g.turn, "unlimited" if g.move_limit is None else g.move_limit),
        "Decoys tripped:    %d" % g.decoys_hit,
        "Mutations:         %d fired, %d landed, %d cancelled" % (g.fired, g.landed, g.cancelled),
        "Close strikes:     %d fired, you beat %d by running" % (g.race_fired, g.race_beaten),
        "Deception score:   %d   (%d turns it was sure of a decoy + %d mutations wasted on decoy routes)"
        % (g.deception_score, g.fooled_turns, g.wasted),
    ]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Schrodinger's Maze")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--daily", action="store_true", help="today's seeded maze")
    ap.add_argument("--ascii", action="store_true", help="ASCII-only glyphs")
    ap.add_argument("--difficulty", choices=LEVELS,
                    help="skip the setup menu and play at this level")
    ap.add_argument("--infmoves", action="store_true", help="no move limit")
    ap.add_argument("--nofog", action="store_true", help="disable fog of war")
    ap.add_argument("--w", type=int, default=cfg.MAZE_W, help="maze width in rooms")
    ap.add_argument("--h", type=int, default=cfg.MAZE_H, help="maze height in rooms")
    args = ap.parse_args()
    locale.setlocale(locale.LC_ALL, "")
    out = {}
    try:
        curses.wrapper(run, args, out)
    except KeyboardInterrupt:
        if "g" in out:
            out["g"].status = "quit"
    if "g" not in out:
        print("\nNo game started.")
        try:
            input("\nPress Enter to exit...")
        
        except (KeyboardInterrupt, EOFError):
            pass
        return
    try:
        print(report(out["g"], out["gl"]))
    except UnicodeEncodeError:             # old consoles that can't print the block symbols
        print(report(out["g"], ASC))

    try:
        input("\nPress Enter to exit...")

    except (KeyboardInterrupt, EOFError):
        pass

if __name__ == "__main__":
    main()