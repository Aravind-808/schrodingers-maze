import config as cfg


class PatientOne:
    def __init__(self):
        self.last_fire = None

    def can_consider(self, g):
        if g.turn < cfg.GRACE or g.charges < 1 or g.pending:
            return False
        if self.last_fire is not None and g.turn - self.last_fire < cfg.COOLDOWN:
            return False
        return True

    def threshold(self, turn):
        ref = self.last_fire if self.last_fire is not None else 0
        return max(cfg.THRESH_MIN, cfg.THRESH_START - cfg.THRESH_DECAY * (turn - ref))

    @staticmethod
    def opportunity(confidence, gain, dist, start_dist):
        bonus = 1.0 + (1.0 - dist / start_dist) if start_dist > 0 else 1.0
        bonus = min(2.0, max(1.0, bonus))
        return confidence * gain * bonus

    def fired(self, turn):
        self.last_fire = turn
