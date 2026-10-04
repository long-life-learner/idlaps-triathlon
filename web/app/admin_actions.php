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
    if($action==='legacy_preview') { $_SESSION['legacy']=legacy_preview(one('SELECT * FROM events WHERE id=?',[$eventId]),$_POST); return 'Periksa tanggal, jenis lintasan, dan waktu arsip sebelum impor.'; }
    if($action==='legacy_commit') {
        $preview=$_SESSION['legacy']??null;
        if(!$preview || $preview['event_id']!==$eventId) throw new RuntimeException('Pratinjau arsip tidak tersedia.');
        $reply=legacy_commit($preview); $_SESSION['legacy_rejected']=$reply['rejected']; unset($_SESSION['legacy']);
        return count($reply['accepted']).' catatan diterima; '.count($reply['rejected']).' ditolak. Jam arsip ditandai belum terverifikasi sampai ditinjau.';
    }
    db()->beginTransaction();
    try {
        $event=lock_event($eventId); $detail=[]; $msg='Perubahan disimpan.';
        switch($action) {
            case 'category':
                $name=trim((string)($_POST['name']??'')); if($name===''||mb_strlen($name)>100) throw new RuntimeException('Nama kategori wajib, maksimal 100 karakter.');
                $start=parse_local((string)$_POST['scheduled'],$event['timezone']); $official=trim((string)($_POST['official']??'')); $official=$official===''?null:parse_local($official,$event['timezone']);
                $bike=(int)$_POST['bike_laps']; $run=(int)$_POST['run_laps']; $bikeMin=(int)$_POST['bike_min_s']; $runMin=(int)$_POST['run_min_s'];
                if(min($bike,$run)<1||max($bike,$run)>100||min($bikeMin,$runMin)<0) throw new RuntimeException('Putaran 1–100 dan durasi minimum tidak boleh negatif.');
                $catId=(int)($_POST['id']??0); $detail=['before'=>$catId?one('SELECT * FROM categories WHERE id=? AND event_id=?',[$catId,$eventId]):null,'name'=>$name,'official_ms'=>$official];
                if($catId) { if(!$detail['before']) throw new RuntimeException('Kategori tidak ditemukan.'); query('UPDATE categories SET name=?,scheduled_ms=?,official_ms=?,bike_laps=?,run_laps=?,bike_min_s=?,run_min_s=? WHERE id=? AND event_id=?',[$name,$start,$official,$bike,$run,$bikeMin,$runMin,$catId,$eventId]); }
                else query('INSERT INTO categories(event_id,name,scheduled_ms,official_ms,bike_laps,run_laps,bike_min_s,run_min_s) VALUES(?,?,?,?,?,?,?,?)',[$eventId,$name,$start,$official,$bike,$run,$bikeMin,$runMin]);
                break;
            case 'participant':
                $id=(int)($_POST['id']??0); $bib=trim((string)$_POST['bib']); $name=trim((string)$_POST['name']); $team=trim((string)($_POST['team']??'')); $epc=strtoupper(str_replace(' ','',trim((string)($_POST['epc']??'')))); $cat=(int)$_POST['category_id']; $status=(string)($_POST['race_status']??'active');
                if(!preg_match('/^[A-Za-z0-9-]{1,30}$/D',$bib)||$name===''||mb_strlen($name)>150||mb_strlen($team)>150) throw new RuntimeException('BIB/nama/tim tidak valid.');
                if($epc!==''&&!preg_match('/^(?:[A-F0-9]{2}){1,64}$/D',$epc)) throw new RuntimeException('EPC harus hexadecimal dengan jumlah digit genap.');
                if(!one('SELECT id FROM categories WHERE id=? AND event_id=?',[$cat,$eventId])||!in_array($status,['active','dns','dnf','dsq'],true)) throw new RuntimeException('Kategori/status tidak valid.');
                if($id) {
                    $old=one('SELECT * FROM participants WHERE id=? AND event_id=?',[$id,$eventId]); if(!$old||$old['bib']!==$bib) throw new RuntimeException('BIB peserta yang sudah disimpan tidak boleh diubah.'); $detail=['before'=>$old];
                    query('UPDATE participants SET name=?,team=?,epc=?,category_id=?,race_status=? WHERE id=? AND event_id=?',[$name,$team,$epc?:null,$cat,$status,$id,$eventId]);
                } else query('INSERT INTO participants(event_id,category_id,bib,name,team,epc) VALUES(?,?,?,?,?,?)',[$eventId,$cat,$bib,$name,$team,$epc?:null]);
                break;
            case 'import_commit':
                $import=$_SESSION['import']??null;
                if(!$import||$import['event_id']!==$eventId||$import['errors']) throw new RuntimeException('Pratinjau impor belum valid.');
                foreach($import['rows'] as $p) query('INSERT INTO participants(event_id,category_id,bib,name,team,epc) VALUES(?,?,?,?,?,?)',[$eventId,$p['category_id'],$p['bib'],$p['name'],$p['team'],$p['epc']]);
                $msg=count($import['rows']).' peserta ditambahkan.'; $detail=['count'=>count($import['rows'])]; unset($_SESSION['import']); break;
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
                query('UPDATE observations SET cancelled=? WHERE id=?',[(int)$o['cancelled']?0:1,$o['id']]); $detail=['record_id'=>$o['record_id'],'reason'=>$reason,'before_cancelled'=>$o['cancelled']]; break;
            case 'decision':
                $bib=trim((string)$_POST['bib']); $key=(string)$_POST['step_key']; $reason=trim((string)$_POST['reason']);
                $p=one('SELECT c.* FROM participants p JOIN categories c ON c.id=p.category_id WHERE p.event_id=? AND p.bib=?',[$eventId,$bib]);
                if(!$p||!in_array($key,array_column(route_steps($p),'key'),true)||$reason==='') throw new RuntimeException('Peserta, tahap/putaran, dan alasan wajib valid.');
                $ms=parse_local((string)$_POST['captured'],$event['timezone']);
                $old=one('SELECT * FROM decisions WHERE event_id=? AND bib=? AND step_key=?',[$eventId,$bib,$key]);
                if($old) query('UPDATE decisions SET captured_ms=?,reason=? WHERE id=?',[$ms,$reason,$old['id']]); else query('INSERT INTO decisions(event_id,bib,step_key,captured_ms,reason) VALUES(?,?,?,?,?)',[$eventId,$bib,$key,$ms,$reason]);
                $detail=['before'=>$old,'bib'=>$bib,'step_key'=>$key,'captured_ms'=>$ms,'reason'=>$reason]; break;
            case 'remove_decision':
                $d=one('SELECT * FROM decisions WHERE id=? AND event_id=?',[(int)$_POST['id'],$eventId]); if(!$d||trim((string)$_POST['reason'])==='') throw new RuntimeException('Koreksi/alasan tidak valid.'); query('DELETE FROM decisions WHERE id=?',[$d['id']]); $detail=['before'=>$d,'reason'=>$_POST['reason']]; break;
            case 'official':
                $run=one('SELECT * FROM result_runs WHERE event_id=? ORDER BY id DESC LIMIT 1',[$eventId]);
                if(!$run||(int)$run['revision']!==(int)$event['revision']) throw new RuntimeException('Hitung ulang hasil terlebih dahulu.');
                if(one('SELECT id FROM categories WHERE event_id=? AND official_ms IS NULL',[$eventId])) throw new RuntimeException('Isi gun time resmi semua kategori.');
                if(one('SELECT id FROM devices WHERE event_id=? AND kind=? AND manual_complete=0 AND revoked=0',[$eventId,'manual'])) throw new RuntimeException('Pastikan seluruh perangkat manual sudah selesai mengirim.');
                foreach(json_decode($run['result_json'],true) as $r) if($r['status']==='Perlu diperiksa') throw new RuntimeException('Selesaikan pemeriksaan peserta atau tetapkan DNF/DNS/DSQ.');
                if(empty($_POST['accept_rfid'])) throw new RuntimeException('Konfirmasi penggunaan RFID untuk catatan manual yang tidak tersedia.');
                query('UPDATE result_runs SET official=1 WHERE id=?',[$run['id']]); audit($eventId,'official',['run_id'=>$run['id']]); db()->commit(); return 'Hasil ditetapkan resmi. Data baru tetap akan menandai hasil perlu dihitung ulang.';
            default: throw new RuntimeException('Aksi tidak dikenal.');
        }
        revise($eventId); query('UPDATE devices SET config_version=config_version+1 WHERE event_id=?',[$eventId]); audit($eventId,$action,$detail); db()->commit(); return $msg;
    } catch(Throwable $e) { db()->rollBack(); throw $e; }
}
