from __future__ import annotations
from enum import Enum, auto

class Phase(Enum):
    PLAYER = auto()
    ENEMY = auto()

class TurnManager:
    def __init__(self) -> None:
        self.turn: int = 1
        self.phase: Phase = Phase.PLAYER
        self._enemy_timer: float = 0.0  # unused for logic now; kept for compatibility

    def end_player_turn(self) -> None:
        if self.phase is Phase.PLAYER:
            self.phase = Phase.ENEMY
            self._enemy_timer = 0.0

    def complete_enemy_turn(self) -> None:
        if self.phase is Phase.ENEMY:
            self.phase = Phase.PLAYER
            self.turn += 1

    def update(self, dt: float) -> bool:
        """
        Legacy hook. Returns True if we just transitioned back to PLAYER (new turn).
        Enemy completion is now controlled externally via complete_enemy_turn().
        """
        return False
