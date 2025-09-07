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
from engine.enemy import Enemy
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

def draw_crates(surface: pg.Surface, tmap: TileMap) -> None:
    for (i, j) in tmap.crates:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        # draw a smaller “box” impression (diamond inset)
        inset = [(int(x + (sx - x) * 0.2), int(y + (sy + S.TILE_H // 2 - y) * 0.2)) for (x, y) in poly]
        pg.draw.polygon(surface, C.CRATE_FILL, inset)
        pg.draw.polygon(surface, C.CRATE_OUTLINE, inset, width=2)

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
    """Simple circle sprite at the unit's pixel position; ring if selected; OW ring if on overwatch."""
    r = max(6, S.TILE_H // 3)
    if getattr(u, "overwatch", False):
        pg.draw.circle(surface, C.OVERWATCH_RING, (int(u.pos_x), int(u.pos_y)), r + 6, width=2)
    pg.draw.circle(surface, C.UNIT_FILL, (int(u.pos_x), int(u.pos_y)), r)
    pg.draw.circle(surface, C.UNIT_OUTLINE, (int(u.pos_x), int(u.pos_y)), r, width=2)
    if selected:
        pg.draw.circle(surface, C.SELECT_OUTLINE, (int(u.pos_x), int(u.pos_y)), r + 3, width=2)
    # ammo pips under the unit
    draw_ammo_pips(surface, u)


def draw_enemies(surface: pg.Surface, enemies: List[Enemy]) -> None:
    r = max(7, S.TILE_H // 3 + 2)
    font_small = pg.font.SysFont("consolas", 14)
    for e in enemies:
        i, j = e.grid
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        cx, cy = sx, sy + S.TILE_H // 2
        pg.draw.circle(surface, C.ENEMY_FILL, (cx, cy), r)
        pg.draw.circle(surface, C.ENEMY_OUTLINE, (cx, cy), r, width=2)
        surf = font_small.render(str(max(0, e.hp)), True, C.TEXT)
        surface.blit(surf, (cx - surf.get_width() // 2, cy - r - surf.get_height()))


def draw_ammo_pips(surface: pg.Surface, u: Unit) -> None:
    # Tiny rectangles below the unit indicating current clip
    cx, cy = int(u.pos_x), int(u.pos_y)
    n = u.clip_max
    w, h, gap = 6, 8, 2
    total_w = n * w + (n - 1) * gap
    x0 = cx - total_w // 2
    y0 = cy + (S.TILE_H // 2) + 6
    for k in range(n):
        rect = pg.Rect(x0 + k * (w + gap), y0, w, h)
        color = C.AMMO_FULL if k < u.ammo else C.AMMO_EMPTY
        pg.draw.rect(surface, color, rect)
        pg.draw.rect(surface, C.UNIT_OUTLINE, rect, 1)


# ---------- Helpers (occupancy, enemies) ----------

def get_unit_at(units: List[Unit], tile: Coord) -> Optional[Unit]:
    for u in units:
        if u.grid == tile:
            return u
    return None


def get_enemy_at(enemies: List[Enemy], tile: Coord) -> Optional[Enemy]:
    for e in enemies:
        if e.grid == tile:
            return e
    return None


def occupied_tiles(units: List[Unit], exclude: Optional[Unit] = None) -> Set[Coord]:
    occ: Set[Coord] = set()
    for u in units:
        if exclude is not None and u is exclude:
            continue
        occ.add(u.grid)
    return occ


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
    t = 0.22
    base1 = (int(cx + (a[0]-b[0]) * t), int(cy + (a[1]-b[1]) * t))
    base2 = (int(cx + (b[0]-a[0]) * t), int(cy + (b[1]-a[1]) * t))
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

# ---------- Vision / Fog of War ----------
def compute_visible_tiles(units: List[Unit], tmap: TileMap) -> Set[Coord]:
    visible: Set[Coord] = set()
    walls = set(tmap.blocked)  # only walls block vision
    R = S.VISION_RANGE_TILES
    for u in units:
        ui, uj = u.grid
        for j in range(max(0, uj - R), min(S.GRID_ROWS, uj + R + 1)):
            for i in range(max(0, ui - R), min(S.GRID_COLS, ui + R + 1)):
                if manhattan((ui, uj), (i, j)) > R:
                    continue
                if has_los((ui, uj), (i, j), walls):
                    visible.add((i, j))
        visible.add(u.grid)
    return visible

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
def draw_selection(surface: pg.Surface, selected: tuple[int, int] | None) -> None:
    if not selected:
        return
    i, j = selected
    sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
    poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
    pg.draw.polygon(surface, C.SELECT_FILL, poly)
    pg.draw.polygon(surface, C.SELECT_OUTLINE, poly, width=2)


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

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


def calc_shot_chances(shooter: Coord, target: Coord, tmap: TileMap, aim_delta: int = 0) -> Optional[tuple[int, int]]:
    if not has_los(shooter, target, set(tmap.blocked)):
        return None
    aim = S.BASE_AIM + aim_delta
    defense = 0
    flanked = not cover_full_on_facing(target, shooter, tmap)
    if not flanked:
        defense += S.COVER_FULL_DEF
    hit = max(S.HIT_FLOOR, min(S.HIT_CEIL, aim - defense))
    crit = max(0, min(100, S.BASE_CRIT + (S.FLANK_CRIT if flanked else 0)))
    return hit, crit


def draw_shot_preview(surface: pg.Surface, font: pg.font.Font, shooter_unit: Unit, hovered: Coord, tmap: TileMap, enemies: List[Enemy]) -> None:
    if get_enemy_at(enemies, hovered) is None:
        return
    sx, sy = grid_to_screen(*hovered, S.TILE_W, S.TILE_H, S.ORIGIN)
    cx, cy = sx, sy + S.TILE_H // 2
    # If shooter is dry, show a hint but still allow LOS preview below
    if not shooter_unit.has_ammo():
        txt_na = font.render("NO AMMO", True, C.KILL_TEXT)
        surface.blit(txt_na, (cx - txt_na.get_width() // 2, cy - S.TILE_H - 16))
    chances = calc_shot_chances(shooter_unit.grid, hovered, tmap)
    if chances is None:
        txt = font.render("NO LOS", True, C.SHOT_NLOS)
        surface.blit(txt, (cx - txt.get_width() // 2, cy - S.TILE_H))
        return
    hit, crit = chances
    extra = f"(+{S.CRIT_BONUS_DMG})" if S.CRIT_BONUS_DMG else ""
    line = f"HIT {hit}%   CRIT {crit}%   DMG {S.WEAPON_DMG_MIN}-{S.WEAPON_DMG_MAX}{extra}"
    txt = font.render(line, True, C.SHOT_TEXT)
    surface.blit(txt, (cx - txt.get_width() // 2, cy - S.TILE_H))


def resolve_shot(rng: random.Random, shooter: Unit, target_tile: Coord, tmap: TileMap, enemies: List[Enemy], log: List[str], aim_delta: int = 0, tag: str = "Shot") -> None:
    # Ammo/AP checks
    if shooter.is_moving():
        return
    target = get_enemy_at(enemies, target_tile)
    if target is None:
        return
    if tag == "Shot":
        if shooter.ap < S.SHOOT_AP_COST:
            return
        if not shooter.has_ammo():
            log.append("Click: OUT OF AMMO (press R to reload)")
            return
    else:  # OVERWATCH shot
        if not shooter.has_ammo():
            # Nothing happens, OW will be cleared by caller
            return

    chances = calc_shot_chances(shooter.grid, target_tile, tmap, aim_delta=aim_delta)
    if chances is None:
        return

    hit_ch, crit_ch, _ctag = chances
    roll = rng.randint(1, 100)
    if roll <= hit_ch:
        crit_roll = rng.randint(1, 100)
        is_crit = crit_roll <= crit_ch
        dmg = rng.randint(S.WEAPON_DMG_MIN, S.WEAPON_DMG_MAX) + (S.CRIT_BONUS_DMG if is_crit else 0)
        target.hp -= dmg
        msg = f"{tag} {target_tile}: HIT for {dmg}{' (CRIT)' if is_crit else ''}"
        if target.hp <= 0:
            enemies.remove(target)
            msg += " — KILL"
        log.append(msg)
    else:
        log.append(f"{tag} {target_tile}: MISS")

    # Spend resources
    shooter.spend_ammo()
    if tag == "Shot":
        # Firing is turn-ending in classic XCOM. Zero out remaining AP.
        shooter.ap = 0


# ---------- Enemy phase & overwatch ----------

def plan_enemy_paths(enemies: List[Enemy], squad: List[Unit], tmap: TileMap) -> Dict[Enemy, List[Coord]]:
    """For each enemy, path toward nearest soldier. Paths exclude final tile if occupied by soldier."""
    occ_squad = {u.grid for u in squad}
    occ_en = {e.grid for e in enemies}
    blocked_static = set(tmap.blocked)

    plans: Dict[Enemy, List[Coord]] = {}
    for e in enemies:
        best_path: List[Coord] = []
        best_len = 10**9
        for u in squad:
            blocked = blocked_static | (occ_squad - {u.grid}) | (occ_en - {e.grid})
            path = a_star(e.grid, u.grid, S.GRID_COLS, S.GRID_ROWS, blocked)
            if path and len(path) < best_len:
                best_path = path
                best_len = len(path)
        if best_path:
            plans[e] = best_path
    return plans


def process_overwatch_triggers(rng: random.Random, squad: List[Unit], mover: Enemy, tmap: TileMap, enemies: List[Enemy], log: List[str]) -> None:
    """Any unit on OW with LOS to mover gets a reaction shot (with aim malus)."""
    for u in squad:
        if not getattr(u, "overwatch", False):
            continue
        if has_los(u.grid, mover.grid, set(tmap.blocked)):
            resolve_shot(rng, u, mover.grid, tmap, enemies, log, aim_delta=-S.OVERWATCH_AIM_MALUS, tag="OVERWATCH")
            u.clear_overwatch()
            if get_enemy_at(enemies, mover.grid) is None:
                break
# ---------- Action bar ----------
def _btn_rects() -> list[pg.Rect]:
    W, H = S.WINDOW_W, S.WINDOW_H
    bar_h = S.UI_BAR_H
    x = 10
    y = H - bar_h + (bar_h - S.UI_BTN_H)//2
    rects = []
    for _ in range(4):  # Fire, Overwatch, Reload, End Turn
        rects.append(pg.Rect(x, y, S.UI_BTN_W, S.UI_BTN_H))
        x += S.UI_BTN_W + S.UI_BTN_GAP
    return rects
def _draw_button(surface: pg.Surface, rect: pg.Rect, label: str, enabled: bool, mouse_pos: tuple[int,int]) -> None:
    hover = rect.collidepoint(mouse_pos)
    if not enabled:
        fill = C.UI_BTN_DISABLED
    else:
        fill = C.UI_BTN_HOVER if hover else C.UI_BTN
    pg.draw.rect(surface, fill, rect, border_radius=8)
    pg.draw.rect(surface, C.UI_FRAME, rect, width=2, border_radius=8)
    font_btn = pg.font.SysFont("consolas", 18)
    txt = font_btn.render(label, True, C.UI_BTN_TEXT if enabled else (180,180,185))
def draw_action_bar(surface: pg.Surface, sel: Unit, hovered: Coord | None, tmap: TileMap, enemies: List[Enemy], tm: TurnManager, squad: List[Unit], visible: Set[Coord]) -> dict[str, pg.Rect]:
    W, H = S.WINDOW_W, S.WINDOW_H
    bar = pg.Rect(0, H - S.UI_BAR_H, W, S.UI_BAR_H)
    pg.draw.rect(surface, C.UI_BG, bar)
    pg.draw.rect(surface, C.UI_FRAME, bar, width=2)

    can_fire = False
    if tm.phase is Phase.PLAYER and not sel.is_moving() and sel.ap > 0 and sel.has_ammo() and hovered is not None and any(e.grid == hovered for e in enemies) and hovered in visible:
        can_fire = calc_shot_chances(sel.grid, hovered, tmap) is not None

    can_ow   = tm.phase is Phase.PLAYER and not sel.is_moving() and sel.ap > 0 and sel.has_ammo() and not sel.overwatch
    can_rel  = tm.phase is Phase.PLAYER and not sel.is_moving() and sel.ap >= S.RELOAD_AP_COST and sel.ammo < sel.clip_max
    can_end  = tm.phase is Phase.PLAYER and all(not u.is_moving() for u in squad)

    r_fire, r_ow, r_rel, r_end = _btn_rects()
    _draw_button(surface, r_fire, "Fire (F)", can_fire, pg.mouse.get_pos())
    _draw_button(surface, r_ow,   "Overwatch (O)", can_ow, pg.mouse.get_pos())
    _draw_button(surface, r_rel,  "Reload (R)", can_rel, pg.mouse.get_pos())
    _draw_button(surface, r_end,  "End Turn (Enter)", can_end, pg.mouse.get_pos())

    return {"fire": r_fire, "ow": r_ow, "reload": r_rel, "end": r_end}

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
    enemies: List[Enemy],
    log: List[str],
    tmap: TileMap
) -> None:
    phase_txt = "PLAYER" if tm.phase is Phase.PLAYER else "ENEMY"
    selected = units[sel_idx] if units else None
    lines = [
        f"Turn: {tm.turn}   Phase: {phase_txt}",
        f"Hovered: {hovered}" if hovered is not None else "Hovered: None",
        f"Selected@{selected.grid if selected else None}  AP: {selected.ap if selected else 0}/{selected.ap_max if selected else 0}  AMMO: {selected.ammo if selected else 0}/{selected.clip_max if selected else 0}  {'[OW]' if (selected and getattr(selected, 'overwatch', False)) else ''}",
        f"Inspect origin: {inspect_tile}",
        f"Enemies: {len(enemies)}   Walls:{len(tmap.blocked)}  Crates:{len(getattr(tmap, 'crates', set()))}",
        f"Origin: {S.ORIGIN}  Tile: {S.TILE_W}x{S.TILE_H}  Grid: {S.GRID_COLS}x{S.GRID_ROWS}",
        f"1 AP tiles: {S.MOVEMENT_TILES_PER_AP} (dash=2x)",
        "Controls: TAB cycle | 1-9 select | L-Click select/move | F fire (turn-ending) | O overwatch (turn-ending) | R reload (1 AP) | N enemy | B wall | H crate | ENTER/E end turn | ESC quit",
    ]
    if path_info is not None:
        steps, ap_cost = path_info
        lines.insert(5, f"Path steps: {steps}   AP cost: {ap_cost}")
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
        pg.display.set_caption("XCOM Iso — Overwatch, Enemy AI, Inspect, Firing & Ammo")
        clock = pg.time.Clock()
        font = pg.font.SysFont("consolas", 16)

        rng = random.Random(1337)

        tmap = TileMap(S.GRID_COLS, S.GRID_ROWS)
        squad: List[Unit] = [Unit(pos, S.TILE_W, S.TILE_H, S.ORIGIN, S.MOVE_SPEED_PPS) for pos in S.UNIT_SPAWNS]
        sel_idx = 0
        tm = TurnManager()

        enemies: List[Enemy] = []
        inspect_tile: Coord | None = None
        pending_dest: Dict[Unit, Coord] = {}
        log: List[str] = []

        enemy_plans: Optional[Dict[Enemy, List[Coord]]] = None
        enemy_step_timer = 0.0
        enemy_steps_left: Dict[Enemy, int] = {}

        running = True
        while running:
            dt = clock.tick(S.FPS) / 1000.0

            for e in pg.event.get():
                if e.type == pg.QUIT:
                    running = False
                elif e.type == pg.KEYDOWN:
                    if e.key == pg.K_ESCAPE:
                        running = False
                    elif tm.phase is Phase.PLAYER:
                        if e.key == pg.K_TAB:
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
                        elif pg.K_1 <= e.key <= pg.K_9:
                            k = e.key - pg.K_1
                            if k < len(squad):
                                sel_idx = k
                        elif e.key == pg.K_b:
                            hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                            if tmap.in_bounds(hov) and get_unit_at(squad, hov) is None and get_enemy_at(enemies, hov) is None:
                                tmap.toggle_block(hov)
                            if inspect_tile == hov:
                                inspect_tile = None

                        elif e.key == pg.K_h:
                            hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                            if tmap.in_bounds(hov) and get_unit_at(squad, hov) is None and get_enemy_at(enemies, hov) is None and hov not in tmap.blocked:
                                if hasattr(tmap, "toggle_crate"):
                                    tmap.toggle_crate(hov)
                        elif e.key == pg.K_n:
                            hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                            if tmap.in_bounds(hov) and hov not in tmap.blocked and get_unit_at(squad, hov) is None:
                                ex = get_enemy_at(enemies, hov)
                                if ex:
                                    enemies.remove(ex)
                                else:
                                    enemies.append(Enemy(hov, getattr(S, "ENEMY_DEFAULT_HP", 3)))
                            if inspect_tile == hov:
                                inspect_tile = None
                        elif e.key == pg.K_f:
                            sel = squad[sel_idx]
                            hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                            resolve_shot(rng, sel, hov, tmap, enemies, log, tag="Shot")
                        elif e.key == pg.K_o:
                            if squad[sel_idx].set_overwatch(getattr(S, "OVERWATCH_AP_COST", 1)):
                                log.append(f"Unit@{squad[sel_idx].grid} set OVERWATCH")
                        elif e.key == pg.K_r:
                            if squad[sel_idx].reload(S.RELOAD_AP_COST):
                                log.append(f"Reloaded @ {squad[sel_idx].grid}")
                            else:
                                if squad[sel_idx].ammo >= squad[sel_idx].clip_max:
                                    log.append("Reload: clip already full")
                                elif squad[sel_idx].ap < S.RELOAD_AP_COST:
                                    log.append("Reload: not enough AP")
                        elif e.key in (pg.K_RETURN, pg.K_e):
                            if all(not u.is_moving() for u in squad):
                                tm.end_player_turn()
                                enemy_plans = plan_enemy_paths(enemies, squad, tmap)
                                enemy_steps_left = {en: min(getattr(S, "ENEMY_STEPS_PER_TURN", 3), len(path)) for en, path in (enemy_plans or {}).items()}
                                enemy_step_timer = 0.0
                elif e.type == pg.MOUSEBUTTONDOWN and tm.phase is Phase.PLAYER:

                    # Action bar click test (left-click on UI buttons)
                    if e.button == 1:
                        rects = _btn_rects()
                        labels = ["fire", "ow", "reload", "end"]
                        hit = None
                        for rect, name in zip(rects, labels):
                            if rect.collidepoint(e.pos):
                                hit = name
                                break
                        if hit is not None:
                            sel = squad[sel_idx]
                            hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                            if hit == "fire":
                                if (tm.phase is Phase.PLAYER and not sel.is_moving() and sel.ap > 0 and sel.has_ammo()
                                    and get_enemy_at(enemies, hov) and calc_shot_chances(sel.grid, hov, tmap)):
                                    resolve_shot(rng, sel, hov, tmap, enemies, log, tag="Shot")
                            elif hit == "ow":
                                if sel.set_overwatch(getattr(S, "OVERWATCH_AP_COST", 1)):
                                    log.append(f"Unit@{sel.grid} set OVERWATCH")
                            elif hit == "reload":
                                if sel.reload(getattr(S, "RELOAD_AP_COST", 1)):
                                    log.append(f"Reloaded @ {sel.grid}")
                                else:
                                    if sel.ammo >= sel.clip_max:
                                        log.append("Reload: clip already full")
                                    elif sel.ap < getattr(S, "RELOAD_AP_COST", 1):
                                        log.append("Reload: not enough AP")
                            elif hit == "end":
                                if all(not u.is_moving() for u in squad):
                                    tm.end_player_turn()
                                    enemy_plans = plan_enemy_paths(enemies, squad, tmap)
                                    enemy_steps_left = {en: min(getattr(S, "ENEMY_STEPS_PER_TURN", 3), len(path)) for en, path in (enemy_plans or {}).items()}
                                    enemy_step_timer = 0.0
                            # # Prevent world-click logic when clicking UI
                            # continue
                            #     i, j = screen_to_grid(*e.pos, S.TILE_W, S.TILE_H, S.ORIGIN)
                            #     tile = (i, j)
                            #     if e.button == 1:
                            #         u_on_tile = get_unit_at(squad, tile)
                            #         if u_on_tile is not None:
                            #             sel_idx = squad.index(u_on_tile)
                            #         else:
                            #             sel = squad[sel_idx]
                            #             if tmap.in_bounds(tile) and tmap.passable(tile) and get_enemy_at(enemies, tile) is None:
                            #                 occ = occupied_tiles(squad, exclude=sel) | {e.grid for e in enemies}
                            #                 if tile not in occ:
                            #                     blocked = set(tmap.blocked) | occ
                            #                     path = a_star(sel.grid, tile, S.GRID_COLS, S.GRID_ROWS, blocked)
                            #                     if path:
                            #                         steps = len(path)
                            #                         ap_cost = math.ceil(steps / S.MOVEMENT_TILES_PER_AP)
                            #                         if sel.can_afford(ap_cost):
                            #                             sel.set_path(path, ap_cost)
                            #                             pending_dest[sel] = tile
                            #     elif e.button == 3:
                            #         if tmap.in_bounds(tile):
                            #             inspect_tile = None if inspect_tile == tile else tile

            # Update units
            for u in squad:
                u.update(dt)
                if u in pending_dest and not u.is_moving():
                    u.set_grid_immediate(pending_dest[u])
                    del pending_dest[u]

            # Enemy phase simulation
            if tm.phase is Phase.ENEMY:
                enemy_step_timer += dt
                if enemy_plans is None:
                    enemy_plans = plan_enemy_paths(enemies, squad, tmap)
                    enemy_steps_left = {en: min(getattr(S, "ENEMY_STEPS_PER_TURN", 3), len(path)) for en, path in enemy_plans.items()}
                while enemy_step_timer >= getattr(S, "ENEMY_STEP_TIME", 0.3):
                    enemy_step_timer -= getattr(S, "ENEMY_STEP_TIME", 0.3)
                    anyone_moved = False
                    occupied_now = {e.grid for e in enemies} | {u.grid for u in squad} | set(tmap.blocked)
                    for en in list(enemies):
                        path = (enemy_plans or {}).get(en, [])
                        if enemy_steps_left.get(en, 0) <= 0 or not path:
                            continue
                        next_tile = path[0]
                        if next_tile in occupied_now:
                            continue
                        en.grid = next_tile
                        enemy_plans[en] = path[1:]
                        enemy_steps_left[en] -= 1
                        anyone_moved = True

                        process_overwatch_triggers(rng, squad, en, tmap, enemies, log)
                        occupied_now = {e.grid for e in enemies} | {u.grid for u in squad} | set(tmap.blocked)

                    if not anyone_moved:
                        break

                still_moving = any(enemy_steps_left.get(en, 0) > 0 and enemy_plans.get(en) for en in enemies)
                if not still_moving:
                    tm.complete_enemy_turn()
                    for u in squad:
                        u.ap = u.ap_max
                        u.clear_overwatch()
                    enemy_plans = None
                    enemy_steps_left = {}
            visible = compute_visible_tiles(squad, tmap)
            # Draw
            screen.fill(C.BG)
            draw_grid(screen)
            draw_obstacles(screen, tmap)
            draw_crates(screen, tmap)
            draw_enemies(screen, enemies)

            sel = squad[sel_idx] if squad else None

            # Ranges & preview origin: INSPECT tile if set, else selected unit
            origin_for_ranges = inspect_tile if inspect_tile is not None else (sel.grid if sel else None)
            occ = occupied_tiles(squad, exclude=sel) | {e.grid for e in enemies}
            blocked = set(tmap.blocked) | occ
            available_ap = sel.ap if (sel and tm.phase is Phase.PLAYER) else 0
            draw_move_ranges(screen, origin_for_ranges, tmap, available_ap, blocked)

            hovered = draw_hover(screen, pg.mouse.get_pos())
            path_info = draw_path_preview(screen, origin_for_ranges, hovered, tmap, blocked) if tm.phase is Phase.PLAYER else None

            # Cover pips on hovered tile
            if hovered:
                draw_cover_pips(screen, hovered, tmap)

            # LOS & flank + shot preview when hovering an enemy
            if hovered and get_enemy_at(enemies, hovered) and sel:
                draw_los_and_flank(screen, sel.grid, hovered, tmap, font)
                draw_shot_preview(screen, font, sel, hovered, tmap, enemies)

            for i, u in enumerate(squad):
                draw_unit(screen, u, selected=(i == sel_idx))

            draw_tile_selection(screen, inspect_tile)
            # Action bar
            rects = draw_action_bar(screen, sel, hovered, tmap, enemies, tm, squad, visible)


            draw_debug(screen, font, hovered, squad, sel_idx, path_info, tm, inspect_tile, enemies, log, tmap)

            pg.display.flip()

        return 0
    finally:
        pg.quit()


if __name__ == "__main__":
    sys.exit(main())