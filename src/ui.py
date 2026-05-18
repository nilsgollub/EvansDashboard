import pygame

class DashboardUI:
    def __init__(self, width=480, height=320, fullscreen=False):
        pygame.init()
        self.width = width
        self.height = height
        
        flags = pygame.FULLSCREEN if fullscreen else 0
        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        pygame.display.set_caption("Evans Co-Pilot Dashboard")
        
        # Initialisiere Fonts
        # SysFont versucht eine passende Systemschriftart zu finden.
        self.font_speed = pygame.font.SysFont('arial', 140, bold=True)
        self.font_limit = pygame.font.SysFont('arial', 80, bold=True)
        self.font_info = pygame.font.SysFont('arial', 24)
        
        # Farben (RGB)
        self.COLOR_BG = (15, 15, 20)      # Sehr dunkles Blau-Grau (besserer Kontrast als pures Schwarz)
        self.COLOR_WHITE = (245, 245, 245)
        self.COLOR_RED = (220, 40, 40)    # Verkehrsrot
        self.COLOR_GREEN = (40, 220, 40)
        self.COLOR_GRAY = (150, 150, 150)
        self.COLOR_YELLOW = (240, 200, 40)
        
    def draw_speed_limit_sign(self, x, y, radius, limit):
        # Weißer Kreis
        pygame.draw.circle(self.screen, self.COLOR_WHITE, (x, y), radius)
        # Roter Rand
        pygame.draw.circle(self.screen, self.COLOR_RED, (x, y), radius, width=int(radius*0.2))
        
        # Limit Text
        if limit is not None:
            text_surface = self.font_limit.render(str(limit), True, (0, 0, 0))
        else:
            text_surface = self.font_limit.render("--", True, (0, 0, 0))
            
        text_rect = text_surface.get_rect(center=(x, y))
        self.screen.blit(text_surface, text_rect)
        
    def render(self, current_speed, speed_limit, sats, road_type, altitude, heading):
        # 1. Hintergrund löschen
        self.screen.fill(self.COLOR_BG)
        
        # 2. Tempolimit Schild (oben links)
        sign_radius = 80
        sign_x = sign_radius + 20
        sign_y = sign_radius + 20
        self.draw_speed_limit_sign(sign_x, sign_y, sign_radius, speed_limit)
        
        # 3. Aktuelle Geschwindigkeit (rechts groß)
        speed_color = self.COLOR_WHITE
        if speed_limit is not None:
            if current_speed > speed_limit + 3:
                speed_color = self.COLOR_RED
            elif current_speed <= speed_limit:
                speed_color = self.COLOR_GREEN
            else:
                speed_color = self.COLOR_YELLOW # Toleranzbereich (1-3 km/h drüber)
                
        speed_text = f"{int(current_speed)}"
        speed_surface = self.font_speed.render(speed_text, True, speed_color)
        speed_rect = speed_surface.get_rect(midright=(self.width - 40, self.height // 2))
        self.screen.blit(speed_surface, speed_rect)
        
        # "km/h" Anzeige direkt unter/neben der Geschwindigkeit
        kmh_surface = self.font_info.render("km/h", True, self.COLOR_GRAY)
        kmh_rect = kmh_surface.get_rect(topright=(self.width - 40, speed_rect.bottom - 20))
        self.screen.blit(kmh_surface, kmh_rect)
        
        # 4. Zusatzinfos (unten links und mitte)
        info_y_start = self.height - 90
        
        # Satelliten mit Farbe (Grün = gut, Rot = schlecht)
        sat_color = self.COLOR_GREEN if sats >= 4 else self.COLOR_RED
        sats_surface = self.font_info.render(f"Sats: {sats}", True, sat_color)
        self.screen.blit(sats_surface, (20, info_y_start))
        
        # Straße
        road_surface = self.font_info.render(f"Straße: {road_type}", True, self.COLOR_GRAY)
        self.screen.blit(road_surface, (20, info_y_start + 30))
        
        # Höhe und Kompass
        alt_surface = self.font_info.render(f"Höhe: {int(altitude)}m | {heading}", True, self.COLOR_GRAY)
        self.screen.blit(alt_surface, (20, info_y_start + 60))
        
        # 5. Display aktualisieren
        pygame.display.flip()
