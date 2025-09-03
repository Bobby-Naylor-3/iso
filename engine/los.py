from __future__ import annotations
from typing import Iterable, Tuple, Set

Coord = Tuple[int, int]

def bresenham_line(a: Coord, b: Coord) -> Iterable[Coord]:
    """Yield grid cells from a to b inclusive using Bresenham (4-neighbor)."""
    x0, y0 = a
    x1, y1 = b
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        yield (x, y)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy

def has_los(a: Coord, b: Coord, blocked: Set[Coord]) -> bool:
    """Return True if no blocked tiles are strictly between a and b."""
    it = iter(bresenham_line(a, b))
    next(it, None)  # skip start
    for c in it:
        if c == b:
            return True
        if c in blocked:
            return False
    return True
