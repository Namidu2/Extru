import pygame

ROWS = 8
COLS = 8
SIZE = 100


def draw_grid(screen, offset_x=0):
    index = 0
    for i in range(COLS):
        for j in range(ROWS):
            index += 1

            color = (238, 238, 210)
            if index % 2 == 0:
                color = (186, 202, 68)

            pygame.draw.rect(screen, color, (offset_x + i * SIZE, j * SIZE, SIZE, SIZE))
        index += 1
