"""Actual local TCP traffic through ReaderWorker and its durable SQLite store."""
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from idlaps.clock import RaceClock
from idlaps.protocol import checksum
from idlaps.reader import ReaderWorker
from idlaps.storage import Store


class ReaderTcpTests(unittest.TestCase):
    def test_thirty_tags_in_fragmented_burst_are_durable(self):
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1)
        port=listener.getsockname()[1];done=threading.Event();errors=[];seen=[];commands=[]
        def response(code,data=b''):
            raw=b'\xcf\x00'+code.to_bytes(2,'big')+bytes([len(data)+1])+b'\x00'+data
            return raw+checksum(raw)
        def server():
            try:
                with listener,listener.accept()[0] as conn:
                    conn.settimeout(10);buffer=b''
                    while True:
                        data=conn.recv(4096)
                        if not data:return
                        buffer+=data
                        while len(buffer)>=7 and len(buffer)>=7+buffer[4]:
                            n=7+buffer[4];packet,buffer=buffer[:n],buffer[n:]
                            assert checksum(packet[:-2])==packet[-2:]
                            code=int.from_bytes(packet[2:4],'big');commands.append(code)
                            if code==2:return
                            if code==1:
                                burst=b''.join(response(1,b'\xfd\xe4\x01\x1a\x0c'+i.to_bytes(12,'big')) for _ in range(10) for i in range(1,31))
                                conn.sendall(burst[:3]);conn.sendall(burst[3:17]);conn.sendall(burst[17:])
                            else:conn.sendall(response(code,bytes(25) if code==0x72 else b''))
            except Exception as e:errors.append(e);done.set()
        def emit(kind,rid,value):
            if kind=='fatal':errors.append(value);done.set()
            elif kind=='tag':
                seen.append(value)
                if len(seen)==300:done.set()
        thread=threading.Thread(target=server,daemon=True);thread.start()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'readings.db';store=Store(path)
            config={'id':1,'host':'127.0.0.1','port':port,'checkpoint':2,'power':20,
                    'detect_mode':'multi','interval_ms':10000,'quiet_ms':2000}
            worker=ReaderWorker(config,1,1,store,RaceClock(),emit)
            worker.start()
            try:
                self.assertTrue(done.wait(15),'TCP capture did not finish')
                self.assertEqual(errors,[])
                self.assertEqual(len(seen),300)
                self.assertEqual(len({r['epc'] for r in seen}),30)
                self.assertEqual(len({r['record_id'] for r in seen}),300)
                self.assertEqual(store.counts(),{'pending':300})
            finally:
                worker.stop();worker.join(5);thread.join(5);store.close()
            self.assertFalse(worker.is_alive())
            self.assertEqual(commands[:4],[0x50,0x72,0x71,1])
            reopened=Store(path)
            self.assertEqual(reopened.counts(),{'pending':300});reopened.close()


if __name__=='__main__':unittest.main()
