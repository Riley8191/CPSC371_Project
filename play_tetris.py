import pygame
from tetris import Tetris, compute_attack, make_shared_bag_provider

BG_COLOR = (18, 20, 28)
PANEL_COLOR = (28, 32, 44)
GRID_COLOR = (40, 45, 60)
LOCKED_COLOR = (135, 145, 170)
GARBAGE_QUEUE_COLOR = (240, 85, 85)
DIVIDER_COLOR = (75, 85, 110)
TEXT_COLOR = (235, 240, 250)
MUTED_COLOR = (120, 128, 150)
WIN_COLOR = (90, 235, 130)
LOSE_COLOR = (255, 90, 90)
CALLOUT_COLOR = (255, 205, 80)

piece_colors = [
    (255, 255, 0),
    (0, 255, 255),
    (0, 255, 0),
    (255, 0, 0),
    (255, 165, 0),
    (0, 0, 255),
    (148, 0, 211),
]


def draw_mini_piece(surface, piece_id, origin_x, origin_y, cell_size, color):
    if piece_id is None:
        return
    for dx, dy in Tetris.SHAPES[piece_id][0]:
        rect = pygame.Rect(
            origin_x + dx * cell_size,
            origin_y + dy * cell_size,
            cell_size,
            cell_size,
        )
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, PANEL_COLOR, rect, 1)


def draw_player_board(
    surface,
    snap,
    player_label,
    is_winner,
    origin_x,
    board_w,
    board_h,
    sidebar_w,
    block_size,
    font,
    small_font,
):
    # Grid lines
    for x in range(snap["board"].shape[0] + 1):
        px = origin_x + x * block_size
        pygame.draw.line(surface, GRID_COLOR, (px, 0), (px, board_h))
    for y in range(snap["board"].shape[1] + 1):
        py = y * block_size
        pygame.draw.line(surface, GRID_COLOR, (origin_x, py), (origin_x + board_w, py))

    # Locked blocks
    board = snap["board"]
    for x in range(board.shape[0]):
        for y in range(board.shape[1]):
            if board[x, y]:
                rect = pygame.Rect(
                    origin_x + x * block_size,
                    y * block_size,
                    block_size,
                    block_size,
                )
                pygame.draw.rect(surface, LOCKED_COLOR, rect)
                pygame.draw.rect(surface, BG_COLOR, rect, 1)

    # Active piece
    if not snap["gameover"]:
        active_color = piece_colors[snap["current_piece"]]
        for x, y in snap["active_coords"]:
            if 0 <= x < board.shape[0] and 0 <= y < board.shape[1]:
                rect = pygame.Rect(
                    origin_x + x * block_size,
                    y * block_size,
                    block_size,
                    block_size,
                )
                pygame.draw.rect(surface, active_color, rect)
                pygame.draw.rect(surface, BG_COLOR, rect, 1)

    # Sidebar
    sb_x = origin_x + board_w
    pygame.draw.rect(surface, PANEL_COLOR, (sb_x, 0, sidebar_w, board_h))
    pad_x = sb_x + 14

    surface.blit(font.render(player_label, True, WIN_COLOR if is_winner else TEXT_COLOR), (pad_x, 10))
    surface.blit(small_font.render(f"Score: {snap['score']}", True, TEXT_COLOR), (pad_x, 35))
    surface.blit(small_font.render(f"Lines: {snap['cleared_lines']}", True, TEXT_COLOR), (pad_x, 54))

    pending_color = GARBAGE_QUEUE_COLOR if snap["pending_garbage"] > 0 else MUTED_COLOR
    surface.blit(
        small_font.render(f"Queued: {snap['pending_garbage']}", True, pending_color),
        (pad_x, 73),
    )

    # Visual garbage queue bar along right edge of sidebar
    bar_w = 8
    bar_x = sb_x + sidebar_w - bar_w - 6
    bar_h = min(snap["pending_garbage"], board.shape[1]) * block_size
    if bar_h > 0:
        pygame.draw.rect(surface, GARBAGE_QUEUE_COLOR, (bar_x, board_h - bar_h, bar_w, bar_h))

    surface.blit(small_font.render("HOLD", True, MUTED_COLOR), (pad_x, 98))
    hold_box = pygame.Rect(pad_x, 116, 100, 50)
    pygame.draw.rect(surface, BG_COLOR, hold_box)
    pygame.draw.rect(surface, GRID_COLOR, hold_box, 1)

    held_id = snap["held_piece"]
    if held_id is not None:
        raw_color = piece_colors[held_id]
        hold_color = raw_color if snap["can_hold"] else tuple(c // 3 for c in raw_color)
        draw_mini_piece(surface, held_id, pad_x + 12, 124, 11, hold_color)

    surface.blit(small_font.render("NEXT", True, MUTED_COLOR), (pad_x, 174))
    for idx, piece_id in enumerate(snap["next_pieces"][:5]):
        draw_mini_piece(surface, piece_id, pad_x + 12, 194 + idx * 42, 10, piece_colors[piece_id])

    if snap["last_move_label"]:
        surface.blit(
            small_font.render(snap["last_move_label"], True, CALLOUT_COLOR),
            (pad_x, board_h - 24),
        )

    if snap["gameover"] or is_winner:
        overlay = pygame.Surface((board_w, board_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        surface.blit(overlay, (origin_x, 0))
        msg = "WINNER!" if is_winner and not snap["gameover"] else "KO"
        color = WIN_COLOR if is_winner and not snap["gameover"] else LOSE_COLOR
        surface.blit(font.render(msg, True, color), (origin_x + board_w // 2 - 36, board_h // 2 - 14))


def main():
    pygame.init()

    bag_provider = make_shared_bag_provider()
    p1 = None
    p2 = None

    def p1_on_clear(lines, t_spin, perfect_clear):
        attack = compute_attack(lines, is_t_spin=t_spin, is_perfect_clear=perfect_clear)
        if p1 is not None and p2 is not None and attack > 0:
            p1.cancel_or_send_garbage(attack, opponent=p2)

    def p2_on_clear(lines, t_spin, perfect_clear):
        attack = compute_attack(lines, is_t_spin=t_spin, is_perfect_clear=perfect_clear)
        if p1 is not None and p2 is not None and attack > 0:
            p2.cancel_or_send_garbage(attack, opponent=p1)

    p1 = Tetris(
        height=20,
        width=10,
        gravity_speed=30,
        lock_delay=30,
        garbage_delay_ticks=30,
        tick_hz=60,
        on_lines_cleared=p1_on_clear,
        bag_provider=bag_provider,
    )
    p2 = Tetris(
        height=20,
        width=10,
        gravity_speed=30,
        lock_delay=30,
        garbage_delay_ticks=30,
        tick_hz=60,
        on_lines_cleared=p2_on_clear,
        bag_provider=bag_provider,
    )
    p1.start_clock()
    p2.start_clock()

    block_size = 28
    board_px_w = p1.width * block_size
    board_px_h = p1.height * block_size
    sidebar_px_w = 165
    pane_w = board_px_w + sidebar_px_w
    divider_w = 6
    banner_h = 34

    screen = pygame.display.set_mode((pane_w * 2 + divider_w, board_px_h + banner_h))
    pygame.display.set_caption("1v1 Tetris")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 20, bold=True)
    small_font = pygame.font.SysFont("arial", 15)

    p1_keys = {
        pygame.K_a: 0,
        pygame.K_d: 1,
        pygame.K_w: 2,
        pygame.K_q: 3,
        pygame.K_s: 4,
        pygame.K_SPACE: 5,
        pygame.K_e: 6,
    }
    p2_keys = {
        pygame.K_LEFT: 0,
        pygame.K_RIGHT: 1,
        pygame.K_UP: 2,
        pygame.K_z: 3,
        pygame.K_DOWN: 4,
        pygame.K_RETURN: 5,
        pygame.K_RSHIFT: 6,
    }

    running = True
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        s1 = p1.get_snapshot()
                        s2 = p2.get_snapshot()
                        if s1["gameover"] or s2["gameover"]:
                            p1.reset()
                            p2.reset()
                    elif event.key in p1_keys:
                        p1.push_action(p1_keys[event.key])
                    elif event.key in p2_keys:
                        p2.push_action(p2_keys[event.key])

            s1 = p1.get_snapshot()
            s2 = p2.get_snapshot()

            p1_won = s2["gameover"] and not s1["gameover"]
            p2_won = s1["gameover"] and not s2["gameover"]

            screen.fill(BG_COLOR)

            pygame.draw.rect(screen, PANEL_COLOR, (0, 0, screen.get_width(), banner_h))
            if s1["gameover"] or s2["gameover"]:
                if p1_won:
                    status_text, status_color = "P1 WINS! Press R for rematch", WIN_COLOR
                elif p2_won:
                    status_text, status_color = "P2 WINS! Press R for rematch", WIN_COLOR
                else:
                    status_text, status_color = "DRAW! Press R for rematch", TEXT_COLOR
            else:
                status_text = "P1: WASD + Q/E/Space   |   P2: Arrows + Z/Shift/Enter"
                status_color = MUTED_COLOR

            screen.blit(small_font.render(status_text, True, status_color), (14, 8))

            board_surface = pygame.Surface((screen.get_width(), board_px_h))
            board_surface.fill(BG_COLOR)

            draw_player_board(
                board_surface,
                s1,
                "PLAYER 1",
                p1_won,
                0,
                board_px_w,
                board_px_h,
                sidebar_px_w,
                block_size,
                font,
                small_font,
            )

            div_x = pane_w
            pygame.draw.rect(board_surface, DIVIDER_COLOR, (div_x, 0, divider_w, board_px_h))

            draw_player_board(
                board_surface,
                s2,
                "PLAYER 2",
                p2_won,
                div_x + divider_w,
                board_px_w,
                board_px_h,
                sidebar_px_w,
                block_size,
                font,
                small_font,
            )

            screen.blit(board_surface, (0, banner_h))
            pygame.display.flip()
            clock.tick(60)
    finally:
        p1.stop_clock()
        p2.stop_clock()
        pygame.quit()


if __name__ == "__main__":
    main()