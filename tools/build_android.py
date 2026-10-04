"""Generate an editable Kodular .aia from the supplied project, preserving its assets.

No APK is produced by this script. Import the resulting .aia into Kodular for device QA.
"""
import argparse
import copy
import json
from pathlib import Path
import uuid
import zipfile
import xml.etree.ElementTree as E

NS = 'https://developers.google.com/blockly/xml'
E.register_namespace('', NS)
def el(tag, attrs=None): return E.Element('{'+NS+'}'+tag, attrs or {})
def block(kind, fields=None, values=None, mutation=None):
    b=el('block', {'type':kind,'id':uuid.uuid4().hex})
    if mutation is not None: b.append(el('mutation',{k:str(v).lower() if isinstance(v,bool) else str(v) for k,v in mutation.items()}))
    for name,value in (fields or {}).items():
        f=el('field',{'name':name});f.text=str(value);b.append(f)
    for name,value in (values or {}).items():
        v=el('value',{'name':name});v.append(value);b.append(v)
    return b
def chain(*blocks):
    blocks=[b for b in blocks if b is not None]
    if not blocks:return None
    root=blocks[0]; last=root
    for b in blocks[1:]:
        n=el('next');n.append(b);last.append(n);last=b
    return root
def stmt(b,name,*blocks):
    s=el('statement',{'name':name});c=chain(*blocks)
    if c is not None:s.append(c)
    b.append(s);return b
def text(s=''):return block('text',{'TEXT':s})
def num(n):return block('math_number',{'NUM':n})
def boolean(v):return block('logic_boolean',{'BOOL':'TRUE' if v else 'FALSE'})
def var(n):return block('lexical_variable_get',{'VAR':n})
def setvar(n,v):return block('lexical_variable_set',{'VAR':n},{'VALUE':v})
def glob(n,v):return block('global_declaration',{'NAME':n},{'VALUE':v})
def seq(*items):return block('lists_create_with',values={f'ADD{i}':v for i,v in enumerate(items)},mutation={'items':len(items)})
def join(*items):return block('text_join',values={f'ADD{i}':v for i,v in enumerate(items)},mutation={'items':len(items)})
def op(kind,a,b):return block({'add':'math_add','sub':'math_subtract','div':'math_division','mul':'math_multiply'}[kind],values={'NUM0' if kind in ('add','mul') else 'A':a,'NUM1' if kind in ('add','mul') else 'B':b},mutation={'items':2} if kind in ('add','mul') else None)
def cmp(a,b,operator='EQ'):return block('math_compare',{'OP':operator},{'A':a,'B':b})
def eq(a,b):return block('logic_compare',{'OP':'EQ'},{'A':a,'B':b})
def both(a,b):return block('logic_operation',{'OP':'AND'},{'A':a,'B':b},mutation={'items':2})
def cond(test,yes,no=None):
    b=block('controls_if',values={'IF0':test},mutation={'else':1} if no is not None else None);stmt(b,'DO0',yes)
    if no is not None:stmt(b,'ELSE',no)
    return b
TYPES={}
def prop(instance,name,value=None):
    return block('component_set_get',{'COMPONENT_SELECTOR':instance,'PROP':name},{'VALUE':value} if value is not None else None,
                 {'component_type':TYPES[instance],'set_or_get':'set' if value is not None else 'get','property_name':name,'is_generic':False,'instance_name':instance})
def call(instance,method,*args):
    return block('component_method',{'COMPONENT_SELECTOR':instance},{f'ARG{i}':v for i,v in enumerate(args)},
                 {'component_type':TYPES[instance],'method_name':method,'is_generic':False,'instance_name':instance})
def event(instance,name,*body):
    return stmt(block('component_event',{'COMPONENT_SELECTOR':instance},mutation={'component_type':TYPES[instance],'is_generic':False,'instance_name':instance,'event_name':name}),'DO',*body)
def proc(name,*body):return stmt(block('procedures_defnoreturn',{'NAME':name}),'STACK',*body)
def run(name):return block('procedures_callnoreturn',{'PROCNAME':name},mutation={'name':name})
def lookup(obj,key,default=None):return block('lists_lookup_in_pairs',values={'KEY':text(key),'LIST':obj,'NOTFOUND':default if default is not None else text()})
def dictionary(pairs):
    vals={}
    for i,(k,v) in enumerate(pairs.items()):vals['ADD'+str(i)]=block('pair',values={'KEY':text(k),'VALUE':v})
    return block('dictionaries_create_with',values=vals,mutation={'items':len(vals)})
def index(obj,n):return block('lists_select_item',values={'LIST':obj,'NUM':num(n)})
def each(name,items,*body):return stmt(block('controls_forEach',{'VAR':name},{'LIST':items}),'DO',*body)
def local(name,value,*body):
    b=block('local_declaration_statement',{'VAR0':name},{'DECL0':value},mutation={})
    b.find('{'+NS+'}mutation').append(el('localname',{'name':name}));return stmt(b,'STACK',*body)
def gettag(name,default=None):return call('TinyDB1','GetValue',text(name),default if default is not None else text())
def storetag(name,value):return call('TinyDB1','StoreValue',text(name),value)
def notice(message):return call('Notifier1','ShowAlert',message)
def now():return call('Clock1','SystemTime')
def length(value):return block('lists_length',values={'LIST':value})
def open_screen(name):return block('controls_openAnotherScreen',values={'SCREEN':text(name)})
def components(names):
    TYPES.clear()
    def visit(c):
        TYPES[c['$Name']]=c['$Type']
        for child in c.get('$Components',[]):visit(child)
    for c in names:visit(c)
def component(name,typ,version,**props):
    return {'$Name':name,'$Type':typ,'$Version':str(version),'Uuid':str(uuid.uuid4().int%2000000000),**{k:str(v) for k,v in props.items()}}
def label(name,value):return component(name,'Label',10,Text=value,Width='-2',FontSize=16)
def button(name,value):return component(name,'Button',13,Text=value,Width='-2',Height=55,FontBold='True',BackgroundColor='&HFF176C65',TextColor='&HFFFFFFFF',Shape=1)
def inputbox(name,hint,**props):return component(name,'TextBox',13,**{'Hint':hint,'Width':'-2','FontSize':20,**props})
def screen(name,children):
    return {'authURL':['creator.kodular.io','creator-old.kodular.io','creator-new.kodular.io'],'YaVersion':'247','Source':'Form','Properties':{
        '$Name':name,'$Type':'Form','$Version':'46','Uuid':'0','AppName':'IDLAPS Triathlon Tap','Title':name,'TitleVisible':'False','ScreenOrientation':'portrait','Sizing':'Responsive','KeepScreenOn':'True','Scrollable':'True','ShowListsAsJson':'True','ShowOptionsMenu':'False','BackgroundColor':'&HFFF4F7F6','PrimaryColor':'&HFF176C65','AccentColor':'&HFF176C65','MinSdk':'23','$Components':children}}
def xml(blocks):
    root=el('xml',{'xmlns':'https://developers.google.com/blockly/xml'})
    # ElementTree already writes the namespace; do not duplicate its xmlns attribute.
    root.attrib.pop('xmlns')
    for i,b in enumerate(blocks):b.set('x',str((i%4)*600));b.set('y',str((i//4)*700));root.append(b)
    root.append(el('yacodeblocks',{'ya-version':'247','language-version':'36'}));return E.tostring(root,encoding='utf-8',xml_declaration=True)

def build(source,destination):
    pages={}
    schema="CREATE TABLE IF NOT EXISTS readings_v2(record_id TEXT PRIMARY KEY,bib TEXT,stage TEXT,lap INTEGER,captured_ms INTEGER,payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,cancelled INTEGER NOT NULL DEFAULT 0,cancel_sent INTEGER NOT NULL DEFAULT 0)"
    c1=[label('Heading','IDLAPS · Pasangkan pencatat manual'),label('Info','Masukkan URL admin dan kode pemasangan. Setelah dipasangkan, pencatatan dapat berjalan tanpa internet.'),inputbox('Server','https://admin-anda.com'),inputbox('Code','Kode pemasangan'),button('Pair','Hubungkan'),button('Continue','Buka pencatatan tersimpan'),label('Status','Belum terhubung'),component('TinyDB1','TinyDB',2,Namespace='IDLAPSTriathlonV2'),component('Web1','Web',6,Timeout=15000),component('Notifier1','Notifier',11),component('Clock1','Clock',4,TimerEnabled='False'),component('SQLite1','SQLite',2,ReturnHeader='False',SuppressToast='True')]
    components(c1+[{'$Name':'Screen1','$Type':'Form'}])
    header=seq(seq(text('Content-Type'),text('application/json')))
    blocks=[glob('pending',num(999999)),
      event('Screen1','Initialize',prop('Server','Text',gettag('url')),prop('Continue','Enabled',cmp(gettag('token'),text(),'NEQ')),prop('Pair','Enabled',boolean(False)),call('SQLite1','SingleSQL',text(schema))),
      event('SQLite1','AfterExecution',cond(var('wasExecuted'),call('SQLite1','RawQuery',text('SELECT COUNT(*) FROM readings_v2 WHERE sent=0 OR (cancelled=1 AND cancel_sent=0)'),seq()),notice(text('Penyimpanan belum siap.')))),
      event('SQLite1','AfterQuery',setvar('global pending',index(index(var('result'),1),1)),prop('Pair','Enabled',boolean(True))),
      event('Continue','Click',open_screen('Screen2')),
      event('Pair','Click',prop('Pair','Enabled',boolean(False)),prop('Web1','Url',join(prop('Server','Text'),text('/api.php?action=pair'))),prop('Web1','RequestHeaders',header),call('Web1','PostText',dictionary({'code':prop('Code','Text')}))),
      event('Web1','GotText',prop('Pair','Enabled',boolean(True)),cond(eq(var('responseCode'),num(200)),
        local('reply',call('Web1','JsonTextDecode',var('responseContent')),
          cond(both(eq(lookup(var('reply'),'ok',boolean(False)),boolean(True)),eq(lookup(lookup(lookup(var('reply'),'config'),'device'),'kind'),text('manual'))),
            cond(block('logic_operation',{'OP':'OR'},{'A':eq(var('global pending'),num(0)),'B':both(eq(lookup(lookup(gettag('config',seq()),'device',seq()),'id'),lookup(lookup(lookup(var('reply'),'config'),'device'),'id')),eq(prop('Server','Text'),gettag('url')))},mutation={'items':2}),
              chain(storetag('url',prop('Server','Text')),storetag('token',lookup(var('reply'),'token')),storetag('config',lookup(var('reply'),'config')),prop('Continue','Enabled',boolean(True)),open_screen('Screen2')),
              notice(text('Masih ada antrean penugasan lama. Kirim dahulu. Kode baru telah terpakai; minta admin membuat ulang setelah antrean selesai.'))),
            notice(text('Kode harus untuk perangkat Android manual. Buat ulang kode dari admin jika salah penugasan.')))),notice(text('Pemasangan gagal. Periksa alamat server, internet, dan kode pemasangan.')))),
      event('Web1','TimedOut',prop('Pair','Enabled',boolean(True)),notice(text('Server belum menjawab. Jika kode sudah terpakai, minta admin membuat ulang kode.'))),
      event('SQLite1','ErrorOccurred',notice(join(text('Penyimpanan: '),var('message'))))]
    pages['Screen1']=(screen('Screen1',c1),xml(blocks))

    # Store immutable payload text so retries use byte-for-byte equivalent fields.
    c2=[label('Heading','IDLAPS · Pencatatan manual'),label('Assignment','Memuat penugasan…'),label('ClockStatus','Jam belum terverifikasi'),label('SyncStatus','Catatan tersimpan lokal'),inputbox('Bib','Nomor BIB',FontSize=32),inputbox('Lap','Putaran',Text='1',NumbersOnly='True'),button('Save','Catat lintasan'),button('Run','Mulai Lari'),button('Send','Kirim Data'),button('Undo','Batalkan catatan terakhir'),button('Refresh','Periksa jam & unduh konfigurasi'),label('History','Riwayat terbaru akan tampil di sini'),component('TinyDB1','TinyDB',2,Namespace='IDLAPSTriathlonV2'),component('SQLite1','SQLite',2,ReturnHeader='False',SuppressToast='True'),component('SQLiteList','SQLite',2,ReturnHeader='False',SuppressToast='True'),component('SQLiteSend','SQLite',2,ReturnHeader='False',SuppressToast='True'),component('SQLiteCancel','SQLite',2,ReturnHeader='False',SuppressToast='True'),component('WebCancel','Web',6,Timeout=15000),component('Web1','Web',6,Timeout=15000),component('WebTime','Web',6,Timeout=10000),component('WebConfig','Web',6,Timeout=15000),component('Clock1','Clock',4,TimerEnabled='True',TimerInterval=60000,TimerAlwaysFires='False'),component('Notifier1','Notifier',11)]
    components(c2+[{'$Name':'Screen2','$Type':'Form'}])
    g=lambda n:var('global '+n)
    setg=lambda n,v:setvar('global '+n,v)
    cfg=lambda key:lookup(g('config'),key)
    dev=lambda key:lookup(cfg('device'),key)
    refresh=call('SQLiteList','RawQuery',text('SELECT bib,stage,lap,captured_ms,sent,cancelled FROM readings_v2 ORDER BY rowid DESC LIMIT 12'),seq())
    globals_=[glob('config',seq()),glob('offset',num(0)),glob('quality',text('unverified')),glob('last_sync',num(0)),glob('requested',num(0)),glob('stage',text()),glob('sent_ids',seq()),glob('counter',num(0)),glob('sample_count',num(0)),glob('best_rtt',num(999999)),glob('best_offset',num(0)),glob('time_busy',boolean(False)),glob('last_saved',text())]
    schema="CREATE TABLE IF NOT EXISTS readings_v2(record_id TEXT PRIMARY KEY,bib TEXT,stage TEXT,lap INTEGER,captured_ms INTEGER,payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,cancelled INTEGER NOT NULL DEFAULT 0,cancel_sent INTEGER NOT NULL DEFAULT 0)"
    blocks=globals_+[
      proc('ApplyConfig',setg('config',gettag('config',seq())),prop('Assignment','Text',join(lookup(cfg('event'),'name'),text(' · '),dev('name'),text(' · titik '),dev('checkpoint'))),prop('Run','Visible',eq(dev('checkpoint'),num(2))),prop('Lap','Visible',cmp(dev('checkpoint'),num(2),'GT')),
        cond(eq(dev('checkpoint'),num(1)),prop('Save','Text',text('Catat Finish Swim')),
          cond(eq(dev('checkpoint'),num(2)),prop('Save','Text',text('Mulai Sepeda')),
            cond(eq(dev('checkpoint'),num(3)),prop('Save','Text',text('Catat Lintasan Sepeda')),prop('Save','Text',text('Catat Lintasan Lari')))))),
      proc('RequestTime',setg('requested',now()),prop('WebTime','Url',join(gettag('url'),text('/api.php?action=time'))),call('WebTime','Get')),
      proc('SyncTime',cond(eq(g('time_busy'),boolean(False)),chain(setg('time_busy',boolean(True)),setg('sample_count',num(0)),setg('best_rtt',num(999999)),run('RequestTime')))),
      proc('ShowHistory',refresh),
      event('Screen2','Initialize',run('ApplyConfig'),prop('Save','Enabled',boolean(False)),prop('Run','Enabled',boolean(False)),prop('Send','Enabled',boolean(False)),setg('counter',gettag('counter',num(0))),setg('last_saved',gettag('last_saved')),setg('offset',gettag('offset',num(0))),call('SQLite1','SingleSQL',text(schema)),run('SyncTime')),
      event('SQLite1','AfterExecution',cond(var('wasExecuted'),chain(prop('Save','Enabled',boolean(True)),prop('Run','Enabled',boolean(True)),prop('Send','Enabled',boolean(True)),run('ShowHistory')),notice(text('Penyimpanan belum siap. Jangan mulai pencatatan.')))),
      event('Save','Click',cond(eq(dev('checkpoint'),num(1)),setg('stage',text('swim_finish')),cond(eq(dev('checkpoint'),num(2)),setg('stage',text('cycle_start')),cond(eq(dev('checkpoint'),num(3)),setg('stage',text('cycle')),setg('stage',text('run'))))),run('Capture')),
      event('Run','Click',setg('stage',text('run_start')),run('Capture')),
      proc('Capture',cond(cmp(prop('Bib','Text'),text(),'NEQ'),chain(
        setg('counter',op('add',g('counter'),num(1))),storetag('counter',g('counter')),
        cond(cmp(op('sub',now(),g('last_sync')),num(0),'LT'),setg('quality',text('jump')),cond(cmp(op('sub',now(),g('last_sync')),num(600000),'GT'),setg('quality',text('stale')))),
        local('stamp',block('math_round',{'OP':'ROUND'},{'NUM':op('add',now(),g('offset'))}),
          local('rid',join(text('manual-'),dev('id'),text('-'),g('counter')),
            local('lap',num(1),
              cond(cmp(dev('checkpoint'),num(2),'GT'),setvar('lap',op('add',prop('Lap','Text'),num(0)))),
              local('payload',dictionary({'record_id':var('rid'),'event_id':lookup(cfg('event'),'id'),'bib':block('text_trim',values={'TEXT':prop('Bib','Text')}),'checkpoint':dev('checkpoint'),'stage':g('stage'),'lap':var('lap'),'captured_ms':var('stamp'),'clock_quality':g('quality'),'config_version':dev('config_version'),'phone_ms':now(),'offset_ms':g('offset'),'sync_age_ms':op('sub',now(),g('last_sync'))}),
                local('inserted',call('SQLite1','Insert',text('readings_v2'),seq(*map(text,['record_id','bib','stage','lap','captured_ms','payload'])),seq(var('rid'),prop('Bib','Text'),g('stage'),var('lap'),var('stamp'),join(text(),var('payload')))),
                  cond(cmp(var('inserted'),num(-1),'NEQ'),chain(setg('last_saved',var('rid')),storetag('last_saved',var('rid')),prop('Bib','Text',text()),prop('SyncStatus','Text',text('Tersimpan di ponsel. Tekan Kirim Data saat internet tersedia.')),run('ShowHistory')),notice(text('Gagal menyimpan. Ulangi pencatatan dan periksa penyimpanan ponsel.'))))))))),notice(text('Isi BIB terlebih dahulu.')))),
      event('SQLiteList','AfterQuery',prop('History','Text',text()),each('row',var('result'),prop('History','Text',join(prop('History','Text'),index(var('row'),1),text(' · '),index(var('row'),2),text(' #'),index(var('row'),3),text(' · '),call('Clock1','FormatDateTime',call('Clock1','MakeInstantFromMillis',index(var('row'),4)),text('dd/MM HH:mm:ss')),text(' · terkirim='),index(var('row'),5),text(' · batal='),index(var('row'),6),text('\n'))))),
      event('Send','Click',prop('Send','Enabled',boolean(False)),call('SQLiteSend','RawQuery',text('SELECT record_id,payload FROM readings_v2 WHERE sent=0 AND cancelled=0 ORDER BY rowid LIMIT 100'),seq())),
      event('SQLiteSend','AfterQuery',cond(cmp(var('numberOfRecords'),num(0),'GT'),chain(setg('sent_ids',seq()),
        local('payloads',seq(),each('row',var('result'),block('lists_add_items',values={'LIST':g('sent_ids'),'ITEM0':index(var('row'),1)},mutation={'items':1}),block('lists_add_items',values={'LIST':var('payloads'),'ITEM0':index(var('row'),2)},mutation={'items':1})),
          prop('Web1','Url',join(gettag('url'),text('/api.php?action=upload'))),prop('Web1','RequestHeaders',seq(seq(text('Content-Type'),text('application/json')))),
          call('Web1','PostText',join(text('{"token":"'),gettag('token'),text('","data":['),block('lists_join_with_separator',values={'SEPARATOR':text(','),'LIST':var('payloads')}),text(']}'))))),chain(prop('Send','Enabled',boolean(True)),prop('SyncStatus','Text',text('Catatan sudah terkirim; memeriksa pembatalan.')),run('SendCancellations')))),
      event('Web1','GotText',prop('Send','Enabled',boolean(True)),cond(eq(var('responseCode'),num(200)),
        local('reply',call('Web1','JsonTextDecode',var('responseContent')),
          cond(eq(lookup(var('reply'),'ok',boolean(False)),boolean(True)),
            chain(each('rid',lookup(var('reply'),'accepted_ids',seq()),cond(block('lists_is_in',values={'ITEM':var('rid'),'LIST':g('sent_ids')}),local('updated',call('SQLite1','Update',text('readings_v2'),seq(text('sent')),seq(num(1)),text('record_id=?'),seq(var('rid'))),cond(eq(var('updated'),num(-1)),notice(text('Status lokal belum tersimpan; kirim ulang aman.')))))),
              prop('SyncStatus','Text',join(text('Diterima server: '),length(lookup(var('reply'),'accepted_ids',seq())),text('. Ditolak: '),length(lookup(var('reply'),'rejected',seq())),text('. Tekan Kirim lagi jika masih ada antrean.'))),
              each('problem',lookup(var('reply'),'rejected',seq()),notice(join(lookup(var('problem'),'record_id'),text(': '),lookup(var('problem'),'message')))),run('ShowHistory'),run('SendCancellations')),
            notice(text('Server belum menerima data. Catatan tetap di ponsel.')))),notice(text('Kirim belum berhasil. Catatan tetap di ponsel; coba lagi.')))),
      event('Web1','TimedOut',prop('Send','Enabled',boolean(True)),notice(text('Koneksi terputus. Tekan Kirim lagi; data yang sama tidak akan digandakan.'))),
      event('Refresh','Click',run('SyncTime'),prop('WebConfig','Url',join(gettag('url'),text('/api.php?action=config'))),prop('WebConfig','RequestHeaders',seq(seq(text('Authorization'),join(text('Bearer '),gettag('token'))))),call('WebConfig','Get')),
      event('WebConfig','GotText',cond(eq(var('responseCode'),num(200)),local('reply',call('WebConfig','JsonTextDecode',var('responseContent')),storetag('config',lookup(var('reply'),'config')),run('ApplyConfig')),notice(text('Konfigurasi tersimpan tetap dipakai. Unduhan belum berhasil.')))),
      event('Clock1','Timer',run('SyncTime')),
      event('WebTime','GotText',cond(eq(var('responseCode'),num(200)),
        local('reply',call('WebTime','JsonTextDecode',var('responseContent')),
          local('rtt',op('sub',now(),g('requested')),
            cond(both(cmp(var('rtt'),num(0),'GTE'),cmp(var('rtt'),g('best_rtt'),'LT')),
              chain(setg('best_rtt',var('rtt')),setg('best_offset',op('sub',op('add',lookup(var('reply'),'server_ms'),op('div',var('rtt'),num(2))),now())))),
            setg('sample_count',op('add',g('sample_count'),num(1))),
            cond(cmp(g('sample_count'),num(3),'LT'),run('RequestTime'),chain(setg('time_busy',boolean(False)),
              cond(cmp(g('best_rtt'),num(2000),'LT'),chain(setg('offset',g('best_offset')),storetag('offset',g('offset')),setg('last_sync',now()),setg('quality',text('synced')),prop('ClockStatus','Text',text('Jam diselaraskan · mengikuti acuan server'))),chain(setg('quality',text('unverified')),prop('ClockStatus','Text',text('Jam belum stabil · catatan akan ditandai')))))))),
        chain(setg('time_busy',boolean(False)),prop('ClockStatus','Text',text('Offline · acuan terakhir, perlu pemeriksaan jika lama terputus'))))),
      event('WebTime','TimedOut',setg('time_busy',boolean(False)),prop('ClockStatus','Text',text('Offline · waktu memakai acuan terakhir'))),
    ]
    blocks.extend([
      event('Undo','Click',cond(cmp(g('last_saved'),text(),'NEQ'),call('Notifier1','ShowChooseDialog',text('Batalkan catatan terakhir? Riwayat tetap tersimpan dan pembatalan ikut dikirim ke server.'),text('Periksa sebelum membatalkan'),text('Ya'),text('Tidak'),boolean(False)),notice(text('Belum ada catatan.')))),
      event('Notifier1','AfterChoosing',cond(eq(var('choice'),text('Ya')),local('updated',call('SQLite1','Update',text('readings_v2'),seq(text('cancelled')),seq(num(1)),text('record_id=?'),seq(g('last_saved'))),cond(cmp(var('updated'),num(-1),'NEQ'),chain(prop('SyncStatus','Text',text('Dibatalkan lokal. Tekan Kirim Data agar server menerima pembatalan.')),run('ShowHistory')),notice(text('Pembatalan belum tersimpan.')))))),
      proc('SendCancellations',call('SQLiteCancel','RawQuery',text('SELECT record_id FROM readings_v2 WHERE cancelled=1 AND cancel_sent=0 LIMIT 100'),seq())),
      event('SQLiteCancel','AfterQuery',cond(cmp(var('numberOfRecords'),num(0),'GT'),local('ids',seq(),each('row',var('result'),block('lists_add_items',values={'LIST':var('ids'),'ITEM0':index(var('row'),1)},mutation={'items':1})),prop('WebCancel','Url',join(gettag('url'),text('/api.php?action=cancel'))),prop('WebCancel','RequestHeaders',seq(seq(text('Content-Type'),text('application/json')))),call('WebCancel','PostText',dictionary({'token':gettag('token'),'record_ids':var('ids')}))))),
      event('WebCancel','GotText',cond(eq(var('responseCode'),num(200)),local('reply',call('WebCancel','JsonTextDecode',var('responseContent')),each('rid',lookup(var('reply'),'accepted_ids',seq()),local('updated',call('SQLite1','Update',text('readings_v2'),seq(text('cancel_sent'),text('sent')),seq(num(1),num(1)),text('record_id=?'),seq(var('rid'))),cond(eq(var('updated'),num(-1)),notice(text('Konfirmasi pembatalan belum tersimpan; kirim ulang.'))))),run('ShowHistory')),notice(text('Pembatalan belum terkirim. Tekan Kirim lagi.')))),
      event('WebCancel','TimedOut',notice(text('Pembatalan tetap tersimpan lokal. Tekan Kirim lagi.'))),
    ])
    for instance in ['SQLite1','SQLiteList','SQLiteSend','SQLiteCancel']:
        blocks.append(event(instance,'ErrorOccurred',prop('Send','Enabled',boolean(True)),notice(join(text('Penyimpanan: '),var('message')))))
    pages['Screen2']=(screen('Screen2',c2),xml(blocks))
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as out:
        for name in original.namelist():
            if name.startswith('assets/'):out.writestr(name,original.read(name))
        base='src/io/kodular/ktcxpgt/IDLapsTap/'
        for name,(design,blocks) in pages.items():
            out.writestr(base+name+'.scm','#|\n$JSON\n'+json.dumps(design,separators=(',',':'))+'\n|#')
            out.writestr(base+name+'.bky',blocks)
        props=original.read('youngandroidproject/project.properties').decode()
        props=props.replace('screenNames=Screen1, Screen2, ScreenIdentitas','screenNames=Screen1, Screen2').replace('packagename=com.idlaps.tap','packagename=com.idlaps.triathlontap').replace('aname=IDLaps Tap','aname=IDLAPS Triathlon Tap').replace('versioncode=1','versioncode=2').replace('versionname=1.1','versionname=2.0').replace('minSdk=21','minSdk=23')
        out.writestr('youngandroidproject/project.properties',props)
    print(destination)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args()
    Path(a.destination).parent.mkdir(parents=True,exist_ok=True);build(a.source,a.destination)
