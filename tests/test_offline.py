import ast
from pathlib import Path
import unittest
from unittest.mock import patch
from tank_clock import Clock, FeedingSchedule
from tank_controls import Buttons

class RTC:
    def __init__(self): self.parts = (2021, 1, 1, 4, 0, 0, 0, 0)
    def datetime(self, value=None):
        if value is not None: self.parts = value
        return self.parts

class OfflineTests(unittest.TestCase):
    def test_clock_set_reset_and_schedule(self):
        rtc = RTC(); clock = Clock(rtc, lambda _: None)
        self.assertTrue(clock.night())
        for hour, minute, night in ((6,59,True),(7,0,False),(19,59,False),(20,0,True),(23,59,True),(0,0,True)):
            clock.set_hm(hour, minute)
            self.assertEqual(clock.local()[3:6], (hour, minute, 0))
            self.assertEqual(clock.night(), night)
        self.assertEqual(Clock(rtc).local()[3:5], (0,0))
        before = rtc.parts
        for h,m in ((24,0),(-1,0),(0,60),(0,-1)):
            with self.assertRaises(ValueError): clock.set_hm(h,m)
            self.assertEqual(rtc.parts,before)

    def test_feeding_rollover_and_once_per_slot(self):
        feed = FeedingSchedule()
        self.assertEqual(feed.poll((2025,1,1,23,45,0),100),0)
        self.assertEqual(feed.poll((2025,1,1,23,45,1),101),1)
        self.assertIsNone(feed.poll((2025,1,1,23,45,28),128))
        self.assertEqual(feed.poll((2025,1,2,0,15,0),1900),0)

    def test_debounce_hold_no_extra_tap_and_tick_wrap(self):
        wrap = 1 << 16
        diff = lambda a,b: ((a-b+wrap//2)%wrap)-wrap//2
        with patch('tank_controls.time.ticks_diff', diff, create=True):
            buttons=Buttons()
            self.assertEqual(buttons.poll((1,0),65500),[])
            self.assertEqual(buttons.poll((1,0),4),[])
            self.assertEqual(buttons.poll((1,0),1204),[(0,'hold')])
            self.assertEqual(buttons.poll((0,0),1210),[])
            self.assertEqual(buttons.poll((0,0),1250),[])
            buttons.poll((0,1),1300); buttons.poll((0,1),1340)
            buttons.poll((0,0),1400)
            self.assertEqual(buttons.poll((0,0),1440),[(1,'tap')])

    def test_no_connectivity_imports_or_private_links(self):
        root = Path(__file__).resolve().parents[1]
        forbidden = {'network','socket','ssl','requests','urequests','ntptime','tank_services','tank_web','tank_update','wifi_config'}
        for path in root.glob('*.py'):
            source=path.read_text()
            for node in ast.walk(ast.parse(source)):
                if isinstance(node,ast.Import): names=[n.name.split('.')[0] for n in node.names]
                elif isinstance(node,ast.ImportFrom): names=[(node.module or '').split('.')[0]]
                else: continue
                self.assertFalse(forbidden.intersection(names),path.name)
            self.assertNotIn('nickymoomeh',source)

class ClockOverlayTests(unittest.TestCase):
    def test_composition_changes_only_badge_and_updates_digits(self):
        from runtime import draw_clock, IndexedDisplay, make_pens
        from test_hardware import Graphics
        graphics = Graphics(); display = IndexedDisplay(graphics)
        pens = make_pens(graphics)[0][0]
        original = bytearray([33]) * 8192
        display.buffer[:] = original
        draw_clock(display.buffer, (2025,1,1,9,59,0))
        first = bytes(display.buffer)
        for y in range(64):
            for x in range(128):
                if x >= 21 or y >= 7:
                    self.assertEqual(first[y*128+x],33)
        self.assertEqual(first[0],28)
        self.assertIn(42,first[:21*128])
        display.draw(pens)
        display.buffer[:] = original
        draw_clock(display.buffer, (2025,1,1,10,0,0))
        self.assertNotEqual(first,bytes(display.buffer))
        display.draw(pens)
        self.assertEqual(graphics.pixels,[pens[i] for i in display.buffer])
        # Normal scenery restoration erases every badge pixel when toggled off.
        display.buffer[:] = original
        display.draw(pens)
        self.assertEqual(graphics.pixels,[pens[33]]*8192)

    def test_unset_clock_uses_dashes(self):
        from runtime import draw_clock
        frame = bytearray(8192)
        draw_clock(frame,(2021,1,1,0,0,0),True)
        for x in (1,5,13,17):
            self.assertEqual(frame[3*128+x:3*128+x+3],bytes([42])*3)
            self.assertEqual(frame[128+x:128+x+3],bytes([28])*3)

    def test_hold_b_toggle_and_editor_cancel_in_runtime(self):
        import runtime
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        rtc=RTC(); rtc.parts=(2025,1,1,2,12,34,0,0)
        graphics=MagicMock(); graphics.get_bounds.return_value=(128,64)
        board=MagicMock(); board.display=graphics
        events=iter([[(1,'hold')],[(0,'hold')],[(1,'hold')],[(1,'hold')]])
        def poll(*args):
            try: return next(events)
            except StopIteration: raise KeyboardInterrupt
        counter=iter(range(0,1000000,10))
        timer=SimpleNamespace(ticks_ms=lambda: next(counter),ticks_us=lambda: next(counter),
                              ticks_diff=lambda a,b:a-b,sleep_ms=lambda _:None)
        snapshots=[]
        def capture(display,pens): snapshots.append(bytes(display.buffer))
        def scene(seconds,pixel,**kwargs):
            # A foreground aquarium object occupies the badge's location.
            pixel(0,0,33)
        with patch.dict('sys.modules',{'machine':SimpleNamespace(RTC=lambda:rtc),
             'interstate75':SimpleNamespace(Interstate75=lambda **_:board,
              DISPLAY_INTERSTATE75_128X64=0,SWITCH_A=0,SWITCH_B=1)}), \
             patch('tank_controls.Buttons.poll',side_effect=poll), \
             patch.object(runtime,'time',timer), \
             patch.object(runtime.IndexedDisplay,'draw',capture), \
             patch('aquarium.load_backgrounds',return_value=True), \
             patch('aquarium.background_frame',return_value=bytes(8192)), \
             patch('aquarium.coral_commands',return_value=b''), \
             patch('aquarium.chest_commands',return_value=b''), \
             patch('aquarium.render',side_effect=scene):
            with self.assertRaises(KeyboardInterrupt): runtime.main()
        self.assertEqual(len(snapshots),3)
        self.assertEqual(snapshots[0][0],28) # Clock draws over the foreground.
        self.assertEqual(snapshots[1],snapshots[0]) # Hold B in editor only cancels.
        self.assertEqual(snapshots[2][0],33) # Subsequent hold B hides clock.
        self.assertEqual(rtc.parts,(2025,1,1,2,12,34,0,0))
