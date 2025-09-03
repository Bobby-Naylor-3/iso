from __future__ import annotations
from typing import Tuple

def grid_to_screen(i: int, j: int, tile_w: int, tile_h: int, origin: Tuple[int, int]) -> Tuple[int, int]:
    """
    Convert grid (i,j) to screen-space coordinates (x,y) of the *top vertex* of the isometric diamond.

    Classic 2:1 iso:
        x = (i - j) * (tile_w // 2) + origin_x
        y = (i + j) * (tile_h // 2) + origin_y
    """
    ox, oy = origin
    half_w = tile_w // 2
    half_h = tile_h // 2
    x = (i - j) * half_w + ox
    y = (i + j) * half_h + oy
    return x, y


def screen_to_grid(x: int, y: int, tile_w: int, tile_h: int, origin: Tuple[int, int]) -> Tuple[int, int]:
    """
    Inverse mapping from screen (x,y) to nearest grid (i,j).
    Rounds to nearest integer tile using float math; callers may want bounds checks.

    Derivation:
        Let dx = x - ox, dy = y - oy
        i' =  (dx / half_w + dy / half_h) / 2
        j' =  (dy / half_h - dx / half_w) / 2
    """
    ox, oy = origin
    dx = x - ox
    dy = y - oy
    half_w = tile_w / 2.0
    half_h = tile_h / 2.0

    i_f = (dx / half_w + dy / half_h) / 2.0
    j_f = (dy / half_h - dx / half_w) / 2.0

    # Round to nearest tile index
    i = int(round(i_f))
    j = int(round(j_f))
    return i, j


def diamond_points(top_x: int, top_y: int, tile_w: int, tile_h: int):
    """
    Return polygon points for a 2:1 iso diamond given its top vertex (x,y).
    Order: top -> right -> bottom -> left.
    """
    half_w = tile_w // 2
    half_h = tile_h // 2
    return [
        (top_x, top_y),
        (top_x + half_w, top_y + half_h),
        (top_x, top_y + tile_h),
        (top_x - half_w, top_y + half_h),
    ]
def tile_center(i: int, j: int, tile_w: int, tile_h: int, origin: Tuple[int, int]) -> Tuple[int, int]:
    """
    Screen-space center of tile (i,j). For a 2:1 iso diamond whose *top* is (sx,sy),
    the center is (sx, sy + tile_h//2).
    """
    sx, sy = grid_to_screen(i, j, tile_w, tile_h, origin)
    return sx, sy + tile_h // 2
