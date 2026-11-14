import random
import threading
import time
from collections import deque
from enum import Enum
import numpy as np


class Tetris:
    class Pieces(Enum):
        O = 0
        I = 1
        S = 2
        Z = 3
        L = 4
        J = 5
        T = 6

    SHAPES = {
        0: [  # O
            [(0, 0), (1, 0), (0, 1), (1, 1)],
            [(0, 0), (1, 0), (0, 1), (1, 1)],
            [(0, 0), (1, 0), (0, 1), (1, 1)],
            [(0, 0), (1, 0), (0, 1), (1, 1)],
        ],
        1: [  # I
            [(0, 1), (1, 1), (2, 1), (3, 1)],
            [(2, 0), (2, 1), (2, 2), (2, 3)],
            [(0, 2), (1, 2), (2, 2), (3, 2)],
            [(1, 0), (1, 1), (1, 2), (1, 3)],
        ],
        2: [  # S
            [(1, 0), (2, 0), (0, 1), (1, 1)],
            [(1, 0), (1, 1), (2, 1), (2, 2)],
            [(1, 1), (2, 1), (0, 2), (1, 2)],
            [(0, 0), (0, 1), (1, 1), (1, 2)],
        ],
        3: [  # Z
            [(0, 0), (1, 0), (1, 1), (2, 1)],
            [(2, 0), (1, 1), (2, 1), (1, 2)],
            [(0, 1), (1, 1), (1, 2), (2, 2)],
            [(1, 0), (0, 1), (1, 1), (0, 2)],
        ],
        4: [  # L
            [(2, 0), (0, 1), (1, 1), (2, 1)],
            [(1, 0), (1, 1), (1, 2), (2, 2)],
            [(0, 1), (1, 1), (2, 1), (0, 2)],
            [(0, 0), (1, 0), (1, 1), (1, 2)],
        ],
        5: [  # J
            [(0, 0), (0, 1), (1, 1), (2, 1)],
            [(1, 0), (2, 0), (1, 1), (1, 2)],
            [(0, 1), (1, 1), (2, 1), (2, 2)],
            [(1, 0), (1, 1), (0, 2), (1, 2)],
        ],
        6: [  # T
            [(1, 0), (0, 1), (1, 1), (2, 1)],
            [(1, 0), (1, 1), (2, 1), (1, 2)],
            [(0, 1), (1, 1), (2, 1), (1, 2)],
            [(1, 0), (0, 1), (1, 1), (1, 2)],
        ],
    }

    def __init__(
        self,
        height=20,
        width=10,
        gravity_speed=15,
        lock_delay=30,
        max_lock_resets=15,
        tick_hz=60,
        buffer_size=8,
    ):
        self.height = height
        self.width = width
        self.gravity_speed = gravity_speed
        self.lock_delay = lock_delay
        self.max_lock_resets = max_lock_resets
        self.tick_hz = tick_hz
        self.action_buffer = deque(maxlen=buffer_size)

        self._lock = threading.Lock()
        self._running = False
        self._clock_thread = None

        self.reset()

    def reset(self):
        with self._lock:
            self.board = np.zeros((self.width, self.height), dtype=bool)
            self.cleared_lines = 0
            self.score = 0
            self.gameover = False
            self.fall_counter = 0
            self.lock_timer = 0
            self.lock_resets = 0
            self.tick_count = 0
            self.held_piece = None
            self.can_hold = True
            self.action_buffer.clear()

            bag = list(range(len(self.Pieces)))
            next_bag = list(range(len(self.Pieces)))
            random.shuffle(bag)
            random.shuffle(next_bag)
            self.queue = bag + next_bag

            self._spawn_piece()
            return self.get_state_properties(self.board)

    def push_action(self, action):
        with self._lock:
            if isinstance(action, (list, tuple)):
                self.action_buffer.extend(action)
            elif action is not None:
                self.action_buffer.append(action)

    def clear_buffer(self):
        with self._lock:
            self.action_buffer.clear()

    def start_clock(self, tick_hz=None):
        if tick_hz is not None:
            self.tick_hz = tick_hz
        if self._running:
            return

        self._running = True
        self._clock_thread = threading.Thread(target=self._clock_loop, daemon=True)
        self._clock_thread.start()

    def stop_clock(self):
        self._running = False
        if self._clock_thread is not None:
            self._clock_thread.join(timeout=1.0)
            self._clock_thread = None

    def _clock_loop(self):
        interval = 1.0 / self.tick_hz if self.tick_hz else 0.0
        next_tick = time.perf_counter()

        while self._running:
            self.tick()
            if interval > 0:
                next_tick += interval
                sleep_time = next_tick - time.perf_counter()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    next_tick = time.perf_counter()

    def tick(self):
        with self._lock:
            action = self.action_buffer.popleft() if self.action_buffer else None
            return self._step_unlocked(action)

    def step(self, action=None):
        with self._lock:
            if action is None and self.action_buffer:
                action = self.action_buffer.popleft()
            return self._step_unlocked(action)

    def _step_unlocked(self, action=None):
        if self.gameover:
            return self.get_state_properties(self.board), 0.0, True

        self.tick_count += 1
        lines = 0

        match action:
            case 0: #left
                self.move(-1)
            case 1: #right
                self.move(1)
            case 2: #right
                self.rotate(1)
            case 3: #left
                self.rotate(-1)
            case 4: #soft
                lines, _ = self.drop()
                self.fall_counter = 0
            case 5: #hard
                lines, _ = self.hard_drop()
            case 6: #hold
                self.hold()

        if action != 5 and not self.gameover:
            if self._is_grounded():
                self.lock_timer += 1
                if self.lock_timer >= self.lock_delay:
                    lines += self._lock_piece()
            else:
                self.fall_counter += 1
                if self.fall_counter >= self.gravity_speed:
                    self.fall_counter = 0
                    dropped_lines, _ = self.drop()
                    lines += dropped_lines

        reward = 1.0 + (lines ** 2) * self.width
        if self.gameover:
            reward -= 5.0

        return self.get_state_properties(self.board), reward, self.gameover
    
    def _spawn_piece(self):
        self.current_piece = self.queue.pop(0)
        self.current_rotation = 0
        self.fall_counter = 0
        self.lock_timer = 0
        self.lock_resets = 0
        self.can_hold = True

        if len(self.queue) <= 7:
            new_bag = list(range(len(self.Pieces)))
            random.shuffle(new_bag)
            self.queue.extend(new_bag)

        self.next_pieces = self.queue[:5]
        self.current_pivot = {
            "x": self.width // 2 - (2 if self.current_piece != self.Pieces.O.value else 1),
            "y": 0,
        }

        if self._check_collision(self.current_pivot, self.current_rotation):
            self.gameover = True

    def _is_grounded(self):
        below = {"x": self.current_pivot["x"], "y": self.current_pivot["y"] + 1}
        return self._check_collision(below, self.current_rotation)

    def _on_manipulation(self):
        if not self._is_grounded():
            self.lock_timer = 0
            self.lock_resets = 0
        elif self.lock_resets < self.max_lock_resets:
            self.lock_timer = 0
            self.lock_resets += 1

    def _get_piece_coords(self, pivot=None, rotation=None):
        if pivot is None:
            pivot = self.current_pivot
        if rotation is None:
            rotation = self.current_rotation

        shape = self.SHAPES[self.current_piece][rotation]
        return [(pivot["x"] + dx, pivot["y"] + dy) for dx, dy in shape]

    def _check_collision(self, pivot, rotation):
        for x, y in self._get_piece_coords(pivot, rotation):
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                return True
            if self.board[x, y]:
                return True
        return False

    def move(self, dx):
        if self.gameover:
            return False
        new_pivot = {"x": self.current_pivot["x"] + dx, "y": self.current_pivot["y"]}
        if not self._check_collision(new_pivot, self.current_rotation):
            self.current_pivot = new_pivot
            self._on_manipulation()
            return True
        return False

    def rotate(self, direction=1):
        if self.gameover:
            return False
        new_rotation = (self.current_rotation + direction) % 4

        kick_offsets = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1)]
        for kx, ky in kick_offsets:
            new_pivot = {
                "x": self.current_pivot["x"] + kx,
                "y": self.current_pivot["y"] + ky,
            }
            if not self._check_collision(new_pivot, new_rotation):
                self.current_pivot = new_pivot
                self.current_rotation = new_rotation
                self._on_manipulation()
                return True
        return False

    def drop(self):
        if self.gameover:
            return 0, True

        new_pivot = {"x": self.current_pivot["x"], "y": self.current_pivot["y"] + 1}
        if not self._check_collision(new_pivot, self.current_rotation):
            self.current_pivot = new_pivot
            self.lock_timer = 0
            return 0, False

        self.lock_timer += 1
        if self.lock_timer >= self.lock_delay:
            lines_cleared = self._lock_piece()
            return lines_cleared, self.gameover

        return 0, False

    def hard_drop(self):
        if self.gameover:
            return 0, True

        while not self._check_collision(
            {"x": self.current_pivot["x"], "y": self.current_pivot["y"] + 1},
            self.current_rotation,
        ):
            self.current_pivot["y"] += 1

        lines_cleared = self._lock_piece()
        return lines_cleared, self.gameover

    def hold(self):
        if self.gameover or not self.can_hold:
            return False

        self.can_hold = False

        if self.held_piece is None:
            self.held_piece = self.current_piece
            self._spawn_piece()
            self.can_hold = False  # _spawn_piece() sets can_hold=True, so re-lock it
        else:
            self.current_piece, self.held_piece = self.held_piece, self.current_piece
            self.current_rotation = 0
            self.fall_counter = 0
            self.lock_timer = 0
            self.lock_resets = 0
            self.current_pivot = {
                "x": self.width // 2 - (2 if self.current_piece != self.Pieces.O.value else 1),
                "y": 0,
            }
            if self._check_collision(self.current_pivot, self.current_rotation):
                self.gameover = True

        return True
    
    def _lock_piece(self):
        for x, y in self._get_piece_coords():
            self.board[x, y] = True

        lines = self._clear_lines()
        self.cleared_lines += lines
        self.score += [0, 40, 100, 300, 1200][lines]
        self._spawn_piece()
        return lines

    def _clear_lines(self):
        full_rows = [y for y in range(self.height) if np.all(self.board[:, y])]
        if not full_rows:
            return 0

        remaining_rows = [y for y in range(self.height) if y not in full_rows]
        new_board = np.zeros((self.width, self.height), dtype=bool)
        new_board[:, len(full_rows) :] = self.board[:, remaining_rows]
        self.board = new_board
        return len(full_rows)

    def get_snapshot(self):
        with self._lock:
            return {
                "board": self.board.copy(),
                "active_coords": [] if self.gameover else self._get_piece_coords(),
                "current_piece": self.current_piece,
                "held_piece": self.held_piece,
                "can_hold": self.can_hold,
                "next_pieces": list(self.next_pieces),
                "score": self.score,
                "cleared_lines": self.cleared_lines,
                "gameover": self.gameover,
                "tick_count": self.tick_count,
            }

    def get_state_properties(self, board=None):
        if board is None:
            board = self.board
        heights = np.zeros(self.width, dtype=int)
        holes = 0

        for x in range(self.width):
            col = board[x, :]
            filled_indices = np.where(col)[0]
            if len(filled_indices) > 0:
                top_y = filled_indices[0]
                heights[x] = self.height - top_y
                holes += np.sum(~col[top_y:])

        aggregate_height = int(np.sum(heights))
        bumpiness = int(np.sum(np.abs(np.diff(heights))))

        return np.array(
            [self.cleared_lines, holes, bumpiness, aggregate_height], dtype=np.float32
        )

# if __name__ == "__main__":
#     game = Tetris(height=20, width=10)
    
#     for _ in range(10):
#         action = 4
#         state, reward, done = game.step(action)
#         print(f"Action: {action} | State [Lines, Holes, Bump, Height]: {state} | Done: {done}")
#         string=""
#         for i in range(20):
#             for j in range(10):
#                 string+= "1" if game.board[j][i] else "0"
#             print(string)
#             string=""
#         if done:
#             game.reset()