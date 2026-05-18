import pygame
import math
import time

class DashboardUI:
    def __init__(self, width=480, height=320, fullscreen=False):
        pygame.init()
        self.width = width
        self.height = height
        
        flags = pygame.FULLSCREEN if fullscreen else 0
        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        pygame.display.set_caption("Evans Co-Pilot Dashboard")
        
        # Initialisiere Fonts
        self.font_speed = pygame.font.SysFont('arial', 140, bold=True)
        self.font_limit = pygame.font.SysFont('arial', 80, bold=True)
        self.font_info = pygame.font.SysFont('arial', 22)
        self.font_compass = pygame.font.SysFont('arial', 14, bold=True)
        self.font_tag = pygame.font.SysFont('arial', 13, bold=True)
        
        # Farben (RGB)
        self.COLOR_BG = (15, 15, 20)      # Sehr dunkles Blau-Grau
        self.COLOR_WHITE = (245, 245, 245)
        self.COLOR_RED = (220, 40, 40)    # Verkehrsrot
        self.COLOR_GREEN = (40, 220, 40)
        self.COLOR_GRAY = (150, 150, 150)
        self.COLOR_DARK_GRAY = (60, 60, 70)
        self.COLOR_YELLOW = (240, 200, 40)
        
        # Schweizer Strassentyp-Übersetzungen (mit "ss" statt "ß")
        self.ROAD_TYPE_TRANSLATIONS = {
            'motorway': 'Autobahn',
            'motorway_link': 'Autobahn-Anschluss',
            'trunk': 'Autostrasse',
            'trunk_link': 'Autostrasse-Anschluss',
            'primary': 'Kantonsstrasse',
            'primary_link': 'Kantonsstrasse',
            'secondary': 'Kantonsstrasse',
            'secondary_link': 'Kantonsstrasse',
            'tertiary': 'Gemeindestrasse',
            'tertiary_link': 'Gemeindestrasse',
            'unclassified': 'Gemeindestrasse',
            'residential': 'Quartierstrasse',
            'living_street': 'Begegnungszone',
            'service': 'Service-Strasse',
            'track': 'Feldweg',
            'unbekannt': 'Unbekannt',
            'fehler': 'Fehler'
        }
        
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
        
    def get_cardinal_direction(self, degrees):
        try:
            deg = float(degrees)
        except (TypeError, ValueError):
            return "N"
        # Mapping von Grad auf deutsche Himmelsrichtung
        directions = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]
        idx = int(((deg + 22.5) % 360) // 45)
        return directions[idx]

    def draw_compass(self, x, y, radius, heading):
        # 1. Äußerer Ring
        pygame.draw.circle(self.screen, self.COLOR_DARK_GRAY, (x, y), radius, width=2)
        # Sehr dezenter innerer Kreis zur Abdunklung
        pygame.draw.circle(self.screen, (25, 25, 30), (x, y), radius - 3)
        
        # 2. Himmelsrichtungen einzeichnen (N, O, S, W)
        cardinals = [
            ("N", 0, self.COLOR_RED),
            ("O", 90, self.COLOR_GRAY),
            ("S", 180, self.COLOR_GRAY),
            ("W", 270, self.COLOR_GRAY)
        ]
        
        for label, deg, color in cardinals:
            rad = math.radians(deg - 90)
            label_x = x + (radius - 12) * math.cos(rad)
            label_y = y + (radius - 12) * math.sin(rad)
            surf = self.font_compass.render(label, True, color)
            rect = surf.get_rect(center=(label_x, label_y))
            self.screen.blit(surf, rect)
            
        # 3. Kompassnadel zeichnen (Richtung des Headings)
        try:
            angle = float(heading)
        except (TypeError, ValueError):
            angle = 0.0
            
        rad_heading = math.radians(angle - 90)
        
        # Nadelspitze (Rot)
        tip_x = x + (radius - 16) * math.cos(rad_heading)
        tip_y = y + (radius - 16) * math.sin(rad_heading)
        
        # Nadelbasis hinten (Süd-Ende, Weiß)
        back_x = x + (radius - 16) * math.cos(rad_heading + math.pi)
        back_y = y + (radius - 16) * math.sin(rad_heading + math.pi)
        
        # Seitliche Breitenpunkte der Nadel für eine klassische Rautenform
        side1_x = x + 5 * math.cos(rad_heading + math.pi / 2)
        side1_y = y + 5 * math.sin(rad_heading + math.pi / 2)
        
        side2_x = x + 5 * math.cos(rad_heading - math.pi / 2)
        side2_y = y + 5 * math.sin(rad_heading - math.pi / 2)
        
        # Rote Nordhälfte (mit 3D Licht-Schatten-Effekt)
        pygame.draw.polygon(self.screen, self.COLOR_RED, [(tip_x, tip_y), (side1_x, side1_y), (x, y)])
        pygame.draw.polygon(self.screen, (160, 30, 30), [(tip_x, tip_y), (side2_x, side2_y), (x, y)]) # Schattenseite
        
        # Weisse/Graue Südhälfte (mit 3D Licht-Schatten-Effekt)
        pygame.draw.polygon(self.screen, self.COLOR_WHITE, [(back_x, back_y), (side1_x, side1_y), (x, y)])
        pygame.draw.polygon(self.screen, self.COLOR_GRAY, [(back_x, back_y), (side2_x, side2_y), (x, y)]) # Schattenseite
        
        # Kleiner Pin in der Mitte
        pygame.draw.circle(self.screen, (80, 80, 90), (x, y), 3)

    def render(self, current_speed, speed_limit, sats, road_type, altitude, heading, is_simulated=True, has_fix=True):
        # 1. Hintergrund löschen
        self.screen.fill(self.COLOR_BG)
        
        # 1.5 Mode Tag (oben rechts)
        tag_x = self.width - 130
        tag_y = 20
        tag_w = 105
        tag_h = 26
        
        if is_simulated:
            bg_color = (40, 25, 20)
            border_color = (220, 100, 20)
            text_color = (240, 140, 40)
            status_text = "SIMULATOR"
            dot_color = (220, 100, 20)
        elif not has_fix:
            bg_color = (25, 30, 40)
            border_color = (60, 120, 220)
            text_color = (200, 220, 245)
            status_text = "SUCHE GPS"
            pulse = int(150 + 105 * abs(math.sin(time.time() * 3)))
            dot_color = (40, 120, pulse)
        else:
            bg_color = (15, 35, 20)
            border_color = (40, 220, 40)
            text_color = (245, 245, 245)
            status_text = "LIVE GPS"
            # Pulsierender Punkt
            pulse = int(150 + 105 * abs(math.sin(time.time() * 3)))
            dot_color = (40, pulse, 40)

        rect = pygame.Rect(tag_x, tag_y, tag_w, tag_h)
        pygame.draw.rect(self.screen, bg_color, rect, border_radius=13)
        pygame.draw.rect(self.screen, border_color, rect, width=1, border_radius=13)
        
        # Zeichne den Status-Punkt
        pygame.draw.circle(self.screen, dot_color, (tag_x + 15, tag_y + 13), 5)
        
        # Zeichne den Text
        text_surf = self.font_tag.render(status_text, True, text_color)
        text_rect = text_surf.get_rect(midleft=(tag_x + 28, tag_y + 13))
        self.screen.blit(text_surf, text_rect)
        
        # 2. Tempolimit Schild (oben links)
        sign_radius = 70
        sign_x = sign_radius + 25
        sign_y = sign_radius + 20
        self.draw_speed_limit_sign(sign_x, sign_y, sign_radius, speed_limit)
        
        # 3. Grafischer Kompass (unten links, perfekt unter dem Tempolimit-Schild platziert)
        compass_radius = 45
        compass_x = sign_x
        compass_y = 250
        self.draw_compass(compass_x, compass_y, compass_radius, heading)
        
        # 4. Aktuelle Geschwindigkeit (rechts groß)
        speed_color = self.COLOR_WHITE
        if speed_limit is not None:
            if current_speed > speed_limit + 3:
                speed_color = self.COLOR_RED
            elif current_speed <= speed_limit:
                speed_color = self.COLOR_GREEN
            else:
                speed_color = self.COLOR_YELLOW # Geringe Toleranz (1-3 km/h drüber)
                
        speed_text = f"{int(current_speed)}"
        speed_surface = self.font_speed.render(speed_text, True, speed_color)
        speed_rect = speed_surface.get_rect(midright=(self.width - 40, self.height // 2 - 10))
        self.screen.blit(speed_surface, speed_rect)
        
        # "km/h" Anzeige direkt unter/neben der Geschwindigkeit
        kmh_surface = self.font_info.render("km/h", True, self.COLOR_GRAY)
        kmh_rect = kmh_surface.get_rect(topright=(self.width - 40, speed_rect.bottom - 15))
        self.screen.blit(kmh_surface, kmh_rect)
        
        # 5. Zusatzinfos (Mitte unten, neben dem Kompass platziert)
        info_x = 165
        info_y_start = 205
        
        # Satelliten mit Farbe (Grün = gut, Rot = schlecht)
        sat_color = self.COLOR_GREEN if sats >= 4 else self.COLOR_RED
        sats_surface = self.font_info.render(f"Sats: {sats}", True, sat_color)
        self.screen.blit(sats_surface, (info_x, info_y_start))
        
        # Strasse mit Schweizer Übersetzung
        road_key = str(road_type).lower()
        translated_road = self.ROAD_TYPE_TRANSLATIONS.get(road_key, road_type)
        road_surface = self.font_info.render(f"Strasse: {translated_road}", True, self.COLOR_GRAY)
        self.screen.blit(road_surface, (info_x, info_y_start + 28))
        
        # Höhe und Himmelsrichtungstext
        heading_text = self.get_cardinal_direction(heading)
        alt_surface = self.font_info.render(f"Höhe: {int(altitude)}m | {heading_text} ({int(heading)}°)", True, self.COLOR_GRAY)
        self.screen.blit(alt_surface, (info_x, info_y_start + 56))
        
        # 6. Display aktualisieren
        pygame.display.flip()
