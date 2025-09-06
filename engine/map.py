from __future__ import annotations
from typing import Tuple, Set
import settings as S

Coord = Tuple[int, int]

class TileMap:
    def __init__(self, cols: int, rows: int) -> None:
        self.cols = cols
        self.rows = rows
        # Full blockers: walls/solid obstacles (block move/LOS)
        self.blocked: Set[Coord] = set()
        # Half-cover props (do not block movement/LOS)
        self.crates: Set[Coord] = set()

        # Optional demo obstacles: a small wall and a blob
        wall_i = S.GRID_COLS // 2
        for j in range(6, 14):
            self.blocked.add((wall_i, j))
        self.blocked.update({(8, 5), (9, 5), (9, 6), (10, 6)})

        # Demo crates (half cover)
        self.crates.update({(6, 8), (11, 9)})

    def in_bounds(self, c: Coord) -> bool:
        i, j = c
        return 0 <= i < self.cols and 0 <= j < self.rows

    def passable(self, c: Coord) -> bool:
        # Crates are half-cover and do not block movement
        return c not in self.blocked

    def toggle_block(self, c: Coord) -> None:
        if not self.in_bounds(c):
            return
        if c in self.blocked:
            self.blocked.remove(c)
        else:
            # Can't have a crate under a wall: remove any crate on this cell
            self.crates.discard(c)
            self.blocked.add(c)

    def toggle_crate(self, c: Coord) -> None:
        if not self.in_bounds(c):
            return
        if c in self.blocked:
            # Walls override crates; no crate placement on walls
            return
        if c in self.crates:
            self.crates.remove(c)
        else:
            self.crates.add(c)
