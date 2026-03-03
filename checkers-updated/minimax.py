from copy import deepcopy


def minimax_with_pruning(position, depth, alpha, beta, maximizing):
    win = position.check_for_win()

    best_move = None

    if win == -1:
        return -100, None
    elif win == 1:
        return 100, None

    if depth == 0:
        return position.return_heuristic(), None

    if maximizing:
        position.white_team.check_possible_moves(position.black_team.pieces)
        max_eval = -1000
        if len(position.white_team.capture_moves) > 0:
            moves = position.white_team.capture_moves
        else:
            moves = position.white_team.possible_moves

        for move in moves:
            position_copy = deepcopy(position)

            if move in position.white_team.capture_moves:
                position_copy.make_capture(move)
            else:
                position_copy.make_move(move)

            eval, _ = minimax_with_pruning(position_copy, depth - 1, alpha, beta, False)

            if eval > max_eval:
                max_eval = eval
                best_move = move

            alpha = max(alpha, eval)
            if beta <= alpha:
                break

        return max_eval, best_move

    else:
        position.black_team.check_possible_moves(position.white_team.pieces)
        min_eval = 1000

        if len(position.black_team.capture_moves) > 0:
            moves = position.black_team.capture_moves
        else:
            moves = position.black_team.possible_moves

        for move in moves:
            position_copy = deepcopy(position)

            if move in position.black_team.capture_moves:
                position_copy.make_capture(move)
            else:
                position_copy.make_move(move)

            eval, _ = minimax_with_pruning(position_copy, depth - 1, alpha, beta, True)

            if eval < min_eval:
                min_eval = eval
                best_move = move

            beta = min(beta, eval)
            if beta <= alpha:
                break

        return min_eval, best_move


def minimax(position, depth, maximizing):
    win = position.check_for_win()

    best_move = None

    if win == -1:
        return -100, None
    elif win == 1:
        return 100, None

    if depth == 0:
        return position.return_heuristic(), None

    if maximizing:
        position.white_team.check_possible_moves(position.black_team.pieces)
        max_eval = -1000
        if len(position.white_team.capture_moves) > 0:
            moves = position.white_team.capture_moves
        else:
            moves = position.white_team.possible_moves

        for move in moves:
            position_copy = deepcopy(position)

            if move in position.white_team.capture_moves:
                position_copy.make_capture(move)
            else:
                position_copy.make_move(move)

            eval, _ = minimax(position_copy, depth - 1, False)

            if eval > max_eval:
                max_eval = eval
                best_move = move

        return max_eval, best_move

    else:
        position.black_team.check_possible_moves(position.white_team.pieces)
        min_eval = 1000

        if len(position.black_team.capture_moves) > 0:
            moves = position.black_team.capture_moves
        else:
            moves = position.black_team.possible_moves

        for move in moves:
            position_copy = deepcopy(position)

            if move in position.black_team.capture_moves:
                position_copy.make_capture(move)
            else:
                position_copy.make_move(move)

            eval, _ = minimax(position_copy, depth - 1, True)

            if eval < min_eval:
                min_eval = eval
                best_move = move

        return min_eval, best_move
