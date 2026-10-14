import random
import sys

import config as cfg
import maze
import simulate
from engine import Game

KEY_OF = {v: k for k, v in maze.DIRS.items()}
STEP_CAP = 8000
STALL_TURNS = 600


_last_landed = {}


def check(g, worst):
    L = maze.shortest_len(g.grid, g.player, g.real_exit)
    assert L is not None, "REAL EXIT UNREACHABLE (seed %d turn %d)" % (g.seed, g.turn)
    if g.landed != _last_landed.get(id(g), 0):
        _last_landed[id(g)] = g.landed
        assert L <= cfg.DETOUR_CAP_MULT * g.base_len, \
            "MUTATION BROKE DETOUR CAP (seed %d turn %d: %d > %d)" % (g.seed, g.turn, L, cfg.DETOUR_CAP_MULT * g.base_len)
        if cfg.INFINITE_MOVES:
            assert g.setback_bank >= -1e-9, \
                "SETBACK BANK OVERSPENT (seed %d turn %d: %.2f)" % (g.seed, g.turn, g.setback_bank)
        worst[0] = max(worst[0], L / g.base_len)


def walk_to_real(g, worst):
    while g.status == "playing" and g.turn < STEP_CAP:
        path = maze.shortest_path(g.grid, g.player, g.real_exit)
        a, b = path[0], path[1]
        g.step(KEY_OF[(b[0] - a[0], b[1] - a[1])])
        check(g, worst)


def play(seed, mode, w, h):
    g = Game(seed, w, h)
    worst = [1.0]
    if mode == "direct":
        walk_to_real(g, worst)
        if cfg.INFINITE_MOVES:   # the bank's promise: an informed walker arrives within a bound
            bound = g.base_len * (1 + cfg.SETBACK_START) / (1 - cfg.SETBACK_RATE) + 3 * cfg.COOLDOWN
            assert g.turn <= bound, "STALLED PAST THE BOUND (seed %d: %d > %.0f)" % (seed, g.turn, bound)
    elif mode == "stall":
        rng = random.Random(seed)
        doors = {d.pos for d in g.doors}
        while g.turn < STALL_TURNS:
            if g.turn == STALL_TURNS // 2:
                g.fired_mid = g.fired
            x, y = g.player
            opts = [k for k, (dx, dy) in maze.DIRS.items()
                    if not g.grid[y + dy][x + dx] and (x + dx, y + dy) not in doors]
            g.step(rng.choice(opts))
            check(g, worst)
        t0, d0, bank0 = g.turn, g.real_dist_now, g.setback_bank
        walk_to_real(g, worst)
        if cfg.INFINITE_MOVES:   # (distance + banked credit) / (1 - rate), from the moment it starts walking
            bound = (d0 + bank0) / (1 - cfg.SETBACK_RATE) + 3 * cfg.COOLDOWN
            assert g.turn - t0 <= bound, "POST-STALL BOUND BROKEN (seed %d: %d > %.0f)" % (seed, g.turn - t0, bound)
            g.stall_slack = bound - (g.turn - t0)
    elif mode == "wander":
        rng = random.Random(seed)
        target = None
        while g.status == "playing" and g.turn < STEP_CAP:
            reach = [d for d in g.alive_doors() if maze.shortest_path(g.grid, g.player, d.pos)]
            if target is None or not target.alive or g.turn % 25 == 0 or target not in reach:
                target = rng.choice(reach)
            path = maze.shortest_path(g.grid, g.player, target.pos)
            a, b = path[0], path[1]
            g.step(KEY_OF[(b[0] - a[0], b[1] - a[1])])
            check(g, worst)
    else:  # explore
        while g.status == "playing" and g.turn < STEP_CAP:
            k = simulate.explore_move(g)
            if k is None or not g.step(k):
                break
            check(g, worst)
    return g, worst[0]


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 8
    level = args[1] if len(args) > 1 else "brutal"
    cfg.apply_difficulty(level)
    cfg.FOG_OF_WAR = "--fog" in sys.argv
    cfg.INFINITE_MOVES = "--limit" not in sys.argv
    print("config: %s, fog=%s, infinite_moves=%s" % (level, cfg.FOG_OF_WAR, cfg.INFINITE_MOVES))
    print("regen: +1 charge / %d turns up to %d; setback credit %.2f/turn, start %.1fx, cap %.1fx"
          % (cfg.REGEN_INTERVAL, cfg.MUTATION_BUDGET, cfg.SETBACK_RATE, cfg.SETBACK_START, cfg.SETBACK_CAP))
    bad = 0
    late = 0
    for mode in ("direct", "wander", "explore", "stall"):
        won = fired = turns = 0
        worst = 1.0
        for s in range(1, n + 1):
            g, wr = play(s, mode, cfg.MAZE_W, cfg.MAZE_H)
            won += g.status == "won"
            fired += g.fired
            turns += g.turn
            if mode == "stall":
                late += g.fired - getattr(g, "fired_mid", 0)
            worst = max(worst, wr)
            if g.status != "won":
                bad += 1
                print("  not won: mode=%s seed=%d status=%s turn=%d" % (mode, s, g.status, g.turn))
        print("%-8s games=%d won=%d/%d  avg_turns=%.0f  mutations/game=%.1f  worst post-mutation path=%.2fx"
              % (mode, n, won, n, turns / n, fired / n, worst), flush=True)
    print("stall bot: mutations fired in the SECOND half of its 600-turn stall (turn %d to %d): %.1f per game"
          % (STALL_TURNS // 2, STALL_TURNS, late / n))
    print("RESULT:", "every game won, exit reachable after every turn" if bad == 0 else "%d game(s) not won" % bad)