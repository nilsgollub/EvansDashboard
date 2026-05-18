Projekt: Evans Co-Pilot Dashboard

1. Projektziel & Hintergrund

Mein Sohn Evan (geb. Juni 2021) hat eine große Faszination für Geschwindigkeiten und Tempolimits beim Autofahren entwickelt. Um seine ständigen Fragen ("Wie schnell dürfen wir hier fahren?", "Wie schnell sind wir?") interaktiv und visuell ansprechend zu beantworten, wird ein kompaktes, dediziertes "Co-Pilot Dashboard" für den Fond unseres VW Passats entwickelt. Das System erfasst die aktuelle Geschwindigkeit via GPS, gleicht diese online mit OpenStreetMap ab, um das lokale Tempolimit zu ermitteln, und visualisiert die Daten kindgerecht auf einem hochauflösenden Display.

2. Hardware-Architektur

Das System nutzt Hardware-Ressourcen, die zum Teil aus vorherigen Projekten (z.B. dem Rosbot) zur Verfügung stehen:

Zentraleinheit: Raspberry Pi Zero WH (mit aufgelöteter Stiftleiste).

Display: Offizielles Adafruit 3.5" PiTFT (320x480 Pixel, TFT-Treiber: HX8357D, Touch-Treiber: STMPE610).

Anschluss: Wird als HAT (Hardware Attached on Top) direkt auf den 40-Pin-Header des Pi Zero gesteckt.

GPS-Modul: U-BLOX NEO-7M.

Anschluss: Per Micro-USB (bzw. USB-OTG-Adapter) direkt an den Daten-USB-Port des Pi Zero. Dies verhindert Pin-Konflikte mit dem Display.

Stromversorgung: Standard 5V USB-Stromversorgung, abgegriffen über das Bordnetz des Passats (z.B. USB-Buchse im Fond oder 12V-Adapter).

3. Mechanik & Gehäusedesign

Als Experte im Mechanical Design wird für das System ein maßgeschneidertes Gehäuse in Fusion 360 konstruiert und anschließend auf dem Ultimaker 2+ gedruckt.

Aufbau: Da der Pi Zero deutlich kleiner ist als das 3.5" Display, wird das Gehäuse primär um die Maße des Adafruit-Displays herum konstruiert (Montage über die 4 Eck-Bohrungen der Platine). Der Pi Zero hängt "huckepack" unter dem Display.

Anschlüsse: Das Gehäuse benötigt Aussparungen an der Unterseite/Seite für den Micro-USB-Stromanschluss und das USB-Kabel zum U-BLOX GPS-Modul.

Befestigung im Passat: * Option A: Eine Klemm- oder Klettkonstruktion an den Stangen der vorderen Kopfstützen.

Option B: Eine Halterung, die über die Lüftungsschlitze der Mittelkonsole im Fond (falls vorhanden) gesteckt wird.

Das Gehäuse sollte abgerundete Ecken haben und robust genug sein, um Kinderhänden standzuhalten.

4. Software-Architektur & Datenfluss

Das System läuft headless unter Raspberry Pi OS und startet das Dashboard automatisch beim Booten. Die Software wird in Python geschrieben und nutzt Multithreading für einen flüssigen Betrieb.

Thread 1 (GPS-Erfassung): Liest kontinuierlich (mehrmals pro Sekunde) die NMEA-Daten ($GPRMC, $GPGGA) des U-BLOX NEO-7M über die serielle USB-Schnittstelle aus. Er extrahiert die aktuelle Geschwindigkeit über Grund, GPS-Koordinaten, Anzahl der Satelliten, Kurs und Höhe.

Thread 2 (Tempolimit-Abfrage): Sobald ein gültiger GPS-Fix vorliegt, sendet dieser Thread alle 10 Sekunden die aktuellen Koordinaten an die OpenStreetMap Overpass API. Gesucht wird im Radius von 30 Metern nach der nächstgelegenen Straße. Extrahiert werden die Tags maxspeed (Tempolimit) und highway (Straßentyp).

Main Thread (UI-Rendering): Nutzt die Pillow (PIL) Bibliothek in Kombination mit Adafruit CircuitPython-Treibern, um die UI-Elemente direkt in den Framebuffer des SPI-Displays zu zeichnen (Hardware-beschleunigt).

5. Benutzeroberfläche (Das Dashboard)

Das User Interface wird im Querformat (480x320 Pixel) gerendert, hat einen dunklen Hintergrund und ist auf maximale Ablesbarkeit ausgelegt.

Das Tempolimit: Wird in Form eines klassischen europäischen Verkehrsschilds (weißer Kreis, roter Rand) oben links groß dargestellt.

Die Geschwindigkeit: Steht sehr groß und zentral auf der rechten Seite. Ein farbliches Feedback signalisiert Regelverstöße:

Grün: Geschwindigkeit im zulässigen Bereich.

Rot: Geschwindigkeit liegt mehr als 3 km/h über dem abgefragten Limit.

Zusatzinformationen für Evan:

Satelliten-Kontakt: "Sats: 8" (gibt das Gefühl einer Weltraum-Verbindung).

Straßentyp: Übersetzung der OSM-Daten in kindgerechte Begriffe (z.B. "Autobahn", "Landstraße", "Dorfstraße").

Höhenmesser & Kompass: Aktuelle Höhe über Meeresspiegel (in der Schweiz sehr dynamisch) und die Himmelsrichtung (N, S, O, W).

6. Vernetzung

Da kein Offline-Betrieb benötigt wird, setzt das System dauerhaft auf eine Online-Verbindung:

Der Raspberry Pi Zero verbindet sich automatisch mit dem WLAN-Hotspot eines Android-Smartphones im Auto.

Über diese Verbindung werden die API-Anfragen an OpenStreetMap gesendet.

7. Zukünftige Ausbaustufen (Phase 2)

Touch-Integration: Das Adafruit-Display besitzt einen resistiven Touchscreen. Später könnten Buttons hinzugefügt werden, mit denen Evan zwischen verschiedenen Ansichten wechseln kann (z.B. eine detailliertere Weltraum-/Satelliten-Ansicht oder ein Trip-Zähler).