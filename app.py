from __future__ import annotations
import sys
import pygame as pg

import settings as S
from engine.iso import grid_to_screen, diamond_points
from engine import colors as C


def draw_grid(surface: pg.Surface) -> None:
    """
    Render a static isometric diamond grid with alternating fill for visual clarity.
    """
    for j in range(S.GRID_ROWS):
        for i in range(S.GRID_COLS):
            sx, sy = grid_to_screen(i, j, S.TILE_W, S.TILE_H, S.ORIGIN)
            poly = diamond_points(sx, sy, S.TILE_W, S.TILE_H)
            # Checkerboard the tiles for depth cues.
            fill = C.GRID_A if (i + j) % 2 == 0 else C.GRID_B
            pg.draw.polygon(surface, fill, poly)
            pg.draw.polygon(surface, C.OUTLINE, poly, width=1)


def main() -> int:
    pg.init()
    try:
        screen = pg.display.set_mode((S.WINDOW_W, S.WINDOW_H))
        pg.display.set_caption("XCOM Iso Bootstrap")
        clock = pg.time.Clock()

        running = True
        while running:
            for e in pg.event.get():
                if e.type == pg.QUIT:
                    running = False
                elif e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                    running = False

            screen.fill(C.BG)
            draw_grid(screen)
            pg.display.flip()
            clock.tick(S.FPS)

        return 0
    finally:
        pg.quit()


if __name__ == "__main__":
    sys.exit(main())
