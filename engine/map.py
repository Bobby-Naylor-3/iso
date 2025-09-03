from __future__ import annotations
from typing import Tuple, Set
import settings as S

Coord = Tuple[int, int]

class TileMap:
    def __init__(self, cols: int, rows: int) -> None:
        self.cols = cols
        self.rows = rows
        self.blocked: Set[Coord] = set()

        # Optional demo obstacles: a small wall and a blob
        wall_i = S.GRID_COLS // 2
        for j in range(6, 14):
            self.blocked.add((wall_i, j))
        self.blocked.update({(8, 5), (9, 5), (9, 6), (10, 6)})

    def in_bounds(self, c: Coord) -> bool:
        i, j = c
        return 0 <= i < self.cols and 0 <= j < self.rows

    def passable(self, c: Coord) -> bool:
        return c not in self.blocked

    def toggle_block(self, c: Coord) -> None:
        if not self.in_bounds(c):
            return
        if c in self.blocked:
            self.blocked.remove(c)
        else:
            self.blocked.add(c)
