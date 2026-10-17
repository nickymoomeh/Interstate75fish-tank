"""Background asset integrity, flash-free playback, and fallback."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import aquarium
from bake_backgrounds import build

ASSET = Path(__file__).resolve().parents[1] / 'backgrounds.bin'


class BakedBackgroundTests(unittest.TestCase):
    def reset_loader(self):
        for name, value in (('_BAKED_ATTEMPTED', False), ('_BAKED_FRAMES', None), ('_BAKED_ERROR', None)):
            patcher = patch.object(aquarium, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_asset_is_reproducible_and_matches_procedural_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, 'backgrounds.bin')
            frames = build(output)
            self.assertEqual(output.read_bytes(), ASSET.read_bytes())
            self.reset_loader()
            self.assertTrue(aquarium.load_backgrounds(str(output)))
            for seconds, index in ((0, 0), (.5, 1), (1, 2), (1.5, 3), (2, 2), (2.5, 1), (3, 0)):
                self.assertEqual(aquarium.background_frame(seconds), frames[index])
            with patch('builtins.open', side_effect=AssertionError('Unexpected flash read')):
                for seconds in (3.1, 9, 100, 400):
                    self.assertEqual(len(aquarium.background_frame(seconds)), 8192)

    def test_invalid_asset_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'backgrounds.bin')
            data = ASSET.read_bytes()
            variants = (b'bad', data[:-1], data[:100] + bytes((data[100] ^ 1,)) + data[101:],
                        data[:8] + b'0' * 32 + data[40:])
            for damaged in variants:
                with patch.object(aquarium, '_BAKED_ATTEMPTED', False), patch.object(aquarium, '_BAKED_FRAMES', None):
                    path.write_bytes(damaged)
                    self.assertFalse(aquarium.load_backgrounds(str(path)))
                    self.assertIsNone(aquarium.background_frame(10))
                    self.assertTrue(aquarium._BAKED_ERROR)

