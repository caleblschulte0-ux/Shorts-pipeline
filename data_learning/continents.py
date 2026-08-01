#!/usr/bin/env python3
"""THE continents (CURIOSITY_BRAIN §7.5 v8): one hand-authored set of
low-poly landmass silhouettes shared by BOTH renderers, so the 2D disc
and the 3D globe read as the same recognizable planet instead of green
circles.

Each landmass is one closed outline of (longitude, latitude) degrees,
coarse on purpose — flat-design planet, not cartography. Consumers
project: the manim asset onto a sinusoidal Atlantic-view disc, the
Blender globe onto the sphere surface. No manim/bpy imports here; this
module must load in either process (and the Blender side actually
receives the data through the hero spec, never by import).
"""

LANDMASSES = {
    # The Americas — Alaska around the Atlantic coast, down to Tierra
    # del Fuego and back up the Pacific side.
    "americas": [
        (-168, 65), (-156, 71), (-125, 70), (-95, 72), (-80, 66),
        (-65, 58), (-55, 50), (-66, 44), (-75, 35), (-81, 31),
        (-80, 25), (-84, 30), (-90, 29), (-97, 26), (-91, 19),
        (-87, 21), (-83, 9), (-71, 12), (-52, 5), (-35, -8),
        (-39, -18), (-48, -28), (-58, -39), (-65, -47), (-71, -54),
        (-75, -45), (-70, -18), (-81, -5), (-77, 7), (-85, 11),
        (-95, 16), (-105, 20), (-117, 32), (-124, 40), (-124, 48),
        (-132, 55), (-152, 59), (-165, 55),
    ],
    # Africa — the most recognizable outline on the planet: the west
    # bulge, the Gulf of Guinea notch, the horn, the southern point.
    "africa": [
        (-6, 35), (10, 37), (20, 32), (32, 31), (34, 28),
        (37, 21), (43, 11), (51, 12), (46, 2), (40, -3),
        (39, -15), (35, -24), (28, -33), (19, -35), (12, -18),
        (9, -1), (9, 4), (-5, 5), (-17, 14), (-10, 25),
    ],
    # Eurasia — Iberia along the Mediterranean, Arabia, India, the
    # Pacific coast, then back across the Arctic to Scandinavia.
    "eurasia": [
        (-9, 43), (-9, 37), (3, 43), (12, 44), (16, 39),
        (19, 42), (23, 36), (27, 41), (36, 36), (39, 21),
        (43, 12), (55, 17), (60, 25), (67, 24), (72, 20),
        (77, 8), (80, 15), (88, 22), (98, 8), (105, 12),
        (109, 18), (117, 23), (122, 31), (122, 40), (127, 40),
        (135, 43), (142, 54), (158, 52), (162, 60), (170, 66),
        (140, 73), (100, 77), (70, 73), (55, 70), (30, 70),
        (12, 65), (5, 58), (8, 55), (0, 49), (-4, 48),
    ],
    # Australia.
    "australia": [
        (114, -22), (114, -34), (124, -33), (132, -32), (138, -35),
        (141, -38), (147, -38), (150, -34), (153, -28), (151, -22),
        (146, -15), (142, -11), (136, -12), (132, -11), (126, -14),
        (122, -17),
    ],
}

# The 2D disc shows the Atlantic hemisphere (the Blue-Marble view):
# these landmasses, Eurasia trimmed to the points west of lon 62 (the
# rest is over the horizon; the trim run is contiguous in the outline).
ATLANTIC_FACE = ("americas", "africa", "eurasia")
EURASIA_FACE_MAX_LON = 62
ATLANTIC_LON0 = -40.0
