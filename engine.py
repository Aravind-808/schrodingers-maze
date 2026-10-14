import math
import random
from collections import Counter

import config as cfg
import maze
from counterplanner import Counterplanner
from mind_reader import MindReader
from patient_one import PatientOne
from reality_bender import RealityBender


class Door:
    def __init__(self, id, pos, real):
        self.id, self.pos, self.real, self.alive = id, pos, real, True


class Game:
    def __init__(self, seed=None, w=cfg.MAZE_W, h=cfg.MAZE_H):
        self.seed = seed if seed is not None else random.randrange(10 ** 8)
        self.rng = random.Random(self.seed)
        self.grid = maze.generate(w, h, self.rng, cfg.LOOP_DENSITY)
        self.start = self.player = (1, 1)

        spots = maze.place_doors(self.grid, self.start, self.rng, cfg.NUM_DOORS)
        real_i = self.rng.randrange(len(spots))
        self.doors = [Door(i, p, i == real_i) for i, p in enumerate(spots)]
        self.real_exit = spots[real_i]
        self.base_len = maze.shortest_len(self.grid, self.start, self.real_exit)
        self.start_dist = {d.id: maze.shortest_len(self.grid, self.start, d.pos) for d in self.doors}
        if cfg.INFINITE_MOVES:
            self.move_limit, self.moves_left = None, math.inf   # rule 6 and the lose check become no-ops
        else:
            self.move_limit = self.moves_left = int(cfg.MOVE_LIMIT_MULT * self.base_len)
        self.protected = {self.start} | set(spots)

        # slow-burn decoy hint. Cosmetic only: its own RNG, never touches the maze or mutations.
        self.shimmer_rng = random.Random("shimmer-%d" % self.seed)
        self.shimmer_id, self.shimmer_until = None, -1
        self.shimmer_gap = float(cfg.SHIMMER_START)
        self.next_shimmer = int(round(self.shimmer_gap))
        self.shimmer_events = 0

        self.mind = MindReader()
        self.bender = RealityBender()
        self.counter = Counterplanner(self.bender)
        self.patient = PatientOne()

        self.turn = 0
        self.charges = cfg.MUTATION_BUDGET
        self.regen_total = 0
        self.real_dist_now = self.base_len                    # current distance to the real exit
        self.setback_bank = cfg.SETBACK_START * self.base_len  # infinite-moves credit (rule 7)
        self.pending, self.last_mutated = [], {}
        self.status = "playing"            # playing | won | lost | quit

        self.message, self.message_until, self.taunt_at = "", -1, {}
        self.walked, self.thought = Counter(), Counter()
        self.fired = self.landed = self.cancelled = 0
        self.wasted = self.fooled_turns = self.decoys_hit = 0
        self.last_opportunity = 0.0

        gh, gw = len(self.grid), len(self.grid[0])
        self.known = [[None] * gw for _ in range(gh)]
        self.visible = set()
        self._refresh_vision()
        self.walked[self.player] += 1

    # ---------- queries ----------
    def alive_doors(self):
        return [d for d in self.doors if d.alive]

    def door_at(self, pos, alive_only=True):
        for d in self.doors:
            if d.pos == pos and (d.alive or not alive_only):
                return d
        return None

    def visible_telegraphs(self):
        return {c for p in self.pending for c in p.cells() if c in self.visible}

    def current_message(self):
        return self.message if self.turn <= self.message_until else ""

    # ---------- turn ----------
    def step(self, key):
        if self.status != "playing":
            return False
        dx, dy = maze.DIRS[key]
        nx, ny = self.player[0] + dx, self.player[1] + dy
        if self.grid[ny][nx]:
            return False                      # bumping a wall is free
        prev, self.player = self.player, (nx, ny)
        self.turn += 1
        self.moves_left -= 1
        if (cfg.REGEN_INTERVAL and self.turn % cfg.REGEN_INTERVAL == 0
                and self.charges < cfg.MUTATION_BUDGET):
            self.charges += 1                 # the maze slowly recharges
            self.regen_total += 1
        self.setback_bank = min(cfg.SETBACK_CAP * self.base_len, self.setback_bank + cfg.SETBACK_RATE)
        self.walked[self.player] += 1
        for p in self.pending:
            if p.seal == self.player:
                p.dodged = True               # ran through a telegraphed seal

        door = self.door_at(self.player)
        if door:
            if door.real:
                self.status = "won"
                self._refresh_vision()
                return True
            door.alive = False
            self.charges += cfg.DECOY_CHARGE  # wrong guesses are paid for
            self.decoys_hit += 1
            self._taunt("decoy", "That one was never real.", 0)

        self._tick_shimmer()
        self._track_real()
        pred = self.mind.update(self.grid, prev, self.player,
                                [(d.id, d.pos) for d in self.alive_doors()])
        self._after_prediction(pred)
        self._resolve_pending()
        self._track_real()
        self._maybe_mutate()
        self._refresh_vision()
        if self.moves_left <= 0 and self.status == "playing":
            self.status = "lost"
        return True

    def shimmering_pos(self):
        """Tile of the decoy that is shimmering right now, or None."""
        if self.shimmer_id is None:
            return None
        d = self.doors[self.shimmer_id]
        return d.pos if d.alive else None

    # ---------- internals ----------
    def _tick_shimmer(self):
        if not cfg.DECOY_SHIMMER:
            return
        if self.shimmer_id is not None and (self.turn > self.shimmer_until
                                            or not self.doors[self.shimmer_id].alive):
            self.shimmer_id = None
        if self.turn >= self.next_shimmer:
            decoys = [d for d in self.alive_doors() if not d.real]
            if decoys:
                self.shimmer_id = self.shimmer_rng.choice(decoys).id
                self.shimmer_until = self.turn + cfg.SHIMMER_DURATION - 1
                self.shimmer_events += 1
            self.shimmer_gap *= cfg.SHIMMER_GROWTH
            self.next_shimmer = self.turn + int(round(self.shimmer_gap))

    def _track_real(self):
        self.real_dist_now = maze.shortest_len(self.grid, self.player, self.real_exit)

    def _after_prediction(self, pred):
        for c in pred.next_steps:
            self.thought[c] += 1
        door = next(d for d in self.doors if d.id == pred.target_id)
        if pred.committed is not None and not door.real:
            self.fooled_turns += 1
        if pred.flipped:
            self._taunt("flip", "...Changed your mind?", 10)
        phrase = self.mind.habit_phrase()
        if phrase:
            self._taunt("habit", phrase, cfg.TAUNT_COOLDOWN)
        elif pred.confidence > 0.8:
            self._taunt("sure", "I know exactly where you're going.", cfg.TAUNT_COOLDOWN)

    def _resolve_pending(self):
        for m in list(self.pending):
            if self.turn < m.due:
                continue
            self.pending.remove(m)
            if m.seal == self.player:         # standing on it: cancel and refund
                self.charges += 1
                self.cancelled += 1
                self._taunt("lucky", "Lucky.", 0)
                continue
            if not self.bender.still_valid(self, m):
                self.charges += 1
                self.cancelled += 1
                continue
            before = self.real_dist_now
            self.bender.apply(self.grid, m)
            after = maze.shortest_len(self.grid, self.player, self.real_exit)
            self.setback_bank -= max(0, after - before)   # spend the credit
            self.landed += 1
            if m.dodged:
                self._taunt("lucky", "Lucky.", 0)

    def _maybe_mutate(self):
        self.last_opportunity = 0.0
        if not self.patient.can_consider(self):
            return
        pred = self.mind.pred
        m = self.counter.propose(self, pred.target_pos)
        if m is None:
            return
        dist = maze.shortest_len(self.grid, self.player, pred.target_pos)
        opp = self.patient.opportunity(pred.confidence, m.gain, dist,
                                       self.start_dist[pred.target_id])
        self.last_opportunity = opp
        if opp <= self.patient.threshold(self.turn):
            return
        m.due = self.turn + cfg.TELEGRAPH_DELAY
        self.charges -= 1
        self.fired += 1
        self.patient.fired(self.turn)
        for c in m.cells():
            self.last_mutated[c] = self.turn
        self.pending.append(m)
        if m.target != self.real_exit:
            self.wasted += 1                  # spent on a decoy route

    def _taunt(self, key, text, cooldown):
        if self.turn - self.taunt_at.get(key, -10 ** 9) < cooldown:
            return
        self.taunt_at[key] = self.turn
        self.message, self.message_until = text, self.turn + 8

    def _refresh_vision(self):
        if cfg.FOG_OF_WAR:
            self.visible = maze.visible_cells(self.grid, self.player, cfg.VISION_RADIUS)
        else:
            self.visible = {(x, y) for y in range(len(self.grid)) for x in range(len(self.grid[0]))}
        for x, y in self.visible:
            if self.grid[y][x]:
                self.known[y][x] = "#"
            elif self.door_at((x, y)):
                self.known[y][x] = "E"
            else:
                self.known[y][x] = "."

    @property
    def deception_score(self):
        """Turns the maze was confidently committed to a decoy + charges it burned on decoy routes."""
        return self.fooled_turns + self.wasted