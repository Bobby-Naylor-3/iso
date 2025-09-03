from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

Coord = Tuple[int, int]

@dataclass
class Enemy:
    grid: Coord
    hp: int = 3
