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
        pg.draw.polygon(surface, C.OBSTACLE_FILL, diamond_points(sx, sy, S.TILE_W, S.TILE_H))
        pg.draw.polygon(surface, C.OBSTACLE_OUTLINE, diamond_points(sx, sy, S.TILE_W, S.TILE_H), width=2)

def draw_hover(surface: pg.Surface, mouse_pos: tuple[int, int]) -> tuple[int, int] | None:
    mx, my = mouse_pos
    i, j = screen_to_grid(mx, my, S.TILE_W, S.TILE_H, S.ORIGIN)
    if 0 <= i < S.GRID_COLS and 0 <= j < S.GRID_ROWS:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        pg.draw.polygon(surface, C.HOVER_FILL, diamond_points(sx, sy, S.TILE_W, S.TILE_H))
        pg.draw.polygon(surface, C.HOVER_OUTLINE, diamond_points(sx, sy, S.TILE_W, S.TILE_H), width=2)
        return (i, j)
    return None

def draw_selection(surface: pg.Surface, tile: Coord | None) -> None:
    if not tile:
        return
    i, j = tile
    sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
    pg.draw.polygon(surface, C.SELECT_FILL, diamond_points(sx, sy, S.TILE_W, S.TILE_H))
    pg.draw.polygon(surface, C.SELECT_OUTLINE, diamond_points(sx, sy, S.TILE_W, S.TILE_H), width=2)

def draw_unit(surface: pg.Surface, u: Unit, selected: bool) -> None:
    r = max(6, S.TILE_H // 3)
    # ring for overwatch
    if u.overwatch:
        pg.draw.circle(surface, C.OVERWATCH_RING, (int(u.pos_x), int(u.pos_y)), r + 6, width=2)
    pg.draw.circle(surface, C.UNIT_FILL, (int(u.pos_x), int(u.pos_y)), r)
    pg.draw.circle(surface, C.UNIT_OUTLINE, (int(u.pos_x), int(u.pos_y)), r, width=2)
    if selected:
        pg.draw.circle(surface, C.SELECT_OUTLINE, (int(u.pos_x), int(u.pos_y)), r + 3, width=2)

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
def cover_full_on_facing(target: Coord, shooter: Coord, tmap: TileMap) -> bool:
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

def draw_shot_preview(surface: pg.Surface, font: pg.font.Font, shooter: Coord, hovered: Coord, tmap: TileMap, enemies: List[Enemy]) -> None:
    if get_enemy_at(enemies, hovered) is None:
        return
    sx, sy = grid_to_screen(*hovered, S.TILE_W, S.TILE_H, S.ORIGIN)
    cx, cy = sx, sy + S.TILE_H // 2
    chances = calc_shot_chances(shooter, hovered, tmap)
    if chances is None:
        txt = font.render("NO LOS", True, C.SHOT_NLOS)
        surface.blit(txt, (cx - txt.get_width() // 2, cy - S.TILE_H))
        return
    hit, crit = chances
    line = f"HIT {hit}%   CRIT {crit}%   DMG {S.WEAPON_DMG_MIN}-{S.WEAPON_DMG_MAX}{'(+%d)' % S.CRIT_BONUS_DMG if S.CRIT_BONUS_DMG else ''}"
    txt = font.render(line, True, C.SHOT_TEXT)
    surface.blit(txt, (cx - txt.get_width() // 2, cy - S.TILE_H))

def resolve_shot(rng: random.Random, shooter: Unit, target_tile: Coord, tmap: TileMap, enemies: List[Enemy], log: List[str], aim_delta: int = 0, tag: str = "Shot") -> None:
    if shooter.is_moving():
        return
    target = get_enemy_at(enemies, target_tile)
    if target is None:
        return
    chances = calc_shot_chances(shooter.grid, target_tile, tmap, aim_delta=aim_delta)
    if chances is None:
        return
    # spend AP only for manual fire (tag=="Shot"); overwatch already paid when set
    if tag == "Shot" and shooter.ap < S.SHOOT_AP_COST:
        return

    hit_ch, crit_ch = chances
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

    if tag == "Shot":
        shooter.ap -= S.SHOOT_AP_COST

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
        if not u.overwatch:
            continue
        if has_los(u.grid, mover.grid, set(tmap.blocked)):
            resolve_shot(rng, u, mover.grid, tmap, enemies, log, aim_delta=-S.OVERWATCH_AIM_MALUS, tag="OVERWATCH")
            u.clear_overwatch()
            if get_enemy_at(enemies, mover.grid) is None:
                # mover died; stop further shots at this tile
                break

# ---------- Debug ----------
def draw_debug(surface: pg.Surface, font: pg.font.Font, hovered: Coord | None, sel_unit: Unit, path_info: tuple[int, int] | None, tm: TurnManager, enemies: List[Enemy], log: List[str]) -> None:
    phase_txt = "PLAYER" if tm.phase is Phase.PLAYER else "ENEMY"
    lines = [
        f"Turn: {tm.turn}   Phase: {phase_txt}",
        f"Hovered: {hovered}" if hovered is not None else "Hovered: None",
        f"Selected@{sel_unit.grid}  AP: {sel_unit.ap}/{sel_unit.ap_max}  {'[OW]' if sel_unit.overwatch else ''}",
        f"Enemies: {len(enemies)}",
        "Controls: TAB cycle | 1-9 select | L-Click select/move | O overwatch | F fire | N place/remove enemy | B toggle obstacle | ENTER/E end turn | ESC quit",
    ]
    if path_info is not None:
        steps, ap_cost = path_info
        lines.insert(3, f"Path steps: {steps}   AP cost: {ap_cost}")

    # recent log (last 4)
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
        pg.display.set_caption("XCOM Iso — Overwatch & Enemy Moves")
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

        # Enemy phase orchestration
        enemy_plans: Optional[Dict[Enemy, List[Coord]]] = None
        enemy_step_timer = 0.0
        enemy_steps_left: Dict[Enemy, int] = {}

        running = True
        while running:
            dt = clock.tick(S.FPS) / 1000.0

            # Input (PLAYER phase)
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
                            # end player turn only if no one is moving
                            if all(not u.is_moving() for u in squad):
                                tm.end_player_turn()
                                # initialize enemy plans
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

            # Update units (player)
            for u in squad:
                u.update(dt)
                if u in pending_dest and not u.is_moving():
                    u.set_grid_immediate(pending_dest[u])
                    del pending_dest[u]

            # Enemy phase simulation (stepwise)
            if tm.phase is Phase.ENEMY:
                enemy_step_timer += dt
                if enemy_plans is None:
                    enemy_plans = plan_enemy_paths(enemies, squad, tmap)
                    enemy_steps_left = {en: min(S.ENEMY_STEPS_PER_TURN, len(path)) for en, path in enemy_plans.items()}
                # move one step every ENEMY_STEP_TIME
                while enemy_step_timer >= S.ENEMY_STEP_TIME:
                    enemy_step_timer -= S.ENEMY_STEP_TIME
                    anyone_moved = False
                    # step each enemy at most once per tick
                    occupied_now = {e.grid for e in enemies} | {u.grid for u in squad} | set(tmap.blocked)
                    for en in list(enemies):  # copy: may remove on death
                        path = (enemy_plans or {}).get(en, [])
                        if enemy_steps_left.get(en, 0) <= 0 or not path:
                            continue
                        next_tile = path[0]
                        if next_tile in occupied_now:
                            # can't step into; skip this step
                            continue
                        # perform step
                        en.grid = next_tile
                        enemy_plans[en] = path[1:]
                        enemy_steps_left[en] -= 1
                        anyone_moved = True

                        # Overwatch reactions
                        process_overwatch_triggers(rng, squad, en, tmap, enemies, log)
                        # update occupied set after potential death
                        occupied_now = {e.grid for e in enemies} | {u.grid for u in squad} | set(tmap.blocked)

                    # if no one could move this tick, break to avoid tight loop
                    if not anyone_moved:
                        break

                # end enemy phase when all paths/steps done
                still_moving = any(enemy_steps_left.get(en, 0) > 0 and enemy_plans.get(en) for en in enemies)
                if not still_moving:
                    tm.complete_enemy_turn()
                    # refresh AP & clear any leftover overwatch states
                    for u in squad:
                        u.ap = u.ap_max
                        u.clear_overwatch()
                    enemy_plans = None
                    enemy_steps_left = {}

            # Draw
            screen.fill(C.BG)
            draw_grid(screen)
            draw_obstacles(screen, tmap)
            draw_enemies(screen, enemies)

            sel = squad[sel_idx]
            occ = occupied_tiles(squad, exclude=sel) | {e.grid for e in enemies}
            if tm.phase is Phase.PLAYER:
                draw_move_ranges(screen, sel.grid, tmap, sel.ap, occ)
            hovered = draw_hover(screen, pg.mouse.get_pos())
            blocked = set(tmap.blocked) | occ
            path_info = draw_path_preview(screen, sel.grid, hovered, tmap, blocked) if tm.phase is Phase.PLAYER else None

            if hovered is not None and tm.phase is Phase.PLAYER:
                draw_shot_preview(screen, font, sel.grid, hovered, tmap, enemies)

            for i, u in enumerate(squad):
                draw_unit(screen, u, selected=(i == sel_idx))

            draw_selection(screen, sel.grid)
            draw_debug(screen, font, hovered, sel, path_info, tm, enemies, log)

            pg.display.flip()

        return 0
    finally:
        pg.quit()

if __name__ == "__main__":
    sys.exit(main())
