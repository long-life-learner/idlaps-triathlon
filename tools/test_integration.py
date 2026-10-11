"""Exercise actual PHP HTTP API, authentication and SQLite-backed test DB.

Run: .venv/bin/python tools/test_integration.py
"""
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
import requests

ROOT=Path(__file__).resolve().parents[1]


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();folder=Path(cls.temp.name);cls.database=folder/'test.db'
        config=folder/'config.php';config.write_text("<?php return ['dsn'=>'sqlite:"+str(folder/'test.db')+"','allow_http_local'=>true];")
        cls.env=dict(os.environ,IDLAPS_CONFIG=str(config))
        subprocess.run(['php',str(ROOT/'web/tests/fixture.php')],env=cls.env,check=True)
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
        cls.url=f'http://127.0.0.1:{port}'
        cls.server=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(ROOT/'web/public')],env=cls.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(40):
            try:
                if requests.get(cls.url+'/api.php?action=time',timeout=1).status_code==200:break
            except requests.RequestException:time.sleep(.05)
        cls.tokens={}
        for kind in ['rfid','manual']:
            r=requests.post(cls.url+'/api.php?action=pair',json={'code':'TEST-'+kind.upper()},timeout=5)
            assert r.status_code==200,r.text
            cls.tokens[kind]=r.json()['token']

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate();cls.server.wait(timeout=5);cls.temp.cleanup()

    def call(self,action,payload,kind='manual'):
        return requests.post(self.url+'/api.php?action='+action,json=dict(payload,token=self.tokens[kind]),timeout=10)

    def record(self,id):
        return {'record_id':id,'event_id':1,'bib':'007','checkpoint':1,'stage':'swim_finish','lap':1,'captured_ms':int(time.time()*1000),'clock_quality':'synced','config_version':1}

    def test_multi_epc_form_api_and_observation_filter(self):
        s=requests.Session();login=s.get(self.url+'/index.php?page=login')
        csrf=re.search(r'name="csrf" value="([^"]+)"',login.text)[1]
        r=s.post(self.url+'/index.php?page=login',data={'csrf':csrf,'username':'tester','password':'local-only-test-password'})
        csrf=re.search(r'name="csrf" value="([^"]+)"',r.text)[1]
        r=s.post(self.url+'/index.php?page=participants',data={'action':'participant','csrf':csrf,'id':1,'bib':'007','name':'Test Athlete','category_id':1,'epc':'ABCD, 0002','race_status':'active'})
        self.assertIn('ABCD, 0002',r.text)
        cfg=requests.get(self.url+'/api.php?action=config',headers={'Authorization':'Bearer '+self.tokens['rfid']}).json()['config']
        self.assertEqual(cfg['participants'][0]['epcs'],['ABCD','0002'])
        row={'record_id':'integration-secondary-epc','event_id':1,'epc':'0002','reader_id':1,'checkpoint':1,'captured_ms':int(time.time()*1000),'clock_quality':'synced','config_version':1}
        self.assertEqual(self.call('upload',{'data':[row]},kind='rfid').json()['accepted_ids'],[row['record_id']])
        page=s.get(self.url+'/index.php?page=observations&bib=007')
        self.assertEqual(page.status_code,200);self.assertIn('<td>0002</td>',page.text)

    def test_pair_once_and_authentication(self):
        self.assertEqual(requests.post(self.url+'/api.php?action=pair',json={'code':'TEST-MANUAL'}).status_code,401)
        self.assertEqual(requests.get(self.url+'/api.php?action=config').status_code,401)
        r=requests.get(self.url+'/api.php?action=config',headers={'Authorization':'Bearer '+self.tokens['rfid']})
        self.assertEqual(r.status_code,200);self.assertEqual(len(r.json()['config']['readers']),1)

    def test_retry_partial_cancel(self):
        valid=self.record('integration-ack-1');bad=self.record('integration-ack-2');bad['bib']='unknown'
        r=self.call('upload',{'data':[valid,bad]}).json();self.assertEqual(r['accepted_ids'],[valid['record_id']]);self.assertEqual(len(r['rejected']),1)
        r=self.call('upload',{'data':[valid]}).json();self.assertEqual(r['accepted_ids'],[valid['record_id']])
        changed=dict(valid,captured_ms=valid['captured_ms']+1)
        self.assertEqual(len(self.call('upload',{'data':[changed]}).json()['rejected']),1)
        r=self.call('cancel',{'record_ids':[valid['record_id']]});self.assertEqual(r.status_code,200);self.assertEqual(r.json()['accepted_ids'],[valid['record_id']])
        self.assertEqual(self.call('cancel',{'record_ids':[valid['record_id']]},kind='rfid').status_code,404)

    def test_cancel_before_upload_and_retry_after_admin_restore(self):
        record=self.record('integration-cancel-first')
        r=self.call('cancel',{'record_ids':[record['record_id']]})
        self.assertEqual(r.json()['accepted_ids'],[record['record_id']])
        self.assertEqual(self.call('upload',{'data':[record]}).json()['accepted_ids'],[record['record_id']])
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT cancelled FROM observations WHERE record_id=?',(record['record_id'],)).fetchone()[0],1)
            db.execute('UPDATE observations SET cancelled=0 WHERE record_id=?',(record['record_id'],))
        self.call('cancel',{'record_ids':[record['record_id']]})
        with sqlite3.connect(self.database) as db:
            self.assertEqual(db.execute('SELECT cancelled FROM observations WHERE record_id=?',(record['record_id'],)).fetchone()[0],0)

    def test_admin_login_calculate_export_and_csrf(self):
        s=requests.Session();login=s.get(self.url+'/index.php?page=login')
        csrf=re.search(r'name="csrf" value="([^"]+)"',login.text)[1]
        r=s.post(self.url+'/index.php?page=login',data={'csrf':csrf,'username':'tester','password':'local-only-test-password'})
        self.assertIn('Ringkasan lomba',r.text)
        csrf=re.search(r'name="csrf" value="([^"]+)"',r.text)[1]
        bad=s.post(self.url+'/index.php?page=results',data={'action':'calculate','csrf':'bad'})
        self.assertIn('kedaluwarsa',bad.text)
        r=s.post(self.url+'/index.php?page=results',data={'action':'calculate','csrf':csrf})
        self.assertIn('Hasil dihitung ulang',r.text)
        excel=s.get(self.url+'/index.php?page=excel');self.assertEqual(excel.status_code,200);self.assertTrue(excel.content.startswith(b'PK'))
        pdf=s.get(self.url+'/index.php?page=pdf');self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.content.startswith(b'%PDF-'))
        self.call('upload',{'data':[self.record('integration-stale-1')]})
        self.assertEqual(s.get(self.url+'/index.php?page=excel').status_code,409)
        self.assertNotIn('Arsip manual lama',r.text)
        self.assertEqual(s.get(self.url+'/index.php?page=legacy').status_code,404)
        for page in ['categories','participants','devices','observations','audit']:
            self.assertEqual(s.get(self.url+'/index.php?page='+page).status_code,200)

if __name__=='__main__':unittest.main(verbosity=2)
