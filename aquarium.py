"""Portable 128x64 aquarium scene. No desktop-only imports."""
import math
import random

WIDTH = 128
HEIGHT = 64
FPS = 15

# Compact ordered sprite commands (dx, dy, palette index). Keep the
# resident cache bounded even as journeys choose new species/colours.
_FISH_SPRITES = {}
_FISH_SPRITE_LIMIT = 32
_SUB_BODY = bytes(v for dy in range(9) for dx in range(3, 26)
                  if ((dx - 14) / 12) ** 2 + ((dy - 4) / 5) ** 2 <= 1
                  for v in (dx, dy, 57 if dy < 3 else 56 if dy < 7 else 58))
_ANGLER_BODY = bytes(v for dy in range(-6, 7) for dx in range(-9, 7)
                     if ((dx + 2) * (dx + 2) / 105.0 + dy * dy / 48.0) < 1
                     for v in (dx + 16, dy + 16, 44 if dy > 1 else 45))

# Colour indices, not RGB pixels. Cycling these colours animates highlights.
BASE_PALETTE = [
    (0, 48, 78), (0, 44, 75), (0, 40, 72), (0, 36, 68),
    (0, 32, 64), (0, 27, 57), (0, 23, 50), (0, 19, 44),
    (7, 32, 33), (13, 52, 43), (23, 76, 48), (36, 99, 53),
    (49, 65, 70), (67, 82, 80), (87, 103, 96), (113, 125, 111),
    (112, 71, 37), (175, 106, 40), (233, 148, 47), (250, 185, 68),
    (181, 65, 37), (238, 111, 51), (244, 168, 100), (245, 210, 154),
    (16, 95, 117), (28, 130, 151), (53, 166, 176), (99, 196, 195),
    (8, 16, 28), (19, 28, 43), (35, 48, 61), (67, 75, 80),
    # Fish-only shades: independent of the cycling water/light palette.
    (29, 129, 222), (95, 211, 255), (255, 217, 55), (245, 120, 36),
    (151, 61, 209), (241, 137, 226), (24, 191, 158), (144, 245, 194),
    (231, 57, 96), (255, 157, 180), (230, 235, 237), (105, 125, 152),
    (20, 34, 44), (35, 53, 62), (53, 75, 83), (72, 96, 101),
    # Coral, anemones and the occasional yellow submarine.
    (226, 88, 137), (255, 160, 194), (112, 67, 177), (179, 132, 233),
    (230, 140, 54), (255, 209, 96), (52, 176, 150), (110, 228, 183),
    (244, 203, 43), (255, 238, 111), (152, 107, 30), (42, 83, 112),
    # Natural seabed: shadow, sand, sunlit sand, ripples, shell and pebble.
    (47, 49, 46), (79, 73, 59), (107, 94, 70), (132, 115, 79),
    (153, 136, 97), (68, 78, 76), (170, 157, 123), (96, 82, 65),
    # Alternate submarine hulls: red, turquoise, purple and their highlights.
    (213, 66, 69), (255, 139, 123), (33, 154, 166), (110, 225, 214),
    (126, 83, 192), (198, 154, 243),
    (234, 111, 30), (255, 187, 91),
    (230, 82, 151), (255, 174, 210),
    (49, 151, 74), (142, 222, 107),
    (34, 56, 107), (228, 181, 65),
    # Dedicated emissive pearl halo/core and warm treasure; bright at night.
    (100, 165, 220), (255, 255, 235), (255, 218, 88),
    # Muted snail interiors: plum, dusty rose, sage and shadow.
    (99, 75, 124), (154, 109, 140), (93, 110, 96), (62, 76, 68),
    (125, 130, 135),  # Soft ghost grey, retained at night.
]
WATER = 0
SAND = 16
PLANT = 8
ROCK = 28
FISH = 20
LIGHT = 24
PEARL_HALO = 82
PEARL_CORE = 83
TREASURE_GLOW = 84


def palette_at(seconds, night=False):
    """Return RGB entries. Indices 24..27 are the cycling light palette."""
    p = list(BASE_PALETTE)
    phase = int(seconds * 1.8) % 4
    shades = BASE_PALETTE[24:28]
    for i in range(4):
        p[24 + i] = shades[(i + phase) % 4]
    if night:
        p = [(r * 2 // 5, g * 2 // 5, b * 3 // 5) for r, g, b in p]
        # Keep small bioluminescent accents bright against dark water.
        for idx in (25, 26, 27, 33, 39, 41, 49, 51, 55, 57, 71, 73, 82, 83, 84, 89):
            p[idx] = BASE_PALETTE[idx]
    return p


_BACKGROUND_TEXTURES = None


def background_textures():
    """Build immutable water grain and sand geometry once, on first use."""
    global _BACKGROUND_TEXTURES
    if _BACKGROUND_TEXTURES is None:
        water = bytearray(WIDTH * HEIGHT)
        floors = bytearray(WIDTH)
        sand = bytearray(WIDTH * 10)
        for y in range(HEIGHT):
            for x in range(WIDTH):
                shade = y // 8
                grain = (x * 17 + y * 29 + (x * y) // 19) & 31
                if grain == 0 and shade > 0:
                    shade -= 1
                elif grain == 1 and shade < 7:
                    shade += 1
                water[y * WIDTH + x] = shade
        for x in range(WIDTH):
            floor = 57 + int(1.2 * math.sin(x * 0.075) +
                             0.8 * math.sin(x * 0.19 + 0.8))
            floors[x] = floor
            for y in range(floor, HEIGHT):
                depth = y - floor
                grain = (x * 37 + y * 19 + x * y * 3) % 97
                if depth == 0:
                    shade = 64 if grain < 22 else 63
                elif depth <= 2:
                    shade = 63 if grain < 17 else 62
                elif depth <= 4:
                    shade = 62 if grain < 83 else 61
                else:
                    shade = 61 if grain < 86 else 67
                sand[x * 10 + depth] = shade
        _BACKGROUND_TEXTURES = (water, floors, sand)
    return _BACKGROUND_TEXTURES


def _sprite(rows, ink):
    return bytes(v for y, row in enumerate(rows) for x, char in enumerate(row)
                 if char in ink for v in (x, y, ink[char]))


# Role indices, not palette indices: body, highlight, fin, marking, eye.
# All guided colours share these three poses, so colour variety adds no shapes.
_GUIDED_BODY = _sprite(("      HH     ", "    HHBBBH   ", "   HBBBMBBE  ",
                       "   BBBBBBBBB ", "    BBBBBFF  ", "     FFF     "),
                      {"B": 0, "H": 1, "F": 2, "M": 3, "E": 4})
_GUIDED_FRAMES = tuple(_GUIDED_BODY + bytes((0, 1 + shift, 2, 1, 2 + shift, 2,
                                            2, 3, 2, 1, 4 + shift, 2, 0, 5 + shift, 2))
                       for shift in (-1, 0, 1))
_GUIDED_PALETTES = (
    (70, 71, 32, 80, 28),  # Lagoon: turquoise/mint/blue.
    (74, 75, 68, 56, 28),  # Sunset: orange/peach/burgundy.
    (72, 73, 76, 36, 28),  # Orchid: violet/lavender/pink.
    (78, 79, 70, 11, 28),  # Emerald: green/lime/teal.
    (56, 57, 74, 58, 28),  # Lemon: yellow/cream/orange.
    (76, 77, 72, 48, 28),  # Coral: rose/light pink/plum.
    (43, 33, 32, 42, 28),  # Arctic: slate/ice blue/white.
    (80, 32, 81, 70, 28),  # Midnight: navy/cobalt/gold.
)


def _guided_palette(trip):
    seed = (trip * 1103515245 + 12345) & 0xffffffff
    return _GUIDED_PALETTES[(seed >> 16) % len(_GUIDED_PALETTES)]


def guided_fish(seconds, pixel):
    age = (seconds - 18) % 110
    if age >= 32:
        return
    trip = int((seconds - 18) // 110)
    direction = 1 if trip % 2 == 0 else -1
    colours = _guided_palette(trip)
    x = _crossing(age, 32, 14, direction)
    y = 17 + (trip * 7) % 23 + int(2 * math.sin(age * .65 + trip))
    sprite = _GUIDED_FRAMES[(1, 2, 1, 0)[int(age * 3) % 4]]
    for at in range(0, len(sprite), 3):
        px, py = x + direction * sprite[at], y + sprite[at + 1]
        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
            pixel(px, py, colours[sprite[at + 2]])


_GREEN_FISH = _sprite(("     HH   ", "T   HBBBE ", "TT BBBBBBB", "T   BBBBF ", "     FF   "),
                      {"H": 79, "B": 78, "T": 38, "F": 55, "E": 28})
_GOLDFISH = _sprite(("      FF    ", "TT   HHHH   ", " T  HBBBEH  ", "TT BBBBBBBH ",
                    " T  BBBBBF  ", "TT   FFFF   ", "      FF    "),
                   {"F": 75, "H": 57, "B": 74, "T": 54, "E": 28})
_TINY_FISH = _sprite(("T HH ", "TTBBE", "T BB "), {"T": 38, "H": 79, "B": 78, "E": 28})
_TINY_GOLD = _sprite(("T HH ", "TTBBE", "T BB "), {"T": 54, "H": 75, "B": 74, "E": 28})
_SHELL = _sprite(("    HHHH   ", "  HHSSSSHH ", " HSSDDSSSH ", " HSDSSDSDSH",
                  " HSDSSDSSH ", "  HSSSSSH  ", "   HHHHH   "),
                 {"H": 75, "S": 74, "D": 58})
_SNAIL_ROWS = ("          EE EE ", "          EE EE ", "    HHH    S S  ",
               "   HSSSH   S S  ", "  HSDDSDH  SSS  ", "  HSDSDSHSSSSSS ",
               "   HSSSHTSTSTSTS", "    HHHTTTTTTTTT", "     TTTTTTTTTT ")
_SNAIL = _sprite(_SNAIL_ROWS, {"E": 83, "S": 87, "H": 86, "D": 85, "T": 88})


def _outlined_sprite(sprite, outline):
    # Bake a thin four-neighbour silhouette once, avoiding per-frame work.
    occupied = {(sprite[at], sprite[at + 1]) for at in range(0, len(sprite), 3)}
    edge = set()
    for x, y in occupied:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if (x + dx, y + dy) not in occupied:
                edge.add((x + dx, y + dy))
    commands = bytearray()
    for x, y in sorted(edge):
        commands.extend(bytes((x + 1, y + 1, outline)))
    for at in range(0, len(sprite), 3):
        commands.extend(bytes((sprite[at] + 1, sprite[at + 1] + 1, sprite[at + 2])))
    return bytes(commands)


_SNAIL_GLOW = _outlined_sprite(_SNAIL, PEARL_HALO)
# One dark pupil inside each 2x2 eye; clockwise movement, baked once.
_SNAIL_EYE_POSES = tuple(_SNAIL_GLOW + bytes((11 + dx, 1 + dy, 28, 14 + dx, 1 + dy, 28))
                         for dx, dy in ((0, 0), (1, 0), (1, 1), (0, 1)))
_GHOST_ROWS = ("    DDDD    ", "   DWWWWD   ", "  DWWWWWWD  ", " DWWWWWWWWD ",
               " DWWDWWDWWD ", " DWWDWWDWWD ", " DWWWWWWWWD ", " DWWWDDWWWD ",
               " DWWWDDWWWD ", " DWWWWWWWWD ", "DWWWWWWWWWWD", " DWWDWWDWWD ",
               "  DD DD DD  ")


def _ghost_sprite(pose):
    rows = list(_GHOST_ROWS)
    if pose:
        rows[7] = " DWWWWWWWWD "
        rows[8] = " DWWWDDWWWD " if pose == 1 else " DWWWWWWWWD "
    if pose == 2:
        rows[5] = " DWWWWWWWWD "  # Half-closed eyes.
    elif pose == 3:
        rows[4] = " DWWWWWWWWD "
        rows[5] = " DWWDDWDDWD "  # Blink: small horizontal eyelids.
    if pose % 2:
        rows[11] = "DWWWDWWDWWWD"
        rows[12] = " DD  DD  DD "
    return _sprite(rows, {"D": 28, "W": 89})


_GHOST_POSES = tuple(_ghost_sprite(pose) for pose in range(4))


def _ghost_pose(age):
    blink = age % 6
    if blink < .25:
        return 3
    if blink < .5 or blink > 5.75:
        return 2
    return int(age * 2) % 2  # Gentle mouth/hem alternation between blinks.


_OYSTER_CLOSED = _sprite(("    HHHHH    ", "  HHSSSSSHH  ", " HSSSDSSDSSH ",
                         "  HSSSSSSSH  ", "   HHHHHHH   "), {"H": 66, "S": 65, "D": 67})
_OYSTER_OPEN = _sprite(("    HHHHH    ", "  HHSSSSSHH  ", " HSSSDSSDSSH ",
                       "  HHHHHHHHH  ", "             ", "             ",
                       " HHH     HHH ", "HSSSSHHHSSSSH", " HHHHHHHHHHH "),
                      {"H": 66, "S": 65, "D": 67})
_OYSTER_CRACKED = _sprite(("    HHHHH    ", "  HHSSSSSHH  ", " HSSSDSSDSSH ",
                          "  HHHHHHHHH  ", "             ", " HSSSSSSSSSH ", "  HHHHHHHHH  "),
                         {"H": 66, "S": 65, "D": 67})
_OYSTER_HALF = _sprite(("    HHHHH    ", "  HHSSSSSHH  ", " HSSSDSSDSSH ",
                       "  HHHHHHHHH  ", "             ", "             ",
                       " HSSSSSSSSSH ", "  HHHHHHHHH  "), {"H": 66, "S": 65, "D": 67})
_OYSTER_POSES = (_OYSTER_CLOSED, _OYSTER_CRACKED, _OYSTER_HALF, _OYSTER_OPEN)


def _opening_pose(age, start, opened, close, end):
    """Four reversible poses: closed, cracked, half open and fully open."""
    if age < start or age >= end:
        return 0
    if age < opened:
        return 1 if age < (start + opened) / 2 else 2
    if age < close:
        return 3
    return 2 if age < (close + end) / 2 else 1


_PEARL = _sprite((" HHH ", "HPPPH", " HHH "), {"H": PEARL_HALO, "P": PEARL_CORE})
_BOTTOM_PLANTS = (
    _sprite(("  L    L ", "  LL  LL ", "   L  L  ", "L  LL L L", "LL  L LLL",
             " LL L LL ", "  LLLLL  ", "   LLL   "), {"L": 78}),
    _sprite(("    H    ", "   HLL   ", "    L    ", " HH L HH ", "  LLLLL  ",
             "    L    ", " HL L LH ", "  LLLLL  ", "    L    "), {"H": 79, "L": 10}),
    _sprite((" H     H ", " HL   LH ", "  L H L  ", "H LLHLL H", " HL L LH ",
             "  LLLLL  ", "   LLL   ", "    L    "), {"H": 55, "L": 38}),
)


def _blit(sprite, x, y, pixel, direction=1):
    for at in range(0, len(sprite), 3):
        px, py = x + direction * sprite[at], y + sprite[at + 1]
        if 0 <= px < WIDTH and 0 <= py < HEIGHT:
            pixel(px, py, sprite[at + 2])


def _crossing(age, duration, margin, direction):
    x = int(-margin + (WIDTH + 2 * margin) * age / duration)
    return x if direction == 1 else WIDTH - 1 - x


_BUBBLE_DOT = b'\x00\x00;'
_HERMIT_BODY = _sprite((" H     H ", "  RHHHR  ", " HRRRRRH ", " R R R R "), {"R": 74, "H": 75})
_RESIDENT_TIPS = tuple(tuple(bytes((0, 1 + kick, shade)) for kick in range(2))
                       for shade in (55, 54))
_HERMIT_LEGS = (
    _sprite(("  RRRRRRR  ", " H R R R H ", "  H H H H  "), {"R": 74, "H": 75}),
    _sprite(("  RRRRRRR  ", "  HR R RH  ", " H H H H H "), {"R": 74, "H": 75}),
)


def _jelly_bell(half_width):
    commands = bytearray()
    for dx in range(-half_width, half_width + 1):
        edge = abs(dx)
        top = -3 if edge <= 1 else -2 if edge <= 3 else -1
        bottom = 1 if edge == half_width else 2
        for dy in range(top, bottom + 1):
            if edge == half_width and dy == top:
                continue
            role = 1 if dy == top or dy == bottom else (0 if (dx + dy) % 7 else 2)
            commands.append(dx + 8)
            commands.append(dy + 8)
            commands.append(role)
    return bytes(commands)


_JELLY_BELLS = (_jelly_bell(4), _jelly_bell(5))


_ORNAMENT_DITHER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def _ornament_layout(seconds):
    cycle = int(seconds // 360)
    age = seconds - cycle * 360
    opacity = min(1.0, (344 - age) / 32)
    if cycle:
        opacity = min(opacity, (age - 16) / 32)
    # Shared layout prevents ornaments choosing the same clearing.
    left = (38, 40, 42)[cycle % 3]
    right = (83, 84, 85)[cycle % 3]
    chest, oyster = (left, right) if cycle % 2 == 0 else (right, left)
    return chest, oyster - 6, int(max(0.0, opacity) * 16)


def extra_life(t, pixel, night=False):
    """Small cached sprites; visitors have independent, sparse schedules."""
    guided_fish(t, pixel)
    # Two residents cross completely before changing direction.
    for i, sprite in enumerate((_GREEN_FISH, _GOLDFISH)):
        clock = t + i * 23
        duration = 53 + i * 8
        trip = int(clock // duration)
        direction = 1 if trip % 2 == 0 else -1
        x = _crossing(clock % duration, duration, 15, direction)
        y = 13 + i * 23 + int(2 * math.sin(t * .65 + i * 2))
        _blit(sprite, x, y, pixel, direction)
        # A little moving tail tip keeps the cached bodies alive.
        _blit(_RESIDENT_TIPS[i][int(t * 3 + i) % 2],
              x - direction, y, pixel, direction)

    age = (t - 48) % 230
    if age < 32:
        trip = int((t - 48) // 230)
        direction = 1 if trip % 2 == 0 else -1
        x = _crossing(age, 32, 65, direction)
        family = trip % 2 == 1
        if family:
            _blit(_GOLDFISH, x, 27, pixel, direction)
        for i in range(6):
            lag = 18 + (i // 2) * 13 if family else (i // 3) * 13
            y = 28 + (i % (2 if family else 3)) * 5
            y += int(math.sin(t * 1.2 + i * 1.7))
            _blit(_TINY_GOLD if family else _TINY_FISH, x - direction * lag, y, pixel, direction)

    # A quiet snail passes independently of the crab and hermit encounter.
    age = (t - 265) % 610
    if age < 115:
        direction = 1 if int((t - 265) // 610) % 2 == 0 else -1
        x = _crossing(age, 115, 18, direction)
        # Advance pupils with each pixel of travel rather than flickering
        # them on every display refresh while the snail is stationary.
        eye_pose = int(age * (WIDTH + 36) / 115) % 4
        _blit(_SNAIL_EYE_POSES[eye_pose], x - direction, 48, pixel, direction)

    # The large oyster occupies the former skull clearing; the pearl stays luminous at night.
    age = (t - 90) % 95
    pose = _opening_pose(age, 8, 12, 29, 33)
    # Relocate only across the shared fully invisible transition.
    _, oyster_x, opacity = _ornament_layout(t)
    top = 59 - (5, 7, 8, 9)[pose]
    if opacity:
        if opacity == 16:
            paint = pixel
        else:
            def paint(x, y, index):
                if _ORNAMENT_DITHER[y & 3][x & 3] < opacity:
                    pixel(x, y, index)
        _blit(_OYSTER_POSES[pose], oyster_x, top, paint)
        if pose >= 2:
            _blit(_PEARL, oyster_x + 4, top + 4, paint)

    # Empty shell, approach, pause inside, then scuttle away carrying it.
    age = (t - 350) % 540
    if age < 90:
        direction = 1 if int((t - 350) // 540) % 2 == 0 else -1
        home = 68 if direction == 1 else 59
        shell_x = home if age < 38 else home + direction * int((age - 38) * 3)
        opacity = min(16, int(age * 2))  # Eight-second arrival before the crab approaches.
        if opacity == 16:
            shell_pixel = pixel
        else:
            def shell_pixel(x, y, index):
                if _ORNAMENT_DITHER[y & 3][x & 3] < opacity:
                    pixel(x, y, index)
        _blit(_SHELL, shell_x, 51, shell_pixel, direction)
        if 12 <= age < 29:
            crab_x = home - direction * int((29 - age) * 5)
            _blit(_HERMIT_BODY, crab_x, 55, pixel, direction)
        elif age >= 38:
            kick = int(t * 6) & 1
            _blit(_HERMIT_LEGS[kick], shell_x, 57, pixel, direction)

    # Night-only cartoon ghost: gentle bob, alternating crossings, no trail.
    age = (t - 120) % 480
    if night and age < 60:
        direction = 1 if int((t - 120) // 480) % 2 == 0 else -1
        fraction = age / 60
        eased = fraction + .55 * math.sin(4 * math.pi * fraction) / (4 * math.pi)
        x = _crossing(eased * 60, 60, 15, direction)
        y = 46 + int(math.sin(age * .5))
        _blit(_GHOST_POSES[_ghost_pose(age)], x, y, pixel, direction)


_CHEST_TICK = None
_CHEST_COMMANDS = b""


def chest_steps(seconds, pixel):
    t = float(seconds)
    def scenery_pixel(x, y, colour, opacity):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and _ORNAMENT_DITHER[y & 3][x & 3] < opacity:
            pixel(x, y, colour)
    # Larger banded chest in the left clearing. Oyster is foreground
    # animation in the right clearing, so its pearl never inherits a stale pose.
    chest = (
        "     DDDDDDDDD     ",
        "   DDWWYWWWYWWDD   ",
        "  DWWWYWWWWWYWWWD  ",
        " DWWWWYWWWWWYWWWWD ",
        " DYYYYYYYYYYYYYYYD ",
        " DYWWWYWWGWWYWWWYD ",
        " DYWWWYWWGWWYWWWYD ",
        " DYWWWYWWWWWYWWWYD ",
        "  DDDDDDDDDDDDDDD  ",
    )
    for site_id, (lo, hi) in enumerate(((40, 40),)):
        yield
        cx, _, opacity = _ornament_layout(t)
        furniture_name, sprite, ink = "chest", chest, {"D": 28, "Y": 56, "W": 58, "G": 34}
        # Treasure chests occasionally open for a few seconds.
        # The animation belongs to the chest's own appearance, so
        # dissolving/reappearing furniture doesn't inherit a random pose.
        chest_age = (t + site_id * 17.0) % 75.0
        chest_pose = _opening_pose(chest_age, 12, 28, 51, 67)
        chest_open = chest_pose == 3
        if chest_open:
            sprite = (
                "    DYYYYYYYYYD    ",
                "   DYWWYWWWYWWYD   ",
                "  DYWWWYWWWYWWWYD  ",
                "   DYYYYYYYYYYYD   ",
                "                   ",
                " DYYYYYYYYYYYYYYYD ",
                " DYWWWYWWGWWYWWWYD ",
                " DYWWWYWWGWWYWWWYD ",
                " DYWWWYWWWWWYWWWYD ",
                "  DDDDDDDDDDDDDDD  ",
            )
        elif chest_pose:
            # Two distinct intermediate lid angles. Eight-second holds
            # span cached background refreshes without extra foreground work.
            body_rows = chest[4:]
            if chest_pose == 1:
                sprite = ("    DDDDDDDDDDD    ", "  DDWWYWWWYWWWWDD  ",
                          " DYYYYYYYYYYYYYYYD ", "                   ") + body_rows
            else:
                sprite = ("     DYYYYYYYD     ", "   DDWWYWWWYWWDD   ",
                          " DYYYYYYYYYYYYYYYD ", "                   ",
                          "                   ") + body_rows
        width = max(len(row) for row in sprite)
        bottom = 58
        left = cx - width // 2
        top = bottom - len(sprite) + 1
        for xx in range(max(0, left + 1), min(WIDTH, left + width - 1)):
            if (xx + site_id) % 3 != 0:
                scenery_pixel(xx, bottom + 1, 60, opacity)
        for yy, row in enumerate(sprite):
            for xx, ch in enumerate(row):
                if ch != " ":
                    scenery_pixel(left + xx, top + yy, ink[ch], opacity)
        if chest_open:
            # A faint reflected pool on the nearby sand; the chest
            # itself retains the stronger warm golden sparkle.
            for glow_dx in range(-9, 10):
                gx = cx + glow_dx
                if 0 <= gx < WIDTH and (glow_dx + int(t * 2)) % 4 < 2:
                    scenery_pixel(gx, 60, 64 if abs(glow_dx) < 6 else 63, opacity)
            # Warm golden glow confined to the open chest, with tiny
            # sparkles and bubbles drifting upward. All use the same
            # ordered-dither opacity as the furniture.
            glow = TREASURE_GLOW
            for dx in range(3, width - 3):
                scenery_pixel(left + dx, top + 4, PEARL_CORE if dx % 3 == 0 else glow, opacity)
                if dx % 3 == 0:
                    scenery_pixel(left + dx, top + 5, TREASURE_GLOW, opacity)
            opening_age = chest_age - 28.0
            for bubble in range(4):
                rise = (opening_age * (2.0 + bubble * 0.55) + bubble * 4) % 24
                bx = cx + (-4, -1, 2, 4)[bubble] + int(
                    math.sin(opening_age * 1.5 + bubble) * 2)
                by = top + 4 - int(rise)
                if 0 <= bx < WIDTH and 0 <= by < HEIGHT:
                    scenery_pixel(bx, by, 27 if bubble % 2 else 55, opacity)
                    if bubble % 2 == 0 and bx + 1 < WIDTH:
                        scenery_pixel(bx + 1, by, 25, opacity)


def chest_commands(seconds):
    global _CHEST_TICK, _CHEST_COMMANDS
    tick = int(seconds * 2)
    if tick != _CHEST_TICK:
        commands = bytearray()
        def record(x, y, index):
            commands.append(x)
            commands.append(y)
            commands.append(index)
        for _ in chest_steps(tick / 2, record):
            pass
        _CHEST_COMMANDS = bytes(commands)
        _CHEST_TICK = tick
    return _CHEST_COMMANDS


_CORAL_KEY = None
_CORAL_COMMANDS = b""


def coral_commands(seconds, night=False):
    global _CORAL_KEY, _CORAL_COMMANDS
    key = (int(seconds), night)
    if key != _CORAL_KEY:
        commands = bytearray()
        def record(x, y, index):
            commands.append(x)
            commands.append(y)
            commands.append(index)
        for _ in coral_steps(key[0], record, night):
            pass
        _CORAL_COMMANDS = bytes(commands)
        _CORAL_KEY = key
    return _CORAL_COMMANDS


def coral_steps(seconds, pixel, night=False):
    t = float(seconds)
    # Stable pseudo-random choices: reproducible at any timestamp, no
    # mutable state or frame-to-frame jitter. Four-by-four ordered dither.
    dither = ((0, 8, 2, 10), (12, 4, 14, 6),
              (3, 11, 1, 9), (15, 7, 13, 5))

    def scenery(slot, duration, salt=0, fade_seconds=8.0):
        cycle = int(t // duration)
        age = t - cycle * duration
        # Scenery fades on both sides of a 2s clear interval; ornaments
        # need a longer fade to span several hardware background refreshes.
        # At startup everything
        # is already fully present; no initial fade-in.
        opacity = min(1.0, (duration - age - 2.0) / fade_seconds)
        if cycle > 0:
            opacity = min(opacity, (age - 2.0) / fade_seconds)
        seed = (cycle * 1103515245 + slot * 2654435761 + salt * 1013904223) & 0xffffffff
        return seed, int(max(0.0, opacity) * 16)

    def scenery_pixel(x, y, colour, opacity):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and dither[y & 3][x & 3] < opacity:
            pixel(x, y, colour)

    # Textured branching coral with shaded trunks, forks and polyp clusters.
    coral_patches = ((19, 57, 48, 49), (61, 58, 50, 51),
                     (107, 57, 52, 53))
    for coral_id, (anchor_x, base_y, shade, tip) in enumerate(coral_patches):
        yield
        seed, opacity = scenery(coral_id, 420 + coral_id * 75, 43)
        base_x = anchor_x + (seed % 7) - 3
        for branch in range(-3, 4):
            height = 5 + (branch * branch * 7 + base_x) % 7
            for step in range(height):
                xx = base_x + branch * step // 7 + (step // 4 if branch > 0 else -(step // 5))
                yy = base_y - step
                if 0 <= xx < WIDTH and 0 <= yy < HEIGHT:
                    scenery_pixel(xx, yy, tip if (step + branch) % 5 == 0 else shade, opacity)
                    if step < height - 3 and branch % 2 == 0 and xx + 1 < WIDTH:
                        scenery_pixel(xx + 1, yy, (tip if step % 9 == 0 else shade) if night else (tip if step % 4 == 0 else shade), opacity)
                if step > 3 and step % 4 == 0:
                    for side in (-1, 1):
                        tx, ty = xx + side, yy - 1
                        if 0 <= tx < WIDTH and 0 <= ty < HEIGHT:
                            scenery_pixel(tx, ty, tip, opacity)
            xx = base_x + branch * height // 7 + (height // 4 if branch > 0 else -(height // 5))
            yy = base_y - height
            for ox, oy in ((0, 0), (-1, 0), (1, 0), (0, -1)):
                if 0 <= xx + ox < WIDTH and 0 <= yy + oy < HEIGHT:
                    scenery_pixel(xx + ox, yy + oy, tip, opacity)

def background_steps(seconds, pixel, night=False, water_row=None, plants=True, ornaments=True):
    """Paint scenery incrementally; consume fully for the desktop scene."""
    t = float(seconds)
    water, floors, sand = background_textures()
    row = bytearray(WIDTH)
    # Three soft shafts drift across the water. Only three sine calls
    # per frame, rather than nested trigonometry for every pixel.
    centres = (24, 65, 108)
    offsets = [int(10 * math.sin(t * 0.10 + i * 2.1)) for i in range(3)]
    caustic_shift = int(t * 2.4)
    # Three slow, widening underwater shafts. Their paths are gently
    # curved rather than rigid columns; ordered dithering feathers the
    # edges without introducing brighter RGB colours.
    # Precompute the geometry once per scanline for MicroPython.
    for y in range(HEIGHT):
        yield
        offset = y * WIDTH
        row[:] = water[offset:offset + WIDTH]
        drift = int(2 * math.sin(t * 0.045 + y * 0.065))
        shaft_centres = (centres[0] + offsets[0] - y // 7 + drift,
                         centres[1] + offsets[1] + drift,
                         centres[2] + offsets[2] + y // 8 - drift)
        shaft_width = 6 + y // 8
        # Later shafts paint first. Earlier shafts then overwrite even
        # undimmed edge pixels, preserving the original overlap priority.
        for shaft_id in range(2, -1, -1):
            centre = shaft_centres[shaft_id]
            for x in range(max(0, centre - shaft_width + 1),
                           min(WIDTH, centre + shaft_width)):
                inner = shaft_width - abs(x - centre)
                shade = water[offset + x]
                threshold = (x * 3 + y * 5 + shaft_id * 7) & 15
                if inner >= 7:
                    shade = max(0, shade - 2)
                elif inner >= 4 or threshold < inner * 2:
                    shade = max(0, shade - 1)
                row[x] = shade
        if water_row is None:
            for x in range(WIDTH):
                pixel(x, y, row[x])
        else:
            # Hardware copies a whole row in C instead of 128 callbacks.
            water_row(y, row)

    # Warm, gently layered sand rather than noisy brown gravel.
    # One continuous crest, sparse ripples, and darker sediment beneath.
    for x in range(WIDTH):
        yield
        floor = floors[x]
        for y in range(floor, HEIGHT):
            depth = y - floor
            shade = sand[x * 10 + depth]
            # Broken, crossing caustic ribbons glide over the sand.
            # Keep the existing palette: no extra brightness.
            if depth <= 2:
                wave_a = (x + caustic_shift + (x // 19) * 4) % 31
                wave_b = (x - caustic_shift // 2 + y * 3) % 43
                if ((wave_a < 3 or wave_b < 2) and
                        ((x * 3 + y * 7 + caustic_shift) & 7) < 5):
                    shade = 66 if depth == 0 else 64
            pixel(x, y, shade)
        # Discontinuous wind-shaped ridges on the sand surface.
        ripple = (x + 3 * (x // 23)) % 29
        if ripple < 7 and floor + 1 < HEIGHT:
            pixel(x, floor + 1, 64 if ripple < 3 else 63)

    # Small embedded stones, shells and scattered grains. Keep them sparse
    # so the sand still reads as a surface rather than pixel noise.
    for x in range(4, WIDTH - 2, 7):
        yield
        floor = 57 + int(1.4 * math.sin(x * 0.095) + 1.2 * math.sin(x * 0.23))
        y = min(HEIGHT - 2, floor + 1 + (x * 13 % 3))
        kind = (x * 17) % 9
        if kind < 3:
            pixel(x, y, 65)
            pixel(x + 1, y, 60)
        elif kind == 4:
            pixel(x, y, 66)
            pixel(x + 1, y, 67)
            if y > 0:
                pixel(x, y - 1, 66)

    if plants:
        for _ in plant_steps(seconds, pixel, night):
            yield
    if ornaments:
        _blit(coral_commands(seconds, night), 0, 0, pixel)
        _blit(chest_commands(seconds), 0, 0, pixel)



_KELP_TICK = None
_KELP_PIXELS = b""


def _kelp_steps(seconds, pixel):
    t = float(seconds)
    # Stable pseudo-random choices: reproducible at any timestamp, no
    # mutable state or frame-to-frame jitter. Four-by-four ordered dither.
    dither = ((0, 8, 2, 10), (12, 4, 14, 6),
              (3, 11, 1, 9), (15, 7, 13, 5))

    def scenery(slot, duration, salt=0):
        cycle = int(t // duration)
        age = t - cycle * duration
        # Old scenery dissolves over 8s, leaving a 2s clear interval.
        # The new object then materialises over 8s. At startup everything
        # is already fully present; no initial fade-in.
        opacity = min(1.0, (duration - age - 2.0) / 8.0)
        if cycle > 0:
            opacity = min(opacity, (age - 2.0) / 8.0)
        seed = (cycle * 1103515245 + slot * 2654435761 + salt * 1013904223) & 0xffffffff
        return seed, int(max(0.0, opacity) * 16)

    def scenery_pixel(x, y, colour, opacity):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and dither[y & 3][x & 3] < opacity:
            pixel(x, y, colour)

    # Rooted kelp with independently swaying stems and short side fronds.
    # A handful of sine calls per stalk; the base stays fixed.
    for plant_id, (anchor, nominal_height) in enumerate(
            ((5, 28), (22, 21), (58, 24), (102, 25), (123, 31))):
        yield
        seed, opacity = scenery(plant_id, 390 + plant_id * 83, 71)
        base_x = anchor + seed % 7 - 3
        if opacity == 0:
            continue
        height = nominal_height + (seed >> 9) % 7 - 3
        phase = (t / FPS) * (0.65 + plant_id * 0.075) + plant_id * 1.9
        sway = math.sin(phase)
        curl = math.sin(phase * 0.57 + 1.4)
        for i in range(height):
            y = 58 - i
            # Displacement increases smoothly towards the flexible tip.
            lean = (sway * 3.0 + curl * 1.3) * i * i / (height * height)
            x = base_x + int(lean + 0.5 if lean >= 0 else lean - 0.5)
            shade = PLANT + (i // 7) % 4
            scenery_pixel(x, y, shade, opacity)
            # Short alternating fronds; longer near the middle.
            if i > 5 and i < height - 2 and i % 5 == plant_id % 5:
                side = 1 if (i // 5 + plant_id) % 2 else -1
                length = 2 + (i % 3)
                for tip in range(1, length + 1):
                    scenery_pixel(x + side * tip, y - tip // 2,
                                  PLANT + 2 if tip == length else PLANT + 1,
                                  opacity)
            if i == height - 1:
                scenery_pixel(x, y - 1, PLANT + 3, opacity)

def _cached_kelp(seconds):
    global _KELP_TICK, _KELP_PIXELS
    tick = int(seconds)
    if tick != _KELP_TICK:
        commands = bytearray()
        def record(x, y, index):
            commands.append(x)
            commands.append(y)
            commands.append(index)
        for _ in _kelp_steps(tick, record):
            pass
        _KELP_PIXELS = bytes(commands)
        _KELP_TICK = tick
    return _KELP_PIXELS


def _legacy_plant_steps(seconds, pixel, night=False):
    """Animate plants over clean cached scenery on every hardware frame."""
    t = float(seconds)
    # Stable pseudo-random choices: reproducible at any timestamp, no
    # mutable state or frame-to-frame jitter. Four-by-four ordered dither.
    dither = ((0, 8, 2, 10), (12, 4, 14, 6),
              (3, 11, 1, 9), (15, 7, 13, 5))

    def scenery(slot, duration, salt=0):
        cycle = int(t // duration)
        age = t - cycle * duration
        # Old scenery dissolves over 8s, leaving a 2s clear interval.
        # The new object then materialises over 8s. At startup everything
        # is already fully present; no initial fade-in.
        opacity = min(1.0, (duration - age - 2.0) / 8.0)
        if cycle > 0:
            opacity = min(opacity, (age - 2.0) / 8.0)
        seed = (cycle * 1103515245 + slot * 2654435761 + salt * 1013904223) & 0xffffffff
        return seed, int(max(0.0, opacity) * 16)

    def scenery_pixel(x, y, colour, opacity):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and dither[y & 3][x & 3] < opacity:
            pixel(x, y, colour)

    # All three anemones share tentacle motion, but have different roots
    # and lengths. Compute each displacement once instead of per plant.
    sin = math.sin
    leans = tuple(tuple(int(sin(t * 1.1 + tentacle * 0.8 + step * 0.3) * step / 4)
                        for step in range(10)) for tentacle in range(7))

    # Replay the same pose until the next one-second animation tick.
    _blit(_cached_kelp(seconds), 0, 0, pixel)
    # Three compact plant forms: ribbon grass, broad leaves and a fan.
    # One sway calculation per plant; the base stays fixed on the sand.
    for kind, anchor in enumerate((7, 57, 119)):
        yield
        sprite = _BOTTOM_PLANTS[kind]
        height = 9 if kind == 1 else 8
        lean = int(2 * math.sin(t * .75 + kind * 2.1))
        for at in range(0, len(sprite), 3):
            row = sprite[at + 1]
            dx = int(lean * (height - 1 - row) / (height - 1))
            x, y = anchor - 4 + sprite[at] + dx, 59 - height + row
            if 0 <= x < WIDTH:
                pixel(x, y, sprite[at + 2])



    # Anemones and seaweed have independent lifetimes and positions.
    for plant_id, (anchor, base_y, shade, tip) in enumerate(
            ((16, 58, 48, 49), (64, 58, 50, 51), (113, 58, 52, 53))):
        yield
        seed, opacity = scenery(plant_id, 510 + plant_id * 67, 59)
        if opacity == 0:
            continue
        paint = pixel if opacity == 16 else lambda x, y, colour: scenery_pixel(x, y, colour, opacity)
        base_x = anchor + seed % 7 - 3
        for tentacle in range(7):
            offset = tentacle - 3
            length = 6 + (tentacle * 3 + base_x) % 5
            motion = leans[tentacle]
            for step in range(length):
                lean = motion[step]
                xx = base_x + offset + lean + offset * step // 14
                paint(xx, base_y - step, tip if step >= length - 2 else shade)



_FOLIAGE_TICK = None
_FOLIAGE_BUFFER = None


_DENSE_FOLIAGE = None


def _build_dense_foliage(t):
    layer = bytearray(b"\xff" * (WIDTH * HEIGHT))
    def paint(x, y, index):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            layer[y * WIDTH + x] = index
    # Dim rear stems provide depth without hiding the fish in bright foliage.
    for stem, anchor in enumerate((3, 8, 14, 20, 24, 34, 43, 54, 58, 62, 66, 70, 79, 88, 98, 103, 110, 117, 123, 127)):
        height = (34, 45, 29, 48, 38, 43, 52, 35)[stem % 8]
        sway = math.sin(t * .32 + stem * 1.73)
        curl = math.sin(t * .21 + stem * .91)
        for step in range(height):
            y = 57 - step
            x = anchor + int((sway * 3 + curl) * step / height)
            shade = 8 + stem % 3
            paint(x, y, shade)
            kind = stem % 3
            if kind == 0:  # Long ribbon leaves, shaded along one edge.
                paint(x + 1, y, 10 if step % 5 else 11)
                if step > 5:
                    paint(x + 2, y, 9)
            elif kind == 1 and step > 3 and step % 3 == 0:  # Feathery fronds.
                reach = 2 + (height - step) // 8
                for side in (-1, 1):
                    for leaf in range(1, reach + 1):
                        paint(x + side * leaf, y - leaf // 2, 9 if leaf < reach else 10)
            elif kind == 2 and step > 4 and step % 6 == 0:  # Broad paired leaves.
                for side in (-1, 1):
                    for leaf in range(1, 6):
                        paint(x + side * leaf, y - leaf // 3, 78 if leaf == 5 else 11)
                        if leaf < 5:
                            paint(x + side * leaf, y - leaf // 3 - 1, 10)
    # Moss and short grass thicken the bottom around, not inside, clearings.
    for anchor in (1, 5, 10, 15, 20, 25, 54, 58, 63, 67, 71, 99, 104, 109, 114, 119, 124, 127):
        sway = int(2 * math.sin(t * .45 + anchor))
        for blade in range(-2, 3):
            height = 4 + (anchor + blade * 3) % 6
            for step in range(height):
                paint(anchor + blade + int(sway * step / height), 58 - step,
                      11 if step == height - 1 else 10)
    return bytes(layer)


def foliage_buffer(seconds):
    """Reuse four rear-garden poses; refresh the composed layer at 2 Hz."""
    global _FOLIAGE_TICK, _DENSE_FOLIAGE, _FOLIAGE_BUFFER
    tick = int(seconds * 2)
    if tick == _FOLIAGE_TICK:
        return _FOLIAGE_BUFFER
    if _DENSE_FOLIAGE is None:
        _DENSE_FOLIAGE = tuple(_build_dense_foliage(t) for t in (0, 1, 2, 3))
    t = tick / 2
    if _FOLIAGE_BUFFER is None:
        _FOLIAGE_BUFFER = bytearray(WIDTH * HEIGHT)
    layer = _FOLIAGE_BUFFER
    layer[:] = _DENSE_FOLIAGE[(0, 1, 2, 3, 2, 1)[tick % 6]]
    def paint(x, y, index):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            layer[y * WIDTH + x] = index
    for _ in _legacy_plant_steps(t, paint):
        pass
    _FOLIAGE_TICK = tick
    return layer


def plant_steps(seconds, pixel, night=False):
    """Replay the cached foliage layer; all foliage poses update twice a second."""
    layer = foliage_buffer(seconds)
    for offset, index in enumerate(layer):
        if index != 255:
            pixel(offset % WIDTH, offset // WIDTH, index)
    yield


BAKED_MAGIC = b"FTBG\x01\x80\x40\x04"
_BAKED_FRAMES = None
_BAKED_ATTEMPTED = False
_BAKED_ERROR = None


def load_backgrounds(path="backgrounds.bin"):
    """Validate and load four complete indexed backgrounds once at startup."""
    global _BAKED_FRAMES, _BAKED_ATTEMPTED, _BAKED_ERROR
    if _BAKED_ATTEMPTED:
        return _BAKED_FRAMES is not None
    _BAKED_ATTEMPTED = True
    try:
        import hashlib
        import gc
        with open(path, "rb") as source:
            header = source.read(72)
            if len(header) != 72 or header[:8] != BAKED_MAGIC:
                raise ValueError("Unsupported background asset")
            palette = bytes(component for colour in BASE_PALETTE for component in colour)
            if header[8:40] != hashlib.sha256(palette).digest():
                raise ValueError("Background palette mismatch; rebuild asset")
            gc.collect()
            frames = []
            digest = hashlib.sha256()
            for _ in range(4):
                frame = source.read(WIDTH * HEIGHT)
                if len(frame) != WIDTH * HEIGHT or max(frame) >= len(BASE_PALETTE):
                    raise ValueError("Invalid background pixels")
                digest.update(frame)
                frames.append(frame)
            if source.read(1) or digest.digest() != header[40:72]:
                raise ValueError("Background checksum mismatch")
        _BAKED_FRAMES = tuple(frames)
        _BAKED_ERROR = None
        return True
    except (OSError, ValueError, MemoryError) as error:
        _BAKED_ERROR = str(error)
        return False


def background_frame(seconds):
    if not _BAKED_ATTEMPTED:
        load_backgrounds()
    if _BAKED_FRAMES is None:
        return None
    return _BAKED_FRAMES[(0, 1, 2, 3, 2, 1)[int(seconds * 2) % 6]]


def resident_species(fish_id, journey):
    # Dedicated special-species slots prevent simultaneous clownfish/angelfish
    # duplication while each slot still varies its silhouette between trips.
    choices = ((3, 0), (1, 0, 2), (4, 2), (7, 1, 7), (5, 0), (6, 1, 6))
    roster = choices[fish_id]
    return roster[journey % len(roster)]


def resident_route(fish_id, cycle, fraction, height):
    entry = 5 + (fish_id * 6 + cycle * 11) % 38
    exit = 5 + (fish_id * 6 + cycle * 7 + 13) % 38
    ease = fraction * fraction * (3 - 2 * fraction)
    return max(3, min(HEIGHT - height - 8, int(entry + (exit - entry) * ease)))


def submarine_motion(fraction, seed):
    cycles = 2 if seed % 2 else 3
    variation = .40 + (seed % 3) * .10
    return fraction + variation * math.sin(cycles * 6.2831853 * fraction) / (cycles * 6.2831853)


_JELLY_PALETTES = ((70, 77, 57), (72, 79, 77), (76, 71, 75), (54, 73, 57))


def render(seconds, pixel, night=False, submarine_at=None, submarine_direction=None,
           feeding_age=None, submarine_colour=None, background=True, plants=False, ornaments=True):
    """Draw one indexed-colour frame using pixel(x, y, palette_index).

    The scene is deterministic for a given timestamp. This is a first
    prototype, not the final fish artwork or hardware driver.
    """
    t = float(seconds)
    if background:
        baked = background_frame(seconds)
        if baked is None:
            for _ in background_steps(seconds, pixel, night, ornaments=ornaments):
                pass
        else:
            for offset, index in enumerate(baked):
                pixel(offset % WIDTH, offset // WIDTH, index)
            if ornaments:
                _blit(coral_commands(seconds, night), 0, 0, pixel)
                _blit(chest_commands(seconds), 0, 0, pixel)
    if plants and not background:
        for _ in plant_steps(seconds, pixel, night):
            pass
    if not background and ornaments:
        _blit(coral_commands(seconds, night), 0, 0, pixel)
        _blit(chest_commands(seconds), 0, 0, pixel)
    # Resident fish use varied swimming lanes on each complete journey.
    # Fish silhouettes adapted from Weather-matrix-display/main.py:
    # 9/11/13px body widths, 5/6/7px heights, tapered body, triangular
    # oscillating tail, fin, eye and gill. Recoloured for indexed rendering.
    # body, highlight, tail, marking; palette variations independent of species.
    fish_colours = ((32, 33, 34, 35), (36, 37, 33, 34),
                    (38, 39, 36, 37), (40, 41, 34, 42),
                    (34, 35, 32, 33), (42, 43, 38, 39),
                    (20, 22, 34, 35), (21, 23, 40, 41))
    fish_specs = ((0.0, 18, 7, 1, 0, 0), (1.7, 41, 31, -1, 1, 1),
                  (3.3, 70, 14, 1, 2, 2), (5.0, 105, 38, -1, 3, 1),
                  (2.6, 9, 44, 1, 4, 0), (4.1, 91, 23, -1, 5, 1))
    widths = (9, 11, 13, 11, 11, 12, 13, 12)
    heights = (5, 6, 7, 11, 9, 4, 9, 7)
    tail_frames = (0, 1, 0, -1)
    for fish_id, (phase, origin_x, y0, initial_dir, colour, species) in enumerate(fish_specs):
        body, highlight, tail, marking = fish_colours[colour]
        # Choose the silhouette only at the start of a complete journey:
        # never transform a fish while it is visible.
        journey = int((t + phase * 3.7) // (36 + fish_id * 2))
        species = resident_species(fish_id, journey)
        if species == 3:
            body, highlight, tail, marking = _guided_palette(journey // 2 + 3)[:4]
        if species == 4 and journey % 4 >= 2:
            # Warm gold/orange variant selected only between journeys.
            body, highlight, tail, marking = 74, 75, 54, 68
        width = widths[species]
        height = heights[species]
        # Each journey starts and ends COMPLETELY offscreen, so the next
        # itinerary cannot pop into existence halfway across the display.
        duration = 36 + fish_id * 2
        clock = t + phase * 3.7
        cycle = int(clock // duration)
        age = clock % duration
        fraction = age / duration
        direction = initial_dir if cycle % 2 == 0 else -initial_dir
        enters_top = (fish_id + cycle) % 4 == 0
        leaves_top = (fish_id + cycle) % 5 == 2
        # Deterministic depth variation per journey; no mid-screen jumps.
        # Each trip uses a distinct entry/exit lane and smoothly joins them.
        lane = resident_route(fish_id, cycle, fraction, height)
        # Smooth, low-amplitude vertical movement; the fish remains in its lane.
        # Slow vertical drift and a gentle acceleration/deceleration
        # within each journey, avoiding sudden changes of heading.
        swim_y = lane + int(2 * math.sin(t * 0.65 + phase) +
                            2 * math.sin(fraction * 6.283 + phase))
        if enters_top:
            # Enter vertically at a stable horizontal position, then cruise
            # across the aquarium and depart fully beyond the opposite side.
            entry_x = 8 + (origin_x + cycle * 29 + fish_id * 17) % 100
            exit_x = WIDTH + width + 2 if direction == 1 else -width - 3
            if age < 7:
                x = entry_x
                f = age / 7.0
                ease = f * f * (3 - 2 * f)
                y = int(-height - 3 + (swim_y + height + 3) * ease)
            else:
                f = (age - 7) / (duration - 7)
                x = int(entry_x + (exit_x - entry_x) * (f + 0.025 * math.sin(f * 6.283)))
                y = swim_y
        else:
            # Side entrance; optionally leave through the top instead of
            # crossing to the far side.
            entry_x = -width - 3 if direction == 1 else WIDTH + width + 3
            if leaves_top:
                exit_x = 8 + (origin_x + cycle * 31 + fish_id * 19) % 100
                if age < duration - 7:
                    f = age / (duration - 7)
                    x = int(entry_x + (exit_x - entry_x) * (f + 0.025 * math.sin(f * 6.283)))
                    y = swim_y
                else:
                    x = exit_x
                    f = (age - (duration - 7)) / 7.0
                    ease = f * f * (3 - 2 * f)
                    y = int(swim_y + (-height - 3 - swim_y) * ease)
            else:
                exit_x = WIDTH + width + 3 if direction == 1 else -width - 3
                x = int(entry_x + (exit_x - entry_x) * (fraction + 0.025 * math.sin(fraction * 6.283)))
                y = swim_y
        middle = height // 2
        tail_shift = tail_frames[int(t * 2.67 + phase) % 4]
        puff = 0
        if species == 4:
            puff_age = (t + phase * 2.0) % 12.0
            if puff_age < 2 or puff_age >= 9:
                puff = 0
            elif puff_age < 3:
                puff = 1
            elif puff_age < 6:
                puff = 2
            elif puff_age < 7:
                puff = 1
            else:
                puff = 0
        key = (species, width, height, tail_shift, puff, body, highlight, tail, marking)
        sprite = _FISH_SPRITES.get(key)
        if sprite is None:
            commands = bytearray()
            def fish_pixel(dx, dy, idx):
                commands.append(dx)
                commands.append(dy)
                commands.append(idx)
            if species == 3:
                # Tall angelfish: pointed dorsal and ventral fins, slim body.
                for dy in range(height):
                    reach = max(1, 5 - abs(dy - middle))
                    for dx in range(4, min(width, 5 + reach)):
                        shade = highlight if dy in (0, 1, height - 2, height - 1) else (
                            marking if dx == 6 else body)
                        fish_pixel(dx, dy, shade)
                for dy in range(2, height - 1):
                    fish_pixel(2, dy + (tail_shift if dy == middle else 0), tail)
                fish_pixel(3, middle, tail)
                fish_pixel(width - 2, middle - 1, 28)
            elif species == 4:
                # Three inflation stages: relaxed, half-puffed and fully round.
                # The phase advances continuously, with no sudden square body.
                # Five cached colour bands soften both puffer variants.
                gradient = (57, 75, 74, 54, 68) if body == 74 else (33, 39, 38, 37, 36)
                for dy in range(1, height - 1):
                    distance = abs(dy - middle)
                    reach = max(0, 3 + puff - (distance * distance) // 5)
                    shade = gradient[0 if dy == 1 else 1 if dy == 2 else
                                     2 if dy <= middle else 3 if dy < height - 2 else 4]
                    for dx in range(5 - reach, 6 + reach):
                        fish_pixel(dx, dy, shade)
                spines = ((5, 0), (9, 2), (10, 5), (7, 8), (3, 7), (2, 3))
                if puff:
                    for dx, dy in spines:
                        if puff == 2 or (dx + dy) % 2 == 0:
                            fish_pixel(dx, dy, tail)
                for dx, dy in ((0, 2), (1, middle + tail_shift), (0, 6)):
                    fish_pixel(dx, dy, tail)
                fish_pixel(9 if puff else 8, 3, 28)
                fish_pixel(9 if puff else 8, 4, 23)
            elif species == 5:
                # Long, fast-looking dartfish with a forked tail.
                for dy in range(height):
                    inset = abs(dy - 1)
                    for dx in range(3 + inset, width - inset):
                        fish_pixel(dx, dy, highlight if dy == 0 else body if dx % 4 else marking)
                for dx, dy in ((0, 0), (1, 1 + tail_shift), (2, 2),
                               (1, 3 + tail_shift), (0, 3)):
                    fish_pixel(dx, max(0, min(height - 1, dy)), tail)
                fish_pixel(width - 2, 1, 28)
            elif species == 6:
                # Black moor: charcoal rounded body, broad flowing double tail,
                # prominent eyes and faint slate highlights for dark water.
                for dy in range(1, 8):
                    reach = 4 - abs(dy - 4) // 2
                    for dx in range(5 - reach, 6 + reach):
                        fish_pixel(dx, dy, 30 if dy < 3 else 29 if dy < 6 else 28)
                for dx, dy in ((0, 1), (1, 2), (2, 3 + tail_shift),
                               (1, 5), (0, 7), (3, 4)):
                    fish_pixel(dx, max(0, min(8, dy)), 31)
                fish_pixel(10, 3, 31)
                fish_pixel(10, 4, 28)
                fish_pixel(9, 3, 41)
                fish_pixel(6, 1, 31)
            elif species == 7:
                # Tapered orange clownfish with two curved white bands.
                for dy in range(height):
                    inset = abs(dy - 3)
                    left = 3 + inset // 2
                    right = 11 - inset
                    for dx in range(left, right + 1):
                        shade = 75 if dy < 2 else 74
                        # Orange body and curved white bands; black only for the eye.
                        if dx in ((5, 9) if dy <= 3 else (4, 8)):
                            shade = 42
                        fish_pixel(dx, dy, shade)
                for dx, dy in ((0, 1), (1, 2 + tail_shift),
                               (2, 3), (1, 4 + tail_shift), (0, 5)):
                    fish_pixel(dx, max(0, min(6, dy)), 74)
                fish_pixel(10, 2, 28)
                fish_pixel(7, 0, 75)
            else:
                for dy in range(height):
                    distance = abs(middle - dy)
                    row_start = 2 + distance // 2
                    row_end = width - 1 - distance
                    for dx in range(row_start, row_end + 1):
                        shade = highlight if dy == 0 or (dy == height - 2 and dx % 3 == 0) else body
                        if species > 0 and dx == width // 2 and 1 <= dy < height - 1:
                            shade = marking
                        elif species == 2 and dx in (width // 2 - 2, width // 2 + 2):
                            shade = marking
                        fish_pixel(dx, dy, shade)
                for dx, dy in ((0, 0), (1, 1), (2, middle),
                               (1, height - 2), (0, height - 1)):
                    if dx < 2:
                        dy = max(0, min(height - 1, dy + tail_shift))
                    fish_pixel(dx, dy, tail)
                fin_y = height - 1 if tail_shift >= 0 else height - 2
                fish_pixel(width // 2, fin_y, tail)
                if species > 0:
                    fish_pixel(width // 2 + 1, fin_y, tail)
                fish_pixel(width - 2, max(1, middle - 1), 28)
                fish_pixel(width - 3, middle, 23)
            sprite = bytes(commands)
            if len(_FISH_SPRITES) >= _FISH_SPRITE_LIMIT:
                _FISH_SPRITES.pop(next(iter(_FISH_SPRITES)))
            _FISH_SPRITES[key] = sprite
        for at in range(0, len(sprite), 3):
            px, py = x + direction * sprite[at], y + sprite[at + 1]
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                pixel(px, py, sprite[at + 2])

    # Feeding event: pellets drift down from the surface while a temporary
    # school converges from both sides. Pellets vanish as they are eaten.
    # feeding_age is seconds since a real-clock :15 or :45 event (or F).
    if feeding_age is not None and 0 <= feeding_age < 28:
        feed = float(feeding_age)
        for pellet in range(14):
            delay = pellet * 0.75
            age = feed - delay
            if 0 <= age < 12 + pellet % 4:
                px = 53 + (pellet * 11) % 24 + int(2 * math.sin(age * 0.8 + pellet))
                py = int(-2 + age * (1.45 + pellet % 3 * 0.25))
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    pixel(px, py, 67 if pellet % 3 else 66)
                    if pellet % 5 == 0 and py + 1 < HEIGHT:
                        pixel(px, py + 1, 65)
        # Six additional fish approach the falling food, dart around it,
        # then swim offscreen again without teleporting at event boundaries.
        for guest in range(6):
            delay = guest * 0.9
            age = feed - delay
            if not (0 <= age < 23):
                continue
            from_left = guest % 2 == 0
            entry = -13 if from_left else WIDTH + 13
            target = 54 + (guest * 9) % 22
            if age < 9:
                progress = age / 9
                fx = int(entry + (target - entry) * progress)
                fy = int((16 + guest * 5) + (15 - guest * 2) * progress)
            elif age < 15:
                fx = target + int(5 * math.sin(age * 3 + guest))
                fy = 20 + guest * 3 + int(3 * math.sin(age * 2.5 + guest))
            else:
                progress = (age - 15) / 8
                exit_x = WIDTH + 14 if from_left else -14
                fx = int(target + (exit_x - target) * progress)
                fy = 20 + guest * 3
            # Fish leave in the same direction as their travel: never tail-first.
            facing = 1 if from_left else -1
            fish_body = (32, 36, 38, 40, 34, 42)[guest]
            fish_fin = (33, 37, 39, 41, 35, 43)[guest]
            for dy in range(5):
                for dx in range(2, 10 - abs(dy - 2)):
                    px = fx + facing * dx
                    py = fy + dy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        pixel(px, py, fish_fin if dy == 0 else fish_body)
            tail_bob = int(math.sin(t * 6 + guest))
            for dy in (0, 2, 4):
                px = fx + facing * (0 if dy != 2 else 1)
                py = fy + dy + tail_bob
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    pixel(px, py, fish_fin)
            ex, ey = fx + facing * 8, fy + 2
            if 0 <= ex < WIDTH and 0 <= ey < HEIGHT:
                pixel(ex, ey, 28)

    # Rare visitors: a pulsing jellyfish and a scuttling crab.
    # Their paths begin and end offscreen, with long quiet intervals.
    jelly_period = 235.0
    jelly_age = (t - 70.0) % jelly_period
    if jelly_age < 32.0:
        jelly_trip = int((t - 70.0) // jelly_period)
        direction = 1 if jelly_trip % 2 == 0 else -1
        progress = jelly_age / 32.0
        jx = int(-10 + progress * (WIDTH + 20)) if direction == 1 else int(WIDTH + 10 - progress * (WIDTH + 20))
        jy = 12 + (jelly_trip * 9) % 18 + int(3 * math.sin(jelly_age * 1.15))
        pulse = int(jelly_age * 3.0) % 4
        # Rotate through cyan, violet, pink and mint on successive visits.
        bell, rim, tentacle = _JELLY_PALETTES[jelly_trip % len(_JELLY_PALETTES)]
        # Domed, lightly shaded bell with a scalloped lower edge.
        bell_shape = _JELLY_BELLS[1 if pulse in (1, 2) else 0]
        colours = (bell, rim, tentacle)
        for at in range(0, len(bell_shape), 3):
            px, py = jx + bell_shape[at] - 8, jy + bell_shape[at + 1] - 8
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                pixel(px, py, colours[bell_shape[at + 2]])
        # Night jellyfish trail longer, undulating luminous tendrils.
        shimmer_phase = int(t * 5)
        for arm, dx in enumerate((-3, -1, 1, 3)):
            length = (8, 14, 12, 10)[arm] if night else (5, 9, 7, 6)[arm]
            length += 1 if pulse == 2 else 0
            sway = math.sin(t * (2.2 if night else 1.7) + arm * 1.4)
            for step in range(length):
                wave = int(sway * step / 5 +
                           (math.sin(t * 2.4 - step * 0.7 + arm * 1.3) *
                            step / 6 if night else 0))
                px, py = jx + dx + wave, jy + 3 + step
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    colour = (55 if (step - shimmer_phase + arm * 4) % 11 < 3
                              else 27 if step % 4 == 0 else tentacle
                              ) if night else (tentacle if step % 4 else rim)
                    pixel(px, py, colour)

    crab_period = 310.0
    crab_age = (t - 125.0) % crab_period
    if crab_age < 26.0:
        crab_trip = int((t - 125.0) // crab_period)
        direction = 1 if crab_trip % 2 == 0 else -1
        # A tiny hesitation halfway across makes the crab less mechanical.
        progress = crab_age / 26.0
        eased = progress + 0.025 * math.sin(progress * 6.283)
        cx = int(-9 + eased * (WIDTH + 18)) if direction == 1 else int(WIDTH + 9 - eased * (WIDTH + 18))
        cy = 55 + int(math.sin(cx * 0.075) + 0.6 * math.sin(cx * 0.19 + 0.8))
        step = int(t * 7) & 1
        for dx, dy in ((-2, 0), (-1, -1), (0, -1), (1, -1), (2, 0),
                       (-2, 1), (-1, 1), (0, 1), (1, 1), (2, 1)):
            px, py = cx + dx, cy + dy
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                pixel(px, py, 20 if dy > 0 else 21)
        for side in (-1, 1):
            for dx, dy in ((3, 0), (4, -1 - step), (4, 1 + step),
                           (3, -2), (4, -3)):
                px, py = cx + side * dx, cy + dy
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    pixel(px, py, 22 if dy < -1 else 20)
        for dx in (-1, 1):
            px, py = cx + dx, cy - 1
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                pixel(px, py, 28)

    # Weather Matrix-inspired UFO: varied coloured hulls and chasing
    # navigation lights, without a downward searchlight.
    ufo_period = 430.0
    ufo_age = (t - 95.0) % ufo_period
    if ufo_age < 21.0:
        ufo_trip = int((t - 95.0) // ufo_period)
        direction = 1 if ufo_trip % 2 == 0 else -1
        fraction = ufo_age / 21.0
        travel = fraction + 0.12 * math.sin(6.2831853 * fraction) / 6.2831853
        ux = int(-13 + (WIDTH + 26) * travel)
        if direction == -1:
            ux = WIDTH - 1 - ux
        uy = 7 + (ufo_trip * 7) % 9 + int(math.sin(t * 1.4))
        hull, dome, trim = ((72, 73, 43), (50, 51, 35),
                            (68, 69, 41), (54, 55, 39),
                            (48, 49, 41), (70, 71, 43))[ufo_trip % 6]
        saucer = (
            "    DDD    ",
            "   DCCCD   ",
            "  DCCGCCD  ",
            " DDDDDDDDD ",
            "DSSSSSSSSSD",
            " DDDDDDDDD ",
        )
        ink = {"D": hull, "C": dome, "G": 27, "S": trim}
        for dy, row in enumerate(saucer):
            for dx, ch in enumerate(row):
                if ch != " ":
                    px, py = ux + dx - 5, uy + dy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        pixel(px, py, ink[ch])
        chase = int(t * (7 if night else 5)) % 5
        for light_id, dx in enumerate((-4, -2, 0, 2, 4)):
            px, py = ux + dx, uy + 5
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                pixel(px, py, (27 if night else 57)
                      if light_id == chase else (25 if night else 43))
        if night:
            # Two small alternating position lights on the wingtips.
            for dx, colour in ((-5, 41), (5, 39)):
                px, py = ux + dx, uy + 4
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    pixel(px, py, colour if int(t * 3) & 1 else 43)

    # Rare nocturnal anglerfish with a luminous lure and friendly smile.
    if night:
        angler_age = (t - 38.0) % 165.0
        if angler_age < 35.0:
            trip = int((t - 38.0) // 165.0)
            direction = 1 if trip % 2 == 0 else -1
            # The angler's mouth points towards negative local X.
            # With direction=1 it must travel right-to-left; mirroring
            # the sprite also mirrors the swimming direction.
            ax = int(WIDTH + 18 - (WIDTH + 36) * angler_age / 35.0)
            if direction == -1:
                ax = WIDTH - 1 - ax
            ay = 29 + (trip * 7) % 13 + int(2 * math.sin(t * 0.8))
            def angler_pixel(dx, dy, colour):
                px, py = ax + direction * dx, ay + dy
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    pixel(px, py, colour)
            # Rounded violet body, pink tail and a friendly expressive face.
            for at in range(0, len(_ANGLER_BODY), 3):
                angler_pixel(_ANGLER_BODY[at] - 16, _ANGLER_BODY[at + 1] - 16,
                             72 if _ANGLER_BODY[at + 2] == 44 else 73)
            # A forked, undersized tail behind the enormous head.
            for dx, dy in ((7, -1), (8, -2), (9, -4), (10, -5),
                           (8, 0), (9, 2), (10, 4), (7, 1)):
                angler_pixel(dx, dy, 77)
            # A small smile and pink cheek replace the open jaws/teeth.
            for dx, dy in ((-9, 1), (-8, 2), (-7, 2), (-6, 2), (-5, 1)):
                angler_pixel(dx, dy, 28)
            angler_pixel(-8, 0, 77)
            for dx, dy in ((-6, -4), (-5, -4), (-6, -3), (-5, -3)):
                angler_pixel(dx, dy, PEARL_CORE)
            angler_pixel(-6, -3, 28)
            # Curved stalk reaches forward of the mouth. A three-pixel
            # lantern pulses while a faint halo breathes around it.
            for dx, dy in ((-2, -7), (-2, -9), (-3, -11),
                           (-5, -12), (-7, -12), (-9, -11)):
                angler_pixel(dx, dy, 46)
            glow = 55 if int(t * 3) & 1 else 57
            angler_pixel(-10, -11, glow)
            angler_pixel(-11, -11, 55)
            angler_pixel(-10, -12, 27)
            if int(t * 2) & 1:
                angler_pixel(-12, -11, 25)
                angler_pixel(-10, -13, 25)


    # Submarine: automatic cameo every three minutes, or S to summon.
    # Alternate automatic direction; manual direction is controlled by the
    # emulator trigger counter. All artwork, including propeller, is mirrored.
    sub_duration = 18.0
    sub_period = 180.0
    auto_phase = (t - 45) % sub_period
    manual_phase = t - submarine_at if submarine_at is not None else -1
    manual = 0 <= manual_phase < sub_duration
    # Manual trip takes precedence. Suppress an automatic cameo that would
    # start during or immediately after that manual trip, rather than
    # allowing a second submarine to appear midway through its route.
    manual_recent = 0 <= manual_phase < sub_duration * 2
    if manual_recent:
        sub_phase = manual_phase if manual else -1
    else:
        sub_phase = auto_phase
    if 0 <= sub_phase < sub_duration:
        trip = int((t - 45) // sub_period)
        direction = (submarine_direction if submarine_direction in (-1, 1) else 1) if manual else (1 if trip % 2 == 0 else -1)
        # Smoothly vary cruising speed without reversing or changing
        # journey duration. The sine term integrates to zero over the trip.
        fraction = sub_phase / sub_duration
        cruise_seed = (submarine_colour if submarine_colour is not None else 0) if manual else trip
        eased = submarine_motion(fraction, cruise_seed)
        progress = int(eased * (WIDTH + 56))
        sx = -28 + progress if direction == 1 else WIDTH + 28 - progress
        sy = 23 + int(2 * math.sin(sub_phase * 0.8))
        # Cycle yellow, red, turquoise and purple; preserve portholes.
        colour_trip = (submarine_colour if submarine_colour is not None else 0) if manual else trip
        hulls = ((56, 57, 58), (68, 69, 58), (70, 71, 59),
                 (72, 73, 43), (74, 75, 58), (76, 77, 58),
                 (78, 79, 43), (80, 81, 59))
        hull, highlight, shadow = hulls[colour_trip % len(hulls)]
        def sub_pixel(dx, dy, shade):
            if shade == 56:
                shade = hull
            elif shade == 57:
                shade = highlight
            elif shade == 58:
                shade = shadow
            px = sx + dx if direction == 1 else sx + 28 - dx
            py = sy + dy
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                pixel(px, py, shade)
        for at in range(0, len(_SUB_BODY), 3):
            sub_pixel(_SUB_BODY[at], _SUB_BODY[at + 1], _SUB_BODY[at + 2])
        for dx in range(11, 18):
            for dy in (-3, -2, -1):
                sub_pixel(dx, dy, 56)
        for dx, dy in ((14, -5), (14, -4), (15, -5), (16, -5)):
            sub_pixel(dx, dy, 59)
        for dx in (9, 15, 21):
            for yy in (3, 4, 5):
                for xx in (-1, 0, 1):
                    if xx * xx + (yy - 4) ** 2 <= 2:
                        # Warm cabin light after dark, with a slow independent
                        # shimmer in each porthole; retain the metal rim.
                        inside = (TREASURE_GLOW if (int(t * 2) + dx // 6) % 5 else PEARL_CORE) if night else 33
                        sub_pixel(dx + xx, yy, 59 if xx * xx + (yy - 4) ** 2 == 2 else inside)
        # Four-frame spinning stern propeller, mirrored with the hull.
        # A dark shaft separates the blades from the submarine body.
        sub_pixel(2, 4, 28)
        sub_pixel(1, 4, 59)
        blade_frames = (
            ((0, 1), (0, 7), (1, 2), (1, 6)),
            ((0, 2), (0, 6), (2, 2), (2, 6)),
            ((0, 3), (0, 5), (1, 1), (1, 7)),
            ((0, 2), (0, 6), (2, 3), (2, 5)),
        )
        for px, py in blade_frames[int(eased * sub_duration * 9) % 4]:
            sub_pixel(px, py, 57)
        sub_pixel(1, 4, 59)

    extra_life(t, pixel, night)

    # Bubbles rise at differing speeds.
    for i in range(17):
        x = (i * 37 + 19) % WIDTH
        y = 56 - int((t * (4 + i % 4) + i * 11) % 62)
        if 0 <= y < HEIGHT:
            # Fixed palette entries avoid the shared lantern colour cycle.
            phase = int(t * (1.3 + (i % 5) * 0.13) + i * 1.618) % 4
            pixel(x, y, 57 if phase in (1, 2) else 59)
            if i % 3 == 0 and phase in (2, 3) and x + 1 < WIDTH:
                pixel(x + 1, y, 59)

