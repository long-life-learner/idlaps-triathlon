"""Execute generated block graphs against SQLite and fake Kodular components.

This catches flow/scope/queue regressions; it is not a Kodular compiler or APK test.
"""
import json
import sqlite3
import unittest
from pathlib import Path
import xml.etree.ElementTree as E
import zipfile
from validate_android import NS,field,value
import android_sql as sql


def pairs(v):
    if isinstance(v,dict):return [[k,pairs(x)] for k,x in v.items()]
    if isinstance(v,list):return [pairs(x) for x in v]
    return v


def ytext(v):
    if isinstance(v,(dict,list)):return json.dumps(v,separators=(',',':'))
    if isinstance(v,bool):return 'true' if v else 'false'
    if isinstance(v,float) and v.is_integer():return str(int(v))
    return str(v)


class Runtime:
    def __init__(self,name,db=None,tags=None):
        self.db=db if db is not None else sqlite3.connect(':memory:')
        self.tags=tags if tags is not None else {}
        self.env={};self.properties={};self.pending=[];self.requests=[];self.alerts=[];self.opened=None;self.now=1791086400000
        with zipfile.ZipFile(Path(__file__).resolve().parents[1]/'android/IDLAPSTriathlonTap.aia') as z:
            key=next(n for n in z.namelist() if n.endswith('/'+name+'.bky'))
            self.root=E.fromstring(z.read(key))
            design=json.loads(z.read(key[:-4]+'.scm').decode().split('$JSON\n')[1].split('\n|#')[0])
            def walk(c):
                for k,v in c.items():
                    if not k.startswith('$'):self.properties[c['$Name']+'.'+k]=v
                for child in c.get('$Components',[]):walk(child)
            walk(design['Properties'])
        self.procs={field(b,'NAME'):b for b in self.root if b.get('type')=='procedures_defnoreturn'}
        self.events={}
        for b in self.root:
            if b.get('type')=='component_event':
                m=b.find('b:mutation',NS);self.events[m.get('instance_name'),m.get('event_name')]=b
            elif b.get('type')=='global_declaration':self.env['global '+field(b,'NAME')]=self.eval(value(b,'VALUE'))

    def body(self,b,name):return self.eval(b.find(f"b:statement[@name='{name}']/b:block",NS))
    def fire(self,instance,event,**args):
        self.env.update(args)
        b=self.events.get((instance,event))
        if b is not None:self.body(b,'DO')
    def pump(self):
        for _ in range(200):
            if not self.pending:return
            instance,event,args=self.pending.pop(0);self.fire(instance,event,**args)
        raise AssertionError('Unbounded callback loop')
    def proc(self,name):return self.body(self.procs[name],'STACK')
    def eval(self,b):
        if b is None:return None
        t=b.get('type');f=lambda k:field(b,k);v=lambda k:self.eval(value(b,k))
        vals=lambda:[self.eval(c.find('b:block',NS)) for c in b.findall('b:value',NS)]
        if t=='text':return f('TEXT')
        if t=='math_number':return float(f('NUM'))
        if t=='logic_boolean':return f('BOOL')=='TRUE'
        if t=='lexical_variable_get':return self.env[f('VAR')]
        if t=='lists_create_with':return vals()
        if t=='lists_lookup_in_pairs':
            obj=v('LIST');key=v('KEY')
            if isinstance(obj,dict):return obj.get(key,v('NOTFOUND'))
            return next((x[1] for x in obj if x[0]==key),v('NOTFOUND'))
        if t=='lists_select_item':
            obj=v('LIST');assert isinstance(obj,list),('select requires list',obj)
            return obj[int(v('NUM'))-1]
        if t=='lists_is_in':return v('ITEM') in v('LIST')
        if t=='lists_length':return len(v('LIST'))
        if t=='pair':return v('KEY'),v('VALUE')
        if t=='dictionaries_create_with':return dict(vals())
        if t=='text_join':return ''.join(map(ytext,vals()))
        if t=='lists_join_with_separator':return ytext(v('SEPARATOR')).join(map(ytext,v('LIST')))
        if t=='text_length':return len(ytext(v('VALUE')))
        if t=='text_segment':return ytext(v('TEXT'))[int(v('START'))-1:int(v('START'))-1+int(v('LENGTH'))]
        if t=='text_replace_all':return ytext(v('TEXT')).replace(ytext(v('SEGMENT')),ytext(v('REPLACEMENT')))
        if t=='logic_negate':return not v('BOOL')
        if t=='logic_operation':return (v('A') and v('B')) if f('OP')=='AND' else (v('A') or v('B'))
        if t in ('math_compare','logic_compare'):
            a,b_=v('A'),v('B');return {'EQ':lambda:a==b_,'NEQ':lambda:a!=b_,'GT':lambda:float(a)>float(b_),'LT':lambda:float(a)<float(b_),'GTE':lambda:float(a)>=float(b_),'LTE':lambda:float(a)<=float(b_)}[f('OP')]()
        if t=='math_add':return sum(float(x) for x in vals())
        if t=='math_subtract':return float(v('A'))-float(v('B'))
        if t=='math_division':return float(v('A'))/float(v('B'))
        if t=='math_round':return round(v('NUM'))
        if t=='controls_choose':return v('THENRETURN') if v('TEST') else v('ELSERETURN')
        if t=='component_set_get':
            m=b.find('b:mutation',NS);key=m.get('instance_name')+'.'+m.get('property_name')
            if m.get('set_or_get')=='get':return self.properties.get(key,'')
            self.properties[key]=v('VALUE')
        elif t=='component_method':
            m=b.find('b:mutation',NS);instance=m.get('instance_name');method=m.get('method_name');a=vals()
            if instance=='TinyDB1':
                if method=='GetValue':return self.tags.get(a[0],a[1])
                if method=='StoreValue':self.tags[a[0]]=a[1]
            elif instance=='Clock1':
                if method=='SystemTime':return self.now
                if method=='MakeInstantFromMillis':return a[0]
                if method=='FormatDateTime':return str(a[0])
            elif instance.startswith('SQLite'):
                if method in ('SingleSQL','MultipleSQL'):
                    with self.db:
                        for statement in ([a[0]] if method=='SingleSQL' else a[0]):self.db.execute(statement)
                    self.pending.append((instance,'AfterExecution',{'wasExecuted':True}))
                elif method=='RawQuery':
                    cur=self.db.execute(a[0],a[1]);rows=[[str(x) if isinstance(x,(int,float)) else x for x in r] for r in cur.fetchall()]
                    # Exercise Kodular's single-column representation that caused the reported failure.
                    result=[r[0] for r in rows] if len(cur.description)==1 else rows
                    self.pending.append((instance,'AfterQuery',{'result':result,'numberOfRecords':len(rows)}))
                elif method=='Insert':
                    with self.db:cur=self.db.execute('INSERT INTO '+a[0]+'('+','.join(a[1])+') VALUES('+','.join('?' for _ in a[1])+')',[ytext(x) if isinstance(x,(dict,list)) else x for x in a[2]])
                    return cur.lastrowid
                elif method=='Update':
                    with self.db:cur=self.db.execute('UPDATE '+a[0]+' SET '+','.join(c+'=?' for c in a[1])+' WHERE '+a[3],a[2]+a[4])
                    return cur.rowcount
                else:raise AssertionError(method)
            elif instance.startswith('Web'):
                if method=='JsonTextDecode':return pairs(json.loads(a[0]))
                self.requests.append((instance,method,self.properties.get(instance+'.Url'),a))
            elif instance=='Notifier1':self.alerts.append(a)
            else:raise AssertionError((instance,method))
        elif t=='lexical_variable_set':self.env[f('VAR')]=v('VALUE')
        elif t=='procedures_callnoreturn':self.proc(f('PROCNAME'))
        elif t=='controls_if':self.body(b,'DO0' if v('IF0') else 'ELSE')
        elif t=='controls_forEach':
            for item in list(v('LIST')):self.env[f('VAR')]=item;self.body(b,'DO')
        elif t=='controls_forRange':
            for i in range(int(v('START')),int(v('END'))+1,int(v('STEP'))):self.env[f('VAR')]=i;self.body(b,'DO')
        elif t=='lists_add_items':v('LIST').append(v('ITEM0'))
        elif t=='local_declaration_statement':
            key=f('VAR0');old=self.env.get(key);self.env[key]=v('DECL0');self.body(b,'STACK')
            if old is None:self.env.pop(key,None)
            else:self.env[key]=old
        elif t=='controls_openAnotherScreen':self.opened=v('SCREEN')
        elif t=='controls_closeScreen':self.opened='closed'
        else:raise AssertionError('Unsupported '+t)
        self.eval(b.find('b:next/b:block',NS))


def config(device=1,checkpoint=1,event=1):
    return {'event':{'id':event,'name':'Event '+str(event)},'device':{'id':device,'name':'Titik '+str(checkpoint),'kind':'manual','checkpoint':checkpoint,'config_version':1},'participants':[{'bib':'007','name':'Ayu','category_id':1},{'bib':'7','name':'Budi','category_id':2}], 'categories':[{'id':1,'name':'Elite'},{'id':2,'name':'Junior'}]}


class AndroidFlowTests(unittest.TestCase):
    def make(self):
        a=Runtime('Screen1',tags={'url':'https://triathlon.idlaps.com','token':'token-1','config':pairs(config())})
        a.fire('Screen1','Initialize');a.pump();return a
    def capture(self,a,bib='007'):
        a.properties['Bib.Text']=bib;a.fire('Bib','OnTextChanged');a.fire('Save','Click');a.pump()
    def test_fresh_screen1_and_upgrade_preserve_unacknowledged_payload(self):
        a=Runtime('Screen1');a.fire('Screen1','Initialize');a.pump();self.assertTrue(a.properties['Pair.Enabled'])
        db=sqlite3.connect(':memory:');db.execute(sql.V2)
        db.execute('INSERT INTO readings_v2(record_id,bib,payload) VALUES(?,?,?)',('manual-1-1','999','{"original":true}'));db.commit()
        a=Runtime('Screen1',db,{'url':'https://triathlon.idlaps.com','token':'old','config':pairs(config())})
        a.fire('Screen1','Initialize');a.pump()
        self.assertEqual(db.execute('SELECT payload,assignment FROM readings_v3').fetchone(),('{"original":true}','p1'))
        self.assertTrue(a.properties['Pair.Enabled']);self.assertEqual(a.env['global pending'],1)
        a.fire('Screen1','Initialize');a.pump();self.assertEqual(db.execute('SELECT COUNT(*) FROM readings_v3').fetchone()[0],1)
    def test_bib_validation_matches_name_and_preserves_leading_zero(self):
        p=self.make();a=Runtime('Screen2',p.db,p.tags);a.fire('Screen2','Initialize');a.pump()
        for value_ in ['', '1234','1.2','-1','1e2',' 7','7 ','１２','abc']:
            a.properties['Bib.Text']=value_;a.fire('Bib','OnTextChanged');self.assertFalse(a.properties['Save.Enabled'],value_)
        for bib,name in [('007','Ayu · Elite'),('7','Budi · Junior')]:
            a.properties['Bib.Text']=bib;a.fire('Bib','OnTextChanged');self.assertEqual(a.properties['Participant.Text'],name)
        self.capture(a)
        row=p.db.execute('SELECT bib,payload FROM readings_v3').fetchone();self.assertEqual(row[0],'007');self.assertEqual(json.loads(row[1])['bib'],'007')
        self.capture(a,'999');self.assertIn('periksa',a.properties['Save.Text']);self.assertEqual(p.db.execute('SELECT COUNT(*) FROM readings_v3').fetchone()[0],2)
    def test_invalid_lap_does_not_crash_or_capture(self):
        p=self.make();p.tags['config']=pairs(config(1,3));p.proc('KeepProfile')
        a=Runtime('Screen2',p.db,p.tags);a.fire('Screen2','Initialize');a.pump()
        for lap in ['', '0', '101', 'abc', '-1', '1.2']:
            a.properties['Lap.Text']=lap;self.capture(a)
            self.assertEqual(p.db.execute('SELECT COUNT(*) FROM readings_v3').fetchone()[0],0)
        a.properties['Lap.Text']='2';self.capture(a)
        self.assertEqual(p.db.execute('SELECT bib,lap FROM readings_v3').fetchone(),('007',2))

    def test_switch_pending_and_upload_each_original_profile(self):
        p=self.make();a=Runtime('Screen2',p.db,p.tags);a.fire('Screen2','Initialize');a.pump();self.capture(a,'999')
        p.fire('Web1','GotText',responseCode=200,responseContent=json.dumps({'ok':True,'token':'token-2','config':config(2,3,2)}));p.pump()
        self.assertEqual(p.opened,'Screen2');self.assertEqual(p.tags['current_profile'],'p2')
        b=Runtime('Screen2',p.db,p.tags);b.fire('Screen2','Initialize');b.pump();self.capture(b,'007')
        b.fire('Send','Click');b.pump()
        post=[x for x in b.requests if x[1]=='PostText'][-1];body=json.loads(post[3][0]);self.assertEqual(body['token'],'token-1');old=body['data'][0];self.assertEqual(old['event_id'],1)
        b.fire('Web1','GotText',responseCode=200,responseContent=json.dumps({'ok':True,'accepted_ids':[],'rejected':[{'record_id':old['record_id'],'message':'BIB belum terdaftar'}]}));b.pump()
        body=json.loads([x for x in b.requests if x[1]=='PostText'][-1][3][0]);self.assertEqual(body['token'],'token-2');self.assertEqual(body['data'][0]['checkpoint'],3)
        b.fire('Web1','GotText',responseCode=200,responseContent=json.dumps({'ok':True,'accepted_ids':[body['data'][0]['record_id']],'rejected':[]}));b.pump()
        self.assertFalse(b.env['global sending']);self.assertEqual(p.db.execute('SELECT COUNT(*) FROM readings_v3 WHERE sent=0').fetchone()[0],1)
    def test_renewed_code_updates_same_profile_without_retargeting_queue(self):
        p=self.make();a=Runtime('Screen2',p.db,p.tags);a.fire('Screen2','Initialize');a.pump();self.capture(a)
        original=p.db.execute('SELECT payload,assignment FROM readings_v3').fetchone()
        p.fire('Web1','GotText',responseCode=200,responseContent=json.dumps({'ok':True,'token':'renewed-token','config':config()}));p.pump()
        self.assertEqual(p.tags['current_profile'],'p1')
        self.assertEqual(p.db.execute('SELECT payload,assignment FROM readings_v3').fetchone(),original)
        b=Runtime('Screen2',p.db,p.tags);b.fire('Screen2','Initialize');b.pump();b.fire('Send','Click');b.pump()
        body=json.loads([x for x in b.requests if x[1]=='PostText'][-1][3][0]);self.assertEqual(body['token'],'renewed-token')

    def test_shared_point_records_both_stages_and_multiple_categories(self):
        p=self.make();p.tags['config']=pairs(config(1,2));p.proc('KeepProfile')
        a=Runtime('Screen2',p.db,p.tags);a.fire('Screen2','Initialize');a.pump()
        self.capture(a,'007');self.capture(a,'7')
        a.properties['Bib.Text']='007';a.fire('Bib','OnTextChanged');a.fire('Run','Click');a.pump()
        self.assertEqual(p.db.execute('SELECT bib,stage FROM readings_v3 ORDER BY rowid').fetchall(),[('007','cycle_start'),('7','cycle_start'),('007','run_start')])

    def test_correction_transaction_retains_time_and_cancel_precedes_replacement(self):
        p=self.make();a=Runtime('Screen2',p.db,p.tags);a.fire('Screen2','Initialize');a.pump();self.capture(a,'999')
        old=p.db.execute('SELECT record_id,captured_ms,payload FROM readings_v3').fetchone()
        r=Runtime('Screen3',p.db,p.tags);r.fire('Screen3','Initialize');r.pump();r.properties['Pick.SelectionIndex']=1;r.fire('Pick','AfterPicking');r.properties['EditBib.Text']='007';r.fire('Correct','Click');r.pump()
        rows=p.db.execute('SELECT record_id,bib,captured_ms,cancelled,replaces FROM readings_v3 ORDER BY rowid').fetchall()
        self.assertEqual(len(rows),2);self.assertEqual(rows[0][3],1);self.assertEqual(rows[1][1],'007');self.assertEqual(rows[1][2],old[1]);self.assertEqual(rows[1][4],old[0])
        self.assertEqual(p.db.execute('SELECT payload FROM readings_v3 WHERE record_id=?',(old[0],)).fetchone()[0],old[2])
        a.fire('Screen2','OtherScreenClosed');a.fire('Send','Click');a.pump()
        req=[x for x in a.requests if x[1]=='PostText'][-1];self.assertTrue(req[2].endswith('cancel'))
        a.fire('Web1','GotText',responseCode=200,responseContent=json.dumps({'ok':True,'accepted_ids':[old[0]],'rejected':[]}));a.pump()
        req=[x for x in a.requests if x[1]=='PostText'][-1];self.assertTrue(req[2].endswith('upload'));self.assertEqual(json.loads(req[3][0])['data'][0]['captured_ms'],old[1])


if __name__=='__main__':unittest.main(verbosity=2)
