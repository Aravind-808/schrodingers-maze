import config as cfg
import maze


class Mutation:
    def __init__(self, kind, seal=None, open=None, target=None):
        self.kind = kind
        self.seal = seal
        self.open = open
        self.target = target   # the position the maze predicted when it chose this
        self.gain = 0
        self.due = None
        self.dodged = False

    def cells(self):
        return [c for c in (self.seal, self.open) if c is not None]


class RealityBender:
    @staticmethod
    def apply(grid, m):
        if m.seal:
            grid[m.seal[1]][m.seal[0]] = True
        if m.open:
            grid[m.open[1]][m.open[0]] = False

    @staticmethod
    def revert(grid, m):
        if m.seal:
            grid[m.seal[1]][m.seal[0]] = False
        if m.open:
            grid[m.open[1]][m.open[0]] = True

    def structure_ok(self, g, m):
        if m.seal:
            x, y = m.seal
            if g.grid[y][x] or not maze.is_slot(g.grid, x, y):
                return False
        if m.open:
            x, y = m.open
            if not g.grid[y][x] or not maze.is_slot(g.grid, x, y):
                return False
        return True

    def static_ok(self, g, m):
        if not self.structure_ok(g, m):
            return False
        for c in m.cells():
            if maze.manhattan(c, g.player) <= cfg.MIN_PLAYER_DIST:
                return False
            if c in g.protected:
                return False
            if g.turn - g.last_mutated.get(c, -10 ** 9) < cfg.CELL_COOLDOWN:
                return False
            if any(c in p.cells() for p in g.pending):
                return False
        return True

    @staticmethod
    def length_ok(g, real_len):
        if real_len is None:
            return False
        if real_len > cfg.DETOUR_CAP_MULT * g.base_len:
            return False
        if real_len > g.moves_left - cfg.MOVE_MARGIN:
            return False
        if cfg.INFINITE_MOVES:
            if max(0, real_len - g.real_dist_now) > g.setback_bank:
                return False
        return True

    def path_ok(self, g, m):
        self.apply(g.grid, m)
        try:
            real_len = maze.shortest_len(g.grid, g.player, g.real_exit)
        finally:
            self.revert(g.grid, m)
        return self.length_ok(g, real_len)

    def validate(self, g, m):
        """Full check used before a mutation is allowed to be telegraphed (rule 5 included)."""
        return g.charges >= 1 and self.static_ok(g, m) and self.path_ok(g, m)

    def still_valid(self, g, m):
        """Re-check at the moment a telegraphed mutation is about to land."""
        return self.structure_ok(g, m) and self.path_ok(g, m)