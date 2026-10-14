"""Counterplanner: picks the mutation that hurts the *predicted* route most.

It attacks where the Mind Reader thinks you are going, not where you are
really going. Fool the Mind Reader and these mutations are wasted.
gain = (new path length to predicted target) - (old path length)
"""
import config as cfg
import maze
from reality_bender import Mutation


class Counterplanner:
    def __init__(self, bender):
        self.bender = bender

    def propose(self, g, target):
        grid = g.grid
        path = maze.shortest_path(grid, g.player, target)
        if not path or len(path) < 2:
            return None
        old = len(path) - 1
        good, blocked = [], []

        # 1) seal candidates along the predicted route
        for c in path[1:-1]:
            if not maze.is_slot(grid, *c):
                continue
            m = Mutation("seal", seal=c, target=target)
            if not self.bender.static_ok(g, m):
                continue
            ok, gain = self._evaluate(g, m, target, old)
            if gain <= 0:
                continue
            (good if ok else blocked).append(m)

        # 2) chokepoints the referee refused: try to pair each with an opener
        #    that restores a (longer) route to the real exit
        g.rng.shuffle(blocked)
        gh, gw = len(grid), len(grid[0])
        for sealed in blocked[:4]:
            sx, sy = sealed.seal
            openers = [
                (x, y)
                for y in range(max(1, sy - 8), min(gh - 1, sy + 9))
                for x in range(max(1, sx - 8), min(gw - 1, sx + 9))
                if maze.is_slot(grid, x, y) and grid[y][x]
            ]
            g.rng.shuffle(openers)
            for o in openers[:20]:
                r = Mutation("reroute", seal=sealed.seal, open=o, target=target)
                if not self.bender.static_ok(g, r):
                    continue
                ok, gain = self._evaluate(g, r, target, old)
                if ok and gain > 0:
                    good.append(r)

        if not good:
            return None
        g.rng.shuffle(good)                 # seeded tie-breaks
        good.sort(key=lambda m: -m.gain)
        return good[0]

    def _evaluate(self, g, m, target, old):
        b = self.bender
        b.apply(g.grid, m)
        try:
            real = maze.shortest_len(g.grid, g.player, g.real_exit)
            tgt = real if target == g.real_exit else maze.shortest_len(g.grid, g.player, target)
        finally:
            b.revert(g.grid, m)
        m.gain = cfg.UNREACHABLE_GAIN if tgt is None else tgt - old
        return b.length_ok(g, real), m.gain
