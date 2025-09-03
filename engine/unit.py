from __future__ import annotations
from typing import List, Tuple, Optional
from collections import deque
import math

from .iso import tile_center

Coord = Tuple[int, int]

class Unit:
    def __init__(self, grid_pos: Coord, tile_w: int, tile_h: int, origin: Tuple[int, int], speed_pps: float = 220.0) -> None:
        self.grid: Coord = grid_pos
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.origin = origin
        self.speed = speed_pps
        self.overwatch = False

        cx, cy = tile_center(*self.grid, self.tile_w, self.tile_h, self.origin)
        self.pos_x = float(cx)
        self.pos_y = float(cy)

        self._waypoints: deque[Tuple[float, float]] = deque()
        self._pending_ap_cost: int = 0

        self.ap_max = 2
        self.ap = 2

    def can_afford(self, ap_cost: int) -> bool:
        return ap_cost > 0 and ap_cost <= self.ap

    def set_path(self, path: List[Coord], ap_cost: int) -> None:
        """
        Provide a tile path from current grid (excluded) to destination (included).
        Consumes ap at completion.
        """
        self._waypoints.clear()
        for (i, j) in path:
            cx, cy = tile_center(i, j, self.tile_w, self.tile_h, self.origin)
            self._waypoints.append((float(cx), float(cy)))
        self._pending_ap_cost = ap_cost

    def update(self, dt: float) -> None:
        if not self._waypoints:
            return

        tx, ty = self._waypoints[0]
        dx = tx - self.pos_x
        dy = ty - self.pos_y
        dist = math.hypot(dx, dy)
        step = self.speed * dt

        if dist <= step or dist == 0.0:
            # Snap to waypoint
            self.pos_x, self.pos_y = tx, ty
            self._waypoints.popleft()
            # Update grid index when we arrive on a tile center
            if not self._waypoints:
                # Recompute integer grid from pos by reversing the center math
                # We can approximate using nearest grid by projecting back to top vertex then to grid
                # but since we know the last waypoint was exact center for (i,j), we can set grid = that tile.
                # To get that tile, use center back to top: top_y = cy - tile_h//2, top_x = cx
                # then convert via origin inverses — not needed if we track the last tile directly.
                pass
        else:
            nx = dx / dist
            ny = dy / dist
            self.pos_x += nx * step
            self.pos_y += ny * step

        # If we just consumed the last waypoint this frame, settle bookkeeping
        if not self._waypoints and self._pending_ap_cost > 0:
            # Deduct AP and update grid index based on final position
            # Recover grid by snapping to nearest center tile using rounding in screen_to_grid,
            # but we avoid importing it here to reduce coupling. Caller should update grid externally
            # after calling update() if needed. We'll signal completion by returning True from done().
            self.ap -= self._pending_ap_cost
            self._pending_ap_cost = 0

    def is_moving(self) -> bool:
        return bool(self._waypoints)

    def done(self) -> bool:
        return not self._waypoints and self._pending_ap_cost == 0

    def set_grid_immediate(self, grid_pos: Coord) -> None:
        """Snap to a grid tile (e.g., after finishing a move)."""
        self.grid = grid_pos
        cx, cy = tile_center(*self.grid, self.tile_w, self.tile_h, self.origin)
        self.pos_x = float(cx)
        self.pos_y = float(cy)
        # --- Overwatch ---
    def set_overwatch(self, ap_cost: int) -> bool:
        if self.is_moving() or self.overwatch or self.ap < ap_cost:
            return False
        self.ap -= ap_cost
        self.overwatch = True
        return True

    def clear_overwatch(self) -> None:
        self.overwatch = False

