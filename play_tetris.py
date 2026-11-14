import pygame
from tetris import Tetris


BG_COLOR = (18, 20, 28)
PANEL_COLOR = (28, 32, 44)
GRID_COLOR = (40, 45, 60)
LOCKED_COLOR = (135, 145, 170)
TEXT_COLOR = (235, 240, 250)
MUTED_COLOR = (120, 128, 150)

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


def main():
    pygame.init()

    game = Tetris(
        height=20,
        width=10,
        gravity_speed=30,
        lock_delay=30,
        tick_hz=60,
    )
    game.start_clock()

    block_size = 28
    board_px_w = game.width * block_size
    board_px_h = game.height * block_size
    sidebar_px_w = 190

    screen = pygame.display.set_mode((board_px_w + sidebar_px_w, board_px_h))
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 20, bold=True)
    small_font = pygame.font.SysFont("arial", 15)

    key_to_action = {
        pygame.K_LEFT: 0,
        pygame.K_a: 0,
        pygame.K_RIGHT: 1,
        pygame.K_d: 1,
        pygame.K_UP: 2,
        pygame.K_x: 2,
        pygame.K_z: 3,
        pygame.K_DOWN: 4,
        pygame.K_s: 4,
        pygame.K_SPACE: 5,
        pygame.K_c: 6,
        pygame.K_LSHIFT: 6,
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
                        snap = game.get_snapshot()
                        if snap["gameover"]:
                            game.reset()
                    elif event.key in key_to_action:
                        game.push_action(key_to_action[event.key])

            snap = game.get_snapshot()

            screen.fill(BG_COLOR)

            for x in range(game.width + 1):
                pygame.draw.line(screen, GRID_COLOR, (x * block_size, 0), (x * block_size, board_px_h))
            for y in range(game.height + 1):
                pygame.draw.line(screen, GRID_COLOR, (0, y * block_size), (board_px_w, y * block_size))

            board = snap["board"]
            for x in range(game.width):
                for y in range(game.height):
                    if board[x, y]:
                        rect = pygame.Rect(x * block_size, y * block_size, block_size, block_size)
                        pygame.draw.rect(screen, LOCKED_COLOR, rect)
                        pygame.draw.rect(screen, BG_COLOR, rect, 1)

            if not snap["gameover"]:
                active_color = piece_colors[snap["current_piece"]]
                for x, y in snap["active_coords"]:
                    if 0 <= x < game.width and 0 <= y < game.height:
                        rect = pygame.Rect(x * block_size, y * block_size, block_size, block_size)
                        pygame.draw.rect(screen, active_color, rect)
                        pygame.draw.rect(screen, BG_COLOR, rect, 1)

            pygame.draw.rect(screen, PANEL_COLOR, (board_px_w, 0, sidebar_px_w, board_px_h))
            pad_x = board_px_w + 16

            screen.blit(font.render(f"Score: {snap['score']}", True, TEXT_COLOR), (pad_x, 16))
            screen.blit(font.render(f"Lines: {snap['cleared_lines']}", True, TEXT_COLOR), (pad_x, 44))

            screen.blit(small_font.render("HOLD (C / Shift)", True, MUTED_COLOR), (pad_x, 82))
            hold_box = pygame.Rect(pad_x, 102, 110, 56)
            pygame.draw.rect(screen, BG_COLOR, hold_box)
            pygame.draw.rect(screen, GRID_COLOR, hold_box, 1)

            held_id = snap["held_piece"]
            if held_id is not None:
                raw_color = piece_colors[held_id]
                hold_color = raw_color if snap["can_hold"] else tuple(c // 3 for c in raw_color)
                draw_mini_piece(screen, held_id, pad_x + 14, 112, 12, hold_color)

            screen.blit(small_font.render("NEXT", True, MUTED_COLOR), (pad_x, 174))
            for idx, piece_id in enumerate(snap["next_pieces"][:5]):
                color = piece_colors[piece_id]
                draw_mini_piece(screen, piece_id, pad_x + 14, 198 + idx * 46, 11, color)

            hints = [
                "Left/Right: Move",
                "Up/Z: Rotate",
                "Down: Soft drop",
                "Space: Hard drop",
                "C / Shift: Hold",
                "R: Restart",
            ]
            for i, text in enumerate(hints):
                screen.blit(
                    small_font.render(text, True, MUTED_COLOR),
                    (pad_x, board_px_h - 135 + i * 20),
                )

            if snap["gameover"]:
                overlay = pygame.Surface((board_px_w, board_px_h), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 165))
                screen.blit(overlay, (0, 0))
                screen.blit(
                    font.render("GAME OVER", True, (255, 90, 90)),
                    (board_px_w // 2 - 65, board_px_h // 2 - 20),
                )
                screen.blit(
                    small_font.render("Press R to restart", True, TEXT_COLOR),
                    (board_px_w // 2 - 58, board_px_h // 2 + 12),
                )

            pygame.display.flip()
            clock.tick(60)
    finally:
        game.stop_clock()
        pygame.quit()


if __name__ == "__main__":
    main()