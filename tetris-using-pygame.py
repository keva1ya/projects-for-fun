import pygame #type: ignore
import random

pygame.init()

width, height = 300, 600
blocksize = 30
columns, rows = width // blocksize, height // blocksize

black = (0, 0, 0)
gray = (128, 128, 128)
white = (255, 255, 255)
colors = [
    (0, 255, 255),
    (255, 105, 180),
    (50, 205, 50),
    (255, 250, 205)
]
shapes = [
    [[1, 1, 1, 1]],
    [[1, 1], [1, 1]],
    [[0, 1, 0], [1, 1, 1]],
    [[1, 0, 0], [1, 1, 1]],
    [[0, 0, 1], [1, 1, 1]],
    [[1, 1, 0], [0, 1, 1]],
    [[0, 1, 1], [1, 1, 0]],
]
class blockgame:
    def __init__(self):
        self.grid = self.make_grid()
        self.score = 0
        self.win = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Tetris")

    def make_grid(self):
        return [[black for _ in range(columns)] for _ in range(rows)]

    def draw(self, piece):
        self.win.fill(black)
        for y in range(rows):
            for x in range(columns):
                pygame.draw.rect(self.win, self.grid[y][x], (x*blocksize, y*blocksize, blocksize, blocksize), 0)
                pygame.draw.rect(self.win, gray, (x*blocksize, y*blocksize, blocksize, blocksize), 1)
        for y, row in enumerate(piece.shape):
            for x, val in enumerate(row):
                if val:
                    pygame.draw.rect(self.win, piece.color, ((piece.x + x) * blocksize, (piece.y + y) * blocksize, blocksize, blocksize), 0)
        font = pygame.font.SysFont("Arial", 24)
        text = font.render(f"Score: {self.score}", True, white)
        self.win.blit(text, (10, 10))
        pygame.display.update()



class piece:
    def __init__(self):
        self.shape = random.choice(shapes)
        self.color = random.choice(colors)
        self.x = columns // 2 - len(self.shape[0]) // 2
        self.y = 0
    def rotate(self):
        self.shape = [list(r) for r in zip(*self.shape[::-1])]

class tetris(blockgame):
    def __init__(self):
        super().__init__()
        self.current = piece()
        self.clock = pygame.time.Clock()
        self.time = 0
        self.running = True

    def is_valid(self, p, dx=0, dy=0):
        for y, row in enumerate(p.shape):
            for x, val in enumerate(row):
                if val:
                    nx = p.x + x + dx
                    ny = p.y + y + dy
                    if nx < 0 or nx >= columns or ny >= rows:
                        return False
                    if ny >= 0 and self.grid[ny][nx] != black:
                        return False
        return True

    def place(self, p):
        for y, row in enumerate(p.shape):
            for x, val in enumerate(row):
                if val:
                    self.grid[p.y + y][p.x + x] = p.color

    def clear(self):
        new = [row for row in self.grid if any(c == black for c in row)]
        cleared = rows - len(new)
        for _ in range(cleared):
            new.insert(0, [black for _ in range(columns)])
        self.grid = new
        self.score += cleared * 10

    def start(self):
        print("Welcome to Tetris!")
        print("Controls:")
        print("←  Move Left")
        print("→  Move Right")
        print("↓  Move Down Faster")
        print("↑  Rotate Block")
        print("ESC Quit Game")
        print("Game starting...")

        try:
            while self.running:
                self.time += self.clock.get_rawtime()
                self.clock.tick(60)

                if self.time > 100:
                    if self.is_valid(self.current, dy=1):
                        self.current.y += 1
                    else:
                        self.place(self.current)
                        self.clear()
                        self.current = piece()
                        if not self.is_valid(self.current):
                            print("Game over!")
                            self.running = False
                    self.time = 0

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.running = False
                        elif event.key == pygame.K_LEFT and self.is_valid(self.current, dx=-1):
                            self.current.x -= 1
                        elif event.key == pygame.K_RIGHT and self.is_valid(self.current, dx=1):
                            self.current.x += 1
                        elif event.key == pygame.K_DOWN and self.is_valid(self.current, dy=1):
                            self.current.y += 1
                        elif event.key == pygame.K_UP:
                            self.current.rotate()
                            if not self.is_valid(self.current):
                                for _ in range(3):
                                    self.current.rotate()

                self.draw(self.current)

        except Exception as e:
            print("Something went wrong:", e)
        finally:
            pygame.quit()
            
t = tetris()
t.start()
