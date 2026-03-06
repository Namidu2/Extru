from pygame.math import Vector2

from grid import COLS, ROWS
from piece import Piece


class Team:
    def __init__(self, color) -> None:
        self.color = color
        self.pieces = self.create_pieces()
        self.possible_moves = []
        self.capture_moves = []

    def create_pieces(self):
        pieces = []
        for i in range(1, ROWS + 1):
            for j in range(1, COLS + 1):
                if (i + j) % 2 != 0:

                    if i < 4 and self.color == "black":
                        pieces.append(Piece(False, Vector2(j, i)))
                    elif i > 5 and self.color == "white":
                        pieces.append(Piece(True, Vector2(j, i)))

        return pieces

    def draw_pieces(self, screen, offset_x=0, selected_piece=None):
        for piece in self.pieces:
            is_selected = piece == selected_piece
            piece.draw(screen, offset_x, is_selected)

        for piece in self.pieces:
            if self.color == "white" and piece.pos.y == 1:
                piece.is_king = True
            elif self.color == "black" and piece.pos.y == 8:
                piece.is_king = True

    def return_possible_moves(self, pos):
        if self.color == "white":
            right_move = Vector2(pos.x + 1, pos.y - 1)
            left_move = Vector2(pos.x - 1, pos.y - 1)
        else:
            right_move = Vector2(pos.x + 1, pos.y + 1)
            left_move = Vector2(pos.x - 1, pos.y + 1)

        return [left_move, right_move]

    def return_possible_king_moves(self, pos):
        if self.color == "white":
            f_right_move = Vector2(pos.x + 1, pos.y - 1)
            f_left_move = Vector2(pos.x - 1, pos.y - 1)
            b_right_move = Vector2(pos.x + 1, pos.y + 1)
            b_left_move = Vector2(pos.x - 1, pos.y + 1)
        else:
            f_right_move = Vector2(pos.x + 1, pos.y + 1)
            f_left_move = Vector2(pos.x - 1, pos.y + 1)
            b_right_move = Vector2(pos.x + 1, pos.y - 1)
            b_left_move = Vector2(pos.x - 1, pos.y - 1)

        return [[f_left_move, f_right_move], [b_left_move, b_right_move]]

    def check_occupied(self, pos, opponents_pieces):
        occupied = False

        for piece in self.pieces:
            if pos == piece.pos:
                occupied = True
                break

        if not occupied:
            for piece in opponents_pieces:
                if pos == piece.pos:
                    occupied = True
                    break

        return occupied

    def check_occupied_by_opponent(self, pos, opponents_pieces):
        occupied = False

        for piece in opponents_pieces:
            if pos == piece.pos:
                occupied = True
                break

        return occupied

    def check_in_bounds(self, pos):
        is_in_bounds = pos.x >= 1 and pos.x <= COLS and pos.y >= 1 and pos.y <= ROWS
        return is_in_bounds

    def make_move(self, move):
        valid = False
        for possible_move in self.possible_moves:
            if move[0].pos == possible_move[0].pos and move[1] == possible_move[1]:
                valid = True

        if valid:
            for piece in self.pieces:
                if piece.pos == move[0].pos:
                    piece.pos = move[1]
                    return True

        return False

    def make_capture_move(self, move, opponents_pieces):
        valid = False
        full_valid = False
        for cap in self.capture_moves:
            if move == cap:
                full_valid = True
            if move[0].pos == cap[0].pos and move[1] == cap[1]:
                valid = True
                break

        if valid:
            diff = move[0].pos - move[1]

            if self.color == "white":
                if diff == Vector2(2, -2):
                    x, y = 1, -1
                elif diff == Vector2(-2, -2):
                    x, y = -1, -1
                elif diff == Vector2(2, 2):
                    x, y = 1, 1
                else:
                    x, y = -1, 1
            else:
                if diff == Vector2(2, 2):
                    x, y = 1, 1
                elif diff == Vector2(-2, 2):
                    x, y = -1, 1
                elif diff == Vector2(2, -2):
                    x, y = 1, -1
                else:
                    x, y = -1, -1

            # Calculate the position of the opponent's piece being captured
            opponents_piece_pos = move[0].pos - Vector2(x, y)

            # Update the moving piece's position
            if full_valid:
                move[0].pos = move[1]

            # Remove the captured opponent's piece
            opponents_pieces = [
                piece for piece in opponents_pieces if piece.pos != opponents_piece_pos
            ]

        return opponents_pieces

    def check_captures(self, opponents_pieces):
        valid_moves = []

        for piece in self.pieces:
            # In Sri Lankan rules, all pieces can capture forward and backward
            if self.color == "white":
                # Forward for white is y-1, Backward is y+1
                f_left = self.check_occupied_by_opponent(
                    Vector2(piece.pos.x - 1, piece.pos.y - 1), opponents_pieces
                )
                f_right = self.check_occupied_by_opponent(
                    Vector2(piece.pos.x + 1, piece.pos.y - 1), opponents_pieces
                )
                b_left = self.check_occupied_by_opponent(
                    Vector2(piece.pos.x - 1, piece.pos.y + 1), opponents_pieces
                )
                b_right = self.check_occupied_by_opponent(
                    Vector2(piece.pos.x + 1, piece.pos.y + 1), opponents_pieces
                )
            else:
                # Forward for black is y+1, Backward is y-1
                f_left = self.check_occupied_by_opponent(
                    Vector2(piece.pos.x - 1, piece.pos.y + 1), opponents_pieces
                )
                f_right = self.check_occupied_by_opponent(
                    Vector2(piece.pos.x + 1, piece.pos.y + 1), opponents_pieces
                )
                b_left = self.check_occupied_by_opponent(
                    Vector2(piece.pos.x - 1, piece.pos.y - 1), opponents_pieces
                )
                b_right = self.check_occupied_by_opponent(
                    Vector2(piece.pos.x + 1, piece.pos.y - 1), opponents_pieces
                )

            dirs = [f_left, f_right, b_left, b_right]

            if dirs[0]:
                dirs[0] = "f_left"
            if dirs[1]:
                dirs[1] = "f_right"
            if dirs[2]:
                dirs[2] = "b_left"
            if dirs[3]:
                dirs[3] = "b_right"

            valid_dirs = []
            for dir in dirs:
                if dir != False:
                    valid_dirs.append(dir)

            for dir in valid_dirs:
                if dir == "f_left":
                    if self.color == "white":
                        pos = piece.pos + Vector2(-2, -2)
                    else:
                        pos = piece.pos + Vector2(-2, 2)
                elif dir == "f_right":
                    if self.color == "white":
                        pos = piece.pos + Vector2(2, -2)
                    else:
                        pos = piece.pos + Vector2(2, 2)
                elif dir == "b_left":
                    if self.color == "white":
                        pos = piece.pos + Vector2(-2, 2)
                    else:
                        pos = piece.pos + Vector2(-2, -2)
                elif dir == "b_right":
                    if self.color == "white":
                        pos = piece.pos + Vector2(2, 2)
                    else:
                        pos = piece.pos + Vector2(2, -2)
                else:
                    pos = None

                in_bounds = self.check_in_bounds(pos)
                if in_bounds:
                    occupied = self.check_occupied(pos, opponents_pieces)
                    if not occupied:
                        valid_moves.append([piece, pos])

        self.capture_moves = valid_moves

    def check_possible_moves(self, opponents_pieces):
        self.possible_moves = []

        for piece in self.pieces:
            if not piece.is_king:
                # Get the left and right moves positions
                right_move, left_move = self.return_possible_moves(piece.pos)

                # Adding the piece that moves into the left and right moves
                right_move = [piece, right_move]
                left_move = [piece, left_move]

                right_pos = right_move[1]
                left_pos = left_move[1]

                # Check if the right move is in bounds of the board
                in_bounds = self.check_in_bounds(right_pos)
                if in_bounds:
                    # Check if the right move is occupied by a different piece
                    occupied = self.check_occupied(right_pos, opponents_pieces)
                    if not occupied:
                        self.possible_moves.append(right_move)

                # Check if the left move is in bounds of the board
                in_bounds = self.check_in_bounds(left_pos)
                if in_bounds:
                    # Check if the left move is occupied by a different piece
                    occupied = self.check_occupied(left_pos, opponents_pieces)
                    if not occupied:
                        self.possible_moves.append(left_move)
            else:
                king_moves = self.return_possible_king_moves(piece.pos)
                for move in king_moves:
                    for i in move:
                        in_bounds = self.check_in_bounds(i)
                        if in_bounds:
                            occupied = self.check_occupied(i, opponents_pieces)
                            if not occupied:
                                self.possible_moves.append([piece, i])

        self.check_captures(opponents_pieces)

    def check_win(self, opponent_team):
        opponent_team.check_possible_moves(self.pieces)
        if (
            len(opponent_team.pieces) == 0
            or len(opponent_team.possible_moves) + len(opponent_team.capture_moves) == 0
        ):
            return True
        return False
