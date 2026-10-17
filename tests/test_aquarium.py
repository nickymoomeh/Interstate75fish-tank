"""Headless tests for the portable aquarium renderer."""
import unittest
from aquarium import WIDTH, HEIGHT, BASE_PALETTE, palette_at, render


class AquariumTests(unittest.TestCase):
    def test_bubbles_have_independent_fixed_colour_phases(self):
        calls = []
        render(0, lambda x, y, i: calls.append((x, y, i)), background=False)
        bubbles = calls[-23:]
        # The bubble pass finishes the frame. Its main pixels use two
        # fixed shades rather than all sharing a lantern palette phase.
        bubble_x = {(i * 37 + 19) % WIDTH for i in range(17)}
        shades = {i for x, y, i in bubbles if x in bubble_x}
        self.assertIn(57, shades)
        self.assertIn(59, shades)

    def test_sprite_cache_is_bounded_and_eviction_preserves_pixels(self):
        import aquarium
        aquarium._FISH_SPRITES.clear()
        def frame(t):
            result = bytearray(WIDTH * HEIGHT)
            render(t, lambda x, y, i: result.__setitem__(y * WIDTH + x, i), background=False)
            return result
        original = frame(12.5)
        self.assertEqual(original, frame(12.5))
        for t in range(0, 3500, 37):
            frame(t)
            self.assertLessEqual(len(aquarium._FISH_SPRITES), aquarium._FISH_SPRITE_LIMIT)
        self.assertEqual(original, frame(12.5))

    def test_new_visitors_are_clipped_and_deterministic(self):
        import aquarium
        for t in (0, 58, 77, 196, 224, 293, 350, 370, 383, 394, 419, 594, 820, 960):
            for night in (False, True):
                calls = []
                render(t, lambda x, y, i: calls.append((x, y, i)), night=night)
                self.assertTrue(all(0 <= x < WIDTH and 0 <= y < HEIGHT and
                                    0 <= i < len(BASE_PALETTE) for x, y, i in calls))
                repeat = []
                render(t, lambda x, y, i: repeat.append((x, y, i)), night=night)
                self.assertEqual(calls, repeat)

    def test_hermit_approaches_hides_and_carries_shell(self):
        import aquarium
        def life(t):
            pixels = {}
            aquarium.extra_life(t, lambda x, y, i: pixels.__setitem__((x, y), i))
            return pixels
        self.assertEqual(life(370).get((25, 56)), 74)
        self.assertNotEqual(life(383).get((25, 56)), 74)
        self.assertEqual(life(358).get((72, 53)), 58)
        self.assertEqual(life(389).get((75, 53)), 58)

    def test_snail_glowing_eyes(self):
        import aquarium
        eyes = [(aquarium._SNAIL[i], aquarium._SNAIL[i + 1])
                for i in range(0, len(aquarium._SNAIL), 3) if aquarium._SNAIL[i + 2] == aquarium.PEARL_CORE]
        self.assertEqual(len(eyes), 8)
        self.assertEqual({y for x, y in eyes}, {0, 1})
        self.assertEqual({x for x, y in eyes}, {10, 11, 13, 14})

    def test_hermit_exit_is_fully_offscreen(self):
        import aquarium
        from unittest.mock import patch
        with patch.object(aquarium, '_SHELL', bytes((0, 0, 81))):
            for trip in (0, 1):
                t = 350 + trip * 540 + 89.9
                pixels = []
                aquarium.extra_life(t, lambda x, y, i: pixels.append((x, y, i)))
                self.assertFalse(any(i == 81 for x, y, i in pixels))

    def test_pearl_and_treasure_stay_bright_at_night(self):
        import aquarium
        day, night = palette_at(0), palette_at(0, True)
        for index in (aquarium.PEARL_HALO, aquarium.PEARL_CORE, aquarium.TREASURE_GLOW):
            self.assertEqual(day[index], night[index])
        foreground = []
        aquarium.extra_life(105, lambda x, y, i: foreground.append(i))
        self.assertIn(aquarium.PEARL_CORE, foreground)
        self.assertIn(aquarium.PEARL_HALO, foreground)
        background = []
        for _ in aquarium.background_steps(410, lambda x, y, i: background.append(i)):
            pass
        self.assertIn(aquarium.PEARL_CORE, background)
        self.assertIn(aquarium.TREASURE_GLOW, background)

    def test_kelp_pose_is_reused_within_each_second(self):
        import aquarium
        from unittest.mock import patch
        aquarium._KELP_TICK = None
        original = aquarium._kelp_steps
        with patch.object(aquarium, '_kelp_steps', wraps=original) as build:
            first = aquarium._cached_kelp(12.0)
            self.assertIs(first, aquarium._cached_kelp(12.99))
            self.assertEqual(build.call_count, 1)
            aquarium._cached_kelp(13.0)
            self.assertEqual(build.call_count, 2)
        expected = bytearray()
        for _ in original(13, lambda x, y, i: expected.extend((x, y, i))):
            pass
        self.assertEqual(aquarium._cached_kelp(13.8), bytes(expected))

    def test_large_oyster_pearl_is_in_right_clearing(self):
        import aquarium
        calls = []
        aquarium.extra_life(105, lambda x, y, i: calls.append((x, y, i)))
        cores = [(x, y) for x, y, i in calls if i == aquarium.PEARL_CORE]
        self.assertEqual(cores, [(82, 55), (83, 55), (84, 55)])
        self.assertGreaterEqual(max(aquarium._OYSTER_OPEN[0::3]) + 1, 13)

    def test_ornaments_open_and_close_through_intermediate_poses(self):
        import aquarium
        sequence = [aquarium._opening_pose(t, 8, 12, 29, 33)
                    for t in (0, 8, 10, 12, 28, 29, 31, 33)]
        self.assertEqual(sequence, [0, 1, 2, 3, 3, 2, 1, 0])
        self.assertEqual(len(set(aquarium._OYSTER_POSES)), 4)
        chest = [aquarium._opening_pose(t, 12, 28, 51, 67)
                 for t in (0, 12, 20, 28, 50, 51, 59, 67)]
        self.assertEqual(chest, [0, 1, 2, 3, 3, 2, 1, 0])

    def test_clownfish_uses_orange_and_white_with_one_dark_eye(self):
        import aquarium
        aquarium._FISH_SPRITES.clear()
        for t in range(0, 160, 5):
            render(t, lambda x, y, i: None, background=False)
        shapes = [sprite for key, sprite in aquarium._FISH_SPRITES.items() if key[0] == 7]
        self.assertTrue(shapes)
        for sprite in shapes:
            shades = list(sprite[2::3])
            self.assertIn(74, shades)
            self.assertIn(42, shades)
            self.assertEqual(shades.count(28), 1)
            self.assertNotIn(40, shades)

    def test_all_submarine_variants_have_independent_night_lights(self):
        import aquarium
        # These times cover both shimmer states; backgrounds are omitted
        # so the warm emissive colour can only come from the submarine.
        for colour in range(8):
            for t in (9.0, 9.5):
                calls = []
                render(t, lambda x, y, i: calls.append(i), night=True,
                       submarine_at=0, submarine_colour=colour, background=False)
                self.assertIn(aquarium.TREASURE_GLOW, calls)
                night = palette_at(t, True)
                self.assertEqual(night[aquarium.TREASURE_GLOW], BASE_PALETTE[aquarium.TREASURE_GLOW])
                self.assertEqual(night[aquarium.PEARL_CORE], BASE_PALETTE[aquarium.PEARL_CORE])

    def test_ghost_is_night_only_and_leaves_screen(self):
        import aquarium
        def life(t, night):
            pixels = {}
            aquarium.extra_life(t, lambda x, y, i: pixels.__setitem__((x, y), i), night)
            return pixels
        day, night = life(143, False), life(143, True)
        self.assertNotEqual(day, night)
        self.assertTrue(any(i == 89 and y >= 46 for (x, y), i in night.items()))
        self.assertEqual(life(119.9, False), life(119.9, True))
        self.assertEqual(life(180, False), life(180, True))

    def test_snail_glow_is_outline_not_body(self):
        import aquarium
        self.assertNotIn(71, aquarium._SNAIL[2::3])
        self.assertNotIn(aquarium.PEARL_HALO, aquarium._SNAIL[2::3])
        self.assertIn(aquarium.PEARL_HALO, aquarium._SNAIL_GLOW[2::3])
        self.assertEqual(palette_at(0)[aquarium.PEARL_HALO], palette_at(0, True)[aquarium.PEARL_HALO])

    def test_ornaments_relocate_only_after_fading_out(self):
        import aquarium
        previous = aquarium._ornament_layout(0)
        for t in (20, 200, 350):
            self.assertEqual(aquarium._ornament_layout(t)[:2], previous[:2])
        self.assertEqual(aquarium._ornament_layout(359.9)[2], 0)
        self.assertEqual(aquarium._ornament_layout(360)[2], 0)
        self.assertEqual(aquarium._ornament_layout(362)[2], 0)
        self.assertNotEqual(aquarium._ornament_layout(408)[:2], previous[:2])
        self.assertEqual(aquarium._ornament_layout(408)[2], 16)
        for cycle in range(12):
            chest, oyster, _ = aquarium._ornament_layout(cycle * 360 + 100)
            self.assertTrue(chest + 9 < oyster or oyster + 12 < chest - 9)

    def test_plants_grow_behind_foreground_chest(self):
        import aquarium
        t = 35
        plants = {}
        for _ in aquarium.plant_steps(t, lambda x, y, i: plants.__setitem__((x, y), i)):
            pass
        chest = aquarium.chest_commands(t)
        commands = {(chest[i], chest[i + 1]): chest[i + 2] for i in range(0, len(chest), 3)}
        self.assertTrue(set(plants) & set(commands))
        pixels = {}
        for _ in aquarium.background_steps(t, lambda x, y, i: pixels.__setitem__((x, y), i)):
            pass
        for xy, index in commands.items():
            self.assertEqual(pixels[xy], index)


    def test_guided_fish_reuse_role_shapes_and_coherent_palettes(self):
        import aquarium
        self.assertEqual(len(aquarium._GUIDED_FRAMES), 3)
        self.assertEqual(len(set(aquarium._GUIDED_PALETTES)), 8)
        for sprite in aquarium._GUIDED_FRAMES:
            self.assertTrue(all(0 <= role < 5 for role in sprite[2::3]))
        for trip in range(24):
            palette = aquarium._guided_palette(trip)
            self.assertEqual(palette[-1], 28)
            self.assertGreater(sum(BASE_PALETTE[palette[1]]), sum(BASE_PALETTE[palette[0]]))
            for age in (0, 8, 16, 24, 31.99, 32):
                calls = []
                aquarium.guided_fish(18 + trip * 110 + age,
                                     lambda x, y, i: calls.append((x, y, i)))
                self.assertTrue(all(0 <= x < WIDTH and 0 <= y < HEIGHT and i in palette
                                    for x, y, i in calls))
                if age in (0, 31.99, 32):
                    self.assertEqual(calls, [])
        self.assertEqual(len(aquarium._GUIDED_FRAMES), 3)

    def test_snail_eye_poses_have_one_pupil_per_eye(self):
        import aquarium
        for sprite in aquarium._SNAIL_EYE_POSES:
            pixels = {(sprite[i], sprite[i + 1]): sprite[i + 2] for i in range(0, len(sprite), 3)}
            for left in (11, 14):
                shades = [pixels[(x, y)] for x in (left, left + 1) for y in (1, 2)]
                self.assertEqual(shades.count(28), 1)
                self.assertEqual(shades.count(aquarium.PEARL_CORE), 3)
        self.assertEqual(len(set(aquarium._SNAIL_EYE_POSES)), 4)

    def test_hermit_shell_fades_before_crab_arrives(self):
        import aquarium
        def shell_count(t):
            pixels = {}
            aquarium.extra_life(t, lambda x, y, i: pixels.__setitem__((x, y), i))
            return sum(1 for (x, y), i in pixels.items() if 68 <= x <= 78 and 51 <= y <= 57 and i in (75, 74, 58))
        self.assertEqual(shell_count(350), 0)
        self.assertGreater(shell_count(354), 0)
        self.assertLess(shell_count(354), shell_count(358))

    def test_dense_foliage_updates_at_two_hz_and_leaves_open_water(self):
        import aquarium
        first = bytes(aquarium.foliage_buffer(0))
        self.assertEqual(first, bytes(aquarium.foliage_buffer(.49)))
        self.assertNotEqual(first, bytes(aquarium.foliage_buffer(.5)))
        coverage = sum(i != 255 for i in first)
        self.assertGreater(coverage, 1800)
        self.assertLess(coverage, 8192 // 2)
        self.assertEqual(len(aquarium._DENSE_FOLIAGE), 4)
        self.assertTrue(all(i == 255 or 0 <= i < len(BASE_PALETTE) for i in first))

    def test_ghost_cached_expressions_blink_and_move_hem(self):
        import aquarium
        self.assertEqual(len(set(aquarium._GHOST_POSES)), 4)
        self.assertEqual(aquarium._ghost_pose(6.1), 3)
        self.assertEqual(aquarium._ghost_pose(6.3), 2)
        self.assertNotEqual(aquarium._ghost_pose(1), aquarium._ghost_pose(1.5))
        for sprite in aquarium._GHOST_POSES:
            self.assertTrue(all(x < 12 for x in sprite[0::3]))
            self.assertTrue(all(y < 13 for y in sprite[1::3]))
            self.assertTrue(all(i in (28, 89) for i in sprite[2::3]))

    def test_coral_draws_in_front_of_background_weeds(self):
        import aquarium
        t = 35
        plants = {}
        for _ in aquarium.plant_steps(t, lambda x, y, i: plants.__setitem__((x, y), i)):
            pass
        coral = aquarium.coral_commands(t)
        expected = {(coral[i], coral[i + 1]): coral[i + 2] for i in range(0, len(coral), 3)}
        self.assertTrue(set(plants) & set(expected))
        result = {}
        for _ in aquarium.background_steps(t, lambda x, y, i: result.__setitem__((x, y), i)):
            pass
        chest = aquarium.chest_commands(t)
        chest_points = {(chest[i], chest[i + 1]) for i in range(0, len(chest), 3)}
        for xy, index in expected.items():
            if xy not in chest_points:
                self.assertEqual(result[xy], index)

    def test_resident_roster_limits_duplicate_special_species(self):
        import aquarium
        phases = (0, 1.7, 3.3, 5, 2.6, 4.1)
        for seconds in range(0, 3600, 7):
            species = [aquarium.resident_species(i, int((seconds + phase * 3.7) // (36 + i * 2)))
                       for i, phase in enumerate(phases)]
            for special in (3, 4, 5, 6, 7):
                self.assertLessEqual(species.count(special), 1)
            self.assertGreaterEqual(len(set(species)), 3)

    def test_resident_routes_and_angel_palettes_vary_between_trips(self):
        import aquarium
        for fish in range(6):
            lanes = [aquarium.resident_route(fish, cycle, 0, 7) for cycle in range(8)]
            self.assertGreater(len(set(lanes)), 4)
            for cycle in range(8):
                path = [aquarium.resident_route(fish, cycle, step / 100, 7) for step in range(101)]
                self.assertTrue(all(3 <= y <= 49 for y in path))
                self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(path, path[1:])))
        angels = {aquarium._guided_palette(journey // 2 + 3) for journey in range(0, 24, 2)}
        self.assertGreater(len(angels), 4)

    def test_submarine_propeller_phase_tracks_speed_continuously(self):
        import aquarium
        for seed in range(8):
            positions = [aquarium.submarine_motion(i / 1000, seed) for i in range(1001)]
            self.assertAlmostEqual(positions[0], 0)
            self.assertAlmostEqual(positions[-1], 1, places=6)
            advances = [b - a for a, b in zip(positions, positions[1:])]
            self.assertTrue(all(delta > 0 for delta in advances))
            self.assertGreater(max(advances), min(advances) * 2)
        self.assertTrue(all(len(set(palette)) == 3 for palette in aquarium._JELLY_PALETTES))

    def test_dimensions(self):
        self.assertEqual((WIDTH, HEIGHT), (128, 64))

    def test_palette_cycle_changes_only_light_entries(self):
        a, b = palette_at(0), palette_at(1)
        self.assertEqual(len(a), len(BASE_PALETTE))
        self.assertEqual(a[:24], b[:24])
        self.assertEqual(a[28:], b[28:])
        self.assertNotEqual(a[24:28], b[24:28])

    def test_palette_indices_are_valid(self):
        indices = []
        render(2.5, lambda x, y, index: indices.append((x, y, index)))
        self.assertTrue(indices)
        self.assertTrue(all(0 <= x < WIDTH and 0 <= y < HEIGHT
                            and 0 <= idx < len(BASE_PALETTE)
                            for x, y, idx in indices))

    def test_submarine_trigger_uses_valid_palette_indices(self):
        indices = []
        render(12, lambda x, y, index: indices.append(index), submarine_at=10)
        self.assertTrue(indices)
        self.assertTrue(all(0 <= idx < len(BASE_PALETTE) for idx in indices))
        self.assertIn(56, indices)

    def test_large_visitors_and_both_submarine_directions(self):
        for seconds in (1, 86, 171):
            for direction in (-1, 1):
                indices = []
                render(seconds, lambda x, y, idx: indices.append(idx),
                       submarine_at=seconds, submarine_direction=direction)
                self.assertTrue(indices)
                self.assertTrue(all(0 <= idx < len(BASE_PALETTE)
                                    for idx in indices))

    def test_night_palette_is_dimmer(self):
        day, night = palette_at(0), palette_at(0, night=True)
        self.assertTrue(all(sum(n) <= sum(d) for d, n in zip(day, night)))


if __name__ == "__main__":
    unittest.main()

