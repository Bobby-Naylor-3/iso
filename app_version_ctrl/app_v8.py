from __future__ import annotations
import sys
import math
from typing import List, Tuple, Optional, Dict, Set
import pygame as pg

import settings as S
from engine.iso import grid_to_screen, screen_to_grid, diamond_points
from engine import colors as C
from engine.map import TileMap
from engine.pathfinding import a_star
from engine.unit import Unit
from engine.turns import TurnManager, Phase

Coord = Tuple[int, int]


# ---------- Drawing ----------

def draw_grid(surface: pg.Surface) -> None:
    """Isometric diamond grid with checkerboard fill and thin outlines."""
    for j in range(S.GRID_ROWS):
        for i in range(S.GRID_COLS):
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
            fill = C.GRID_A if (i + j) % 2 == 0 else C.GRID_B
            pg.draw.polygon(surface, fill, poly)
            pg.draw.polygon(surface, C.OUTLINE, poly, width=1)


def draw_obstacles(surface: pg.Surface, tmap: TileMap) -> None:
    """Paint blocked tiles."""
    for (i, j) in tmap.blocked:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(surface, C.OBSTACLE_FILL, poly)
        pg.draw.polygon(surface, C.OBSTACLE_OUTLINE, poly, width=2)


def draw_hover(surface: pg.Surface, mouse_pos: tuple[int, int]) -> tuple[int, int] | None:
    """Highlight the tile under the mouse; return (i, j) or None."""
    mx, my = mouse_pos
    i, j = screen_to_grid(mx, my, S.TILE_W, S.TILE_H, S.ORIGIN)
    if 0 <= i < S.GRID_COLS and 0 <= j < S.GRID_ROWS:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(surface, C.HOVER_FILL, poly)
        pg.draw.polygon(surface, C.HOVER_OUTLINE, poly, width=2)
        return (i, j)
    return None


def draw_tile_selection(surface: pg.Surface, tile: tuple[int, int] | None) -> None:
    """Render a selected/inspection tile diamond, if any."""
    if not tile:
        return
    i, j = tile
    sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
    poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
    pg.draw.polygon(surface, C.SELECT_FILL, poly)
    pg.draw.polygon(surface, C.SELECT_OUTLINE, poly, width=2)


def draw_unit(surface: pg.Surface, u: Unit, selected: bool) -> None:
    """Simple circle sprite at the unit's pixel position; ring if selected."""
    r = max(6, S.TILE_H // 3)
    pg.draw.circle(surface, C.UNIT_FILL, (int(u.pos_x), int(u.pos_y)), r)
    pg.draw.circle(surface, C.UNIT_OUTLINE, (int(u.pos_x), int(u.pos_y)), r, width=2)
    if selected:
        pg.draw.circle(surface, C.SELECT_OUTLINE, (int(u.pos_x), int(u.pos_y)), r + 3, width=2)


# ---------- Occupancy / Ranges / Paths ----------

def occupied_tiles(units: List[Unit], exclude: Optional[Unit] = None) -> Set[Coord]:
    occ: Set[Coord] = set()
    for u in units:
        if exclude is not None and u is exclude:
            continue
        occ.add(u.grid)
    return occ


def bfs_reachable(origin: Coord, max_steps: int, tmap: TileMap, extra_blocked: Set[Coord]) -> set[Coord]:
    """Uniform-cost BFS limited by max_steps, treating extra_blocked tiles as impassable."""
    from collections import deque
    frontier = deque()
    frontier.append((origin, 0))
    visited = {origin}
    reachable: set[Coord] = set()

    while frontier:
        (ci, cj), d = frontier.popleft()
        if d == max_steps:
            continue
        for (ni, nj) in ((ci+1,cj), (ci-1,cj), (ci,cj+1), (ci,cj-1)):
            nc = (ni, nj)
            if not tmap.in_bounds(nc) or not tmap.passable(nc) or nc in extra_blocked or nc in visited:
                continue
            visited.add(nc)
            reachable.add(nc)
            frontier.append((nc, d + 1))
    return reachable


def draw_move_ranges(
    surface: pg.Surface,
    origin: Coord | None,
    tmap: TileMap,
    available_ap: int,
    occ: Set[Coord],
) -> None:
    """Obstacle- & occupancy-aware rings. Blue if AP>=1; yellow if AP>=2."""
    if not origin or available_ap <= 0:
        return

    overlay = pg.Surface(surface.get_size(), pg.SRCALPHA)

    blue = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP, tmap, occ)
    for (i, j) in blue:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(overlay, C.MOVE_BLUE_FILL, poly)
        pg.draw.polygon(overlay, C.MOVE_BLUE_OUTLINE, poly, width=1)

    if available_ap >= 2:
        yellow = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP * 2, tmap, occ) - blue
        for (i, j) in yellow:
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
            pg.draw.polygon(overlay, C.MOVE_YELLOW_FILL, poly)
            pg.draw.polygon(overlay, C.MOVE_YELLOW_OUTLINE, poly, width=1)

    surface.blit(overlay, (0, 0))


def draw_path_preview(
    surface: pg.Surface,
    origin: Coord | None,
    hovered: Coord | None,
    tmap: TileMap,
    blocked: Set[Coord],
) -> tuple[int, int] | None:
    """A* path preview from origin to hovered; caps at 2 AP. Returns (steps, ap_cost)."""
    if not origin or not hovered:
        return None
    if hovered in blocked or not tmap.passable(hovered):
        return None

    path = a_star(origin, hovered, S.GRID_COLS, S.GRID_ROWS, blocked)
    if not path:
        return None

    max_steps = S.MOVEMENT_TILES_PER_AP * 2
    path = path[:max_steps]

    overlay = pg.Surface(surface.get_size(), pg.SRCALPHA)
    for (i, j) in path:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(overlay, C.PATH_FILL, poly)
        pg.draw.polygon(overlay, C.PATH_OUTLINE, poly, width=1)
    surface.blit(overlay, (0, 0))

    steps = len(path)
    ap_cost = math.ceil(steps / S.MOVEMENT_TILES_PER_AP) if steps > 0 else 0
    return steps, ap_cost


# ---------- Debug HUD ----------

def draw_debug(
    surface: pg.Surface,
    font: pg.font.Font,
    hovered: Coord | None,
    units: List[Unit],
    sel_idx: int,
    path_info: tuple[int, int] | None,
    tm: TurnManager,
    inspect_tile: Coord | None,
) -> None:
    phase_txt = "PLAYER" if tm.phase is Phase.PLAYER else "ENEMY"
    selected = units[sel_idx] if units else None
    lines = [
        f"Turn: {tm.turn}   Phase: {phase_txt}",
        f"Hovered: {hovered}" if hovered is not None else "Hovered: None",
        f"Selected idx: {sel_idx}  Grid: {selected.grid if selected else None}  AP: {selected.ap if selected else 0}/{selected.ap_max if selected else 0}",
        f"Inspect origin: {inspect_tile}",
        f"Origin: {S.ORIGIN}  Tile: {S.TILE_W}x{S.TILE_H}  Grid: {S.GRID_COLS}x{S.GRID_ROWS}",
        f"1 AP tiles: {S.MOVEMENT_TILES_PER_AP} (dash=2x)",
        "TAB: cycle unit   NUM[1..9]: select   ENTER/E: end turn   L-Click: select/move   R-Click: set/clear INSPECT tile   B: toggle obstacle   R: refill AP (selected)   ESC: quit",
    ]
    if path_info is not None:
        steps, ap_cost = path_info
        lines.insert(4, f"Path steps: {steps}   AP cost: {ap_cost}")

    ap_line = "Squad AP: " + "  ".join(f"{i}:{u.ap}/{u.ap_max}@{u.grid}" for i, u in enumerate(units))
    lines.append(ap_line)

    x, y = 10, 10
    for text in lines:
        surf = font.render(text, True, C.TEXT)
        surface.blit(surf, (x, y))
        y += surf.get_height() + 2


# ---------- Main ----------

def main() -> int:
    pg.init()
    try:
        screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
        pg.display.set_caption("XCOM Iso — Squad, Turns, Inspect & Obstacles")
        clock = pg.time.Clock()
        font = pg.font.SysFont("consolas", 16)

        tmap = TileMap(S.GRID_COLS, S.GRID_ROWS)
        squad: List[Unit] = [Unit(pos, S.TILE_W, S.TILE_H, S.ORIGIN, S.MOVE_SPEED_PPS) for pos in S.UNIT_SPAWNS]
        sel_idx = 0
        tm = TurnManager()

        inspect_tile: Coord | None = None
        pending_dest: Dict[Unit, Coord] = {}

        running = True
        while running:
            dt = clock.tick(S.FPS) / 1000.0  # seconds

            for e in pg.event.get():
                if e.type == pg.QUIT:
                    running = False
                elif e.type == pg.KEYDOWN:
                    if e.key == pg.K_ESCAPE:
                        running = False
                    elif e.key == pg.K_TAB and tm.phase is Phase.PLAYER:
                        # Cycle to next unit (prefer one with AP > 0 and not moving)
                        if squad:
                            start = (sel_idx + 1) % len(squad)
                            idx = start
                            chosen = start
                            for _ in range(len(squad)):
                                if not squad[idx].is_moving() and squad[idx].ap > 0:
                                    chosen = idx
                                    break
                                idx = (idx + 1) % len(squad)
                            sel_idx = chosen
                    elif pg.K_1 <= e.key <= pg.K_9 and tm.phase is Phase.PLAYER:
                        k = e.key - pg.K_1
                        if k < len(squad):
                            sel_idx = k
                    elif e.key == pg.K_b and tm.phase is Phase.PLAYER:
                        hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                        # Only toggle if no unit occupies the tile
                        if tmap.in_bounds(hov) and all(u.grid != hov for u in squad):
                            tmap.toggle_block(hov)
                            # Clear inspect tile if we just blocked it
                            if inspect_tile == hov:
                                inspect_tile = None
                    elif e.key == pg.K_r and tm.phase is Phase.PLAYER:
                        squad[sel_idx].ap = squad[sel_idx].ap_max
                    elif e.key in (pg.K_RETURN, pg.K_e):
                        if tm.phase is Phase.PLAYER and all(not u.is_moving() for u in squad):
                            tm.end_player_turn()
                elif e.type == pg.MOUSEBUTTONDOWN and tm.phase is Phase.PLAYER:
                    i, j = screen_to_grid(*e.pos, S.TILE_W, S.TILE_H, S.ORIGIN)
                    tile = (i, j)
                    if e.button == 1:
                        # Left-click: select unit if clicked on one; else try to move selected unit.
                        u_on_tile = next((u for u in squad if u.grid == tile), None)
                        if u_on_tile is not None:
                            sel_idx = squad.index(u_on_tile)
                        else:
                            sel = squad[sel_idx]
                            if tmap.in_bounds(tile) and tmap.passable(tile):
                                occ = occupied_tiles(squad, exclude=sel)
                                if tile not in occ:
                                    blocked = set(tmap.blocked) | occ
                                    path = a_star(sel.grid, tile, S.GRID_COLS, S.GRID_ROWS, blocked)
                                    if path:
                                        steps = len(path)
                                        ap_cost = math.ceil(steps / S.MOVEMENT_TILES_PER_AP)
                                        if sel.can_afford(ap_cost):
                                            sel.set_path(path, ap_cost)
                                            pending_dest[sel] = tile
                    elif e.button == 3:
                        # Right-click: toggle INSPECT tile for planning overlays (no move)
                        if tmap.in_bounds(tile):
                            inspect_tile = None if inspect_tile == tile else tile

            # Update units
            for u in squad:
                u.update(dt)
                if u in pending_dest and not u.is_moving():
                    u.set_grid_immediate(pending_dest[u])
                    del pending_dest[u]

            # Turn manager
            started_player_turn = tm.update(dt)
            if started_player_turn:
                for u in squad:
                    u.ap = u.ap_max

            # Draw
            screen.fill(C.BG)
            draw_grid(screen)
            draw_obstacles(screen, tmap)

            sel = squad[sel_idx] if squad else None
            # AP rings + path preview origin: inspection override if set, else selected unit grid
            origin_for_ranges = inspect_tile if inspect_tile is not None else (sel.grid if sel else None)
            occ = occupied_tiles(squad, exclude=sel) if sel else set()
            available_ap = sel.ap if (sel and tm.phase is Phase.PLAYER) else 0
            draw_move_ranges(screen, origin_for_ranges, tmap, available_ap, occ)

            hovered = draw_hover(screen, pg.mouse.get_pos())
            blocked = set(tmap.blocked) | occ
            path_info = (
                draw_path_preview(screen, origin_for_ranges, hovered, tmap, blocked)
                if tm.phase is Phase.PLAYER
                else None
            )

            # Units & selections
            for i, u in enumerate(squad):
                draw_unit(screen, u, selected=(i == sel_idx))
            draw_tile_selection(screen, inspect_tile)

            draw_debug(screen, font, hovered, squad, sel_idx, path_info, tm, inspect_tile)

            pg.display.flip()

        return 0
    finally:
        pg.quit()


if __name__ == "__main__":
    sys.exit(main())