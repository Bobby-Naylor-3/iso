
from __future__ import annotations

# Window
WINDOW_W = 1280
WINDOW_H = 720
FPS = 60

# Grid
GRID_COLS = 20
GRID_ROWS = 20

# Isometric tile size (2:1 diamond)
# Width must be ~2x height for classic iso diamonds
TILE_W = 64
TILE_H = 32

# Where the (0,0) tile's top vertex lands on screen.
# Center X; some headroom Y so the grid sits nicely.
ORIGIN_X = WINDOW_W // 2
ORIGIN_Y = 100
ORIGIN = (ORIGIN_X, ORIGIN_Y)
