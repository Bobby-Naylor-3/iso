from __future__ import annotations
import sys
import math
import random
from typing import List, Tuple, Optional, Dict, Set
import pygame as pg

import settings as S
from engine.iso import grid_to_screen, screen_to_grid, diamond_points
from engine import colors as C
from engine.map import TileMap
from engine.pathfinding import a_star
from engine.unit import Unit
from engine.turns import TurnManager, Phase
from engine.los import has_los

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


# ---------- Helpers (occupancy, enemies) ----------

def get_unit_at(units: List[Unit], tile: Coord) -> Optional[Unit]:
    for u in units:
        if u.grid == tile:
            return u
    return None


def occupied_tiles(units: List[Unit], exclude: Optional[Unit] = None) -> Set[Coord]:
    occ: Set[Coord] = set()
    for u in units:
        if exclude is not None and u is exclude:
            continue
        occ.add(u.grid)
    return occ


def draw_enemies(surface: pg.Surface, enemies: Dict[Coord, int]) -> None:
    r = max(7, S.TILE_H // 3 + 2)
    for (i, j), hp in enemies.items():
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        cx, cy = sx, sy + S.TILE_H // 2
        pg.draw.circle(surface, C.ENEMY_FILL, (cx, cy), r)
        pg.draw.circle(surface, C.ENEMY_OUTLINE, (cx, cy), r, width=2)
        # tiny hp pips text
        hp_text = str(hp)
        font_small = pg.font.SysFont("consolas", 14)
        surf = font_small.render(hp_text, True, C.TEXT)
        surface.blit(surf, (cx - surf.get_width() // 2, cy - r - surf.get_height()))


# ---------- Cover & LOS ----------

def cover_sides_from_obstacles(tile: Coord, tmap: TileMap) -> dict[str, bool]:
    """Return dict of sides {'up','right','down','left'} mapping to FULL cover True/False based on adjacent obstacles."""
    i, j = tile
    return {
        'up':    (i, j-1) in tmap.blocked,
        'right': (i+1, j) in tmap.blocked,
        'down':  (i, j+1) in tmap.blocked,
        'left':  (i-1, j) in tmap.blocked,
    }


def edge_triangle(topx: int, topy: int, tile_w: int, tile_h: int, side: str) -> list[tuple[int, int]]:
    """Small triangle pip along a diamond edge, pointing inward."""
    pts = diamond_points(topx, topy, tile_w, tile_h)
    center = ((pts[0][0] + pts[2][0]) // 2, (pts[0][1] + pts[2][1]) // 2)
    if side == 'up':
        a, b = pts[0], pts[1]
    elif side == 'right':
        a, b = pts[1], pts[2]
    elif side == 'down':
        a, b = pts[2], pts[3]
    else:  # 'left'
        a, b = pts[3], pts[0]
    cx = (a[0] + b[0]) / 2
    cy = (a[1] + b[1]) / 2
    # Base points along the edge near center
    t = 0.22
    base1 = (int(cx + (a[0]-b[0]) * t), int(cy + (a[1]-b[1]) * t))
    base2 = (int(cx + (b[0]-a[0]) * t), int(cy + (b[1]-a[1]) * t))
    # Apex toward tile center
    ax = int(cx + (center[0]-cx) * 0.45)
    ay = int(cy + (center[1]-cy) * 0.45)
    return [base1, base2, (ax, ay)]


def draw_cover_pips(surface: pg.Surface, tile: Coord, tmap: TileMap) -> None:
    i, j = tile
    sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
    sides = cover_sides_from_obstacles(tile, tmap)
    for side, full in sides.items():
        tri = edge_triangle(sx, sy, S.TILE_W, S.TILE_H, side)
        if full:
            pg.draw.polygon(surface, C.COVER_FULL, tri)
        else:
            pg.draw.polygon(surface, C.COVER_NONE, tri, width=1)


def facing_side(from_tile: Coord, to_tile: Coord) -> str:
    """Which side of 'to_tile' faces 'from_tile' (dominant axis)."""
    dx = from_tile[0] - to_tile[0]
    dy = from_tile[1] - to_tile[1]
    if abs(dx) >= abs(dy):
        return 'right' if dx > 0 else 'left'
    else:
        return 'down' if dy > 0 else 'up'


def draw_los_and_flank(surface: pg.Surface, shooter: Coord, target: Coord, tmap: TileMap, font: pg.font.Font) -> None:
    blocked = set(tmap.blocked)  # ignoring units for LOS simplicity
    los = has_los(shooter, target, blocked)
    sx0, sy0 = grid_to_screen(*shooter, S.TILE_W, S.TILE_H, S.ORIGIN)
    cx0, cy0 = sx0, sy0 + S.TILE_H // 2
    sx1, sy1 = grid_to_screen(*target, S.TILE_W, S.TILE_H, S.ORIGIN)
    cx1, cy1 = sx1, sy1 + S.TILE_H // 2
    pg.draw.line(surface, C.LOS_OK if los else C.LOS_BLOCKED, (cx0, cy0), (cx1, cy1), width=2)

    if los:
        sides = cover_sides_from_obstacles(target, tmap)
        face = facing_side(shooter, target)
        flanked = not sides.get(face, False)
        if flanked:
            txt = font.render("FLANK!", True, C.FLANK_TEXT)
            surface.blit(txt, (cx1 - txt.get_width()//2, cy1 - S.TILE_H))


# ---------- Occupancy / Ranges / Paths ----------

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
    blocked: Set[Coord],
) -> None:
    """Obstacle- & occupancy-aware rings. Blue if AP>=1; yellow if AP>=2."""
    if not origin or available_ap <= 0:
        return

    overlay = pg.Surface(surface.get_size(), pg.SRCALPHA)

    blue = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP, tmap, blocked)
    for (i, j) in blue:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(overlay, C.MOVE_BLUE_FILL, poly)
        pg.draw.polygon(overlay, C.MOVE_BLUE_OUTLINE, poly, width=1)

    if available_ap >= 2:
        yellow = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP * 2, tmap, blocked) - blue
        for (i, j) in yellow:
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
            pg.draw.polygon(overlay, C.MOVE_YELLOW_FILL, poly)
        # Outline once at the end to reduce overdrawing
        for (i, j) in yellow:
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
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


# ---------- Shooting (preview & resolution) ----------

def cover_full_on_facing(target: Coord, shooter: Coord, tmap: TileMap) -> bool:
    """Full cover if obstacle adjacent on the side of target that faces the shooter."""
    ti, tj = target
    sx, sy = shooter
    dx = sx - ti
    dy = sy - tj
    if abs(dx) >= abs(dy):
        side = (ti + (1 if dx < 0 else -1), tj)
    else:
        side = (ti, tj + (1 if dy < 0 else -1))
    return side in tmap.blocked


def calc_shot_chances(shooter: Coord, target: Coord, tmap: TileMap) -> Optional[tuple[int, int]]:
    if not has_los(shooter, target, set(tmap.blocked)):
        return None
    aim = S.BASE_AIM
    defense = 0
    flanked = not cover_full_on_facing(target, shooter, tmap)
    if not flanked:
        defense += S.COVER_FULL_DEF
    else:
        aim += S.FLANK_AIM
    hit = max(S.HIT_FLOOR, min(S.HIT_CEIL, aim - defense))
    crit = max(0, min(100, S.BASE_CRIT + (S.FLANK_CRIT if flanked else 0)))
    return hit, crit


def draw_shot_preview(surface: pg.Surface, font: pg.font.Font, shooter: Coord, hovered: Coord, tmap: TileMap, enemies: Dict[Coord, int]) -> None:
    if hovered not in enemies:
        return
    sx, sy = grid_to_screen(*hovered, S.TILE_W, S.TILE_H, S.ORIGIN)
    cx, cy = sx, sy + S.TILE_H // 2
    chances = calc_shot_chances(shooter, hovered, tmap)
    if chances is None:
        txt = font.render("NO LOS", True, C.SHOT_NLOS)
        surface.blit(txt, (cx - txt.get_width() // 2, cy - S.TILE_H))
        return
    hit, crit = chances
    extra = f"(+{S.CRIT_BONUS_DMG})" if S.CRIT_BONUS_DMG else ""
    line = f"HIT {hit}%   CRIT {crit}%   DMG {S.WEAPON_DMG_MIN}-{S.WEAPON_DMG_MAX}{extra}"
    txt = font.render(line, True, C.SHOT_TEXT)
    surface.blit(txt, (cx - txt.get_width() // 2, cy - S.TILE_H))


def resolve_shot(rng: random.Random, shooter: Unit, target_tile: Coord, tmap: TileMap, enemies: Dict[Coord, int], log: List[str]) -> None:
    if shooter.ap < S.SHOOT_AP_COST or shooter.is_moving():
        return
    chances = calc_shot_chances(shooter.grid, target_tile, tmap)
    if chances is None or target_tile not in enemies:
        return
    hit_ch, crit_ch = chances
    roll = rng.randint(1, 100)
    if roll <= hit_ch:
        crit_roll = rng.randint(1, 100)
        is_crit = crit_roll <= crit_ch
        dmg = rng.randint(S.WEAPON_DMG_MIN, S.WEAPON_DMG_MAX) + (S.CRIT_BONUS_DMG if is_crit else 0)
        enemies[target_tile] -= dmg
        shooter.ap -= S.SHOOT_AP_COST
        msg = f"Shot {target_tile}: HIT for {dmg}{' (CRIT)' if is_crit else ''}"
        if enemies[target_tile] <= 0:
            del enemies[target_tile]
            msg += " — KILL"
        log.append(msg)
    else:
        shooter.ap -= S.SHOOT_AP_COST
        log.append(f"Shot {target_tile}: MISS")


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
    enemies: Dict[Coord, int],
    log: List[str],
) -> None:
    phase_txt = "PLAYER" if tm.phase is Phase.PLAYER else "ENEMY"
    selected = units[sel_idx] if units else None
    lines = [
        f"Turn: {tm.turn}   Phase: {phase_txt}",
        f"Hovered: {hovered}" if hovered is not None else "Hovered: None",
        f"Selected idx: {sel_idx}  Grid: {selected.grid if selected else None}  AP: {selected.ap if selected else 0}/{selected.ap_max if selected else 0}",
        f"Inspect origin: {inspect_tile}",
        f"Enemies: {len(enemies)}",
        f"Origin: {S.ORIGIN}  Tile: {S.TILE_W}x{S.TILE_H}  Grid: {S.GRID_COLS}x{S.GRID_ROWS}",
        f"1 AP tiles: {S.MOVEMENT_TILES_PER_AP} (dash=2x)",
        "TAB: cycle unit   NUM[1..9]: select   ENTER/E: end turn   L-Click: select/move   R-Click: set/clear INSPECT tile   N: toggle enemy   F: fire at hovered enemy   B: toggle obstacle   R: refill AP (selected)   ESC: quit",
    ]
    if path_info is not None:
        steps, ap_cost = path_info
        lines.insert(5, f"Path steps: {steps}   AP cost: {ap_cost}")
    # recent log (last 4)
    for entry in log[-4:]:
        lines.append(entry)

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
        pg.display.set_caption("XCOM Iso — Squad, LOS, Cover, Inspect & Firing")
        clock = pg.time.Clock()
        font = pg.font.SysFont("consolas", 16)

        rng = random.Random(1337)

        tmap = TileMap(S.GRID_COLS, S.GRID_ROWS)
        squad: List[Unit] = [Unit(pos, S.TILE_W, S.TILE_H, S.ORIGIN, S.MOVE_SPEED_PPS) for pos in S.UNIT_SPAWNS]
        sel_idx = 0
        tm = TurnManager()

        enemies: Dict[Coord, int] = {}
        inspect_tile: Coord | None = None
        pending_dest: Dict[Unit, Coord] = {}
        log: List[str] = []

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
                        # Only toggle if no unit or enemy occupies the tile
                        if tmap.in_bounds(hov) and get_unit_at(squad, hov) is None and hov not in enemies:
                            tmap.toggle_block(hov)
                            if inspect_tile == hov:
                                inspect_tile = None
                    elif e.key == pg.K_n and tm.phase is Phase.PLAYER:
                        hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                        if tmap.in_bounds(hov) and hov not in tmap.blocked and get_unit_at(squad, hov) is None:
                            if hov in enemies:
                                del enemies[hov]
                            else:
                                enemies[hov] = 3  # demo HP
                            if inspect_tile == hov:
                                inspect_tile = None
                    elif e.key == pg.K_f and tm.phase is Phase.PLAYER:
                        sel = squad[sel_idx]
                        hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                        if hov in enemies:
                            resolve_shot(rng, sel, hov, tmap, enemies, log)
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
                        u_on_tile = get_unit_at(squad, tile)
                        if u_on_tile is not None:
                            sel_idx = squad.index(u_on_tile)
                        else:
                            sel = squad[sel_idx]
                            if tmap.in_bounds(tile) and tmap.passable(tile) and tile not in enemies:
                                occ = occupied_tiles(squad, exclude=sel)
                                if tile not in occ:
                                    blocked = set(tmap.blocked) | occ | set(enemies.keys())
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

            # Enemies
            draw_enemies(screen, enemies)

            sel = squad[sel_idx] if squad else None
            # AP rings + path preview origin: inspection override if set, else selected unit grid
            origin_for_ranges = inspect_tile if inspect_tile is not None else (sel.grid if sel else None)
            occ = occupied_tiles(squad, exclude=sel) if sel else set()
            blocked = set(tmap.blocked) | occ | set(enemies.keys())
            available_ap = sel.ap if (sel and tm.phase is Phase.PLAYER) else 0
            draw_move_ranges(screen, origin_for_ranges, tmap, available_ap, blocked)

            hovered = draw_hover(screen, pg.mouse.get_pos())
            path_info = (
                draw_path_preview(screen, origin_for_ranges, hovered, tmap, blocked)
                if tm.phase is Phase.PLAYER
                else None
            )

            # Cover pips on hovered tile (what cover you'd get if you stood there)
            if hovered:
                draw_cover_pips(screen, hovered, tmap)

            # LOS & flank preview if hovering an enemy
            if hovered and hovered in enemies and sel:
                draw_los_and_flank(screen, sel.grid, hovered, tmap, font)
                # Also show shot percentages
                draw_shot_preview(screen, font, sel.grid, hovered, tmap, enemies)

            # Units & selections
            for i, u in enumerate(squad):
                draw_unit(screen, u, selected=(i == sel_idx))
            draw_tile_selection(screen, inspect_tile)

            draw_debug(screen, font, hovered, squad, sel_idx, path_info, tm, inspect_tile, enemies, log)

            pg.display.flip()

        return 0
    finally:
        pg.quit()


if __name__ == "__main__":
    sys.exit(main())