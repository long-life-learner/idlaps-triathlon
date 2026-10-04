<?php
declare(strict_types=1);
// Explicit import context replaces the missing event/date in the old table.
function legacy_connection(): PDO {
    $c=config()['legacy']??null;
    if(!$c) return db();
    return new PDO($c['dsn'],$c['user'],$c['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
}
function legacy_preview(array $event,array $input): array {
    $from=(int)($input['from_id']??0);$to=(int)($input['to_id']??0);$cp=(int)($input['checkpoint']??0);
    $date=(string)($input['date']??''); $fraction=(string)($input['fraction']??'');$stage=(string)($input['stage']??'');
    if($from<1||$to<$from||$cp<1||$cp>4||!in_array($fraction,['millisecond','decimal'],true)) throw new RuntimeException('Rentang ID, checkpoint, dan arti pecahan waktu wajib diisi.');
    $midnight=parse_local($date.'T00:00:00',$event['timezone']);
    if($cp===2&&!in_array($stage,['cycle_start','run_start'],true)) throw new RuntimeException('Pilih jenis lintasan titik 2 untuk kelompok data ini.');
    $stage=[1=>'swim_finish',2=>$stage,3=>'cycle',4=>'run'][$cp]; $lap=max(1,(int)($input['lap']??1));
    $stmt=legacy_connection()->prepare('SELECT id,bib,time,mac,coords,checkpoint FROM result_logs WHERE id>=? AND id<=? AND checkpoint=? ORDER BY id LIMIT 2001'); $stmt->execute([$from,$to,$cp]);$raw=$stmt->fetchAll();
    if(count($raw)>2000) throw new RuntimeException('Batasi impor sampai 2.000 catatan per kelompok.');
    $records=[];$errors=[];
    foreach($raw as $r) {
        if(!preg_match('/^(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?$/D',$r['time'],$m)||(int)$m[1]>23||(int)$m[2]>59||(int)$m[3]>59) {$errors[]='ID '.$r['id'].': format waktu tidak valid.';continue;}
        $part=$m[4]??'0';$ms=$fraction==='millisecond'?(int)$part:(int)str_pad($part,3,'0');
        $captured=$midnight+((int)$m[1]*3600+(int)$m[2]*60+(int)$m[3])*1000+$ms;
        $records[]=['record_id'=>'legacy-'.$event['id'].'-'.$r['id'],'event_id'=>(int)$event['id'],'bib'=>$r['bib'],'checkpoint'=>$cp,'stage'=>$stage,'lap'=>$lap,'captured_ms'=>$captured,'clock_quality'=>'unverified','config_version'=>1,'legacy'=>$r];
    }
    if(!$raw)$errors[]='Tidak ada catatan pada rentang ini.';
    return ['event_id'=>(int)$event['id'],'checkpoint'=>$cp,'records'=>$records,'errors'=>$errors,'date'=>$date,'fraction'=>$fraction];
}
function legacy_commit(array $preview): array {
    if($preview['errors']) throw new RuntimeException('Perbaiki kesalahan pratinjau.');
    $event=(int)$preview['event_id'];$name='Arsip manual · titik '.$preview['checkpoint'];
    $d=one('SELECT * FROM devices WHERE event_id=? AND name=? AND kind=?',[$event,$name,'manual']);
    if(!$d){query('INSERT INTO devices(event_id,name,kind,checkpoint,token_hash,revoked,manual_complete) VALUES(?,?,?,?,?,?,?)',[$event,$name,'manual',$preview['checkpoint'],hash('sha256',random_bytes(32)),1,1]);$d=one('SELECT * FROM devices WHERE id=?',[db()->lastInsertId()]);}
    $accepted=[];$rejected=[];
    foreach(array_chunk($preview['records'],500) as $chunk){$r=ingest($d,$chunk);$accepted=array_merge($accepted,$r['accepted_ids']);$rejected=array_merge($rejected,$r['rejected']);}
    audit($event,'legacy_import',['date'=>$preview['date'],'fraction'=>$preview['fraction'],'accepted_ids'=>$accepted,'rejected'=>$rejected]);
    return ['accepted'=>$accepted,'rejected'=>$rejected];
}
