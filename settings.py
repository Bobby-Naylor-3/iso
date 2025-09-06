
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
# Movement preview tuning
MOVEMENT_TILES_PER_AP = 6  # 1 AP radius (Manhattan), dash = 2 AP
# Pathfinding / movement
ALLOW_DIAGONAL = False  # reserved for future; current A* uses 4-dir
# Demo unit spawn & movement
UNIT_SPAWN = (5, 5)
MOVE_SPEED_PPS = 220  # pixels per second for movement animation
# Squad spawns (grid coords)
UNIT_SPAWNS = [(5, 5), (7, 6), (9, 8)]
# Combat tuning (bootstrap, super simple)
BASE_AIM = 65               # shooter base aim
BASE_CRIT = 0               # base crit chance
COVER_FULL_DEF = 40         # defense from a blocking adjacent obstacle (treated as full cover)
FLANK_AIM = 0               # aim bonus on flank (classic XCOM flanks give crit, not aim)
FLANK_CRIT = 40             # crit bonus on flank
HIT_FLOOR = 5               # clamp hit chance [HIT_FLOOR, HIT_CEIL]
HIT_CEIL = 95

SHOOT_AP_COST = 1

WEAPON_DMG_MIN = 2
WEAPON_DMG_MAX = 4
CRIT_BONUS_DMG = 2          # flat bonus on crit
# Overwatch & enemy AI (bootstrap)
OVERWATCH_AP_COST = 1
OVERWATCH_AIM_MALUS = 15  # penalty applied to OW shots

ENEMY_DEFAULT_HP = 3
ENEMY_STEPS_PER_TURN = 6     # tiles per enemy per enemy phase
ENEMY_STEP_TIME = 0.08       # seconds per enemy step (visual pacing)
# Ammo / reload
CLIP_SIZE = 3
RELOAD_AP_COST = 1
# Cover values
COVER_HALF_DEF = 20  # defense from half cover (crates)
# COVER_FULL_DEF already exists (40)
