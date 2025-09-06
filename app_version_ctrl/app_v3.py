from __future__ import annotations
import sys
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


def draw_debug(surface: pg.Surface, font: pg.font.Font, hovered: tuple[int, int] | None, selected: tuple[int, int] | None) -> None:
    \"\"\"Draw lightweight debug HUD for hovered/selected tiles and controls."""
    lines = [
        f"Hovered: {hovered}" if hovered is not None else "Hovered: None",
        f"Selected: {selected}" if selected is not None else "Selected: None",
        f"Origin: {S.ORIGIN}  Tile: {S.TILE_W}x{S.TILE_H}  Grid: {S.GRID_COLS}x{S.GRID_ROWS}",
        "L-Click: select tile   R-Click: clear selection   ESC: quit",
    ]
    x, y = 10, 10
    for text in lines:
        surf = font.render(text, True, C.TEXT)
        surface.blit(surf, (x, y))
        y += surf.get_height() + 2


def main() -> int:
    pg.init()
    try:
        screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
        pg.display.set_caption(\"XCOM Iso — Hover, Selection & Debug")
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
                    if e.button == 1:  # left click → select tile
                        i, j = screen_to_grid(*e.pos, S.TILE_W, S.TILE_H, S.ORIGIN)
                        if 0 <= i < S.GRID_COLS and 0 <= j < S.GRID_ROWS:
                            selected = (i, j)
                    elif e.button == 3:  # right click → clear selection
                        selected = None

            screen.fill(C.BG)
            draw_grid(screen)
            draw_selection(screen, selected)
            hovered = draw_hover(screen, pg.mouse.get_pos())
            draw_debug(screen, font, hovered, selected)

            pg.display.flip()
            clock.tick(S.FPS)

        return 0
    finally:
        pg.quit()


if __name__ == "__main__":
    sys.exit(main())

