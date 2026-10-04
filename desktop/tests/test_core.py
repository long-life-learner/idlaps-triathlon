import json
import tempfile
import unittest
from pathlib import Path
from idlaps.protocol import Parser, checksum, command, tag_from_frame
from idlaps.storage import Store
from idlaps.clock import RaceClock


def frame(data=b'\xfd\xe4\x01\x1a\x02\xab\xcd'):
    raw=b'\xcf\x00\x00\x01'+bytes([len(data)+1])+b'\x00'+data
    return raw+checksum(raw)


class ProtocolTests(unittest.TestCase):
    def test_vendor_crc(self):
        self.assertEqual(command(0x50).hex(), 'cfff0050000726')

    def test_every_split_and_coalescing(self):
        raw=frame()
        for cut in range(1,len(raw)):
            p=Parser(); self.assertEqual(p.feed(raw[:cut]),[])
            frames=p.feed(raw[cut:]+raw)
            self.assertEqual(len(frames),2)
            self.assertEqual(tag_from_frame(frames[0])['epc'],'ABCD')
            self.assertEqual(tag_from_frame(frames[0])['rssi'],-54.0)

    def test_corrupt_and_noise_resync(self):
        p=Parser(); corrupt=bytearray(frame());corrupt[-1]^=1
        output=p.feed(b'noise'+corrupt+frame())
        self.assertEqual(len(output),1);self.assertEqual(p.corrupt,1)


class StorageTests(unittest.TestCase):
    def test_ack_only_sent_batch_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.db';s=Store(path)
            a={'record_id':'one','event_id':1};b={'record_id':'two','event_id':1}
            s.append(a);batch=s.pending(1);s.append(b)
            s.acknowledge([x['record_id'] for x in batch],['one','two'],[])
            self.assertEqual(s.pending(1),[b]);s.close()
            s=Store(path);self.assertEqual(s.counts(),{'pending':1,'sent':1});s.close()

    def test_rejection_retained_and_event_separated(self):
        with tempfile.TemporaryDirectory() as folder:
            s=Store(Path(folder)/'data.db');s.append({'record_id':'a','event_id':1});s.append({'record_id':'b','event_id':2})
            s.acknowledge(['a'],[],[{'record_id':'a','message':'BIB unknown'}])
            self.assertEqual(s.pending(1),[]);self.assertEqual(len(s.pending(2)),1)
            self.assertEqual(s.errors(),[('a','BIB unknown')]);s.retry_rejected();self.assertEqual(len(s.pending(1)),1);s.close()


class ClockTests(unittest.TestCase):
    def test_windows_wall_change_does_not_change_race_time(self):
        ticks=[1_000_000_000];wall=[1_700_000_000_000_000_000]
        c=RaceClock(lambda:ticks[0],lambda:wall[0]);c.discipline(1_700_000_000_000,ticks[0],20)
        ticks[0]+=1_000_000_000;wall[0]-=120_000_000_000
        self.assertEqual(c.stamp()['captured_ms'],1_700_000_001_000)

    def test_resync_slews_without_backwards_step(self):
        ticks=[0];c=RaceClock(lambda:ticks[0],lambda:0);c.discipline(1_000_000,0,10)
        ticks[0]=10_000_000_000;before=c.stamp()['captured_ms']
        c.discipline(before-100,ticks[0],10)
        self.assertEqual(c.stamp()['captured_ms'],before)
        ticks[0]+=1_000_000_000;self.assertGreater(c.stamp()['captured_ms'],before)
        self.assertFalse(c.discipline(9_000_000,ticks[0],10));self.assertEqual(c.stamp()['clock_quality'],'jump')

    def test_long_offline_marked_stale_and_restart_unverified(self):
        ticks=[0];c=RaceClock(lambda:ticks[0],lambda:0);c.discipline(1_000_000,0,10)
        ticks[0]=4000_000_000_000;self.assertEqual(c.stamp()['clock_quality'],'stale')
        self.assertEqual(RaceClock().stamp()['clock_quality'],'unverified')

if __name__=='__main__':unittest.main()
