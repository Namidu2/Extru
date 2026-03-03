import pygame

from constants import GRAY
from grid import SIZE


class Piece:
    def __init__(self, team, pos):  # team is true for white and false for black
        self.team = team
        self.color = self.get_color()
        self.pos = pos
        self.is_king = False

    def get_color(self):
        if self.team == True:
            return "white"
        else:
            return GRAY

    def draw(self, screen, offset_x=0, is_selected=False):
        opp_color = "black" if self.color == "white" else "white"
        
        center = ((self.pos.x * SIZE) - SIZE // 2 + offset_x, (self.pos.y * SIZE) - SIZE // 2)

        pygame.draw.circle(
            screen,
            self.color,
            center,
            SIZE // 3,
        )
        if not self.is_king:

            pygame.draw.circle(
                screen,
                opp_color,
                center,
                SIZE // 3,
                3,
            )
        else:
            pygame.draw.circle(
                screen,
                "gold",
                center,
                SIZE // 3,
                3,
            )
        
        # Draw highlight if selected
        if is_selected:
            pygame.draw.circle(
                screen,
                "yellow",
                center,
                SIZE // 3 + 5,
                4,
            )
