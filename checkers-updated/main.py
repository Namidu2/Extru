import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'

import pygame
import pygame.gfxdraw
import threading
from tkinter import Tk, messagebox
from board import Board
from constants import FPS, SCREEN_SIZE, SCOREBOARD_WIDTH
from network import Network

# ─── Init ────────────────────────────────────────────────────────────────────
pygame.init()
root = Tk()
root.withdraw()

display_surf = pygame.display.set_mode(SCREEN_SIZE, pygame.RESIZABLE)
screen       = pygame.Surface(SCREEN_SIZE)

# --- Scaling logic ---
def get_scaled_rect(win_w, win_h, log_w, log_h):
    win_r = win_w / win_h
    log_r = log_w / log_h
    if win_r > log_r:
        new_h = win_h
        new_w = int(log_w * (win_h / log_h))
        x = (win_w - new_w) // 2
        y = 0
    else:
        new_w = win_w
        new_h = int(log_h * (win_w / log_w))
        x = 0
        y = (win_h - new_h) // 2
    return pygame.Rect(x, y, new_w, new_h)

_orig_mouse_get_pos = pygame.mouse.get_pos
def _scaled_mouse_get_pos():
    mx, my = _orig_mouse_get_pos()
    win_w, win_h = display_surf.get_size()
    scaled_rect = get_scaled_rect(win_w, win_h, SCREEN_SIZE[0], SCREEN_SIZE[1])
    if scaled_rect.width > 0 and scaled_rect.height > 0:
        lx = (mx - scaled_rect.x) * (SCREEN_SIZE[0] / scaled_rect.width)
        ly = (my - scaled_rect.y) * (SCREEN_SIZE[1] / scaled_rect.height)
        return (lx, ly)
    return (mx, my)

pygame.mouse.get_pos = _scaled_mouse_get_pos

_orig_display_update = pygame.display.update
def _scaled_display_update(*args, **kwargs):
    win_w, win_h = display_surf.get_size()
    scaled_rect = get_scaled_rect(win_w, win_h, SCREEN_SIZE[0], SCREEN_SIZE[1])
    # logical board 'screen' is 800x600 (or whatever SCREEN_SIZE is)
    scaled_surf = pygame.transform.smoothscale(screen, (scaled_rect.width, scaled_rect.height))
    display_surf.fill((0, 0, 0))
    display_surf.blit(scaled_surf, (scaled_rect.x, scaled_rect.y))
    _orig_display_update(*args, **kwargs)

pygame.display.update = _scaled_display_update

clock  = pygame.time.Clock()
pygame.display.set_caption("Checkers")

running = False   # set to True once the game loop starts
paused  = False
board   = None

# ─── Game state variables ─────────────────────────────────────────────────────
selected_difficulty = None
selected_ai_mode    = None   # True=AI, False=local human, "lan"=LAN

# ─── LAN state ────────────────────────────────────────────────────────────────
net: Network | None = None   # active Network instance
lan_role      = None          # "host" or "client"
lan_my_color  = None          # "white" (host) or "black" (client)
lan_status    = ""            # status string shown on the LAN lobby screen
lan_error     = ""
lan_connecting = False        # background thread is working
lan_input_text = ""          # IP address the user types
lan_input_active = False      # whether the IP text box is focused
lan_ready     = False         # both sides connected & handshake done
# sub-screen within "LAN lobby"
# None → pick Host/Join, "hosting" → waiting, "joining" → type IP, "connected" → ready
lan_screen    = None
last_ping_time = 0   # Track for keep-alive

# ─── Colours ──────────────────────────────────────────────────────────────────
C_BG         = (10,  15,  30)
C_PANEL      = (20,  28,  50)
C_ACCENT     = (72, 149, 239)
C_ACCENT2    = (76, 201, 240)
C_GREEN      = (40, 200, 100)
C_RED        = (220,  60,  60)
C_GOLD       = (255, 215,   0)
C_TEXT       = (220, 230, 255)
C_SUBTEXT    = (140, 155, 190)
C_WHITE_PIECE= (240, 240, 240)
C_BLACK_PIECE= ( 48,  48,  48)


# ─── Button class ─────────────────────────────────────────────────────────────
class Button:
    def __init__(self, text, pos, size,
                 color=C_ACCENT, hover_color=C_ACCENT2,
                 font_size=32, radius=10):
        self.rect        = pygame.Rect(pos, size)
        self.color       = color
        self.hover_color = hover_color
        self.text        = text
        self.font        = pygame.font.SysFont("segoeui", font_size, bold=True)
        self.radius      = radius
        self._alpha      = 0          # for fade-in (unused here but handy)

    def draw(self, surf):
        hovered = self.rect.collidepoint(pygame.mouse.get_pos())
        c = self.hover_color if hovered else self.color
        # shadow
        shadow_rect = self.rect.move(3, 3)
        s = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (0, 0, 0, 80), s.get_rect(), border_radius=self.radius)
        surf.blit(s, shadow_rect.topleft)
        # button
        pygame.draw.rect(surf, c, self.rect, border_radius=self.radius)
        if hovered:
            glow = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*c, 60), glow.get_rect(), border_radius=self.radius)
            surf.blit(glow, self.rect.topleft)
        lbl = self.font.render(self.text, True, (255, 255, 255))
        surf.blit(lbl, lbl.get_rect(center=self.rect.center))

    def is_clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN and
                event.button == 1 and
                self.rect.collidepoint(event.pos))


# ─── Helper: draw rounded panel ──────────────────────────────────────────────
def draw_panel(surf, rect, color=C_PANEL, radius=16, alpha=220):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
    surf.blit(s, rect.topleft)


# ─── Fonts ────────────────────────────────────────────────────────────────────
font_huge  = pygame.font.SysFont("segoeui", 72, bold=True)
font_large = pygame.font.SysFont("segoeui", 44, bold=True)
font_med   = pygame.font.SysFont("segoeui", 28)
font_small = pygame.font.SysFont("segoeui", 22)
font_tiny  = pygame.font.SysFont("segoeui", 18)

sw, sh = int(SCREEN_SIZE[0]), int(SCREEN_SIZE[1])


# ─── Build buttons ────────────────────────────────────────────────────────────
# Difficulty
BW, BH = 190, 75
GAP = 18
diff_buttons = {
    "Very Easy": Button("Very Easy", (0,0), (BW,BH), (80,160,80),  (110,210,110), 26),
    "Easy":      Button("Easy",      (0,0), (BW,BH), (50,180,100), (80, 230,130), 26),
    "Hard":      Button("Hard",      (0,0), (BW,BH), (200,100,40), (240,140, 60), 26),
    "Very Hard": Button("Very Hard", (0,0), (BW,BH), (190, 40, 40),(230, 70, 70), 26),
}
diff_map = {"Very Easy": 1, "Easy": 2, "Hard": 3, "Very Hard": 4}

# Play-mode
PM_W, PM_H = 210, 80
play_vs_ai_btn    = Button("vs AI",      (0,0), (PM_W, PM_H), (60,100,190),  (90,140,240), 28)
play_vs_human_btn = Button("vs Human",   (0,0), (PM_W, PM_H), (60,150,100),  (90,200,140), 28)
play_vs_lan_btn   = Button("LAN / Wi-Fi",(0,0), (PM_W, PM_H), (120, 60,180), (160, 90,230), 28)

# LAN lobby
lan_host_btn   = Button("Host Game",  (0,0), (200, 65), (60,100,190),  (90,140,240), 26)
lan_join_btn   = Button("Join Game",  (0,0), (200, 65), (60,150,100),  (90,200,140), 26)
lan_back_btn   = Button("← Back",     (0,0), (140, 48), C_RED, (230,80,80), 22)
lan_connect_btn= Button("Connect",    (0,0), (160, 52), C_GREEN, (60,230,120), 24)

# Pause-menu
pause_play_btn    = Button("Resume",  (0,0), (200, 60), C_GREEN,       (60,230,120))
pause_restart_btn = Button("Restart", (0,0), (200, 60), C_ACCENT,      C_ACCENT2)
pause_exit_btn    = Button("Exit",    (0,0), (200, 60), C_RED,         (230, 80, 80))
back_btn          = Button("← Back",  (0,0), (140, 48), C_RED,         (230, 80, 80), 22)


# ─── Scoreboard ───────────────────────────────────────────────────────────────
def draw_scoreboard(surf, brd):
    pygame.draw.rect(surf, (18,22,40), (0, 0, SCOREBOARD_WIDTH, sh))
    pygame.draw.line(surf, (50,60,90), (SCOREBOARD_WIDTH-2, 0), (SCOREBOARD_WIDTH-2, sh), 2)

    def label(txt, y, color=C_TEXT, fnt=font_tiny):
        t = fnt.render(txt, True, color)
        surf.blit(t, (SCOREBOARD_WIDTH//2 - t.get_width()//2, y))

    label("SCORE", 14, C_ACCENT2, font_small)
    pygame.draw.line(surf, (50,60,90), (8, 36), (SCOREBOARD_WIDTH-8, 36), 1)

    # White
    label("White", 46, C_WHITE_PIECE)
    wt = font_large.render(str(len(brd.white_team.pieces)), True, C_WHITE_PIECE)
    surf.blit(wt, (SCOREBOARD_WIDTH//2 - wt.get_width()//2, 68))

    pygame.draw.line(surf, (50,60,90), (8, 115), (SCOREBOARD_WIDTH-8, 115), 1)

    # Black
    label("Black", 125, C_SUBTEXT)
    bt = font_large.render(str(len(brd.black_team.pieces)), True, C_SUBTEXT)
    surf.blit(bt, (SCOREBOARD_WIDTH//2 - bt.get_width()//2, 148))

    pygame.draw.line(surf, (50,60,90), (8, 195), (SCOREBOARD_WIDTH-8, 195), 1)

    # Turn
    label("Turn", 205, C_SUBTEXT)
    turn_name = "WHITE" if brd.turn == brd.white_team else "BLACK"
    tc = C_WHITE_PIECE if brd.turn == brd.white_team else C_SUBTEXT
    tt = font_tiny.render(turn_name, True, tc)
    surf.blit(tt, (SCOREBOARD_WIDTH//2 - tt.get_width()//2, 228))

    # LAN role indicator
    if lan_role:
        pygame.draw.line(surf, (50,60,90), (8, 258), (SCOREBOARD_WIDTH-8, 258), 1)
        you_color = "WHITE" if lan_my_color == "white" else "BLACK"
        label("You:", 268, C_SUBTEXT)
        yc = C_WHITE_PIECE if lan_my_color == "white" else C_SUBTEXT
        yl = font_tiny.render(you_color, True, yc)
        surf.blit(yl, (SCOREBOARD_WIDTH//2 - yl.get_width()//2, 290))


# ─── Win overlay ──────────────────────────────────────────────────────────────
def draw_win_message(surf, brd):
    ov = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
    ov.fill((0, 0, 0, 170))
    surf.blit(ov, (0, 0))
    wt = font_huge.render(f"{brd.winner} WINS!", True, C_GOLD)
    surf.blit(wt, wt.get_rect(center=(sw//2, sh//2 - 50)))
    st = font_med.render("Press ESC to return to menu", True, C_TEXT)
    surf.blit(st, st.get_rect(center=(sw//2, sh//2 + 40)))


# ─── Blur helper ─────────────────────────────────────────────────────────────
def blur_surface(surface, amt):
    scale = 1.0 / amt
    small = pygame.transform.smoothscale(surface,
                (int(surface.get_width()*scale), int(surface.get_height()*scale)))
    return pygame.transform.smoothscale(small, surface.get_size())


# ─── Gradient background ─────────────────────────────────────────────────────
_bg_cache = None
def draw_gradient_bg(surf):
    global _bg_cache
    if _bg_cache is None:
        _bg_cache = pygame.Surface((sw, sh))
        for y in range(sh):
            t = y / sh
            r = int(10 + 20*t)
            g = int(15 + 10*t)
            b = int(30 + 30*t)
            pygame.draw.line(_bg_cache, (r, g, b), (0, y), (sw, y))
    surf.blit(_bg_cache, (0, 0))


# ─── Screen: Difficulty ───────────────────────────────────────────────────────
def draw_difficulty_screen(surf):
    draw_gradient_bg(surf)
    title = font_huge.render("Checkers", True, C_ACCENT2)
    surf.blit(title, title.get_rect(center=(sw//2, 80)))
    sub = font_med.render("Select Difficulty", True, C_SUBTEXT)
    surf.blit(sub, sub.get_rect(center=(sw//2, 140)))

    gw = BW*2 + GAP
    gh = BH*2 + GAP
    sx = sw//2 - gw//2
    sy = sh//2 - gh//2 + 20

    positions = {
        "Very Easy": (sx,        sy),
        "Easy":      (sx+BW+GAP, sy),
        "Hard":      (sx,        sy+BH+GAP),
        "Very Hard": (sx+BW+GAP, sy+BH+GAP),
    }
    for name, (x, y) in positions.items():
        diff_buttons[name].rect.topleft = (x, y)
        diff_buttons[name].draw(surf)


# ─── Screen: Play Mode ────────────────────────────────────────────────────────
def draw_play_mode_screen(surf):
    draw_gradient_bg(surf)
    title = font_large.render("Select Play Mode", True, C_ACCENT2)
    surf.blit(title, title.get_rect(center=(sw//2, 100)))

    total_w = PM_W*3 + GAP*2
    sx = sw//2 - total_w//2
    sy = sh//2 - PM_H//2

    play_vs_ai_btn.rect.topleft    = (sx,              sy)
    play_vs_human_btn.rect.topleft = (sx + PM_W + GAP, sy)
    play_vs_lan_btn.rect.topleft   = (sx + (PM_W+GAP)*2, sy)

    for btn in [play_vs_ai_btn, play_vs_human_btn, play_vs_lan_btn]:
        btn.draw(surf)

    back_btn.rect.topleft = (20, sh - 70)
    back_btn.draw(surf)


# ─── Screen: LAN Lobby ────────────────────────────────────────────────────────
def draw_lan_lobby(surf):
    draw_gradient_bg(surf)

    # Title
    title = font_large.render("LAN Multiplayer", True, C_ACCENT2)
    surf.blit(title, title.get_rect(center=(sw//2, 70)))

    panel_rect = pygame.Rect(sw//2 - 280, 120, 560, 340)
    draw_panel(surf, panel_rect)

    if lan_screen is None:
        # Pick Host or Join
        info = font_med.render("Choose your role:", True, C_TEXT)
        surf.blit(info, info.get_rect(center=(sw//2, 190)))

        lan_host_btn.rect.center = (sw//2 - 115, 270)
        lan_join_btn.rect.center = (sw//2 + 115, 270)
        lan_host_btn.draw(surf)
        lan_join_btn.draw(surf)

        tip = font_tiny.render("Both computers must be on the same network (Wi-Fi or LAN cable).", True, C_SUBTEXT)
        surf.blit(tip, tip.get_rect(center=(sw//2, 370)))

    elif lan_screen == "hosting":
        draw_lan_hosting(surf, panel_rect)

    elif lan_screen == "joining":
        draw_lan_joining(surf, panel_rect)

    elif lan_screen == "connected":
        draw_lan_connected(surf, panel_rect)

    lan_back_btn.rect.topleft = (20, sh - 70)
    lan_back_btn.draw(surf)


def draw_lan_hosting(surf, panel_rect):
    heading = font_med.render("Hosting Game", True, C_ACCENT)
    surf.blit(heading, heading.get_rect(center=(sw//2, panel_rect.top + 35)))

    if lan_error:
        err = font_small.render(lan_error, True, C_RED)
        surf.blit(err, err.get_rect(center=(sw//2, panel_rect.top + 80)))
    elif lan_status:
        lines = lan_status.split("\n")
        for i, line in enumerate(lines):
            t = font_small.render(line, True, C_TEXT)
            surf.blit(t, t.get_rect(center=(sw//2, panel_rect.top + 80 + i*30)))

        # Animated waiting dots
        dots = "." * (int(pygame.time.get_ticks() / 400) % 4)
        dt = font_med.render(f"Waiting{dots}", True, C_SUBTEXT)
        surf.blit(dt, dt.get_rect(center=(sw//2, panel_rect.top + 180)))


def draw_lan_joining(surf, panel_rect):
    heading = font_med.render("Join Game", True, C_ACCENT)
    surf.blit(heading, heading.get_rect(center=(sw//2, panel_rect.top + 35)))

    prompt = font_small.render("Enter host IP address:", True, C_SUBTEXT)
    surf.blit(prompt, prompt.get_rect(center=(sw//2, panel_rect.top + 85)))

    # IP text box
    box_rect = pygame.Rect(sw//2 - 160, panel_rect.top + 110, 320, 46)
    border_color = C_ACCENT if lan_input_active else C_SUBTEXT
    pygame.draw.rect(surf, (30, 38, 65), box_rect, border_radius=8)
    pygame.draw.rect(surf, border_color, box_rect, 2, border_radius=8)

    display_text = lan_input_text
    if lan_input_active and (pygame.time.get_ticks() // 500) % 2 == 0:
        display_text += "|"
    it = font_med.render(display_text, True, C_TEXT)
    surf.blit(it, (box_rect.x + 12, box_rect.y + 10))

    if lan_error:
        err = font_small.render(lan_error, True, C_RED)
        surf.blit(err, err.get_rect(center=(sw//2, panel_rect.top + 180)))
    elif lan_status:
        st = font_small.render(lan_status, True, C_TEXT)
        surf.blit(st, st.get_rect(center=(sw//2, panel_rect.top + 180)))

    if not lan_connecting:
        lan_connect_btn.rect.center = (sw//2, panel_rect.top + 230)
        lan_connect_btn.draw(surf)

    tip = font_tiny.render("Find host IP: run  ipconfig  in Command Prompt → IPv4 Address", True, C_SUBTEXT)
    surf.blit(tip, tip.get_rect(center=(sw//2, panel_rect.bottom - 22)))


def draw_lan_connected(surf, panel_rect):
    icon = font_huge.render("✓", True, C_GREEN)
    surf.blit(icon, icon.get_rect(center=(sw//2, panel_rect.top + 80)))
    msg = font_med.render("Connected! Game starting…", True, C_TEXT)
    surf.blit(msg, msg.get_rect(center=(sw//2, panel_rect.top + 170)))


# ─── LAN background workers ───────────────────────────────────────────────────
def _host_worker():
    global lan_status, lan_error, lan_screen, lan_connecting, lan_ready
    ok, info = net.host(status_callback=lambda s: _set_status(s))
    lan_connecting = False
    if ok:
        lan_screen = "connected"
        lan_ready  = True
    else:
        lan_error = f"Error: {info}"


def _join_worker(ip):
    global lan_status, lan_error, lan_screen, lan_connecting, lan_ready
    ok, info = net.join(ip)
    lan_connecting = False
    if ok:
        lan_screen = "connected"
        lan_ready  = True
    else:
        lan_error = f"Could not connect: {info}"
        lan_status = ""


def _set_status(s):
    global lan_status
    lan_status = s


# ─── Start game (local or LAN) ────────────────────────────────────────────────
def start_new_game(depth=2, ai=False, lan=False):
    global board, running
    board   = Board(depth, ai)
    running = True


# ─── LAN: apply a move received from the peer ─────────────────────────────────
def apply_network_move(brd, msg):
    """Apply a move/capture received from the remote peer."""
    from pygame.math import Vector2
    fx, fy = msg["from"]
    tx, ty = msg["to"]
    from_v  = Vector2(fx, fy)
    to_v    = Vector2(tx, ty)

    # Determine which team made the move (the opponent's team)
    if lan_my_color == "white":
        acting_team  = brd.black_team
        other_team   = brd.white_team
    else:
        acting_team  = brd.white_team
        other_team   = brd.black_team

    acting_team.check_possible_moves(other_team.pieces)

    if msg["type"] == "capture":
        for cap in acting_team.capture_moves:
            if cap[0].pos == from_v and cap[1] == to_v:
                other_team.pieces = acting_team.make_capture_move(cap, other_team.pieces)
                brd._play_sound('capture')
                break
    else:  # move
        for piece in acting_team.pieces:
            if piece.pos == from_v:
                acting_team.make_move([piece, to_v])
                brd._play_sound('move')
                brd._play_sound('move')
                break


def apply_network_moves_from_queue():
    if not (net and net.connected and board and not board.game_over):
        return
    while True:
        msg = net.poll()
        if msg is None:
            break
        if msg["type"] == "quit":
            messagebox.showinfo("Opponent left", "Your opponent disconnected.")
            board.game_over = True
            board.winner = "WHITE" if lan_my_color == "black" else "BLACK"
            break
        elif msg["type"] in ("move", "capture"):
            apply_network_move(board, msg)
            # Switch turn ONLY if the move was final (handles streaks)
            if msg.get("is_final", True):
                if board.turn == board.white_team:
                    board.turn = board.black_team
                else:
                    board.turn = board.white_team


# ─── Main game loop ───────────────────────────────────────────────────────────
_app_running = True
selected_difficulty = None
selected_ai_mode    = None

while _app_running:
    dt = clock.tick(FPS)
    
    raw_events = pygame.event.get()
    events = []
    
    win_w, win_h = display_surf.get_size()
    scaled_rect = get_scaled_rect(win_w, win_h, SCREEN_SIZE[0], SCREEN_SIZE[1])
    
    for event in raw_events:
        if event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            continue
        elif hasattr(event, 'pos') and scaled_rect.width > 0 and scaled_rect.height > 0:
            lx = (event.pos[0] - scaled_rect.x) * (SCREEN_SIZE[0] / scaled_rect.width)
            ly = (event.pos[1] - scaled_rect.y) * (SCREEN_SIZE[1] / scaled_rect.height)
            d = event.dict.copy()
            d['pos'] = (lx, ly)
            events.append(pygame.event.Event(event.type, d))
        else:
            events.append(event)
            
    for event in events:
        if event.type == pygame.QUIT:
            _app_running = False

        # ── Difficulty screen ──────────────────────────────────────────────
        if selected_difficulty is None:
            for name, btn in diff_buttons.items():
                if btn.is_clicked(event):
                    selected_difficulty = diff_map[name]

        # ── Play-mode screen ───────────────────────────────────────────────
        elif selected_ai_mode is None and board is None:
            if back_btn.is_clicked(event):
                selected_difficulty = None

            if play_vs_ai_btn.is_clicked(event):
                selected_ai_mode = "ai"
                start_new_game(selected_difficulty, ai=True)

            elif play_vs_human_btn.is_clicked(event):
                selected_ai_mode = "human"
                start_new_game(selected_difficulty, ai=False)

            elif play_vs_lan_btn.is_clicked(event):
                selected_ai_mode = "lan"
                # go to LAN lobby (don't create board yet)

        # ── LAN lobby ─────────────────────────────────────────────────────
        elif selected_ai_mode == "lan" and board is None:
            if lan_back_btn.is_clicked(event):
                # go back
                if lan_screen is None:
                    selected_ai_mode = None
                    net = None
                    lan_role = None
                else:
                    if net:
                        net.disconnect()
                    net = None
                    lan_role = None
                    lan_screen = None
                    lan_status = ""
                    lan_error  = ""
                    lan_input_text = ""
                    lan_connecting = False
                    lan_ready = False

            if lan_screen is None:
                if lan_host_btn.is_clicked(event):
                    lan_role   = "host"
                    lan_screen = "hosting"
                    lan_status = "Starting server…"
                    lan_error  = ""
                    net = Network()
                    lan_connecting = True
                    threading.Thread(target=_host_worker, daemon=True).start()

                elif lan_join_btn.is_clicked(event):
                    lan_role   = "client"
                    lan_screen = "joining"
                    lan_input_active = True
                    lan_error  = ""
                    net = Network()

            elif lan_screen == "joining":
                # Click on text box
                box_rect = pygame.Rect(sw//2 - 160, 230, 320, 46)
                if event.type == pygame.MOUSEBUTTONDOWN:
                    lan_input_active = box_rect.collidepoint(event.pos)

                if event.type == pygame.KEYDOWN and lan_input_active:
                    if event.key == pygame.K_BACKSPACE:
                        lan_input_text = lan_input_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        pass  # handled by connect button
                    elif len(lan_input_text) < 20:
                        if event.unicode in "0123456789.":
                            lan_input_text += event.unicode

                if lan_connect_btn.is_clicked(event) and not lan_connecting:
                    ip = lan_input_text.strip()
                    if ip:
                        lan_connecting = True
                        lan_status = f"Connecting to {ip}…"
                        lan_error  = ""
                        threading.Thread(target=_join_worker, args=(ip,), daemon=True).start()

            # Once connected, wait a tick then start the game
            if lan_ready:
                # Assign colours: host=white, client=black
                if lan_role == "host":
                    lan_my_color = "white"
                else:
                    lan_my_color = "black"

                start_new_game(selected_difficulty, ai=False, lan=True)
                lan_ready = False

        # ── In-game events ────────────────────────────────────────────────
        elif board is not None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if board.game_over:
                    board = None
                    selected_difficulty = None
                    selected_ai_mode    = None
                    if net:
                        net.disconnect()
                        net = None
                    lan_role = lan_screen = lan_my_color = None
                    lan_status = lan_error = lan_input_text = ""
                    lan_connecting = lan_ready = False
                else:
                    paused = not paused

            if paused and board is not None:
                if pause_play_btn.is_clicked(event):
                    paused = False
                elif pause_restart_btn.is_clicked(event):
                    if messagebox.askyesno("Restart", "Restart the game?"):
                        board = None
                        selected_difficulty = None
                        selected_ai_mode    = None
                        paused = False
                        if net:
                            net.disconnect()
                            net = None
                        lan_role = lan_screen = lan_my_color = None
                        lan_status = lan_error = lan_input_text = ""
                elif pause_exit_btn.is_clicked(event):
                    if messagebox.askyesno("Exit", "Quit the game?"):
                        _app_running = False

    # ── Check for incoming LAN messages (drain full queue each frame) ──────────
    apply_network_moves_from_queue()

    # ── Draw ──────────────────────────────────────────────────────────────────
    if not _app_running:
        break

    # ── Difficulty screen ──────────────────────────────────────────────────────
    if selected_difficulty is None:
        draw_difficulty_screen(screen)

    # ── Play-mode screen ───────────────────────────────────────────────────────
    elif selected_ai_mode is None and board is None:
        draw_play_mode_screen(screen)

    # ── LAN lobby ─────────────────────────────────────────────────────────────
    elif selected_ai_mode == "lan" and board is None:
        draw_lan_lobby(screen)

    # ── Paused overlay ────────────────────────────────────────────────────────
    elif paused and board is not None:
        board.draw(screen)
        screen.blit(blur_surface(screen.copy(), 15), (0, 0))

        cx, cy = sw//2, sh//2
        pause_play_btn.rect.center    = (cx, cy - 80)
        pause_restart_btn.rect.center = (cx, cy)
        pause_exit_btn.rect.center    = (cx, cy + 80)
        for b in [pause_play_btn, pause_restart_btn, pause_exit_btn]:
            b.draw(screen)

    # ── Active game ───────────────────────────────────────────────────────────
    else:
        if board is not None:
            draw_scoreboard(screen, board)
            board.draw(screen)

            if board.game_over:
                draw_win_message(screen, board)
            else:
                # --- LAN mode ---
                if selected_ai_mode == "lan" and net and net.connected:
                    my_turn = (
                        (lan_my_color == "white" and board.turn == board.white_team) or
                        (lan_my_color == "black" and board.turn == board.black_team)
                    )
                    if my_turn:
                        res = board.play_lan(lan_my_color, events)
                        if res and res[0]:  # made_move is True
                            _, move_data, is_final = res
                            mtype, frm, to = move_data
                            if mtype == "capture":
                                net.send_capture(frm, to, is_final=is_final)
                            else:
                                net.send_move(frm, to, is_final=is_final)
                    else:
                        # Show "waiting for opponent"
                        wt = font_small.render("Waiting for opponent…", True, C_SUBTEXT)
                        screen.blit(wt, wt.get_rect(center=(sw//2, sh - 20)))

                elif selected_ai_mode == "lan" and (not net or not net.connected):
                    # Lost connection mid-game
                    et = font_small.render("Connection lost!", True, C_RED)
                    screen.blit(et, et.get_rect(center=(sw//2, sh - 20)))

                # Keep-alive Pings
                if net and net.connected:
                    now = pygame.time.get_ticks()
                    if now - last_ping_time > 20000: # Every 20 seconds
                        net.send_ping()
                        last_ping_time = now
                else:
                    # Local game (AI or human)
                    board.play()

    pygame.display.update()

pygame.quit()
