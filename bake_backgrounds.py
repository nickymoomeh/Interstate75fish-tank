"""Build the Pico background asset on a desktop: python3 bake_backgrounds.py."""
import argparse
import hashlib
from pathlib import Path
import aquarium


def build(output):
    frames = []
    for seconds in (0, .5, 1, 1.5):
        frame = bytearray(aquarium.WIDTH * aquarium.HEIGHT)
        def pixel(x, y, index):
            frame[y * aquarium.WIDTH + x] = index
        for _ in aquarium.background_steps(seconds, pixel, plants=True, ornaments=False):
            pass
        frames.append(bytes(frame))
    payload = b''.join(frames)
    palette = bytes(component for colour in aquarium.BASE_PALETTE for component in colour)
    header = aquarium.BAKED_MAGIC + hashlib.sha256(palette).digest() + hashlib.sha256(payload).digest()
    Path(output).write_bytes(header + payload)
    return frames


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='backgrounds.bin')
    args = parser.parse_args()
    build(args.output)
    print('Wrote', args.output, '(4 indexed frames, 32840 bytes)')

