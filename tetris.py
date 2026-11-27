import random
import threading
import time
from collections import deque
from enum import Enum
import numpy as np


ATTACK_TABLE = {
    (1, False, False): 0,   # Single
    (2, False, False): 1,   # Double
    (3, False, False): 2,   # Triple
    (4, False, False): 4,   # Tetris
    (1, True, False): 2,    # T-Spin Single
    (2, True, False): 4,    # T-Spin Double
    (3, True, False): 6,    # T-Spin Triple
}


def compute_attack(lines_cleared, is_t_spin=False, is_perfect_clear=False):
    if lines_cleared <= 0:
        return 0
    if is_perfect_clear:
        return 10
    if is_t_spin:
        return ATTACK_TABLE.get((lines_cleared, True, False), lines_cleared * 2)
    return ATTACK_TABLE.get((lines_cleared, False, False), max(0, lines_cleared - 1))


def make_shared_bag_provider(seed=None):
    """Returns a thread-safe callable that yields identical 7-bag pieces."""
    rng = random.Random(seed)
    lock = threading.Lock()
    pool = []

    def next_bag():
        with lock:
            while len(pool) < 14:
                bag = list(range(len(Tetris.Pieces)))
                rng.shuffle(bag)
                pool.extend(bag)
            out = pool[:14]
            del pool[:14]
            return out

    return next_bag


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

    SRS_JLSTZ_KICKS = {
        (0, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
        (1, 2): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
        (2, 3): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
        (3, 0): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
        (0, 3): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
        (3, 2): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
        (2, 1): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
        (1, 0): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    }

    def __init__(
        self,
        height=20,
        width=10,
        gravity_speed=15,
        lock_delay=30,
        max_lock_resets=15,
        garbage_delay_ticks=30,
        tick_hz=60,
        buffer_size=8,
        on_lines_cleared=None,
        bag_provider=None,
    ):
        self.height = height
        self.width = width
        self.gravity_speed = gravity_speed
        self.lock_delay = lock_delay
        self.max_lock_resets = max_lock_resets
        self.garbage_delay_ticks = garbage_delay_ticks
        self.tick_hz = tick_hz
        self.action_buffer = deque(maxlen=buffer_size)
        self.on_lines_cleared = on_lines_cleared
        self.bag_provider = bag_provider

        self._lock = threading.RLock()
        self._running = False
        self._clock_thread = None

        self.reset()

    def _draw_bag_chunk(self):
        if self.bag_provider is not None:
            return list(self.bag_provider())
        bag = list(range(len(self.Pieces)))
        next_bag = list(range(len(self.Pieces)))
        random.shuffle(bag)
        random.shuffle(next_bag)
        return bag + next_bag

    def reset(self):
        with self._lock:
            self.board = np.zeros((self.width, self.height), dtype=bool)
            self.cleared_lines = 0
            self.garbage_received = 0
            self.pending_garbage = 0
            self._garbage_age = 0
            self.last_was_rotation = False
            self.last_move_label = ""
            self.score = 0
            self.gameover = False
            self.fall_counter = 0
            self.lock_timer = 0
            self.lock_resets = 0
            self.tick_count = 0
            self.held_piece = None
            self.can_hold = True
            self.action_buffer.clear()

            self.queue = self._draw_bag_chunk()
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
        if self.pending_garbage > 0:
            self._garbage_age += 1

        lines = 0
        piece_locked_this_step = False

        match action:
            case 0:  # left
                self.move(-1)
            case 1:  # right
                self.move(1)
            case 2:  # rotate right
                self.rotate(1)
            case 3:  # rotate left
                self.rotate(-1)
            case 4:  # soft drop
                lines, _, locked = self.drop(return_locked=True)
                piece_locked_this_step = locked
                self.fall_counter = 0
            case 5:  # hard drop
                lines, _, locked = self.hard_drop(return_locked=True)
                piece_locked_this_step = locked
            case 6:  # hold
                self.hold()

        if action != 5 and not self.gameover and not piece_locked_this_step:
            if self._is_grounded():
                self.lock_timer += 1
                if self.lock_timer >= self.lock_delay:
                    lines += self._lock_piece()
                    piece_locked_this_step = True
            else:
                self.fall_counter += 1
                if self.fall_counter >= self.gravity_speed:
                    self.fall_counter = 0
                    dropped_lines, _, locked = self.drop(return_locked=True)
                    lines += dropped_lines
                    piece_locked_this_step = locked


        if (
            piece_locked_this_step
            and not self.gameover
            and lines == 0
            and self.pending_garbage > 0
            and self._garbage_age >= self.garbage_delay_ticks
        ):
            to_apply = self.pending_garbage
            self.pending_garbage = 0
            self._garbage_age = 0
            self._apply_garbage_unlocked(to_apply)

        reward = 1.0 + (lines ** 2) * self.width
        if self.gameover:
            reward -= 5.0

        return self.get_state_properties(self.board), reward, self.gameover

    def queue_garbage(self, lines):
        """Add incoming garbage lines to this player's pending queue."""
        if lines <= 0:
            return
        with self._lock:
            if self.gameover:
                return
            self.pending_garbage += int(lines)

    def cancel_or_send_garbage(self, attack_lines, opponent=None):
        """Cancel own pending garbage first; send leftover attack to opponent."""
        if attack_lines <= 0:
            return 0
        with self._lock:
            canceled = min(int(attack_lines), self.pending_garbage)
            self.pending_garbage -= canceled
            if self.pending_garbage == 0:
                self._garbage_age = 0
            leftover = int(attack_lines) - canceled
        if leftover > 0 and opponent is not None:
            opponent.queue_garbage(leftover)
        return leftover

    def add_garbage(self, lines, hole_x=None):
        """Immediately push `lines` rows of garbage up from the bottom."""
        if lines <= 0:
            return
        with self._lock:
            self._apply_garbage_unlocked(lines, hole_x=hole_x)

    def _apply_garbage_unlocked(self, lines, hole_x=None):
        if self.gameover or lines <= 0:
            return

        n = min(int(lines), self.height)
        if np.any(self.board[:, :n]):
            self.gameover = True
            return

        new_board = np.zeros((self.width, self.height), dtype=bool)
        if n < self.height:
            new_board[:, : self.height - n] = self.board[:, n:]

        for row_offset in range(n):
            y = self.height - 1 - row_offset
            hole = random.randrange(self.width) if hole_x is None else (hole_x % self.width)
            new_board[:, y] = True
            new_board[hole, y] = False

        self.board = new_board
        self.garbage_received += n

        if self._check_collision(self.current_pivot, self.current_rotation):
            nudge_up = {"x": self.current_pivot["x"], "y": self.current_pivot["y"] - n}
            if not self._check_collision(nudge_up, self.current_rotation):
                self.current_pivot = nudge_up
            else:
                self.gameover = True

    def _is_t_spin(self):
        if self.current_piece != self.Pieces.T.value or not self.last_was_rotation:
            return False

        cx = self.current_pivot["x"] + 1
        cy = self.current_pivot["y"] + 1
        corners = [
            (cx - 1, cy - 1),
            (cx + 1, cy - 1),
            (cx - 1, cy + 1),
            (cx + 1, cy + 1),
        ]

        occupied = 0
        for x, y in corners:
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                occupied += 1
            elif self.board[x, y]:
                occupied += 1

        return occupied >= 3

    def _spawn_piece(self):
        self.current_piece = self.queue.pop(0)
        self.current_rotation = 0
        self.fall_counter = 0
        self.lock_timer = 0
        self.lock_resets = 0
        self.last_was_rotation = False
        self.can_hold = True

        if len(self.queue) <= 7:
            self.queue.extend(self._draw_bag_chunk())

        self.next_pieces = self.queue[:5]
        self.current_pivot = {
            "x": self.width // 2 - (2 if self.current_piece != self.Pieces.O.value else 1),
            "y": 0 if self.current_piece != self.Pieces.I.value else -1,
        }

        if self._check_collision(self.current_pivot, self.current_rotation):
            self.gameover = True

    def _is_grounded(self):
        below = {"x": self.current_pivot["x"], "y": self.current_pivot["y"] + 1}
        return self._check_collision(below, self.current_rotation)

    def _on_manipulation(self, was_rotation=False):
        self.last_was_rotation = was_rotation
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
            self._on_manipulation(was_rotation=False)
            return True
        return False

    def rotate(self, direction=1):
        if self.gameover:
            return False
        if self.current_piece == self.Pieces.O.value:
            self._on_manipulation(was_rotation=True)
            return True

        old_rotation = self.current_rotation
        new_rotation = (old_rotation + direction) % 4

        if self.current_piece == self.Pieces.I.value:
            kick_offsets = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1), (0, 1)]
        else:
            kick_offsets = self.SRS_JLSTZ_KICKS.get(
                (old_rotation, new_rotation), [(0, 0)]
            )

        for kx, ky in kick_offsets:
            new_pivot = {
                "x": self.current_pivot["x"] + kx,
                "y": self.current_pivot["y"] + ky,
            }
            if not self._check_collision(new_pivot, new_rotation):
                self.current_pivot = new_pivot
                self.current_rotation = new_rotation
                self._on_manipulation(was_rotation=True)
                return True
        return False

    def drop(self, return_locked=False):
        if self.gameover:
            return (0, True, False) if return_locked else (0, True)

        new_pivot = {"x": self.current_pivot["x"], "y": self.current_pivot["y"] + 1}
        if not self._check_collision(new_pivot, self.current_rotation):
            self.current_pivot = new_pivot
            self.last_was_rotation = False
            self.lock_timer = 0
            return (0, False, False) if return_locked else (0, False)

        self.lock_timer += 1
        if self.lock_timer >= self.lock_delay:
            lines_cleared = self._lock_piece()
            return (lines_cleared, self.gameover, True) if return_locked else (lines_cleared, self.gameover)

        return (0, False, False) if return_locked else (0, False)

    def hard_drop(self, return_locked=False):
        if self.gameover:
            return (0, True, False) if return_locked else (0, True)

        moved = False
        while not self._check_collision(
            {"x": self.current_pivot["x"], "y": self.current_pivot["y"] + 1},
            self.current_rotation,
        ):
            self.current_pivot["y"] += 1
            moved = True

        if moved:
            self.last_was_rotation = False

        lines_cleared = self._lock_piece()
        return (lines_cleared, self.gameover, True) if return_locked else (lines_cleared, self.gameover)

    def hold(self):
        if self.gameover or not self.can_hold:
            return False

        self.can_hold = False
        self.last_was_rotation = False

        if self.held_piece is None:
            self.held_piece = self.current_piece
            self._spawn_piece()
            self.can_hold = False
        else:
            self.current_piece, self.held_piece = self.held_piece, self.current_piece
            self.current_rotation = 0
            self.fall_counter = 0
            self.lock_timer = 0
            self.lock_resets = 0
            self.current_pivot = {
                "x": self.width // 2 - (2 if self.current_piece != self.Pieces.O.value else 1),
                "y": 0 if self.current_piece != self.Pieces.I.value else -1,
            }
            if self._check_collision(self.current_pivot, self.current_rotation):
                self.gameover = True

        return True

    def _lock_piece(self):
        t_spin = self._is_t_spin()
        for x, y in self._get_piece_coords():
            self.board[x, y] = True

        lines = self._clear_lines()
        perfect_clear = lines > 0 and bool(np.all(~self.board))

        self.cleared_lines += lines
        self.score += [0, 40, 100, 300, 1200][lines]

        if lines > 0:
            if perfect_clear:
                self.last_move_label = f"PERFECT CLEAR ({lines})"
            elif t_spin:
                names = {1: "T-SPIN SINGLE", 2: "T-SPIN DOUBLE", 3: "T-SPIN TRIPLE"}
                self.last_move_label = names.get(lines, f"T-SPIN ({lines})")
            else:
                names = {1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE", 4: "TETRIS"}
                self.last_move_label = names.get(lines, f"{lines} LINES")

            if self.on_lines_cleared is not None:
                self.on_lines_cleared(lines, t_spin, perfect_clear)

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
                "garbage_received": self.garbage_received,
                "pending_garbage": self.pending_garbage,
                "last_move_label": self.last_move_label,
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