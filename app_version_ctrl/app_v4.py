from __future__ import annotations
import sys
import math
import pygame as pg

import settings as S
from engine.iso import grid_to_screen, screen_to_grid, diamond_points
from engine import colors as C


def draw_grid(surface: pg.Surface) -> None:
    """Render an isometric diamond grid with a checkerboard fill and thin outlines."""
    for j in range(S.GRID_ROWS):
        for i in range(S.GRID_COLS):
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
            fill = C.GRID_A if (i + j) % 2 == 0 else C.GRID_B
            pg.draw.polygon(surface, fill, poly)
            pg.draw.polygon(surface, C.OUTLINE, poly, width=1)


def draw_hover(surface: pg.Surface, mouse_pos: tuple[int, int]) -> tuple[int, int] | None:
    """Highlight the tile under the mouse and return (i, j) if in-bounds; otherwise None."""
    mx, my = mouse_pos
    i, j = screen_to_grid(mx, my, S.TILE_W, S.TILE_H, S.ORIGIN)
    if 0 <= i < S.GRID_COLS and 0 <= j < S.GRID_ROWS:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(surface, C.HOVER_FILL, poly)
        pg.draw.polygon(surface, C.HOVER_OUTLINE, poly, width=2)
        return (i, j)
    return None


def draw_selection(surface: pg.Surface, selected: tuple[int, int] | None) -> None:
    """Render the currently selected tile, if any."""
    if not selected:
        return
    i, j = selected
    sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
    poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
    pg.draw.polygon(surface, C.SELECT_FILL, poly)
    pg.draw.polygon(surface, C.SELECT_OUTLINE, poly, width=2)


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def compute_move_ranges(origin: tuple[int, int]) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """Return (blue_set, yellow_set) using Manhattan distance and MOVEMENT_TILES_PER_AP."""
    blue: set[tuple[int, int]] = set()
    yellow: set[tuple[int, int]] = set()
    max_blue = S.MOVEMENT_TILES_PER_AP
    max_yellow = S.MOVEMENT_TILES_PER_AP * 2
    oi, oj = origin

    for j in range(S.GRID_ROWS):
        for i in range(S.GRID_COLS):
            d = abs(i - oi) + abs(j - oj)
            if d == 0:
                continue  # skip the origin tile
            if d <= max_blue:
                blue.add((i, j))
            elif d <= max_yellow:
                yellow.add((i, j))
    return blue, yellow


def draw_move_ranges(surface: pg.Surface, selected: tuple[int, int] | None) -> None:
    """Overlay blue (1 AP) and yellow (2 AP) move ranges when a tile is selected."""
    if not selected:
        return
    blue, yellow = compute_move_ranges(selected)

    overlay = pg.Surface(surface.get_size(), pg.SRCALPHA)
    for (i, j) in yellow:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(overlay, C.MOVE_YELLOW_FILL, poly)
        pg.draw.polygon(overlay, C.MOVE_YELLOW_OUTLINE, poly, width=1)

    for (i, j) in blue:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(overlay, C.MOVE_BLUE_FILL, poly)
        pg.draw.polygon(overlay, C.MOVE_BLUE_OUTLINE, poly, width=1)

    surface.blit(overlay, (0, 0))


def straight_path(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """
    Naive 4-dir path: step along the axis with greatest remaining delta.
    Returns the sequence of tiles from start-excluded to end-included.
    """
    (i0, j0) = start
    (i1, j1) = end
    path: list[tuple[int, int]] = []
    ii, jj = i0, j0

    while (ii, jj) != (i1, j1):
        di = 0 if ii == i1 else (1 if i1 > ii else -1)
        dj = 0 if jj == j1 else (1 if j1 > jj else -1)
        # Prefer stepping on the axis with larger remaining distance
        if abs(i1 - ii) >= abs(j1 - jj) and di != 0:
            ii += di
        elif dj != 0:
            jj += dj
        else:
            ii += di  # fallback
        if 0 <= ii < S.GRID_COLS and 0 <= jj < S.GRID_ROWS:
            path.append((ii, jj))
        else:
            break
    return path


def draw_path_preview(surface: pg.Surface, selected: tuple[int, int] | None, hovered: tuple[int, int] | None) -> tuple[int, int] | None:
    """Preview a straight-line path from selected to hovered tile; return (steps, ap_cost)."""
    if not selected or not hovered:
        return None

    path = straight_path(selected, hovered)
    if not path:
        return None

    # Cap the visual to 2 AP range
    max_steps = S.MOVEMENT_TILES_PER_AP * 2
    path = path[:max_steps]

    overlay = pg.Surface(surface.get_size(), pg.SRCALPHA)
    for (i, j) in path:
        sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
        poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
        pg.draw.polygon(overlay, C.PATH_FILL, poly)
        pg.draw.polygon(overlay, C.PATH_OUTLINE, poly, width=1)

    surface.blit(overlay, (0, 0))
    # Return length/AP for debug
    steps = len(path)
    ap_cost = math.ceil(steps / S.MOVEMENT_TILES_PER_AP) if steps > 0 else 0
    return steps, ap_cost


def draw_debug(surface: pg.Surface, font: pg.font.Font, hovered: tuple[int, int] | None, selected: tuple[int, int] | None, path_info: tuple[int, int] | None) -> None:
    """Draw lightweight debug HUD for hovered/selected tiles, path preview, and controls."""
    lines = [
        f"Hovered: {hovered}" if hovered is not None else "Hovered: None",
        f"Selected: {selected}" if selected is not None else "Selected: None",
        f"Origin: {S.ORIGIN}  Tile: {S.TILE_W}x{S.TILE_H}  Grid: {S.GRID_COLS}x{S.GRID_ROWS}",
        f"1 AP tiles: {S.MOVEMENT_TILES_PER_AP} (dash=2x)",
        "L-Click: select   R-Click: clear   ESC: quit",
    ]
    if path_info is not None:
        steps, ap_cost = path_info
        lines.insert(3, f"Path steps: {steps}   AP cost: {ap_cost}")

    x, y = 10, 10
    for text in lines:
        surf = font.render(text, True, C.TEXT)
        surface.blit(surf, (x, y))
        y += surf.get_height() + 2


def main() -> int:
    pg.init()
    try:
        screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
        pg.display.set_caption("XCOM Iso — Ranges & Path Preview")
        clock = pg.time.Clock()
        font = pg.font.SysFont("consolas", 16)

        selected: tuple[int, int] | None = None

        running = True
        while running:
            for e in pg.event.get():
                if e.type == pg.QUIT:
                    running = False
                elif e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                    running = False
                elif e.type == pg.MOUSEBUTTONDOWN:
                    if e.button == 1:  # select
                        i, j = screen_to_grid(*e.pos, S.TILE_W, S.TILE_H, S.ORIGIN)
                        if 0 <= i < S.GRID_COLS and 0 <= j < S.GRID_ROWS:
                            selected = (i, j)
                    elif e.button == 3:  # clear
                        selected = None

            screen.fill(C.BG)
            draw_grid(screen)
            draw_selection(screen, selected)
            draw_move_ranges(screen, selected)
            hovered = draw_hover(screen, pg.mouse.get_pos())
            path_info = draw_path_preview(screen, selected, hovered)
            draw_debug(screen, font, hovered, selected, path_info)

            pg.display.flip()
            clock.tick(S.FPS)

        return 0
    finally:
        pg.quit()


if __name__ == "__main__":
    sys.exit(main())