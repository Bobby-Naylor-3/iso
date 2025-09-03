from __future__ import annotations
from enum import Enum, auto

class Phase(Enum):
    PLAYER = auto()
    ENEMY = auto()

class TurnManager:
    def __init__(self) -> None:
        self.turn: int = 1
        self.phase: Phase = Phase.PLAYER
        self._enemy_timer: float = 0.0  # simple placeholder for enemy turn duration

    def end_player_turn(self) -> None:
        if self.phase is Phase.PLAYER:
            self.phase = Phase.ENEMY
            self._enemy_timer = 0.8  # seconds to "process" enemy turn

    def update(self, dt: float) -> bool:
        """
        Returns True if we just transitioned back to PLAYER (new turn).
        """
        if self.phase is Phase.ENEMY:
            self._enemy_timer -= dt
            if self._enemy_timer <= 0.0:
                self.phase = Phase.PLAYER
                self.turn += 1
                return True
        return False
