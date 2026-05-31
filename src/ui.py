import math
import time
from datetime import datetime

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
        self.font_speed = pygame.font.SysFont("arial", 150, bold=False)
        self.font_limit = pygame.font.SysFont("arial", 80, bold=True)
        self.font_info = pygame.font.SysFont("arial", 22)
        self.font_compass = pygame.font.SysFont("arial", 14, bold=True)
        self.font_tag = pygame.font.SysFont("arial", 13, bold=True)

        # Fonts für Zeit, Datum und Wetter (Top Bar)
        self.font_time = pygame.font.SysFont("arial", 28, bold=True)
        self.font_date = pygame.font.SysFont("arial", 18)
        self.font_weather = pygame.font.SysFont("arial", 22, bold=True)
        # Such-Screen Titel (kleiner als font_limit, damit er neben dem Radar nicht abgeschnitten wird)
        self.font_search = pygame.font.SysFont("arial", 54, bold=True)

        # Farben (RGB)
        self.COLOR_BG = (15, 15, 20)  # Sehr dunkles Blau-Grau
        self.COLOR_WHITE = (245, 245, 245)
        self.COLOR_RED = (220, 40, 40)  # Verkehrsrot
        self.COLOR_GREEN = (40, 220, 40)
        self.COLOR_GRAY = (150, 150, 150)
        self.COLOR_DARK_GRAY = (60, 60, 70)
        self.COLOR_YELLOW = (240, 200, 40)

        # Schweizer Strassentyp-Übersetzungen (mit "ss" statt "ß")
        self.ROAD_TYPE_TRANSLATIONS = {
            "motorway": "Autobahn",
            "motorway_link": "Autobahn-Anschluss",
            "trunk": "Autostrasse",
            "trunk_link": "Autostrasse-Anschluss",
            "primary": "Kantonsstrasse",
            "primary_link": "Kantonsstrasse",
            "secondary": "Kantonsstrasse",
            "secondary_link": "Kantonsstrasse",
            "tertiary": "Gemeindestrasse",
            "tertiary_link": "Gemeindestrasse",
            "unclassified": "Gemeindestrasse",
            "residential": "Quartierstrasse",
            "living_street": "Begegnungszone",
            "service": "Service-Strasse",
            "track": "Feldweg",
            "unbekannt": "Unbekannt",
            "fehler": "Fehler",
        }

    def draw_speed_limit_sign(self, x, y, radius, limit):
        # Weißer Kreis
        pygame.draw.circle(self.screen, self.COLOR_WHITE, (x, y), radius)
        # Roter Rand
        pygame.draw.circle(self.screen, self.COLOR_RED, (x, y), radius, width=int(radius * 0.2))

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
            ("W", 270, self.COLOR_GRAY),
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
        pygame.draw.polygon(self.screen, (160, 30, 30), [(tip_x, tip_y), (side2_x, side2_y), (x, y)])  # Schattenseite

        # Weisse/Graue Südhälfte (mit 3D Licht-Schatten-Effekt)
        pygame.draw.polygon(self.screen, self.COLOR_WHITE, [(back_x, back_y), (side1_x, side1_y), (x, y)])
        pygame.draw.polygon(
            self.screen, self.COLOR_GRAY, [(back_x, back_y), (side2_x, side2_y), (x, y)]
        )  # Schattenseite

        # Kleiner Pin in der Mitte
        pygame.draw.circle(self.screen, (80, 80, 90), (x, y), 3)

    def draw_weather_icon(self, x, y, size, condition):
        """
        Zeichnet wunderschöne, maßgeschneiderte Wetter-Icons direkt als Vektorgrafik.
        Löst das Problem fehlender Emoji-Unicode-Glyphen in Standard-Linux-Schriftarten.
        """
        cx = x + size // 2
        cy = y + size // 2
        drawer = {
            "sun": self._draw_sun,
            "cloud": self._draw_cloud,
            "cloud_sun": self._draw_cloud_sun,
            "rain": self._draw_rain,
            "snow": self._draw_snow,
            "storm": self._draw_storm,
        }.get(condition, self._draw_unknown)
        drawer(cx, cy, size)

    def _draw_sun(self, cx, cy, size):
        # Gelbe Sonne mit Sonnenstrahlen
        r = int(size * 0.3)
        pygame.draw.circle(self.screen, (255, 215, 0), (cx, cy), r)
        for i in range(8):
            angle = math.radians(i * 45)
            x1 = cx + int(r * 1.3 * math.cos(angle))
            y1 = cy + int(r * 1.3 * math.sin(angle))
            x2 = cx + int(r * 1.8 * math.cos(angle))
            y2 = cy + int(r * 1.8 * math.sin(angle))
            pygame.draw.line(self.screen, (255, 215, 0), (x1, y1), (x2, y2), 2)

    def _draw_cloud(self, cx, cy, size):
        # Schöne graue/weiße Wolke aus überlappenden Kreisen
        r = int(size * 0.22)
        c_color = (180, 185, 195)
        pygame.draw.circle(self.screen, c_color, (cx - int(size * 0.25), cy + int(size * 0.08)), int(r * 0.85))
        pygame.draw.circle(self.screen, c_color, (cx + int(size * 0.25), cy + int(size * 0.08)), int(r * 0.85))
        pygame.draw.circle(self.screen, c_color, (cx, cy - int(size * 0.05)), r)
        # Wolkenbasis abflachen
        pygame.draw.rect(
            self.screen,
            c_color,
            (cx - int(size * 0.28), cy + int(size * 0.15) - int(r * 0.5), int(size * 0.56), int(r)),
            border_radius=3,
        )

    def _draw_cloud_sun(self, cx, cy, size):
        # Sonne hinter Wolke
        # 1. Sonne hinten rechts
        sun_cx = cx + int(size * 0.16)
        sun_cy = cy - int(size * 0.16)
        sun_r = int(size * 0.22)
        pygame.draw.circle(self.screen, (255, 210, 0), (sun_cx, sun_cy), sun_r)
        for i in range(8):
            angle = math.radians(i * 45)
            x1 = sun_cx + int(sun_r * 1.2 * math.cos(angle))
            y1 = sun_cy + int(sun_r * 1.2 * math.sin(angle))
            x2 = sun_cx + int(sun_r * 1.6 * math.cos(angle))
            y2 = sun_cy + int(sun_r * 1.6 * math.sin(angle))
            pygame.draw.line(self.screen, (255, 210, 0), (x1, y1), (x2, y2), 1)

        # 2. Wolke vorne links
        r = int(size * 0.18)
        c_color = (200, 205, 215)
        cloud_cx = cx - int(size * 0.12)
        cloud_cy = cy + int(size * 0.08)
        pygame.draw.circle(
            self.screen, c_color, (cloud_cx - int(size * 0.2), cloud_cy + int(size * 0.06)), int(r * 0.85)
        )
        pygame.draw.circle(
            self.screen, c_color, (cloud_cx + int(size * 0.2), cloud_cy + int(size * 0.06)), int(r * 0.85)
        )
        pygame.draw.circle(self.screen, c_color, (cloud_cx, cloud_cy - int(size * 0.05)), r)
        pygame.draw.rect(
            self.screen,
            c_color,
            (cloud_cx - int(size * 0.22), cloud_cy + int(size * 0.12) - int(r * 0.5), int(size * 0.44), int(r)),
            border_radius=3,
        )

    def _draw_rain(self, cx, cy, size):
        # Wolke mit Regen
        self._draw_cloud(cx, cy - int(size * 0.08), size)
        # 3 Regentropfen
        drop_color = (80, 150, 240)
        ry = cy + int(size * 0.24)
        pygame.draw.line(self.screen, drop_color, (cx - 5, ry), (cx - 7, ry + 5), 2)
        pygame.draw.line(self.screen, drop_color, (cx + 1, ry), (cx - 1, ry + 5), 2)
        pygame.draw.line(self.screen, drop_color, (cx + 7, ry), (cx + 5, ry + 5), 2)

    def _draw_snow(self, cx, cy, size):
        # Wolke mit Schneeflocken
        self._draw_cloud(cx, cy - int(size * 0.08), size)
        # Schneeflocken als winzige weisse Punkte/Kreuze
        snow_color = (240, 245, 255)
        sy = cy + int(size * 0.24)
        pygame.draw.circle(self.screen, snow_color, (cx - 5, sy + 2), 2)
        pygame.draw.circle(self.screen, snow_color, (cx + 1, sy + 2), 2)
        pygame.draw.circle(self.screen, snow_color, (cx + 7, sy + 2), 2)

    def _draw_storm(self, cx, cy, size):
        # Wolke mit Blitz
        self._draw_cloud(cx, cy - int(size * 0.08), size)
        # Gelber Blitz
        bolt_color = (255, 220, 0)
        by = cy + int(size * 0.16)
        pts = [(cx + 2, by), (cx - 3, by + 6), (cx, by + 6), (cx - 2, by + 12), (cx + 4, by + 5), (cx + 1, by + 5)]
        pygame.draw.polygon(self.screen, bolt_color, pts)

    def _draw_unknown(self, cx, cy, size):
        # Fragezeichen bei Unbekannt
        pygame.draw.circle(self.screen, self.COLOR_DARK_GRAY, (cx, cy), size // 3, width=1)
        qm_surf = self.font_tag.render("?", True, self.COLOR_GRAY)
        qm_rect = qm_surf.get_rect(center=(cx, cy))
        self.screen.blit(qm_surf, qm_rect)

    def draw_wifi_icon(self, x, y, signal_pct):
        """
        Zeichnet ein WiFi-Signalstärke-Icon (3 Bögen + Punkt).
        signal_pct: 0-100 (0=kein Signal, 100=voll)
        """
        # Farbe basierend auf Signalstärke
        if signal_pct >= 60:
            color = (40, 200, 120)  # Grün: gutes Signal
        elif signal_pct >= 30:
            color = (240, 200, 40)  # Gelb: mittleres Signal
        elif signal_pct > 0:
            color = (240, 120, 40)  # Orange: schwaches Signal
        else:
            color = (80, 80, 90)  # Grau: kein Signal

        dim_color = (45, 45, 55)  # Dunkelgrau für inaktive Bögen

        # Basispunkt unten Mitte
        bx = x + 10
        by = y + 16

        # Punkt am Fuß
        pygame.draw.circle(self.screen, color if signal_pct > 0 else dim_color, (bx, by), 2)

        # 3 Bögen (von innen nach außen)
        for i, threshold in enumerate([15, 40, 65]):
            arc_color = color if signal_pct >= threshold else dim_color
            radius = 6 + i * 5
            rect = pygame.Rect(bx - radius, by - radius, radius * 2, radius * 2)
            pygame.draw.arc(self.screen, arc_color, rect, math.radians(30), math.radians(150), 2)

    def render(
        self,
        current_speed,
        speed_limit,
        sats,
        road_type,
        altitude,
        heading,
        is_simulated=True,
        has_fix=True,
        weather_temp=None,
        weather_desc=None,
        wifi_ssid=None,
        wifi_signal=0,
        version=None,
        dim_factor=1.0,
        gps_connected=False,
    ):
        self.screen.fill(self.COLOR_BG)
        self._render_top_bar(is_simulated, has_fix, gps_connected, weather_temp, weather_desc, wifi_signal)
        # In der Suchphase (echter Sensor, aber noch kein Fix und keine Simulation)
        # zeigen wir statt Tacho/Schild eine kinderfreundliche Such-Animation.
        if not has_fix and not is_simulated:
            self._render_searching(sats, gps_connected, version)
        else:
            self._render_center(current_speed, speed_limit, version)
        self._render_bottom_bar(heading, altitude, road_type, sats)
        self._apply_dimming(dim_factor)

        # Display aktualisieren
        pygame.display.flip()

    def _render_top_bar(self, is_simulated, has_fix, gps_connected, weather_temp, weather_desc, wifi_signal):
        # --- 1. TOP BAR (Höhe: 45px) ---
        # Hintergrund und Trennlinie
        pygame.draw.rect(self.screen, (20, 20, 25), (0, 0, self.width, 45))
        pygame.draw.line(self.screen, (40, 40, 50), (0, 45), (self.width, 45), 2)

        # 1.1 Uhrzeit & Datum (Links)
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%d.%m.%Y")

        time_surf = self.font_time.render(time_str, True, self.COLOR_WHITE)
        self.screen.blit(time_surf, (15, 8))

        date_surf = self.font_date.render(date_str, True, (200, 200, 210))
        self.screen.blit(date_surf, (15 + time_surf.get_width() + 10, 16))

        # 1.2 Wetter (Mitte) - Zentriert gerendert aus Temperatur und Custom-Vektor-Icon
        if weather_temp is not None and weather_desc is not None:
            temp_str = f"{weather_temp}°C"
            temp_surf = self.font_weather.render(temp_str, True, self.COLOR_YELLOW)

            icon_size = 24
            gap = 8
            total_w = temp_surf.get_width() + gap + icon_size

            start_x = (self.width // 2) - (total_w // 2) + 10  # Offset für zentrierten Gesamteindruck
            self.screen.blit(temp_surf, (start_x, 11))

            # Custom Vector Wetter-Icon daneben zeichnen
            self.draw_weather_icon(start_x + temp_surf.get_width() + gap, 10, icon_size, weather_desc)
        else:
            weather_str = "--°C"
            weather_surf = self.font_weather.render(weather_str, True, self.COLOR_DARK_GRAY)
            weather_rect = weather_surf.get_rect(center=(self.width // 2 + 10, 22))
            self.screen.blit(weather_surf, weather_rect)

        # 1.3 Mode Tag (Rechts)
        if is_simulated:
            bg_color = (40, 25, 20)
            border_color = (220, 100, 20)
            text_color = (240, 140, 40)
            status_text = "SIMULATOR"
            dot_color = (220, 100, 20)
        elif not gps_connected:
            bg_color = (30, 30, 35)
            border_color = (70, 70, 80)
            text_color = (130, 130, 140)
            status_text = "KEIN SENSOR"
            dot_color = (100, 100, 110)
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
            pulse = int(150 + 105 * abs(math.sin(time.time() * 3)))
            dot_color = (40, pulse, 40)

        tag_w = 115
        tag_h = 26
        tag_x = self.width - tag_w - 45
        tag_y = 9
        rect = pygame.Rect(tag_x, tag_y, tag_w, tag_h)
        pygame.draw.rect(self.screen, bg_color, rect, border_radius=13)
        pygame.draw.rect(self.screen, border_color, rect, width=1, border_radius=13)
        pygame.draw.circle(self.screen, dot_color, (tag_x + 15, tag_y + 13), 5)

        text_surf = self.font_tag.render(status_text, True, text_color)
        text_rect = text_surf.get_rect(midleft=(tag_x + 28, tag_y + 13))
        self.screen.blit(text_surf, text_rect)

        # 1.4 WiFi-Status (Obere Leiste ganz rechts)
        self.draw_wifi_icon(self.width - 35, 12, wifi_signal)

    def _render_center(self, current_speed, speed_limit, version):
        # --- 2. MAIN CENTER (Y: 45 bis 260) ---
        # 2.1 Tempolimit Schild (Linke Spalte)
        sign_radius = 65
        sign_x = 90
        sign_y = 155
        self.draw_speed_limit_sign(sign_x, sign_y, sign_radius, speed_limit)

        # 2.2 Aktuelle Geschwindigkeit (Rechte Spalte)
        speed_color = self.COLOR_WHITE
        if speed_limit is not None:
            if current_speed > speed_limit + 3:
                speed_color = self.COLOR_RED
            elif current_speed <= speed_limit:
                speed_color = self.COLOR_GREEN
            else:
                speed_color = self.COLOR_YELLOW

        speed_text = f"{int(current_speed)}"
        speed_surface = self.font_speed.render(speed_text, True, speed_color)
        speed_rect = speed_surface.get_rect(midright=(self.width - 30, 145))
        self.screen.blit(speed_surface, speed_rect)

        # "km/h" Anzeige rechtsbündig unter der Geschwindigkeit
        kmh_surface = self.font_info.render("km/h", True, self.COLOR_GRAY)
        kmh_rect = kmh_surface.get_rect(topright=(self.width - 35, speed_rect.bottom - 5))
        self.screen.blit(kmh_surface, kmh_rect)

        # 2.3 Versionsanzeige knapp über der unteren Leiste ganz rechts
        if version:
            ver_surf = self.font_tag.render(f"v{version}", True, (90, 90, 105))
            ver_rect = ver_surf.get_rect(bottomright=(self.width - 20, 255))
            self.screen.blit(ver_surf, ver_rect)

    def _render_searching(self, sats, gps_connected, version):
        """Such-Animation fuer Evan, solange noch kein GPS-Fix da ist.

        Links: Radar-Sweep mit kleinen Punkten pro sichtbarem Satelliten.
        Rechts: grosse, freundliche Sat-Zahl plus motivierender Untertitel,
        der sich mit der Sat-Anzahl mitfaerbt.
        """
        sat_count = max(0, int(sats or 0))

        # --- Radar (links) ---
        cx, cy = 110, 155
        r = 75
        # Dunkler Radar-Hintergrund + konzentrische Ringe + Fadenkreuz
        pygame.draw.circle(self.screen, (8, 22, 12), (cx, cy), r)
        for ring in (r, int(r * 0.66), int(r * 0.33)):
            pygame.draw.circle(self.screen, (30, 80, 40), (cx, cy), ring, 1)
        pygame.draw.line(self.screen, (30, 80, 40), (cx - r, cy), (cx + r, cy), 1)
        pygame.draw.line(self.screen, (30, 80, 40), (cx, cy - r), (cx, cy + r), 1)

        # Rotierender Sweep mit kleinem Nachleucht-Schweif (eine Umdrehung / 2.5 s)
        sweep_angle = (time.time() * (2 * math.pi / 2.5)) % (2 * math.pi)
        for i in range(0, 9):
            a = sweep_angle - i * 0.07
            ex = cx + int(r * math.cos(a))
            ey = cy + int(r * math.sin(a))
            fade = max(0.0, 1.0 - i / 9.0)
            color = (int(40 * fade), int(210 * fade), int(60 * fade))
            pygame.draw.line(self.screen, color, (cx, cy), (ex, ey), 2)

        # Pro sichtbarem Sat ein Punkt - Position deterministisch (goldener Winkel),
        # damit die Punkte nicht von Frame zu Frame herumspringen.
        for i in range(min(sat_count, 16)):
            angle = math.radians(i * 137.508)
            rad = int(r * 0.25) + ((i * 11) % int(r * 0.55))
            dx = cx + int(rad * math.cos(angle))
            dy = cy + int(rad * math.sin(angle))
            pygame.draw.circle(self.screen, (220, 240, 220), (dx, dy), 3)
            pygame.draw.circle(self.screen, (40, 80, 40), (dx, dy), 4, 1)

        # --- Text-Bereich (rechts) ---
        text_cx = (cx + r + 20 + self.width - 20) // 2

        # Grosses freundliches "Suche..."
        title_surf = self.font_search.render("Suche...", True, self.COLOR_WHITE)
        title_rect = title_surf.get_rect(midtop=(text_cx, 80))
        self.screen.blit(title_surf, title_rect)

        # Sat-Zaehler in der Farbe der Stimmung
        if sat_count >= 4:
            counter_color = self.COLOR_GREEN
            sub_text = "Gleich geht's los!"
            sub_color = (180, 240, 180)
        elif sat_count >= 1:
            counter_color = self.COLOR_YELLOW
            sub_text = "Schau zum Himmel!"
            sub_color = self.COLOR_YELLOW
        else:
            counter_color = self.COLOR_GRAY
            sub_text = "Warte kurz..." if gps_connected else "Kein GPS-Sensor"
            sub_color = self.COLOR_GRAY

        sat_word = "Satellit" if sat_count == 1 else "Satelliten"
        counter_surf = self.font_weather.render(f"{sat_count} {sat_word}", True, counter_color)
        counter_rect = counter_surf.get_rect(midtop=(text_cx, 165))
        self.screen.blit(counter_surf, counter_rect)

        sub_surf = self.font_info.render(sub_text, True, sub_color)
        sub_rect = sub_surf.get_rect(midtop=(text_cx, 200))
        self.screen.blit(sub_surf, sub_rect)

        # Versionsanzeige beibehalten, damit das Layout konsistent bleibt
        if version:
            ver_surf = self.font_tag.render(f"v{version}", True, (90, 90, 105))
            ver_rect = ver_surf.get_rect(bottomright=(self.width - 20, 255))
            self.screen.blit(ver_surf, ver_rect)

    def _render_bottom_bar(self, heading, altitude, road_type, sats):
        # --- 3. BOTTOM BAR (Y: 260 bis 320) ---
        # Trennlinie
        pygame.draw.line(self.screen, (40, 40, 50), (0, 260), (self.width, 260), 2)

        # 3.1 Kompass (Links)
        compass_radius = 28
        compass_x = 45
        compass_y = 290
        self.draw_compass(compass_x, compass_y, compass_radius, heading)

        # 3.2 Himmelsrichtung & Höhe (Neben Kompass)
        heading_text = self.get_cardinal_direction(heading)
        alt_surface = self.font_info.render(f"{heading_text} | {int(altitude)}m", True, self.COLOR_GRAY)
        self.screen.blit(alt_surface, (85, 278))

        # 3.3 WiFi-Status entfernt (in die obere Leiste verschoben)

        # 3.4 Strassentyp (Zentriert-Rechts)
        road_key = str(road_type).lower()
        translated_road = self.ROAD_TYPE_TRANSLATIONS.get(road_key, road_type)
        road_surface = self.font_info.render(translated_road, True, self.COLOR_WHITE)
        road_rect = road_surface.get_rect(center=(self.width // 2 + 40, 290))
        self.screen.blit(road_surface, road_rect)

        # 3.5 Satelliten (Rechts) – Orange bei wenig Sats statt unlesbarem Dunkelrot
        if sats >= 4:
            sat_color = self.COLOR_GREEN
        elif sats >= 1:
            sat_color = (255, 180, 40)  # Helles Orange – gut lesbar auf dunklem Hintergrund
        else:
            sat_color = (180, 180, 190)  # Helles Grau bei 0 Sats
        sats_surface = self.font_info.render(f"Sats: {sats}", True, sat_color)
        sats_rect = sats_surface.get_rect(midright=(self.width - 20, 290))
        self.screen.blit(sats_surface, sats_rect)

    def _apply_dimming(self, dim_factor):
        # Software-Dimmen (stufenloser Fallback bei Nacht / Dämmerung)
        if dim_factor < 1.0:
            dim_val = max(0.1, dim_factor)  # Mindesthelligkeit von 10%, damit man noch etwas sieht
            alpha = int((1.0 - dim_val) * 255)
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, alpha))
            self.screen.blit(overlay, (0, 0))
