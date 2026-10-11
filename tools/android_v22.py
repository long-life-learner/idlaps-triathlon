"""Kodular screens with durable per-assignment queues and explicit local corrections."""
from android_blocks import *
import android_sql as sql
from android_ui import decorate

SERVER='https://triathlon.idlaps.com'
g=lambda n:var('global '+n)
sg=lambda n,v:setvar('global '+n,v)


def getkey(key,default=None):return call('TinyDB1','GetValue',key,default if default is not None else text())
def putkey(key,value):return call('TinyDB1','StoreValue',key,value)
def neq(a,b):return block('logic_compare',{'OP':'NEQ'},{'A':a,'B':b})
def either(a,b):return block('logic_operation',{'OP':'OR'},{'A':a,'B':b},mutation={'items':2})
def choose(test,yes,no):return block('controls_choose',values={'TEST':test,'THENRETURN':yes,'ELSERETURN':no})
def textlen(v):return block('text_length',values={'VALUE':v})
def quoted(v):return join(text("'"),block('text_replace_all',values={'TEXT':v,'SEGMENT':text("'"),'REPLACEMENT':text("''")}),text("'"))
def add(items,value):return block('lists_add_items',values={'LIST':items,'ITEM0':value},mutation={'items':1})
def inlist(item,items):return block('lists_is_in',values={'ITEM':item,'LIST':items})
def close_screen():return block('controls_closeScreen')
def cfg(key):return lookup(g('config'),key)
def dev(key):return lookup(cfg('device'),key)
def profile(key):return getkey(join(text('profile:'),key),seq())
def response():return call('Web1','JsonTextDecode',var('responseContent'))
def headers():return seq(seq(text('Content-Type'),text('application/json')))
def sqlite(name):return component(name,'SQLite',2,ReturnHeader='False',SuppressToast='True')
def hidden(names=()):return [component('TinyDB1','TinyDB',2,Namespace='IDLAPSTriathlonV2'),component('Clock1','Clock',4,TimerEnabled='False'),component('Notifier1','Notifier',11)]+[sqlite(n) for n in names]
def layout(children):
    c=component('Page','VerticalArrangement',10,Width=-1092,Height=-1,AlignHorizontal=3)
    c['$Components']=children;return c
def tint(item,**props):item.update({k:str(v) for k,v in props.items()});return item
def bibbox(name):return inputbox(name,'BIB · 1–3 digit',InputType=5,Multiline='False',FontSize=30,TextAlignment=1)
def stage_text(stage):
    result=text('Lintasan')
    for key,label_ in reversed(list({'swim_finish':'Finish swim','cycle_start':'Mulai sepeda','run_start':'Mulai lari','cycle':'Sepeda','run':'Lari'}.items())):
        result=choose(eq(stage(),text(key)),text(label_),result)
    return result


def profile_blocks():
    # A profile ID is local and stable even when a token is renewed. No user text enters migration SQL.
    return [proc('KeepProfile',
      cond(neq(gettag('token'),text()),local('identity',join(gettag('url',text(SERVER)),text('|'),lookup(lookup(gettag('config',seq()),'event',seq()),'id'),text('|'),lookup(lookup(gettag('config',seq()),'device',seq()),'id')),
        local('key',getkey(join(text('identity:'),var('identity'))),
          cond(eq(var('key'),text()),chain(storetag('profile_counter',op('add',gettag('profile_counter',num(0)),num(1))),setvar('key',join(text('p'),gettag('profile_counter'))),putkey(join(text('identity:'),var('identity')),var('key')))),
          putkey(join(text('profile:'),var('key')),seq(seq(text('token'),gettag('token')),seq(text('url'),gettag('url',text(SERVER))),seq(text('config'),gettag('config',seq())))),
          storetag('current_profile',var('key'))))))]


def validation_proc():
    # Keyboard type is only a hint; validate paste and each character without truncating or numeric coercion.
    loop=stmt(block('controls_forRange',{'VAR':'i'},{'START':num(1),'END':textlen(g('bib_value')),'STEP':num(1)}),'DO',
        cond(block('logic_negate',values={'BOOL':inlist(block('text_segment',values={'TEXT':g('bib_value'),'START':var('i'),'LENGTH':num(1)}),seq(*[text(str(i)) for i in range(10)]))}),sg('bib_valid',boolean(False))))
    return proc('ValidateBib',sg('bib_valid',both(cmp(textlen(g('bib_value')),num(0),'GT'),cmp(textlen(g('bib_value')),num(3),'LTE'))),cond(g('bib_valid'),loop))


def screen1():
    visual=[label('Heading','IDLAPS · TRIATHLON'),label('Info','Masukkan kode.\nSiap mencatat.'),inputbox('Code','Kode pemasangan'),button('Pair','Hubungkan penugasan'),button('Continue','Lanjutkan pencatatan'),label('Status','Menyiapkan penyimpanan…')]
    # Layout version 2.2 intentionally has no editable server field.
    cs=decorate(visual+hidden(['SQLite1'])+[component('Web1','Web',6,Timeout=15000)],1,component)
    components(cs+[{'$Name':'Screen1','$Type':'Form'}])
    migration=join(text("INSERT OR IGNORE INTO readings_v3(record_id,bib,stage,lap,captured_ms,payload,assignment,sent,cancelled,cancel_sent) SELECT record_id,bib,stage,lap,captured_ms,payload,'"),gettag('current_profile'),text("',sent,cancelled,cancel_sent FROM readings_v2"))
    blocks=[glob('phase',text('schema')),glob('pending',num(0))]+profile_blocks()+[
      proc('CheckQueue',prop('Pair','Enabled',boolean(False)),prop('Continue','Enabled',boolean(False)),call('SQLite1','RawQuery',text(sql.QUEUE),seq())),
      event('Screen1','Initialize',prop('Pair','Enabled',boolean(False)),prop('Continue','Enabled',boolean(False)),run('KeepProfile'),call('SQLite1','MultipleSQL',seq(text(sql.V2),text(sql.V3),text(sql.AUDIT)))),
      event('SQLite1','AfterExecution',cond(var('wasExecuted'),
        cond(both(eq(g('phase'),text('schema')),both(neq(gettag('current_profile'),text()),eq(gettag('migration22',boolean(False)),boolean(False)))),
          chain(sg('phase',text('migrate')),call('SQLite1','SingleSQL',migration)),
          chain(cond(eq(g('phase'),text('migrate')),storetag('migration22',boolean(True))),sg('phase',text('ready')),run('CheckQueue'))),notice(text('Penyimpanan belum siap. Catatan lama tetap dipertahankan.')))),
      event('Screen1','OtherScreenClosed',run('CheckQueue')),
      event('SQLite1','AfterQuery',sg('pending',var('numberOfRecords')),prop('Pair','Enabled',boolean(True)),prop('Continue','Enabled',neq(gettag('token'),text())),prop('Status','Text',join(var('numberOfRecords'),text(' catatan menunggu kirim. Boleh berganti titik; catatan lama tetap pada penugasan asal.')))),
      event('Continue','Click',open_screen('Screen2')),
      event('Pair','Click',prop('Pair','Enabled',boolean(False)),run('KeepProfile'),prop('Web1','Url',text(SERVER+'/api.php?action=pair')),prop('Web1','RequestHeaders',headers()),call('Web1','PostText',dictionary({'code':prop('Code','Text')}))),
      event('Web1','GotText',prop('Pair','Enabled',boolean(True)),cond(eq(var('responseCode'),num(200)),local('reply',response(),
        cond(both(eq(lookup(var('reply'),'ok',boolean(False)),boolean(True)),eq(lookup(lookup(lookup(var('reply'),'config'),'device'),'kind'),text('manual'))),
          chain(storetag('url',text(SERVER)),storetag('token',lookup(var('reply'),'token')),storetag('config',lookup(var('reply'),'config')),run('KeepProfile'),prop('Continue','Enabled',boolean(True)),open_screen('Screen2')),
          notice(text('Gunakan kode untuk Android manual. Minta admin membuat ulang kode jika salah jenis perangkat.')))),notice(text('Kode tidak berlaku atau koneksi gagal. Penugasan dan antrean lama tetap tersedia.')))),
      event('Web1','TimedOut',prop('Pair','Enabled',boolean(True)),notice(text('Belum terhubung. Jika kode terpakai, minta admin membuat ulang kode.'))),
      event('SQLite1','ErrorOccurred',notice(join(text('Penyimpanan: '),var('message'))))]
    return screen('Screen1',cs),xml(blocks)


def capture_blocks():
    capture=proc('Capture',run('MatchBib'),sg('lap_valid',boolean(True)),
      cond(cmp(dev('checkpoint'),num(2),'GT'),chain(
        sg('bib_value',prop('Lap','Text')),run('ValidateBib'),sg('lap_valid',g('bib_valid')),
        cond(g('lap_valid'),sg('lap_valid',both(cmp(op('add',prop('Lap','Text'),num(0)),num(1),'GTE'),cmp(op('add',prop('Lap','Text'),num(0)),num(100),'LTE')))),
        sg('bib_value',prop('Bib','Text')),run('ValidateBib'))),
      cond(both(g('bib_valid'),g('lap_valid')),chain(
        sg('counter',op('add',g('counter'),num(1))),storetag('counter',g('counter')),
        cond(cmp(op('sub',now(),g('last_sync')),num(0),'LT'),sg('quality',text('jump')),cond(cmp(op('sub',now(),g('last_sync')),num(600000),'GT'),sg('quality',text('stale')))),
        local('stamp',block('math_round',{'OP':'ROUND'},{'NUM':op('add',now(),g('offset'))}),
          local('rid',join(text('manual-'),dev('id'),text('-'),g('counter')),
            local('lap',choose(cmp(dev('checkpoint'),num(2),'GT'),op('add',prop('Lap','Text'),num(0)),num(1)),
              local('payload',dictionary({'record_id':var('rid'),'event_id':lookup(cfg('event'),'id'),'bib':g('bib_value'),'checkpoint':dev('checkpoint'),'stage':g('stage'),'lap':var('lap'),'captured_ms':var('stamp'),'clock_quality':g('quality'),'config_version':dev('config_version'),'phone_ms':now(),'offset_ms':g('offset'),'sync_age_ms':op('sub',now(),g('last_sync')),'operator_review':block('logic_negate',values={'BOOL':g('known')})}),
                local('inserted',call('SQLite1','Insert',text('readings_v3'),seq(*map(text,['record_id','bib','stage','lap','captured_ms','payload','assignment','error'])),seq(var('rid'),g('bib_value'),g('stage'),var('lap'),var('stamp'),join(text(),var('payload')),gettag('current_profile'),choose(g('known'),text(),text('BIB belum terdaftar; periksa atau unduh peserta terbaru.')))),
                  cond(cmp(var('inserted'),num(-1),'NEQ'),chain(prop('Bib','Text',text()),prop('SyncStatus','Text',text('Tersimpan di ponsel. Waktu tidak berubah saat dikirim.')),run('ShowHistory')),notice(text('Gagal menyimpan. Catat ulang dan periksa penyimpanan.'))))))))),notice(choose(g('bib_valid'),text('Isi nomor putaran 1–100.'),text('BIB harus 1–3 digit angka.')))))
    return [capture,
      proc('MatchBib',sg('bib_value',prop('Bib','Text')),run('ValidateBib'),sg('known',boolean(False)),prop('Participant','Text',text('BIB harus 1–3 digit angka.')),
        cond(g('bib_valid'),chain(prop('Participant','Text',text('Belum terdaftar · boleh simpan untuk diperiksa.')),
          each('p',lookup(g('config'),'participants',seq()),cond(eq(join(text('bib:'),lookup(var('p'),'bib')),join(text('bib:'),g('bib_value'))),chain(sg('known',boolean(True)),
            prop('Participant','Text',lookup(var('p'),'name')),each('c',lookup(g('config'),'categories',seq()),cond(eq(lookup(var('c'),'id'),lookup(var('p'),'category_id')),prop('Participant','Text',join(lookup(var('p'),'name'),text(' · '),lookup(var('c'),'name')))))))))),
        prop('Save','Enabled',both(g('ready'),g('bib_valid'))),prop('Run','Enabled',both(g('ready'),g('bib_valid'))),
        prop('Save','Text',choose(g('known'),choose(eq(dev('checkpoint'),num(1)),text('Catat Finish Swim'),choose(eq(dev('checkpoint'),num(2)),text('Mulai Sepeda'),choose(eq(dev('checkpoint'),num(3)),text('Catat Lintasan Sepeda'),text('Catat Lintasan Lari')))),choose(eq(dev('checkpoint'),num(2)),text('Sepeda · simpan untuk diperiksa'),text('Simpan untuk diperiksa')))),
        prop('Run','Text',choose(g('known'),text('Mulai Lari'),text('Lari · simpan untuk diperiksa')))),
      event('Bib','OnTextChanged',run('MatchBib')),
      event('Save','Click',sg('stage',choose(eq(dev('checkpoint'),num(1)),text('swim_finish'),choose(eq(dev('checkpoint'),num(2)),text('cycle_start'),choose(eq(dev('checkpoint'),num(3)),text('cycle'),text('run'))))),run('Capture')),
      event('Run','Click',sg('stage',text('run_start')),run('Capture'))]


def sync_blocks():
    update=lambda rid,columns,vals:local('updated',call('SQLite1','Update',text('readings_v3'),seq(*map(text,columns)),seq(*vals),text('record_id=?'),seq(rid)),cond(eq(var('updated'),num(-1)),notice(text('Status lokal belum tersimpan; kirim ulang aman.'))))
    return [
      proc('NextBatch',call('SQLiteSend','RawQuery',text(sql.NEXT),seq(g('send_round'),g('send_round'),g('send_round')))),
      proc('FinishSend',sg('sending',boolean(False)),prop('Send','Enabled',boolean(True)),run('ShowHistory'),call('SQLiteCounts','RawQuery',text(sql.QUEUE),seq())),
      event('Send','Click',cond(eq(g('sending'),boolean(False)),chain(sg('sending',boolean(True)),sg('send_round',join(now(),text('-'),g('counter'))),prop('Send','Enabled',boolean(False)),prop('SyncStatus','Text',text('Mengirim antrean semua penugasan…')),run('NextBatch')))),
      event('SQLiteSend','AfterQuery',cond(cmp(var('numberOfRecords'),num(0),'GT'),chain(sg('sent_ids',seq()),sg('send_cancel',eq(op('add',index(index(var('result'),1),4),num(0)),num(1))),sg('send_profile',profile(index(index(var('result'),1),3))),
        local('payloads',seq(),each('row',var('result'),add(g('sent_ids'),index(var('row'),1)),add(var('payloads'),index(var('row'),2))),
          each('rid',g('sent_ids'),update(var('rid'),['attempt'],[g('send_round')])),
          prop('Web1','Url',join(lookup(g('send_profile'),'url'),text('/api.php?action='),choose(g('send_cancel'),text('cancel'),text('upload')))),prop('Web1','RequestHeaders',headers()),
          call('Web1','PostText',choose(g('send_cancel'),join(text(),dictionary({'token':lookup(g('send_profile'),'token'),'record_ids':g('sent_ids')})),join(text('{"token":"'),lookup(g('send_profile'),'token'),text('","data":['),block('lists_join_with_separator',values={'SEPARATOR':text(','),'LIST':var('payloads')}),text(']}')))))),run('FinishSend'))),
      event('Web1','GotText',cond(eq(var('responseCode'),num(200)),local('reply',response(),
        each('rid',lookup(var('reply'),'accepted_ids',seq()),cond(inlist(var('rid'),g('sent_ids')),update(var('rid'),['sent','cancel_sent','error'],[num(1),choose(g('send_cancel'),num(1),num(0)),text()]))),
        each('problem',lookup(var('reply'),'rejected',seq()),cond(inlist(lookup(var('problem'),'record_id'),g('sent_ids')),update(lookup(var('problem'),'record_id'),['error'],[lookup(var('problem'),'message')])))),
        each('rid',g('sent_ids'),update(var('rid'),['error'],[choose(eq(var('responseCode'),num(401)),text('Akses penugasan asal dicabut. Minta kode baru untuk perangkat asal.'),text('Server belum menerima; kirim ulang.'))]))),run('NextBatch')),
      event('Web1','TimedOut',each('rid',g('sent_ids'),update(var('rid'),['error'],[text('Koneksi terputus. Kirim ulang aman.')])),run('NextBatch')),
      event('SQLiteCounts','AfterQuery',prop('SyncStatus','Text',join(var('numberOfRecords'),text(' catatan/pembatalan masih menunggu. Lihat Catatan perlu diperiksa jika ada kesalahan.')))),
    ]


def clock_blocks():
    return [
      proc('RequestTime',sg('requested',now()),prop('WebTime','Url',text(SERVER+'/api.php?action=time')),call('WebTime','Get')),
      proc('SyncTime',cond(eq(g('time_busy'),boolean(False)),chain(sg('time_busy',boolean(True)),sg('sample_count',num(0)),sg('best_rtt',num(999999)),run('RequestTime')))),
      event('Clock1','Timer',run('SyncTime')),
      event('WebTime','GotText',cond(eq(var('responseCode'),num(200)),local('reply',call('WebTime','JsonTextDecode',var('responseContent')),
        local('rtt',op('sub',now(),g('requested')),cond(both(cmp(var('rtt'),num(0),'GTE'),cmp(var('rtt'),g('best_rtt'),'LT')),chain(sg('best_rtt',var('rtt')),sg('best_offset',op('sub',op('add',lookup(var('reply'),'server_ms'),op('div',var('rtt'),num(2))),now()))))),
        sg('sample_count',op('add',g('sample_count'),num(1))),cond(cmp(g('sample_count'),num(3),'LT'),run('RequestTime'),chain(sg('time_busy',boolean(False)),
          cond(cmp(g('best_rtt'),num(2000),'LT'),chain(sg('offset',g('best_offset')),storetag('offset',g('offset')),sg('last_sync',now()),sg('quality',text('synced')),prop('ClockStatus','Text',text('Jam diselaraskan · acuan server'))),prop('ClockStatus','Text',text('Jam belum stabil · perlu diperiksa')))))),chain(sg('time_busy',boolean(False)),prop('ClockStatus','Text',text('Offline · memakai acuan terakhir'))))),
      event('WebTime','TimedOut',sg('time_busy',boolean(False)),prop('ClockStatus','Text',text('Offline · memakai acuan terakhir')))]


def screen2():
    cs=[label('Heading','IDLAPS'),label('Assignment','Memuat…'),label('ClockStatus','Jam belum terverifikasi'),label('SyncStatus','Catatan tersimpan lokal'),bibbox('Bib'),label('Participant','Isi BIB peserta'),inputbox('Lap','Putaran',Text='1'),button('Save','Catat lintasan'),button('Run','Mulai Lari'),button('Send','Kirim Data · semua penugasan'),button('Review','Catatan perlu diperiksa'),button('Switch','Ganti titik / event'),button('Refresh','Periksa jam & konfigurasi'),label('History','Belum ada catatan')]+hidden(['SQLite1','SQLiteList','SQLiteSend','SQLiteCounts'])+[component(n,'Web',6,Timeout=15000) for n in ['Web1','WebTime','WebConfig']]
    next(c for c in cs if c['$Name']=='Clock1').update(TimerEnabled='True',TimerInterval='60000',TimerAlwaysFires='False')
    cs=decorate(cs,2,component);components(cs+[{'$Name':'Screen2','$Type':'Form'}])
    defaults={'config':seq(),'offset':num(0),'quality':text('unverified'),'last_sync':num(0),'requested':num(0),'stage':text(),'sent_ids':seq(),'counter':num(0),'sample_count':num(0),'best_rtt':num(999999),'best_offset':num(0),'time_busy':boolean(False),'bib_value':text(),'bib_valid':boolean(False),'known':boolean(False),'ready':boolean(False),'lap_valid':boolean(True),'sending':boolean(False),'send_round':text(),'send_cancel':boolean(False),'send_profile':seq()}
    blocks=[glob(k,v) for k,v in defaults.items()]+profile_blocks()+[validation_proc(),
      proc('ApplyConfig',sg('config',gettag('config',seq())),prop('Assignment','Text',join(lookup(cfg('event'),'name'),text('\n'),dev('name'),text(' · titik '),dev('checkpoint'))),prop('Run','Visible',eq(dev('checkpoint'),num(2))),prop('Lap','Visible',cmp(dev('checkpoint'),num(2),'GT')),prop('LapLabel','Visible',cmp(dev('checkpoint'),num(2),'GT')),run('MatchBib')),
      proc('ShowHistory',call('SQLiteList','RawQuery',text(sql.HISTORY),seq(gettag('current_profile')))),
      event('Screen2','Initialize',sg('counter',gettag('counter',num(0))),sg('offset',gettag('offset',num(0))),run('ApplyConfig'),sg('ready',boolean(True)),run('MatchBib'),run('ShowHistory'),run('SyncTime')),
      event('Screen2','OtherScreenClosed',sg('counter',gettag('counter',num(0))),run('ShowHistory')),
      event('Review','Click',cond(g('sending'),notice(text('Tunggu pengiriman selesai sebelum memperbaiki catatan.')),open_screen('Screen3'))),
      event('Switch','Click',close_screen()),
      event('SQLiteList','AfterQuery',prop('History','Text',text()),each('row',var('result'),prop('History','Text',join(prop('History','Text'),index(var('row'),1),text(' · '),stage_text(lambda:index(var('row'),2)),text(' #'),index(var('row'),3),text(' · '),call('Clock1','FormatDateTime',call('Clock1','MakeInstantFromMillis',index(var('row'),4)),text('HH:mm:ss')),text(' · '),choose(eq(op('add',index(var('row'),6),num(0)),num(1)),text('dibatalkan'),choose(eq(op('add',index(var('row'),5),num(0)),num(1)),text('terkirim'),text('menunggu'))),text('\n'))))),
      event('Refresh','Click',run('SyncTime'),prop('WebConfig','Url',join(gettag('url',text(SERVER)),text('/api.php?action=config'))),prop('WebConfig','RequestHeaders',seq(seq(text('Authorization'),join(text('Bearer '),gettag('token'))))),call('WebConfig','Get')),
      event('WebConfig','GotText',cond(eq(var('responseCode'),num(200)),local('reply',call('WebConfig','JsonTextDecode',var('responseContent')),storetag('config',lookup(var('reply'),'config')),run('KeepProfile'),run('ApplyConfig')),notice(text('Konfigurasi tersimpan tetap dipakai.')))),
    ]+capture_blocks()+sync_blocks()+clock_blocks()
    for name in ['SQLite1','SQLiteList','SQLiteSend','SQLiteCounts']:
        blocks.append(event(name,'ErrorOccurred',sg('sending',boolean(False)),prop('Send','Enabled',boolean(True)),notice(join(text('Penyimpanan: '),var('message')))))
    return screen('Screen2',cs),xml(blocks)


def screen3():
    picker=component('Pick','ListPicker',9,Text='Pilih catatan',Width=-2,Height=56,ShowFilterBar='True',Title='Catatan semua penugasan',BackgroundColor='&HFF176C65',TextColor='&HFFFFFFFF')
    cs=[layout([label('Heading','CATATAN PERLU DIPERIKSA'),label('Help','Pilih catatan untuk memperbaiki BIB atau membatalkannya. Waktu dan penugasan asal tetap dipertahankan.'),picker,label('Detail','Memuat catatan…'),bibbox('EditBib'),button('Correct','Simpan perbaikan BIB'),button('Cancel','Batalkan catatan'),button('Back','Kembali ke pencatatan')])]+hidden(['SQLiteReview','SQLiteEdit'])+[component('Web1','Web',6)]
    components(cs+[{'$Name':'Screen3','$Type':'Form'}])
    # Selected row: id,bib,stage,lap,ms,payload,assignment,sent,cancelled,error.
    selected=lambda n:index(g('selected'),n)
    newpayload=lambda:dictionary({'record_id':g('new_id'),'bib':g('bib_value'),'event_id':lookup(g('old_payload'),'event_id'),'checkpoint':lookup(g('old_payload'),'checkpoint'),'stage':lookup(g('old_payload'),'stage'),'lap':lookup(g('old_payload'),'lap',num(1)),'captured_ms':lookup(g('old_payload'),'captured_ms'),'clock_quality':lookup(g('old_payload'),'clock_quality',text('unverified')),'config_version':lookup(g('old_payload'),'config_version',num(1)),'replaces_record_id':selected(1),'correction_reason':text('Perbaikan BIB oleh operator')})
    cancel_sql=lambda:join(text('UPDATE readings_v3 SET cancelled=1,error=\'\' WHERE record_id='),quoted(selected(1)))
    audit_sql=lambda action:join(text('INSERT INTO local_changes(old_id,new_id,action,created_ms) VALUES('),quoted(selected(1)),text(','),quoted(g('new_id')),text(','),quoted(text(action)),text(','),now(),text(')'))
    correct_sql=lambda:join(text('INSERT INTO readings_v3(record_id,bib,stage,lap,captured_ms,payload,assignment,replaces) VALUES('),quoted(g('new_id')),text(','),quoted(g('bib_value')),text(','),quoted(selected(3)),text(','),selected(4),text(','),selected(5),text(','),quoted(join(text(),newpayload())),text(','),quoted(selected(7)),text(','),quoted(selected(1)),text(')'))
    blocks=[glob('records',seq()),glob('selected',seq()),glob('bib_value',text()),glob('bib_valid',boolean(False)),glob('old_payload',seq()),glob('new_id',text()) ,validation_proc(),
      proc('Load',prop('Correct','Enabled',boolean(False)),prop('Cancel','Enabled',boolean(False)),prop('Pick','Enabled',boolean(False)),call('SQLiteReview','RawQuery',text(sql.REVIEW),seq())),
      event('Screen3','Initialize',run('Load')),
      event('SQLiteReview','AfterQuery',sg('records',var('result')),local('labels',seq(),each('row',g('records'),add(var('labels'),join(index(var('row'),2),text(' · '),stage_text(lambda:index(var('row'),3)),text(' · '),call('Clock1','FormatDateTime',call('Clock1','MakeInstantFromMillis',index(var('row'),5)),text('dd/MM HH:mm:ss')),text(' · '),lookup(lookup(lookup(profile(index(var('row'),7)),'config',seq()),'event',seq()),'name') ,text(' · '),choose(eq(op('add',index(var('row'),9),num(0)),num(1)),text('dibatalkan'),choose(eq(op('add',index(var('row'),8),num(0)),num(1)),text('terkirim'),text('menunggu'))),text(' · '),index(var('row'),10)))),prop('Pick','Elements',var('labels'))),prop('Pick','Enabled',cmp(var('numberOfRecords'),num(0),'GT')),prop('Detail','Text',text('Pilih catatan. Koreksi BIB tersedia untuk catatan yang belum dikonfirmasi server.'))),
      event('Pick','AfterPicking',cond(cmp(prop('Pick','SelectionIndex'),num(0),'GT'),chain(sg('selected',block('lists_select_item',values={'LIST':g('records'),'NUM':prop('Pick','SelectionIndex')})),prop('EditBib','Text',selected(2)),prop('Detail','Text',join(text('BIB '),selected(2),text(' · '),stage_text(lambda:selected(3)),text('\nWaktu '),call('Clock1','FormatDateTime',call('Clock1','MakeInstantFromMillis',selected(5)),text('dd/MM HH:mm:ss')),text('\n'),lookup(lookup(lookup(profile(selected(7)),'config',seq()),'device',seq()),'name'),text('\n'),selected(10))),prop('Correct','Enabled',both(eq(op('add',selected(8),num(0)),num(0)),eq(op('add',selected(9),num(0)),num(0)))),prop('Cancel','Enabled',eq(op('add',selected(9),num(0)),num(0)))))),
      event('Correct','Click',sg('bib_value',prop('EditBib','Text')),run('ValidateBib'),cond(both(g('bib_valid'),both(eq(op('add',selected(8),num(0)),num(0)),eq(op('add',selected(9),num(0)),num(0)))),
        cond(neq(join(text('bib:'),g('bib_value')),join(text('bib:'),selected(2))),chain(
          storetag('counter',op('add',gettag('counter',num(0)),num(1))),sg('new_id',join(text('manual-fix-'),now(),text('-'),gettag('counter'))),sg('old_payload',call('Web1','JsonTextDecode',selected(6))),prop('Correct','Enabled',boolean(False)),prop('Cancel','Enabled',boolean(False)),prop('Pick','Enabled',boolean(False)),call('SQLiteEdit','MultipleSQL',seq(correct_sql(),cancel_sql(),audit_sql('correct_bib')))),notice(text('BIB belum berubah.'))),notice(text('Isi BIB 1–3 digit. Catatan yang sudah terkirim dikoreksi melalui admin.')))),
      event('Cancel','Click',call('Notifier1','ShowChooseDialog',text('Batalkan catatan yang dipilih? Riwayat tetap tersimpan. Tekan Kirim Data setelah kembali.'),text('Pembatalan catatan'),text('Ya'),text('Tidak'),boolean(False))),
      event('Notifier1','AfterChoosing',cond(eq(var('choice'),text('Ya')),chain(sg('new_id',text()),prop('Correct','Enabled',boolean(False)),prop('Cancel','Enabled',boolean(False)),prop('Pick','Enabled',boolean(False)),call('SQLiteEdit','MultipleSQL',seq(cancel_sql(),audit_sql('cancel')))))),
      event('SQLiteEdit','AfterExecution',cond(var('wasExecuted'),chain(notice(text('Perubahan tersimpan. Kembali dan tekan Kirim Data.')),run('Load')),chain(notice(text('Perubahan gagal; catatan asli tetap tersimpan.')),run('Load')))),
      event('Back','Click',close_screen())]
    for name in ['SQLiteEdit','SQLiteReview']:blocks.append(event(name,'ErrorOccurred',notice(join(text('Penyimpanan: '),var('message')))))
    return screen('Screen3',cs),xml(blocks)


def pages():return {'Screen1':screen1(),'Screen2':screen2(),'Screen3':screen3()}
