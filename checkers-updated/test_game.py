import pygame
from board import Board
from constants import FPS, SCREEN_SIZE, SCOREBOARD_WIDTH

pygame.init()
screen = pygame.display.set_mode(SCREEN_SIZE)
clock = pygame.time.Clock()
pygame.display.set_caption("Checkers - Test")

board = Board(depth=2, ai=False)
running = True
count = 0

while running and count < 100:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    screen.fill((0, 0, 0))
    board.draw(screen)
    pygame.display.update()
    clock.tick(FPS)
    count += 1
    print(f"Frame: {count}")

pygame.quit()
print("Test complete!")
