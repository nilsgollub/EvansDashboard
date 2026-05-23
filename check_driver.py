import os

import pygame

drivers = ["x11", "kmsdrm", "directfb", "fbcon", "dummy", "offscreen", "wayland"]
valid = []
for d in drivers:
    os.environ["SDL_VIDEODRIVER"] = d
    try:
        pygame.display.init()
        valid.append(d)
        pygame.display.quit()
    except Exception:
        pass

print("AVAILABLE DRIVERS:", valid)
