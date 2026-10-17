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
