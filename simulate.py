import random
import sys

import maze
from engine import Game

KEY_OF = {v: k for k, v in maze.DIRS.items()}


def explore_move(g, _retry=True):
    from collections import deque
    start = g.player
    prev = {start: None}
    q = deque([start])
    goal = None
    while q:
        cur = q.popleft()
        x, y = cur
        k = g.known[y][x]
        if cur != start and (k == "E" and g.door_at(cur)):
            goal = cur
            break
        frontier = any(g.known[y + dy][x + dx] is None for dx, dy in maze.DIRS.values()
                       if 0 <= y + dy < len(g.grid) and 0 <= x + dx < len(g.grid[0]))
        if cur != start and frontier and goal is None:
            goal = cur
            break
        for dx, dy in maze.DIRS.values():
            n = (x + dx, y + dy)
            if n not in prev and g.known[n[1]][n[0]] in (".", "E"):
                prev[n] = cur
                q.append(n)
    if goal is None:
        if not _retry:
            return None
        for y, row in enumerate(g.known):
            for x, k in enumerate(row):
                if k == "#" and (x, y) not in g.visible:
                    g.known[y][x] = None
        return explore_move(g, False)
    while prev[goal] != start:
        goal = prev[goal]
    return KEY_OF[(goal[0] - start[0], goal[1] - start[1])]


def play(seed, mode):
    g = Game(seed)
    if mode == "explore":
        for _ in range(3000):
            if g.status != "playing":
                break
            k = explore_move(g)
            if k is None or not g.step(k):
                break
            assert maze.shortest_len(g.grid, g.player, g.real_exit) is not None, "REAL EXIT UNREACHABLE"
        return g
    brng = random.Random(seed)
    target = None
    while g.status == "playing":
        alive = g.alive_doors()
        if mode == "direct":
            target = g.doors[[d.real for d in g.doors].index(True)]
        elif (target is None or not target.alive or g.turn % 25 == 0
              or not maze.shortest_path(g.grid, g.player, target.pos)):
            reachable = [d for d in alive if maze.shortest_path(g.grid, g.player, d.pos)]
            target = brng.choice(reachable)   
        path = maze.shortest_path(g.grid, g.player, target.pos)
        assert path, "bot has no path to its target"
        a, b = path[0], path[1]
        g.step(KEY_OF[(b[0] - a[0], b[1] - a[1])])
        assert maze.shortest_len(g.grid, g.player, g.real_exit) is not None, "REAL EXIT UNREACHABLE"
    return g


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    s0 = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    if len(sys.argv) > 3:
        import config
        config.apply_difficulty(sys.argv[3])
        print("difficulty:", sys.argv[3])
    for mode in ("direct", "wander", "explore"):
        wins = fired = landed = canc = wasted = moves = limit = 0
        for s in range(s0, s0 + n):
            g = play(s, mode)
            wins += g.status == "won"
            fired += g.fired; landed += g.landed; canc += g.cancelled; wasted += g.wasted
            moves += g.turn; limit += g.move_limit or 0
        print(f"{mode:7s} games={n} wins={wins} avg_moves={moves/n:.0f}/{limit/n:.0f} "
              f"mutations fired={fired/n:.1f} landed={landed/n:.1f} "
              f"cancelled={canc/n:.1f} wasted_on_decoys={wasted/n:.1f}")