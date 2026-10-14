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
    "T H E   H O U S E   A L W A Y S   W I N S",
    "",
    "You are lost in a maze that is watching you.",
    "",
    "  - Three doors marked E. One is real. Two are decoys.",
    "  - The maze predicts where you're headed and rewrites itself to block you.",
    "  - A shimmering wall marks a shift about to land. You get 2 moves to run through.",
    "  - Every decoy you trip feeds the maze another charge.",
    "  - Make it believe you're going somewhere you aren't.",
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
    put(scr, 0, 1, "SCHRIDINGER'S MAZE  [%s]" % getattr(g, "difficulty", "normal").upper(), at["taunt"])
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
LEVEL_KEYS = {ord("1"): "easy", ord("2"): "normal", ord("3"): "hard", ord("4"): "brutal",
              ord("e"): "easy", ord("n"): "normal", ord("h"): "hard", ord("b"): "brutal",
              10: "normal", 13: "normal", curses.KEY_ENTER: "normal"}


def choose_difficulty(scr, at):
    lines = ["CHOOSE DIFFICULTY", ""]
    for i, name in enumerate(LEVELS, 1):
        lines.append("%d  %-7s %s" % (i, name.upper(), cfg.DIFFICULTY_BLURBS[name]))
    lines += ["", "Press 1-4 (Enter = normal)   q to quit"]
    while True:
        scr.erase()
        banner(scr, lines, at)
        k = scr.getch()
        if k in (ord("q"), ord("Q"), 27):
            return None
        if k in LEVEL_KEYS:
            return LEVEL_KEYS[k]


def run(scr, args, gl, out):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    scr.keypad(True)
    at = init_attrs()
    scr.erase()
    banner(scr, INTRO, at)
    scr.getch()
    name = args.difficulty or choose_difficulty(scr, at)
    if name is None:
        return
    cfg.apply_difficulty(name)
    g = Game(args.seed, args.w, args.h)
    g.difficulty = name
    out["g"] = g
    while True:
        draw(scr, g, gl, at)
        scr.timeout(250 if g.shimmering_pos() else -1)   # keep redrawing only while something shimmers
        k = scr.getch()
        if k == -1:
            continue
        if k in (ord("q"), ord("Q"), 27):
            g.status = "quit"
            return
        if k in KEYS:
            g.step(KEYS[k])
            if g.status in ("won", "lost"):
                scr.timeout(-1)
                draw(scr, g, gl, at)
                if g.status == "won":
                    banner(scr, ["  YOU ESCAPED  ", "  the maze never saw it coming  ", "  press any key  "], at)
                else:
                    banner(scr, ["  SCHRIDINGER'S MAZE  ", "  you ran out of moves  ", "  press any key  "], at)
                scr.getch()
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
        "Difficulty:        %s" % getattr(g, "difficulty", "normal"),
        "Moves used:        %d / %s" % (g.turn, "unlimited" if g.move_limit is None else g.move_limit),
        "Decoys tripped:    %d" % g.decoys_hit,
        "Mutations:         %d fired, %d landed, %d cancelled" % (g.fired, g.landed, g.cancelled),
        "Deception score:   %d   (%d turns it was sure of a decoy + %d mutations wasted on decoy routes)"
        % (g.deception_score, g.fooled_turns, g.wasted),
    ]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Schridinger's Maze")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--daily", action="store_true", help="today's seeded maze")
    ap.add_argument("--ascii", action="store_true", help="ASCII-only glyphs")
    ap.add_argument("--difficulty", choices=["easy", "normal", "hard", "brutal"],
                    help="skip the menu and pick a level")
    ap.add_argument("--infmoves", action="store_true", help="no move limit")
    ap.add_argument("--nofog", action="store_true", help="disable fog of war")
    ap.add_argument("--w", type=int, default=cfg.MAZE_W, help="maze width in rooms")
    ap.add_argument("--h", type=int, default=cfg.MAZE_H, help="maze height in rooms")
    args = ap.parse_args()
    if args.nofog:
        cfg.FOG_OF_WAR = False
    if args.infmoves:
        cfg.INFINITE_MOVES = True
    if args.daily:
        args.seed = int(datetime.date.today().strftime("%Y%m%d"))
    gl = ASC if args.ascii else UNI
    locale.setlocale(locale.LC_ALL, "")
    out = {}
    try:
        curses.wrapper(run, args, gl, out)
    except KeyboardInterrupt:
        if "g" in out:
            out["g"].status = "quit"
    if "g" not in out:
        print("\nNo game started.")
        return
    print(report(out["g"], gl))


if __name__ == "__main__":
    main()