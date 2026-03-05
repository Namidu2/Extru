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

            x = round(offset_x + i * SIZE)
            y = round(j * SIZE)
            w = round(offset_x + (i + 1) * SIZE) - x
            h = round((j + 1) * SIZE) - y
            pygame.draw.rect(screen, color, (x, y, w, h))
        index += 1
