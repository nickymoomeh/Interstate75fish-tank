"""Host checks for scheduling and the PicoGraphics adapter (no board claims)."""
import unittest
import hashlib
import aquarium
from runtime import BRIGHTNESS, BackgroundCache, IndexedDisplay, make_pens, scheduled_night, changed_runs, overlay_foliage, overlay_sprite


class Graphics:
    def __init__(self):
        self.pixels = [None] * 8192
        self.created = []
        self.rectangles = 0

    def create_pen(self, r, g, b):
        self.created.append((r, g, b))
        return (r, g, b)

    def set_pen(self, pen):
        self.pen = pen

    def rectangle(self, x, y, width, height):
        self.rectangles += 1
        for xx in range(x, x + width):
            self.pixels[y * 128 + xx] = self.pen


class HardwareTests(unittest.TestCase):
    def test_run_scanner_capacity_and_last_row(self):
        current = bytearray(8192)
        previous = bytearray(8192)
        dirty = bytearray(256)
        commands = bytearray(385)
        commands[384] = 173
        current[8064:] = bytes(i % 2 for i in range(128))
        self.assertEqual(changed_runs(current, previous, dirty, commands, 8064, 1), 384)
        self.assertEqual(commands[384], 173)
        self.assertEqual(commands[381:384], bytes((127, 1, 1)))
        current[:] = previous
        self.assertEqual(changed_runs(current, previous, dirty, commands, 8064, 0), 0)
        dirty[0] = 1
        self.assertEqual(changed_runs(current, previous, dirty, commands, 8064, 0), 3)
        self.assertEqual(commands[:3], bytes((0, 128, 0)))

    def test_random_frames_and_palette_transitions(self):
        import random
        rng = random.Random(28)
        graphics = Graphics()
        adapter = IndexedDisplay(graphics)
        palettes = make_pens(graphics)
        for frame in range(24):
            for _ in range(400):
                adapter.buffer[rng.randrange(8192)] = rng.randrange(len(aquarium.BASE_PALETTE))
            pens = palettes[frame % 2][(frame // 3) % 4]
            adapter.draw(pens)
            self.assertEqual(graphics.pixels, [pens[i] for i in adapter.buffer])

    def test_foliage_overlay_matches_portable_plant_pixels(self):
        for t in (0, .2, .5, 4, 405):
            buffer = bytearray(i % 85 for i in range(8192))
            expected = bytearray(buffer)
            for _ in aquarium.plant_steps(t, lambda x, y, i: expected.__setitem__(y * 128 + x, i)):
                pass
            overlay_foliage(buffer, aquarium.foliage_buffer(t))
            self.assertEqual(buffer, expected)
        blank = bytearray([255]) * 8192
        before = bytes(buffer)
        overlay_foliage(buffer, blank)
        self.assertEqual(bytes(buffer), before)

    def test_schedule_boundaries_and_unset_clock(self):
        for hour, minute, expected in ((19, 59, False), (20, 0, True),
                                       (6, 59, True), (7, 0, False), (0, 0, True)):
            self.assertEqual(scheduled_night((2026, 10, 10, hour, minute, 0, 0, 0)), expected)
        self.assertTrue(scheduled_night((2021, 1, 1, 12, 0, 0, 0, 0)))

    def test_scanline_output_matches_scene_and_palette_changes(self):
        graphics = Graphics()
        adapter = IndexedDisplay(graphics)
        pens = make_pens(graphics)
        count = len(graphics.created)
        for seconds, night in ((0, False), (1, False), (2.5, True), (86, True)):
            aquarium.render(seconds, adapter.pixel, night=night)
            palette = pens[int(night)][int(seconds * 1.8) % 4]
            adapter.draw(palette)
            self.assertEqual(graphics.pixels, [palette[i] for i in adapter.buffer])
            expected = tuple(tuple(int(c * BRIGHTNESS) for c in rgb)
                             for rgb in aquarium.palette_at(seconds, night))
            self.assertEqual(palette, expected)
        self.assertEqual(len(graphics.created), count)
        self.assertLessEqual(max(c for rgb in graphics.created for c in rgb), 255)

    @staticmethod
    def with_plants(buffer, seconds, night):
        result = bytearray(buffer)
        for _ in aquarium.plant_steps(seconds, lambda x, y, i: result.__setitem__(y * 128 + x, i), night):
            pass
        coral = aquarium.coral_commands(seconds, night)
        overlay_sprite(result, coral, len(coral))
        overlay_sprite(result, aquarium.chest_commands(seconds), len(aquarium.chest_commands(seconds)))
        return result

    def test_plants_animate_over_cached_background(self):
        cache = BackgroundCache()
        cache.initialise(0, False)
        self.assertNotEqual(self.with_plants(cache.front, 0, False),
                            self.with_plants(cache.front, 0.5, False))

    def test_background_reference_frames_with_bottom_plants(self):
        fixtures = [(0, False, '042728e1dff7693e38d9be967fc6f304288f589a3a8469a4d95eaf52e695a077'), (86, True, '2cb6731c32f5ee85f04d406dfd1dd03f915dad41cc6fd596a7d89e3c4b42ea79'), (482, False, 'ffc761689d996e90792eb55d1b042845ce4e4d3f2446dcc7ce1904ab8c93777e'), (803, True, '758e8c8d35c51cf46bd6aea52a331dc29d6c391625874e8546ee53f440e58e67'), (1710, False, '92e4bc1a61abe854b958f59eee7624b71200c95b6f868af7832f664b4fee58f5')]
        for seconds, night, expected in fixtures:
            cache = BackgroundCache()
            cache.initialise(seconds, night)
            self.assertEqual(hashlib.sha256(self.with_plants(cache.front, seconds, night)).hexdigest(), expected)

    def test_unchanged_frame_skips_drawing_and_palette_changes_repaint(self):
        graphics = Graphics()
        adapter = IndexedDisplay(graphics)
        pens = make_pens(graphics)
        adapter.buffer[:] = bytes(i % len(pens[0][0]) for i in range(8192))
        adapter.draw(pens[0][0])
        graphics.rectangles = 0
        adapter.draw(pens[0][0])
        self.assertEqual(graphics.rectangles, 0)
        for palette in (pens[0][1], pens[1][1], pens[0][0]):
            adapter.draw(palette)
            self.assertEqual(graphics.pixels, [palette[i] for i in adapter.buffer])
        # Moving a sprite must erase its old position as well as paint the new one.
        adapter.buffer[0:3] = bytes((43, 43, 43))
        adapter.draw(pens[0][0])
        adapter.buffer[0:3] = bytes((0, 1, 2))
        adapter.draw(pens[0][0])
        self.assertEqual(graphics.pixels, [pens[0][0][i] for i in adapter.buffer])

    def test_full_brightness_preserves_original_colours(self):
        graphics = Graphics()
        pens = make_pens(graphics, 1.0)
        self.assertEqual(pens[0][0], tuple(aquarium.palette_at(0)))
        self.assertEqual(pens[1][0], tuple(aquarium.palette_at(0, True)))
        for invalid in (0, -0.1, 1.1):
            with self.assertRaises(ValueError):
                make_pens(graphics, invalid)

    def test_incremental_scenery_composes_without_trails(self):
        cache = BackgroundCache()
        cache.initialise(0, False)
        initial = bytes(cache.front)
        expected = bytearray(8192)
        def pixel(x, y, index):
            expected[y * 128 + x] = index
        for _ in aquarium.background_steps(12, pixel, True, plants=False, ornaments=False):
            pass
        cache.advance(12, True)
        while cache.steps is not None:
            self.assertEqual(bytes(cache.front), initial)
            cache.advance(12, True)
        self.assertEqual(cache.front, expected)
        for seconds in (12, 12.5, 14):
            composed = bytearray(cache.front)
            aquarium.render(seconds, lambda x, y, i: composed.__setitem__(y * 128 + x, i),
                            night=True, background=False, plants=True)
            # A freshly restored backdrop prevents trails from prior fish.
            reference = bytearray(expected)
            aquarium.render(seconds, lambda x, y, i: reference.__setitem__(y * 128 + x, i),
                            night=True, background=False, plants=True)
            self.assertEqual(composed, reference)


if __name__ == '__main__':
    unittest.main()

