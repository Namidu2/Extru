import pygame
import os
import sys
from pygame.math import Vector2

from grid import SIZE, draw_grid
from minimax import minimax, minimax_with_pruning
from team import Team
from constants import SCOREBOARD_WIDTH


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class Board:
    def __init__(self, depth=2, ai=False):
        self.white_team = Team("white")
        self.black_team = Team("black")
        self.turn = self.white_team
        self.selected_piece = None
        self.selected_location = None
        self.depth = depth
        self.ai = ai
        self.prune = False
        self.game_over = False
        self.winner = None
        
        # Initialize sound
        self.move_sound = None
        self.capture_sound = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            move_path = resource_path(os.path.join('assets', 'move.wav'))
            capture_path = resource_path(os.path.join('assets', 'capture.wav'))
            
            if os.path.exists(move_path):
                self.move_sound = pygame.mixer.Sound(move_path)
            if os.path.exists(capture_path):
                self.capture_sound = pygame.mixer.Sound(capture_path)
        except Exception as e:
            print(f"Could not initialize sounds: {e}")

    def __getstate__(self):
        """Prepare state for pickling/deepcopying by removing unpicklable sound objects."""
        state = self.__dict__.copy()
        state['move_sound'] = None
        state['capture_sound'] = None
        return state

    def __setstate__(self, state):
        """Restore state after pickling/deepcopying."""
        self.__dict__.update(state)

    def _play_sound(self, sound_type):
        if sound_type == 'move' and self.move_sound:
            self.move_sound.play()
        elif sound_type == 'capture' and self.capture_sound:
            self.capture_sound.play()

    def make_move(self, move):
        if move[0].color == "white":
            self.white_team.make_move(move)
        else:
            self.black_team.make_move(move)

    def make_capture(self, capture):
        if capture[0].color == "white":
            self.black_team.pieces = self.white_team.make_capture_move(
                capture, self.black_team.pieces
            )
        else:
            self.white_team.pieces = self.black_team.make_capture_move(
                capture, self.white_team.pieces
            )

    def return_heuristic(self):
        white_pieces = len(self.white_team.pieces)
        black_pieces = len(self.black_team.pieces)

        if white_pieces > black_pieces:
            return white_pieces - black_pieces
        elif white_pieces < black_pieces:
            return (black_pieces - white_pieces) * -1
        else:
            return 0

    def check_for_win(self):
        white_win = self.white_team.check_win(self.black_team)
        black_win = self.black_team.check_win(self.white_team)

        if black_win:
            return -1
        elif white_win:
            return 1
        else:
            return 0

    def play(self):
        win = self.check_for_win()
        if win == -1:
            self.game_over = True
            self.winner = "BLACK"
        elif win == 1:
            self.game_over = True
            self.winner = "WHITE"

        if self.turn == self.white_team:
            switch = self.white_to_play()
        else:
            if self.ai:
                pygame.display.update()
                switch = self.black_to_play_ai()
            else:
                switch = self.black_to_play()

        if switch:
            if self.turn == self.white_team:
                self.turn = self.black_team
            else:
                self.turn = self.white_team

    def play_lan(self, my_color, events=None):
        """Handle input for the local player in LAN mode.
        Returns (made_move, move_data) where move_data is
        (type_str, from_pos, to_pos) or None.
        events: list of pygame events from the main loop (required for responsive input).
        """
        win = self.check_for_win()
        if win == -1:
            self.game_over = True
            self.winner = "BLACK"
            return False, None
        elif win == 1:
            self.game_over = True
            self.winner = "WHITE"
            return False, None

        if events is None:
            events = []

        if my_color == "white":
            result = self._white_to_play_lan(events)
        else:
            result = self._black_to_play_lan(events)

        if result and result[0]:  # made_move is True
            made_move, move_data = result
            # Switch turn
            if self.turn == self.white_team:
                self.turn = self.black_team
            else:
                self.turn = self.white_team
            return True, move_data
        return False, None

    def _white_to_play_lan(self, events):
        """White player's LAN turn. Returns (True, (type, from, to)) or (False, None)."""
        self.white_team.check_possible_moves(self.black_team.pieces)
        made_move = False

        for event in events:
            if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
                continue
            raw = event.pos
            click_pos = Vector2(((raw[0] - SCOREBOARD_WIDTH) // SIZE) + 1, (raw[1] // SIZE) + 1)

            if self.selected_piece is None:
                self.selected_piece = click_pos
            elif (self.selected_piece is not None
                  and click_pos != self.selected_piece
                  and self.selected_location is None):
                self.selected_location = click_pos
            elif self.selected_location is not None:
                can_capture = len(self.white_team.capture_moves) > 0
                found_piece = False
                for piece in self.white_team.pieces:
                    if piece.pos == self.selected_piece:
                        self.selected_piece = piece
                        found_piece = True
                        break
                move_data = None
                if found_piece:
                    if can_capture:
                        for captures in self.white_team.capture_moves:
                            if captures[0] == self.selected_piece and captures[1] == self.selected_location:
                                from_pos = self.selected_piece.pos
                                to_pos   = self.selected_location
                                self.black_team.pieces = self.white_team.make_capture_move(captures, self.black_team.pieces)
                                self._play_sound('capture')
                                self.white_team.check_possible_moves(self.black_team.pieces)
                                if len(self.white_team.capture_moves) < 1:
                                    made_move = True
                                    move_data = ('capture', from_pos, to_pos)
                                else:
                                    cap_streak = any(c[0] == self.selected_piece for c in self.white_team.capture_moves)
                                    if not cap_streak:
                                        made_move = True
                                        move_data = ('capture', from_pos, to_pos)
                                    else:
                                        # Do not set made_move to True; allow the player to continue capturing with the SAME piece.
                                        # We need to send the partial move over the network though so the opponent sees it.
                                        # But the framework currently only sends ONE move per turn transition.
                                        # Let's see if we can just wait for the turn to actually end.
                                        # Actually to keep it simple, we don't return True until the streak ends.
                                        pass
                                break
                    else:
                        from_pos = self.selected_piece.pos
                        to_pos   = self.selected_location
                        made_move = self.white_team.make_move([self.selected_piece, self.selected_location])
                        if made_move:
                            self._play_sound('move')
                            move_data = ('move', from_pos, to_pos)

                if not made_move and "cap_streak" in locals() and cap_streak:
                    # If we are in the middle of a capture streak, we do NOT clear selected_piece!
                    self.selected_location = None
                else:
                    self.selected_piece = None
                    self.selected_location = None
                    
                if made_move:
                    return True, move_data
        return False, None

    def _black_to_play_lan(self, events):
        """Black player's LAN turn. Returns (True, (type, from, to)) or (False, None)."""
        self.black_team.check_possible_moves(self.white_team.pieces)
        made_move = False

        for event in events:
            if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
                continue
            raw = event.pos
            click_pos = Vector2(((raw[0] - SCOREBOARD_WIDTH) // SIZE) + 1, (raw[1] // SIZE) + 1)

            if self.selected_piece is None:
                self.selected_piece = click_pos
            elif (self.selected_piece is not None
                  and click_pos != self.selected_piece
                  and self.selected_location is None):
                self.selected_location = click_pos
            elif self.selected_location is not None:
                can_capture = len(self.black_team.capture_moves) > 0
                found_piece = False
                for piece in self.black_team.pieces:
                    if piece.pos == self.selected_piece:
                        self.selected_piece = piece
                        found_piece = True
                        break
                move_data = None
                if found_piece:
                    if can_capture:
                        for captures in self.black_team.capture_moves:
                            if captures[0] == self.selected_piece and captures[1] == self.selected_location:
                                from_pos = self.selected_piece.pos
                                to_pos   = self.selected_location
                                self.white_team.pieces = self.black_team.make_capture_move(captures, self.white_team.pieces)
                                self._play_sound('capture')
                                self.black_team.check_possible_moves(self.white_team.pieces)
                                if len(self.black_team.capture_moves) < 1:
                                    made_move = True
                                    move_data = ('capture', from_pos, to_pos)
                                else:
                                    cap_streak = any(c[0] == self.selected_piece for c in self.black_team.capture_moves)
                                    if not cap_streak:
                                        made_move = True
                                        move_data = ('capture', from_pos, to_pos)
                                    else:
                                        pass
                                break
                    else:
                        from_pos = self.selected_piece.pos
                        to_pos   = self.selected_location
                        made_move = self.black_team.make_move([self.selected_piece, self.selected_location])
                        if made_move:
                            self._play_sound('move')
                            move_data = ('move', from_pos, to_pos)

                if not made_move and "cap_streak" in locals() and cap_streak:
                    # If we are in the middle of a capture streak, we do NOT clear selected_piece!
                    self.selected_location = None
                else:
                    self.selected_piece = None
                    self.selected_location = None
                    
                if made_move:
                    return True, move_data
        return False, None

    def draw(self, screen):
        draw_grid(screen, SCOREBOARD_WIDTH)
        
        # Find the selected piece object for highlighting
        selected_piece_obj = None
        if self.selected_piece is not None:
            if hasattr(self.selected_piece, 'pos'):  # It's already a piece object
                selected_piece_obj = self.selected_piece
            else:  # It's a position (Vector2)
                # Find the piece at this position
                for piece in self.white_team.pieces + self.black_team.pieces:
                    if piece.pos == self.selected_piece:
                        selected_piece_obj = piece
                        break
        
        self.white_team.draw_pieces(screen, SCOREBOARD_WIDTH, selected_piece_obj)
        self.black_team.draw_pieces(screen, SCOREBOARD_WIDTH, selected_piece_obj)

    def white_to_play(self):
        self.white_team.check_possible_moves(self.black_team.pieces)

        made_move = False
        clicked = False
        click_pos = None
        if pygame.mouse.get_pressed()[0]:
            click_pos = pygame.mouse.get_pos()
            click_pos = Vector2(((click_pos[0] - SCOREBOARD_WIDTH) // SIZE) + 1, (click_pos[1] // SIZE) + 1)
            clicked = True

        if clicked:
            if (
                self.selected_piece is None
            ):  # If we dont have a selected piece assign the clicked position to the selected piece

                self.selected_piece = click_pos

            elif (
                self.selected_piece
                is not None  # If we have a selected piece then assign the clicked position to the selected location
                and click_pos != self.selected_piece
                and self.selected_location is None
            ):
                self.selected_location = click_pos

            elif self.selected_location is not None:

                ended_capture_streek = False
                can_capture = len(self.white_team.capture_moves) > 0

                found_piece = False
                for piece in self.white_team.pieces:
                    if piece.pos == self.selected_piece:
                        self.selected_piece = piece
                        found_piece = True
                        break
                if found_piece:

                    if can_capture:
                        for captures in self.white_team.capture_moves:
                            if (
                                captures[0] == self.selected_piece
                                and captures[1] == self.selected_location
                            ):
                                # If the player is making a capture move
                                black_pieces = self.white_team.make_capture_move(
                                    captures, self.black_team.pieces
                                )
                                self.black_team.pieces = black_pieces
                                self._play_sound('capture')
                                
                                self.white_team.check_possible_moves(
                                    self.black_team.pieces
                                )
                                if len(self.white_team.capture_moves) < 1:
                                    made_move = True
                                    ended_capture_streek = True
                                else:
                                    cap_streak = False
                                    for capture in self.white_team.capture_moves:
                                        if capture[0] == self.selected_piece:
                                            made_move = False
                                            cap_streak = True
                                            break
                                    if not cap_streak:
                                        made_move = True

                    elif not can_capture:
                        made_move = self.white_team.make_move(
                            [self.selected_piece, self.selected_location],
                        )
                        if made_move:
                            self._play_sound('move')
                    elif ended_capture_streek:
                        made_move = True

                    else:
                        made_move = False

                if not made_move and "cap_streak" in locals() and cap_streak:
                    self.selected_location = None
                else:
                    self.selected_piece = None
                    self.selected_location = None

                if made_move:
                    return made_move


    def black_to_play(self):
        self.black_team.check_possible_moves(self.white_team.pieces)

        made_move = False
        clicked = False
        click_pos = None
        if pygame.mouse.get_pressed()[0]:
            click_pos = pygame.mouse.get_pos()
            click_pos = Vector2(((click_pos[0] - SCOREBOARD_WIDTH) // SIZE) + 1, (click_pos[1] // SIZE) + 1)
            clicked = True

        if clicked:
            if (
                self.selected_piece is None
            ):  # If we dont have a selected piece assign the clicked position to the selected piece

                self.selected_piece = click_pos

            elif (
                self.selected_piece
                is not None  # If we have a selected piece then assign the clicked position to the selected location
                and click_pos != self.selected_piece
                and self.selected_location is None
            ):
                self.selected_location = click_pos

            elif self.selected_location is not None:

                ended_capture_streek = False
                can_capture = len(self.black_team.capture_moves) > 0

                found_piece = False
                for piece in self.black_team.pieces:
                    if piece.pos == self.selected_piece:
                        self.selected_piece = piece
                        found_piece = True
                        break
                if found_piece:

                    if can_capture:
                        for captures in self.black_team.capture_moves:
                            if (
                                captures[0] == self.selected_piece
                                and captures[1] == self.selected_location
                            ):
                                # If the player is making a capture move
                                white_pieces = self.black_team.make_capture_move(
                                    captures, self.white_team.pieces
                                )
                                self.white_team.pieces = white_pieces
                                self._play_sound('capture')
                                
                                self.black_team.check_possible_moves(
                                    self.white_team.pieces
                                )
                                if len(self.black_team.capture_moves) < 1:
                                    made_move = True
                                    ended_capture_streek = True
                                else:
                                    cap_streak = False
                                    for capture in self.black_team.capture_moves:
                                        if capture[0] == self.selected_piece:
                                            made_move = False
                                            cap_streak = True
                                            break

                                    if not cap_streak:
                                        made_move = True

                    elif not can_capture:
                        made_move = self.black_team.make_move(
                            [self.selected_piece, self.selected_location],
                        )
                        if made_move:
                            self._play_sound('move')
                    elif ended_capture_streek:
                        made_move = True

                    else:
                        made_move = False

                else:  # If the player did not select a piece
                    made_move = False

                if not made_move and "cap_streak" in locals() and cap_streak:
                    self.selected_location = None
                else:
                    self.selected_piece = None
                    self.selected_location = None

                if made_move:
                    return made_move

    def black_to_play_ai(self):
        if self.selected_piece is None:
            if self.prune:
                move = minimax_with_pruning(self, self.depth, -1000, 1000, False)
            else:
                move = minimax(self, self.depth, False)
            self.selected_piece = move[1][0]
            self.selected_location = move[1][1]

            for piece in self.black_team.pieces:
                if piece.pos == self.selected_piece.pos:
                    self.selected_piece = piece.pos
                    break
        else:
            self.black_team.check_possible_moves(self.white_team.pieces)
            for cap in self.black_team.capture_moves:
                if cap[0] == self.selected_piece:
                    self.selected_location = cap[1]
                    break
            self.selected_piece = self.selected_piece.pos

        made_move = False
        ended_capture_streek = False
        can_capture = len(self.black_team.capture_moves) > 0
        found_piece = False

        for piece in self.black_team.pieces:
            if piece.pos == self.selected_piece:
                self.selected_piece = piece
                found_piece = True
                break

        if found_piece:

            self.black_team.check_possible_moves(self.white_team.pieces)

            if can_capture:
                for captures in self.black_team.capture_moves:
                    if (
                        captures[0] == self.selected_piece
                        and captures[1] == self.selected_location
                    ):
                        # If the player is making a capture move
                        white_pieces = self.black_team.make_capture_move(
                            captures, self.white_team.pieces
                        )
                        self.white_team.pieces = white_pieces
                        self._play_sound('capture')

                        self.black_team.check_possible_moves(self.white_team.pieces)
                        if len(self.black_team.capture_moves) < 1:
                            made_move = True
                            ended_capture_streek = True
                        else:
                            cap_streak = False
                            for capture in self.black_team.capture_moves:
                                if capture[0] == self.selected_piece:
                                    made_move = False
                                    cap_streak = True
                                    break

                            if not cap_streak:
                                made_move = True

            elif not can_capture:
                made_move = self.black_team.make_move(
                    [self.selected_piece, self.selected_location],
                )
                if made_move:
                    self._play_sound('move')
            elif ended_capture_streek:
                made_move = True

            else:
                made_move = False

        else:  # If the player did not select a piece
            made_move = False

        if not made_move and "cap_streak" in locals() and cap_streak:
            self.selected_location = None
        else:
            self.selected_piece = None
            self.selected_location = None

        if made_move:
            return made_move
