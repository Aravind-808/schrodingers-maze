import math
from collections import Counter, deque

import config as cfg
import maze

DIR_OF = {v: k for k, v in maze.DIRS.items()}


class Prediction:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class MindReader:
    def __init__(self):
        self.moves = deque(maxlen=cfg.HISTORY_LEN)
        self.deltas = deque(maxlen=cfg.HISTORY_LEN)  # {door_id: distance gained}
        self.forks = deque(maxlen=8)
        self.heading = None
        self.committed = None  # door id it is currently sure about (belief > 0.5)
        self.pred = None

    def update(self, grid, prev, cur, doors):
        """doors: list of (id, pos) for live doors."""
        move = DIR_OF[(cur[0] - prev[0], cur[1] - prev[1])]
        self._note_fork(grid, prev, move)
        self.moves.append(move)
        self.heading = move

        delta = {}
        for did, pos in doors:
            dist = maze.bfs_dist(grid, pos)
            a, b = dist.get(prev), dist.get(cur)
            delta[did] = (a - b) if a is not None and b is not None else 0
        self.deltas.append(delta)

        ids = sorted(d[0] for d in doors)
        belief = self._beliefs(ids)
        top = max(ids, key=lambda i: (belief[i], -i))
        pos_of = dict(doors)

        k = len(ids)
        target_conf = 1.0 if k == 1 else max(0.0, (belief[top] - 1 / k) / (1 - 1 / k))
        habit_move, habit_conf = self._habit()
        confidence = 0.65 * target_conf + 0.35 * habit_conf

        committed = top if belief[top] > 0.5 else None
        flipped = False
        if committed is not None:
            flipped = self.committed is not None and committed != self.committed
            self.committed = committed
        elif self.committed not in ids:
            self.committed = None

        path = maze.shortest_path(grid, cur, pos_of[top])
        self.pred = Prediction(
            target_id=top, target_pos=pos_of[top], belief=belief,
            confidence=confidence, target_conf=target_conf,
            habit_conf=habit_conf, habit_move=habit_move,
            next_steps=path[1:6] if path else [],
            committed=committed, flipped=flipped,
        )
        return self.pred

    # ---- pieces ----
    def _beliefs(self, ids):
        scores = {i: 0.0 for i in ids}
        for age, d in enumerate(reversed(self.deltas)):
            w = cfg.RECENCY_DECAY ** age
            for i in ids:
                scores[i] += w * d.get(i, 0)
        m = max(scores.values())
        exps = {i: math.exp(cfg.SOFTMAX_BETA * (s - m)) for i, s in scores.items()}
        z = sum(exps.values())
        return {i: e / z for i, e in exps.items()}

    def _habit(self):
        m = list(self.moves)
        if len(m) < 3:
            return None, 0.0
        key = (m[-2], m[-1])
        nxt = Counter()
        for i in range(len(m) - 2):
            if (m[i], m[i + 1]) == key:
                nxt[m[i + 2]] += 1
        n = sum(nxt.values())
        if n == 0:
            return None, 0.0
        move, c = nxt.most_common(1)[0]
        return move, (c / n) * min(1.0, n / 4)

    def _note_fork(self, grid, cell, new_dir):
        if self.heading is None:
            return
        x, y = cell
        opens = sum(1 for dx, dy in maze.DIRS.values() if not grid[y + dy][x + dx])
        if opens < 3:
            return
        hx, hy = maze.DIRS[self.heading]
        dx, dy = maze.DIRS[new_dir]
        cross = hx * dy - hy * dx  # y-down screen coords: >0 is a right turn
        if cross > 0:
            self.forks.append("R")
        elif cross < 0:
            self.forks.append("L")
        elif hx * dx + hy * dy > 0:
            self.forks.append("S")

    def habit_phrase(self):
        if len(self.forks) < 5:
            return None
        side, n = Counter(self.forks).most_common(1)[0]
        if side in "LR" and n / len(self.forks) >= 0.8:
            return "You always turn %s at forks." % ("left" if side == "L" else "right")
        return None
