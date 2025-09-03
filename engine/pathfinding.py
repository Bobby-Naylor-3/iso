from __future__ import annotations
from typing import Iterable, Tuple, Dict, List
import heapq

Coord = Tuple[int, int]

class PriorityQueue:
    def __init__(self) -> None:
        self._h: list[tuple[int, Coord]] = []

    def push(self, priority: int, item: Coord) -> None:
        heapq.heappush(self._h, (priority, item))

    def pop(self) -> Coord:
        return heapq.heappop(self._h)[1]

    def __bool__(self) -> bool:
        return bool(self._h)


def manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def neighbors_4(i: int, j: int) -> Iterable[Coord]:
    yield (i + 1, j)
    yield (i - 1, j)
    yield (i, j + 1)
    yield (i, j - 1)


def a_star(start: Coord, goal: Coord, cols: int, rows: int, blocked: set[Coord]) -> List[Coord]:
    """
    4-direction A* on a uniform-cost grid. Returns path from start-excluded to goal-included.
    """
    if start == goal:
        return []

    openq = PriorityQueue()
    openq.push(0, start)

    came_from: Dict[Coord, Coord] = {}
    g: Dict[Coord, int] = {start: 0}

    while openq:
        current = openq.pop()
        if current == goal:
            break

        for nx, ny in neighbors_4(*current):
            if not (0 <= nx < cols and 0 <= ny < rows):
                continue
            if (nx, ny) in blocked:
                continue
            tentative = g[current] + 1
            if tentative < g.get((nx, ny), 1_000_000_000):
                g[(nx, ny)] = tentative
                came_from[(nx, ny)] = current
                f = tentative + manhattan((nx, ny), goal)
                openq.push(f, (nx, ny))

    if goal not in came_from and goal != start:
        return []  # no path

    # Reconstruct
    path: List[Coord] = []
    node = goal
    while node != start:
        path.append(node)
        node = came_from.get(node, start)
        if node == start:
            break
    path.reverse()
    return path
