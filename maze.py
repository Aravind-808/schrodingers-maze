
from collections import deque

DIRS = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
_ORDER = list(DIRS.values())


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def is_slot(grid, x, y):
    return 0 < x < len(grid[0]) - 1 and 0 < y < len(grid) - 1 and (x + y) % 2 == 1


def generate(w, h, rng, loop_density):
    gw, gh = 2 * w + 1, 2 * h + 1
    grid = [[True] * gw for _ in range(gh)]
    start = (1, 1)
    grid[1][1] = False
    seen = {start}
    stack = [start]
    while stack:  # iterative recursive-backtracker
        x, y = stack[-1]
        opts = [
            (x + dx * 2, y + dy * 2, dx, dy)
            for dx, dy in _ORDER
            if 0 < x + dx * 2 < gw and 0 < y + dy * 2 < gh
            and (x + dx * 2, y + dy * 2) not in seen
        ]
        if not opts:
            stack.pop()
            continue
        nx, ny, dx, dy = rng.choice(opts)
        grid[y + dy][x + dx] = False
        grid[ny][nx] = False
        seen.add((nx, ny))
        stack.append((nx, ny))
    walls = [(x, y) for y in range(1, gh - 1) for x in range(1, gw - 1)
             if (x + y) % 2 == 1 and grid[y][x]]
    for x, y in rng.sample(walls, int(len(walls) * loop_density)):
        grid[y][x] = False
    return grid


def bfs_dist(grid, src):
    dist = {src: 0}
    q = deque([src])
    while q:
        x, y = q.popleft()
        d = dist[(x, y)] + 1
        for dx, dy in _ORDER:
            n = (x + dx, y + dy)
            if n not in dist and not grid[n[1]][n[0]]:
                dist[n] = d
                q.append(n)
    return dist


def shortest_len(grid, src, dst):
    if src == dst:
        return 0
    dist = {src: 0}
    q = deque([src])
    while q:
        x, y = q.popleft()
        d = dist[(x, y)] + 1
        for dx, dy in _ORDER:
            n = (x + dx, y + dy)
            if n not in dist and not grid[n[1]][n[0]]:
                if n == dst:
                    return d
                dist[n] = d
                q.append(n)
    return None


def shortest_path(grid, src, dst):
    if src == dst:
        return [src]
    prev = {src: None}
    q = deque([src])
    while q:
        cur = q.popleft()
        for dx, dy in _ORDER:
            n = (cur[0] + dx, cur[1] + dy)
            if n not in prev and not grid[n[1]][n[0]]:
                prev[n] = cur
                if n == dst:
                    path = [n]
                    while prev[path[-1]] is not None:
                        path.append(prev[path[-1]])
                    return path[::-1]
                q.append(n)
    return None


def place_doors(grid, start, rng, n):
    dist = bfs_dist(grid, start)
    rooms = sorted(p for p in dist if p[0] % 2 == 1 and p[1] % 2 == 1 and p != start)
    maxd = max(dist[p] for p in rooms)
    far = [p for p in rooms if dist[p] >= 0.6 * maxd]
    if len(far) < n * 2:
        far = sorted(rooms, key=lambda p: -dist[p])[: n * 4]
    sep = (len(grid[0]) + len(grid)) // 4
    while True:
        rng.shuffle(far)
        doors = []
        for p in far:
            if all(manhattan(p, d) >= sep for d in doors):
                doors.append(p)
                if len(doors) == n:
                    return doors
        sep = max(0, sep - 2)


def _line_clear(grid, a, b):
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1
    err = dx - dy
    x, y = x0, y0
    while (x, y) != (x1, y1):
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
        if (x, y) != (x1, y1) and grid[y][x]:
            return False
    return True


def visible_cells(grid, pos, radius):
    vis = {pos}
    px, py = pos
    for y in range(py - radius, py + radius + 1):
        for x in range(px - radius, px + radius + 1):
            if (x - px) ** 2 + (y - py) ** 2 > radius * radius:
                continue
            if 0 <= y < len(grid) and 0 <= x < len(grid[0]) and _line_clear(grid, pos, (x, y)):
                vis.add((x, y))
    return vis
