<?php
declare(strict_types=1);
function admin_action(string $action,int $eventId): string {
    require_csrf();
    if($action==='event') {
        $name=trim((string)($_POST['name']??'')); $tz=(string)($_POST['timezone']??'Asia/Jakarta');
        if($name===''||mb_strlen($name)>150||!in_array($tz,DateTimeZone::listIdentifiers(),true)) throw new RuntimeException('Nama event/zona waktu tidak valid.');
        query('INSERT INTO events(name,timezone,created_ms) VALUES(?,?,?)',[$name,$tz,now_ms()]); $_SESSION['event_id']=(int)db()->lastInsertId(); return 'Event dibuat. Tambahkan kategori dan peserta.';
    }
    if($action==='calculate') { compute_event($eventId); return 'Hasil dihitung ulang dengan catatan manual sebagai prioritas.'; }
    if($action==='import_preview') {
        if(($_FILES['file']['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_OK) throw new RuntimeException('Unggahan gagal. Pilih file .xlsx maksimal 5 MB.');
        $_SESSION['import']=preview_import($_FILES['file']['tmp_name'],$eventId); return 'Periksa pratinjau sebelum menyimpan peserta.';
    }
    db()->beginTransaction();
    try {
        $event=lock_event($eventId); $detail=[]; $affected=[]; $msg='Perubahan disimpan.';
        switch($action) {
            case 'category':
                $name=trim((string)($_POST['name']??'')); if($name===''||mb_strlen($name)>100) throw new RuntimeException('Nama kategori wajib, maksimal 100 karakter.');
                $start=parse_local((string)$_POST['scheduled'],$event['timezone']); $official=trim((string)($_POST['official']??'')); $official=$official===''?null:parse_local($official,$event['timezone']);
                $bike=(int)$_POST['bike_laps']; $run=(int)$_POST['run_laps']; $bikeMin=(int)$_POST['bike_min_s']; $runMin=(int)$_POST['run_min_s'];
                if(min($bike,$run)<1||max($bike,$run)>100||min($bikeMin,$runMin)<0) throw new RuntimeException('Putaran 1–100 dan durasi minimum tidak boleh negatif.');
                $catId=(int)($_POST['id']??0); $detail=['before'=>$catId?one('SELECT * FROM categories WHERE id=? AND event_id=?',[$catId,$eventId]):null,'name'=>$name,'official_ms'=>$official];
                if($detail['before'] && ((int)$detail['before']['bike_laps']!==$bike || (int)$detail['before']['run_laps']!==$run) && one('SELECT id FROM observations WHERE event_id=? AND test=0 LIMIT 1',[$eventId])) throw new RuntimeException('Jumlah putaran sudah digunakan dalam pencatatan. Tetapkan rute sebelum lomba; gunakan event baru untuk rute berbeda. Gun time tetap dapat diperbarui.');
                if($catId) { if(!$detail['before']) throw new RuntimeException('Kategori tidak ditemukan.'); query('UPDATE categories SET name=?,scheduled_ms=?,official_ms=?,bike_laps=?,run_laps=?,bike_min_s=?,run_min_s=? WHERE id=? AND event_id=?',[$name,$start,$official,$bike,$run,$bikeMin,$runMin,$catId,$eventId]); }
                else query('INSERT INTO categories(event_id,name,scheduled_ms,official_ms,bike_laps,run_laps,bike_min_s,run_min_s) VALUES(?,?,?,?,?,?,?,?)',[$eventId,$name,$start,$official,$bike,$run,$bikeMin,$runMin]);
                $affected[]=$catId?: (int)db()->lastInsertId();
                break;
            case 'participant':
                $id=(int)($_POST['id']??0); $bib=trim((string)$_POST['bib']); $name=trim((string)$_POST['name']); $team=trim((string)($_POST['team']??'')); $epcs=parse_epcs((string)($_POST['epc']??'')); $cat=(int)$_POST['category_id']; $status=(string)($_POST['race_status']??'active');
                if(!preg_match('/^[0-9]{1,3}$/D',$bib)||$name===''||mb_strlen($name)>150||mb_strlen($team)>150) throw new RuntimeException('BIB/nama/tim tidak valid.');
                if(!one('SELECT id FROM categories WHERE id=? AND event_id=?',[$cat,$eventId])||!in_array($status,['active','dns','dnf','dsq'],true)) throw new RuntimeException('Kategori/status tidak valid.');
                if($status==='dsq' && trim((string)($_POST['status_reason']??''))==='') throw new RuntimeException('Alasan diskualifikasi wajib diisi.');
                if($id) {
                    $old=one('SELECT * FROM participants WHERE id=? AND event_id=?',[$id,$eventId]); if(!$old||$old['bib']!==$bib) throw new RuntimeException('BIB peserta yang sudah disimpan tidak boleh diubah.'); $old['epcs']=with_participant_tags([$old],$eventId)[0]['epcs']; $detail=['before'=>$old,'reason'=>trim((string)($_POST['status_reason']??''))]; $affected[]=(int)$old['category_id'];
                    query('UPDATE participants SET name=?,team=?,category_id=?,race_status=? WHERE id=? AND event_id=?',[$name,$team,$cat,$status,$id,$eventId]);
                } else { query('INSERT INTO participants(event_id,category_id,bib,name,team,race_status) VALUES(?,?,?,?,?,?)',[$eventId,$cat,$bib,$name,$team,$status]); $id=(int)db()->lastInsertId(); $detail=['bib'=>$bib,'after'=>$status,'reason'=>trim((string)($_POST['status_reason']??''))]; }
                save_participant_tags($eventId,$id,$epcs); $detail['epcs']=$epcs;
                $affected[]=$cat;
                break;
            case 'participant_status':
                $p=one('SELECT * FROM participants WHERE id=? AND event_id=?',[(int)($_POST['id']??0),$eventId]);
                $status=(string)($_POST['race_status']??''); $reason=trim((string)($_POST['reason']??''));
                if(!$p || !in_array($status,['active','dns','dnf','dsq'],true)) throw new RuntimeException('Peserta atau status tidak valid.');
                if($status==='dsq' && $reason==='') throw new RuntimeException('Alasan diskualifikasi wajib diisi.');
                query('UPDATE participants SET race_status=? WHERE id=?',[$status,$p['id']]);
                $affected[]=(int)$p['category_id']; $detail=['bib'=>$p['bib'],'before'=>$p['race_status'],'after'=>$status,'reason'=>$reason];
                $msg='Status peserta disimpan. Tekan Hitung Hasil untuk memperbarui peringkat.';
                break;
            case 'import_commit':
                $import=$_SESSION['import']??null;
                if(!$import||$import['event_id']!==$eventId||$import['errors']) throw new RuntimeException('Pratinjau impor belum valid.');
                foreach($import['rows'] as $p) { query('INSERT INTO participants(event_id,category_id,bib,name,team) VALUES(?,?,?,?,?)',[$eventId,$p['category_id'],$p['bib'],$p['name'],$p['team']]); save_participant_tags($eventId,(int)db()->lastInsertId(),$p['epcs']??parse_epcs((string)($p['epc']??''))); }
                $affected=array_map('intval',array_column($import['rows'],'category_id')); $msg=count($import['rows']).' peserta ditambahkan.'; $detail=['count'=>count($import['rows'])]; unset($_SESSION['import']); break;
            case 'device':
                $name=trim((string)$_POST['name']); $kind=(string)$_POST['kind']; $cp=(int)$_POST['checkpoint'];
                if($name===''||mb_strlen($name)>100||!in_array($kind,['manual','rfid'],true)||$cp<1||$cp>4) throw new RuntimeException('Penugasan perangkat tidak valid.');
                $code=strtoupper(bin2hex(random_bytes(8)));
                query('INSERT INTO devices(event_id,name,kind,checkpoint,token_hash,pairing_hash,pairing_expires_ms) VALUES(?,?,?,?,?,?,?)',[$eventId,$name,$kind,$cp,hash('sha256',random_bytes(32)),hash('sha256',$code),now_ms()+86400000]);
                $_SESSION['pairing_code']=$code; $msg='Perangkat dibuat. Kode pemasangan berlaku 24 jam dan hanya bisa dipakai sekali.'; break;
            case 'revoke':
                query('UPDATE devices SET revoked=1 WHERE id=? AND event_id=?',[(int)$_POST['id'],$eventId]); $detail=['device'=>(int)$_POST['id']]; break;
            case 're_pair':
                $code=strtoupper(bin2hex(random_bytes(8)));
                query('UPDATE devices SET token_hash=?,pairing_hash=?,pairing_expires_ms=?,pairing_consumed=0,revoked=0 WHERE id=? AND event_id=?',[hash('sha256',random_bytes(32)),hash('sha256',$code),now_ms()+86400000,(int)$_POST['id'],$eventId]); $_SESSION['pairing_code']=$code; break;
            case 'reader':
                $device=one('SELECT * FROM devices WHERE id=? AND event_id=? AND kind=?',[(int)$_POST['device_id'],$eventId,'rfid']); if(!$device) throw new RuntimeException('Pilih desktop RFID.');
                $host=trim((string)$_POST['host']); $port=(int)$_POST['port']; $cp=(int)$_POST['checkpoint']; $mode=(string)$_POST['detect_mode']; $power=(int)$_POST['power']; $interval=(int)$_POST['interval_s']*1000; $quiet=(int)$_POST['quiet_ms']; $name=trim((string)$_POST['name']);
                if(!filter_var($host,FILTER_VALIDATE_IP,FILTER_FLAG_IPV4)||$port<1||$port>65535||$cp<1||$cp>4||!in_array($mode,['single','multi'],true)||$power<0||$power>30||$interval<0||$quiet<100||$name==='') throw new RuntimeException('Pengaturan reader tidak valid. Gunakan alamat IPv4 reader.');
                if($cp===2&&$mode==='single') throw new RuntimeException('Titik 2 melayani dua tahapan; gunakan multi detect.');
                $id=(int)($_POST['id']??0);
                if($id) { $old=one('SELECT r.* FROM readers r JOIN devices d ON d.id=r.device_id WHERE r.id=? AND d.event_id=?',[$id,$eventId]); if(!$old) throw new RuntimeException('Reader tidak ditemukan.'); if((int)$old['device_id']!==(int)$device['id']||(int)$old['checkpoint']!==$cp) throw new RuntimeException('Identitas titik/perangkat reader tidak boleh diubah. Buat reader baru untuk penugasan berbeda.'); query('UPDATE readers SET name=?,host=?,port=?,detect_mode=?,interval_ms=?,quiet_ms=?,power=?,enabled=? WHERE id=?',[$name,$host,$port,$mode,$interval,$quiet,$power,isset($_POST['enabled'])?1:0,$id]); }
                else query('INSERT INTO readers(device_id,name,host,port,checkpoint,detect_mode,interval_ms,quiet_ms,power) VALUES(?,?,?,?,?,?,?,?,?)',[$device['id'],$name,$host,$port,$cp,$mode,$interval,$quiet,$power]);
                break;
            case 'manual_complete':
                $id=(int)$_POST['id']; query('UPDATE devices SET manual_complete=? WHERE id=? AND event_id=? AND kind=?',[isset($_POST['complete'])?1:0,$id,$eventId,'manual']); $detail=['device'=>$id,'complete'=>isset($_POST['complete'])]; break;
            case 'cancel':
                $reason=trim((string)$_POST['reason']); if($reason==='') throw new RuntimeException('Alasan pembatalan wajib.');
                $o=one('SELECT * FROM observations WHERE id=? AND event_id=?',[(int)$_POST['id'],$eventId]); if(!$o) throw new RuntimeException('Catatan tidak ditemukan.');
                query('UPDATE observations SET cancelled=? WHERE id=?',[(int)$o['cancelled']?0:1,$o['id']]); $affected=observation_categories($eventId,$o['bib'],$o['epc']); $detail=['record_id'=>$o['record_id'],'reason'=>$reason,'before_cancelled'=>$o['cancelled']]; break;
            case 'decision':
                $bib=trim((string)$_POST['bib']); $key=(string)$_POST['step_key']; $reason=trim((string)$_POST['reason']);
                $p=one('SELECT c.* FROM participants p JOIN categories c ON c.id=p.category_id WHERE p.event_id=? AND p.bib=?',[$eventId,$bib]);
                if(!$p||!in_array($key,array_column(route_steps($p),'key'),true)||$reason==='') throw new RuntimeException('Peserta, tahap/putaran, dan alasan wajib valid.');
                $ms=parse_local((string)$_POST['captured'],$event['timezone']);
                $old=one('SELECT * FROM decisions WHERE event_id=? AND bib=? AND step_key=?',[$eventId,$bib,$key]);
                if($old) query('UPDATE decisions SET captured_ms=?,reason=? WHERE id=?',[$ms,$reason,$old['id']]); else query('INSERT INTO decisions(event_id,bib,step_key,captured_ms,reason) VALUES(?,?,?,?,?)',[$eventId,$bib,$key,$ms,$reason]);
                $affected=observation_categories($eventId,$bib,null); $detail=['before'=>$old,'bib'=>$bib,'step_key'=>$key,'captured_ms'=>$ms,'reason'=>$reason]; break;
            case 'remove_decision':
                $d=one('SELECT * FROM decisions WHERE id=? AND event_id=?',[(int)$_POST['id'],$eventId]); if(!$d||trim((string)$_POST['reason'])==='') throw new RuntimeException('Koreksi/alasan tidak valid.'); query('DELETE FROM decisions WHERE id=?',[$d['id']]); $affected=observation_categories($eventId,$d['bib'],null); $detail=['before'=>$d,'reason'=>$_POST['reason']]; break;
            case 'official':
                publish_category($eventId,(int)($_POST['category_id']??0)); db()->commit(); return 'Hasil kategori ditetapkan resmi.';
            default: throw new RuntimeException('Aksi tidak dikenal.');
        }
        revise($eventId,array_values(array_unique($affected))); query('UPDATE devices SET config_version=config_version+1 WHERE event_id=?',[$eventId]); audit($eventId,$action,$detail); db()->commit(); return $msg;
    } catch(Throwable $e) { db()->rollBack(); throw $e; }
}
