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


# ---------- Render helpers ----------
def draw_grid(surface: pg.Surface) -> None:
    for j in range(S.GRID_ROWS):
        for i in range(S.GRID_COLS):
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
            fill = C.GRID_A if (i + j) % 2 == 0 else C.GRID_B
            pg.draw.polygon(surface, fill, poly)
            pg.draw.polygon(surface, C.OUTLINE, poly, width=1)

def draw_obstacles(surface: pg.Surface, tmap: TileMap) -> None:
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
    mx, my = mouse_pos
    i, j = screen_to_grid(mx, my, S.TILE_W, S.TILE_H, S.ORIGIN)
    if 0 <= i < S.GRID_COLS and 0 <= j < S.GRID_ROWS:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(surface, C.HOVER_FILL, poly)
        pg.draw.polygon(surface, C.HOVER_OUTLINE, poly, width=2)
        return (i, j)
    return None

def draw_selection(surface: pg.Surface, tile: Coord | None) -> None:
    if not tile:
        return
    i, j = tile
    sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
    poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
    pg.draw.polygon(surface, C.SELECT_FILL, poly)
    pg.draw.polygon(surface, C.SELECT_OUTLINE, poly, width=2)

def draw_unit(surface: pg.Surface, u: Unit, selected: bool) -> None:
    r = max(6, S.TILE_H // 3)
    if u.overwatch:
        pg.draw.circle(surface, C.OVERWATCH_RING, (int(u.pos_x), int(u.pos_y)), r + 6, width=2)
    pg.draw.circle(surface, C.UNIT_FILL, (int(u.pos_x), int(u.pos_y)), r)
    pg.draw.circle(surface, C.UNIT_OUTLINE, (int(u.pos_x), int(u.pos_y)), r, width=2)
    if selected:
        pg.draw.circle(surface, C.SELECT_OUTLINE, (int(u.pos_x), int(u.pos_y)), r + 3, width=2)
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

# ---------- Utility ----------
def occupied_tiles(units: List[Unit], exclude: Optional[Unit] = None) -> Set[Coord]:
    occ: Set[Coord] = set()
    for u in units:
        if exclude is not None and u is exclude:
            continue
        occ.add(u.grid)
    return occ

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

# ---------- Cover helpers ----------
def neighbor_on_side(tile: Coord, side: str) -> Coord:
    i, j = tile
    if side == 'up': return (i, j-1)
    if side == 'right': return (i+1, j)
    if side == 'down': return (i, j+1)
    return (i-1, j)  # left

def cover_level_from_adjacent(tile: Coord, tmap: TileMap, side: str) -> int:
    """Return 2 for FULL (obstacle), 1 for HALF (crate), 0 for none, based on adjacent tile."""
    n = neighbor_on_side(tile, side)
    if n in tmap.blocked:
        return 2
    if n in tmap.crates:
        return 1
    return 0

def cover_levels_all_sides(tile: Coord, tmap: TileMap) -> dict[str, int]:
    return {s: cover_level_from_adjacent(tile, tmap, s) for s in ('up','right','down','left')}

def facing_side(from_tile: Coord, to_tile: Coord) -> str:
    dx = from_tile[0] - to_tile[0]
    dy = from_tile[1] - to_tile[1]
    if abs(dx) >= abs(dy):
        return 'right' if dx > 0 else 'left'
    else:
        return 'down' if dy > 0 else 'up'

def cover_level_on_facing(target: Coord, shooter: Coord, tmap: TileMap) -> int:
    return cover_level_from_adjacent(target, tmap, facing_side(shooter, target))

def edge_triangle(topx: int, topy: int, tile_w: int, tile_h: int, side: str) -> list[tuple[int, int]]:
    pts = diamond_points(topx, topy, tile_w, tile_h)
    center = ((pts[0][0] + pts[2][0]) // 2, (pts[0][1] + pts[2][1]) // 2)
    if side == 'up':
        a, b = pts[0], pts[1]
    elif side == 'right':
        a, b = pts[1], pts[2]
    elif side == 'down':
        a, b = pts[2], pts[3]
    else:
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
    levels = cover_levels_all_sides(tile, tmap)
    for side, lvl in levels.items():
        tri = edge_triangle(sx, sy, S.TILE_W, S.TILE_H, side)
        if lvl == 2:
            pg.draw.polygon(surface, C.COVER_FULL, tri)
        elif lvl == 1:
            pg.draw.polygon(surface, C.COVER_HALF, tri)
        else:
            pg.draw.polygon(surface, C.COVER_NONE, tri, width=1)

# ---------- Movement ranges & path preview ----------
def bfs_reachable(origin: Coord, max_steps: int, tmap: TileMap, extra_blocked: Set[Coord]) -> set[Coord]:
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

def draw_move_ranges(surface: pg.Surface, origin: Coord | None, tmap: TileMap, available_ap: int, occ: Set[Coord]) -> None:
    if not origin or available_ap <= 0:
        return
    overlay = pg.Surface(surface.get_size(), pg.SRCALPHA)
    blue = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP, tmap, occ)
    for (i, j) in blue:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        pg.draw.polygon(overlay, C.MOVE_BLUE_FILL, diamond_points(sx, sy, S.TILE_W, S.TILE_H))
        pg.draw.polygon(overlay, C.MOVE_BLUE_OUTLINE, diamond_points(sx, sy, S.TILE_W, S.TILE_H), width=1)
    if available_ap >= 2:
        yellow = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP * 2, tmap, occ) - blue
        for (i, j) in yellow:
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            pg.draw.polygon(overlay, C.MOVE_YELLOW_FILL, diamond_points(sx, sy, S.TILE_W, S.TILE_H))
            pg.draw.polygon(overlay, C.MOVE_YELLOW_OUTLINE, diamond_points(sx, sy, S.TILE_W, S.TILE_H), width=1)
    surface.blit(overlay, (0, 0))

def draw_path_preview(surface: pg.Surface, origin: Coord | None, hovered: Coord | None, tmap: TileMap, blocked: Set[Coord]) -> tuple[int, int] | None:
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
        pg.draw.polygon(overlay, C.PATH_FILL, diamond_points(sx, sy, S.TILE_W, S.TILE_H))
        pg.draw.polygon(overlay, C.PATH_OUTLINE, diamond_points(sx, sy, S.TILE_W, S.TILE_H), width=1)
    surface.blit(overlay, (0, 0))
    steps = len(path)
    ap_cost = math.ceil(steps / S.MOVEMENT_TILES_PER_AP) if steps > 0 else 0
    return steps, ap_cost

# ---------- Combat (preview + resolution) ----------
def calc_shot_chances(shooter: Coord, target: Coord, tmap: TileMap, aim_delta: int = 0) -> Optional[tuple[int, int, str]]:
    if not has_los(shooter, target, set(tmap.blocked)):
        return None
    aim = S.BASE_AIM + aim_delta
    defense = 0
    lvl = cover_level_on_facing(target, shooter, tmap)  # 0/1/2
    tag = "FLANK"
    if lvl == 2:
        defense += S.COVER_FULL_DEF
        tag = "FULL"
    elif lvl == 1:
        defense += S.COVER_HALF_DEF
        tag = "HALF"
    hit = max(S.HIT_FLOOR, min(S.HIT_CEIL, aim - defense))
    crit = max(0, min(100, S.BASE_CRIT + (S.FLANK_CRIT if tag == "FLANK" else 0)))
    return hit, crit, tag

def draw_shot_preview(surface: pg.Surface, font: pg.font.Font, shooter_unit: Unit, hovered: Coord, tmap: TileMap, enemies: List[Enemy]) -> None:
    if get_enemy_at(enemies, hovered) is None:
        return
    sx, sy = grid_to_screen(*hovered, S.TILE_W, S.TILE_H, S.ORIGIN)
    cx, cy = sx, sy + S.TILE_H // 2
    if not shooter_unit.has_ammo():
        txt_na = font.render("NO AMMO", True, C.KILL_TEXT)
        surface.blit(txt_na, (cx - txt_na.get_width() // 2, cy - S.TILE_H - 16))
    info = calc_shot_chances(shooter_unit.grid, hovered, tmap)
    if info is None:
        txt = font.render("NO LOS", True, C.SHOT_NLOS)
        surface.blit(txt, (cx - txt.get_width() // 2, cy - S.TILE_H))
        return
    hit, crit, tag = info
    line = f"{tag} — HIT {hit}%   CRIT {crit}%   DMG {S.WEAPON_DMG_MIN}-{S.WEAPON_DMG_MAX}{'(+%d)' % S.CRIT_BONUS_DMG if S.CRIT_BONUS_DMG else ''}"
    txt = font.render(line, True, C.SHOT_TEXT)
    surface.blit(txt, (cx - txt.get_width() // 2, cy - S.TILE_H))

def resolve_shot(rng: random.Random, shooter: Unit, target_tile: Coord, tmap: TileMap, enemies: List[Enemy], log: List[str], aim_delta: int = 0, tag: str = "Shot") -> None:
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
    else:
        if not shooter.has_ammo():
            return
    info = calc_shot_chances(shooter.grid, target_tile, tmap, aim_delta=aim_delta)
    if info is None:
        return
    hit_ch, crit_ch, _tag = info
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
    shooter.spend_ammo()
    if tag == "Shot":
        shooter.ap -= S.SHOOT_AP_COST

# ---------- Enemy phase & overwatch ----------
def plan_enemy_paths(enemies: List[Enemy], squad: List[Unit], tmap: TileMap) -> Dict[Enemy, List[Coord]]:
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
    for u in squad:
        if not u.overwatch:
            continue
        if has_los(u.grid, mover.grid, set(tmap.blocked)):
            resolve_shot(rng, u, mover.grid, tmap, enemies, log, aim_delta=-S.OVERWATCH_AIM_MALUS, tag="OVERWATCH")
            u.clear_overwatch()
            if get_enemy_at(enemies, mover.grid) is None:
                break

# ---------- Movement ----------
def bfs_reachable(origin: Coord, max_steps: int, tmap: TileMap, extra_blocked: Set[Coord]) -> set[Coord]:
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

def draw_move_ranges(surface: pg.Surface, origin: Coord | None, tmap: TileMap, available_ap: int, occ: Set[Coord]) -> None:
    if not origin or available_ap <= 0:
        return
    overlay = pg.Surface(surface.get_size(), pg.SRCALPHA)
    blue = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP, tmap, occ)
    for (i, j) in blue:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        pg.draw.polygon(overlay, C.MOVE_BLUE_FILL, diamond_points(sx, sy, S.TILE_W, S.TILE_H))
        pg.draw.polygon(overlay, C.MOVE_BLUE_OUTLINE, diamond_points(sx, sy, S.TILE_W, S.TILE_H), width=1)
    if available_ap >= 2:
        yellow = bfs_reachable(origin, S.MOVEMENT_TILES_PER_AP * 2, tmap, occ) - blue
        for (i, j) in yellow:
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            pg.draw.polygon(overlay, C.MOVE_YELLOW_FILL, diamond_points(sx, sy, S.TILE_W, S.TILE_H))
            pg.draw.polygon(overlay, C.MOVE_YELLOW_OUTLINE, diamond_points(sx, sy, S.TILE_W, S.TILE_H), width=1)
    surface.blit(overlay, (0, 0))

def draw_path_preview(surface: pg.Surface, origin: Coord | None, hovered: Coord | None, tmap: TileMap, blocked: Set[Coord]) -> tuple[int, int] | None:
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
        pg.draw.polygon(overlay, C.PATH_FILL, diamond_points(sx, sy, S.TILE_W, S.TILE_H))
        pg.draw.polygon(overlay, C.PATH_OUTLINE, diamond_points(sx, sy, S.TILE_W, S.TILE_H), width=1)
    surface.blit(overlay, (0, 0))
    steps = len(path)
    ap_cost = math.ceil(steps / S.MOVEMENT_TILES_PER_AP) if steps > 0 else 0
    return steps, ap_cost

# ---------- Debug ----------
def draw_debug(surface: pg.Surface, font: pg.font.Font, hovered: Coord | None, sel_unit: Unit, path_info: tuple[int, int] | None, tm: TurnManager, enemies: List[Enemy], log: List[str], tmap: TileMap) -> None:
    phase_txt = "PLAYER" if tm.phase is Phase.PLAYER else "ENEMY"
    lines = [
        f"Turn: {tm.turn}   Phase: {phase_txt}",
        f"Hovered: {hovered}" if hovered is not None else "Hovered: None",
        f"Selected@{sel_unit.grid}  AP: {sel_unit.ap}/{sel_unit.ap_max}  AMMO: {sel_unit.ammo}/{sel_unit.clip_max}  {'[OW]' if sel_unit.overwatch else ''}",
        f"Enemies: {len(enemies)}   Walls:{len(tmap.blocked)}  Crates:{len(tmap.crates)}",
        "Controls: TAB cycle | 1-9 select | L-Click select/move | F fire | O overwatch | R reload | N enemy | B wall | H crate | ENTER/E end turn | ESC quit",
    ]
    if path_info is not None:
        steps, ap_cost = path_info
        lines.insert(3, f"Path steps: {steps}   AP cost: {ap_cost}")

    for entry in log[-4:]:
        lines.append(entry)

    x, y = 10, 10
    for text in lines:
        surf = font.render(text, True, C.TEXT)
        surface.blit(surf, (x, y))
        y += surf.get_height() + 2

# ---------- App ----------
def main() -> int:
    pg.init()
    try:
        screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
        pg.display.set_caption("XCOM Iso — Half vs Full Cover")
        clock = pg.time.Clock()
        font = pg.font.SysFont("consolas", 16)

        rng = random.Random(1337)

        tmap = TileMap(S.GRID_COLS, S.GRID_ROWS)
        squad: List[Unit] = [Unit(pos, S.TILE_W, S.TILE_H, S.ORIGIN, S.MOVE_SPEED_PPS) for pos in S.UNIT_SPAWNS]
        sel_idx = 0
        tm = TurnManager()
        enemies: List[Enemy] = []
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
                        elif e.key == pg.K_h:
                            hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                            if tmap.in_bounds(hov) and get_unit_at(squad, hov) is None and get_enemy_at(enemies, hov) is None and hov not in tmap.blocked:
                                tmap.toggle_crate(hov)
                        elif e.key == pg.K_n:
                            hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                            if tmap.in_bounds(hov) and hov not in tmap.blocked and get_unit_at(squad, hov) is None:
                                ex = get_enemy_at(enemies, hov)
                                if ex:
                                    enemies.remove(ex)
                                else:
                                    enemies.append(Enemy(hov, S.ENEMY_DEFAULT_HP))
                        elif e.key == pg.K_f:
                            sel = squad[sel_idx]
                            hov = screen_to_grid(*pg.mouse.get_pos(), S.TILE_W, S.TILE_H, S.ORIGIN)
                            resolve_shot(rng, sel, hov, tmap, enemies, log, tag="Shot")
                        elif e.key == pg.K_o:
                            if squad[sel_idx].set_overwatch(S.OVERWATCH_AP_COST):
                                log.append(f"Unit@{squad[sel_idx].grid} set OVERWATCH")
                        elif e.key in (pg.K_RETURN, pg.K_e):
                            if all(not u.is_moving() for u in squad):
                                tm.end_player_turn()
                                enemy_plans = plan_enemy_paths(enemies, squad, tmap)
                                enemy_steps_left = {en: min(S.ENEMY_STEPS_PER_TURN, len(path)) for en, path in (enemy_plans or {}).items()}
                                enemy_step_timer = 0.0
                elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1 and tm.phase is Phase.PLAYER:
                    i, j = screen_to_grid(*e.pos, S.TILE_W, S.TILE_H, S.ORIGIN)
                    tile = (i, j)
                    u_on_tile = get_unit_at(squad, tile)
                    if u_on_tile is not None:
                        sel_idx = squad.index(u_on_tile)
                    else:
                        sel = squad[sel_idx]
                        if tmap.in_bounds(tile) and tmap.passable(tile) and get_enemy_at(enemies, tile) is None:
                            occ = occupied_tiles(squad, exclude=sel) | {e.grid for e in enemies}
                            if tile not in occ:
                                blocked = set(tmap.blocked) | occ
                                path = a_star(sel.grid, tile, S.GRID_COLS, S.GRID_ROWS, blocked)
                                if path:
                                    steps = len(path)
                                    ap_cost = math.ceil(steps / S.MOVEMENT_TILES_PER_AP)
                                    if sel.can_afford(ap_cost):
                                        sel.set_path(path, ap_cost)
                                        pending_dest[sel] = tile

            # Update units
            for u in squad:
                u.update(dt)
                if u in pending_dest and not u.is_moving():
                    u.set_grid_immediate(pending_dest[u])
                    del pending_dest[u]

            # Enemy phase (stepwise)
            if tm.phase is Phase.ENEMY:
                enemy_step_timer += dt
                if enemy_plans is None:
                    enemy_plans = plan_enemy_paths(enemies, squad, tmap)
                    enemy_steps_left = {en: min(S.ENEMY_STEPS_PER_TURN, len(path)) for en, path in enemy_plans.items()}
                while enemy_step_timer >= S.ENEMY_STEP_TIME:
                    enemy_step_timer -= S.ENEMY_STEP_TIME
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
                        # Overwatch reactions
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

            # Draw
            screen.fill(C.BG)
            draw_grid(screen)
            draw_obstacles(screen, tmap)
            draw_crates(screen, tmap)
            draw_enemies(screen, enemies)

            sel = squad[sel_idx]
            occ = occupied_tiles(squad, exclude=sel) | {e.grid for e in enemies}
            if tm.phase is Phase.PLAYER:
                draw_move_ranges(screen, sel.grid, tmap, sel.ap, occ)
            hovered = draw_hover(screen, pg.mouse.get_pos())
            blocked = set(tmap.blocked) | occ
            path_info = draw_path_preview(screen, sel.grid, hovered, tmap, blocked) if tm.phase is Phase.PLAYER else None

            # Cover pips on hovered tile
            if hovered:
                draw_cover_pips(screen, hovered, tmap)

            if hovered is not None and tm.phase is Phase.PLAYER:
                draw_shot_preview(screen, font, sel, hovered, tmap, enemies)

            for i, u in enumerate(squad):
                draw_unit(screen, u, selected=(i == sel_idx))

            draw_selection(screen, sel.grid)
            draw_debug(screen, font, hovered, sel, path_info, tm, enemies, log, tmap)

            pg.display.flip()

        return 0
    finally:
        pg.quit()

if __name__ == "__main__":
    sys.exit(main())
