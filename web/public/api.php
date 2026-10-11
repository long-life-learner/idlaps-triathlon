<?php
declare(strict_types=1);
$received=(int)floor(microtime(true)*1000);
try {
    require dirname(__DIR__).'/app/bootstrap.php';
    header('Cache-Control: no-store');
    if((empty($_SERVER['HTTPS']) || $_SERVER['HTTPS']==='off') && empty(config()['allow_http_local'])) json_out(['ok'=>false,'message'=>'HTTPS wajib.'],400);
    $action=$_GET['action']??'';
    if($action==='time') json_out(['ok'=>true,'received_ms'=>$received,'server_ms'=>now_ms()]);
    $raw=file_get_contents('php://input',false,null,0,2097153);
    if(strlen($raw)>2097152) json_out(['ok'=>false,'message'=>'Kiriman terlalu besar.'],413);
    $body=$raw!==''?json_decode($raw,true,512,JSON_THROW_ON_ERROR):[];
    if(!is_array($body)) json_out(['ok'=>false,'message'=>'JSON harus objek.'],400);
    if($action==='pair') {
        if($_SERVER['REQUEST_METHOD']!=='POST') json_out(['ok'=>false],405);
        $code=strtoupper(trim((string)($body['code']??''))); $hash=hash('sha256',$code);
        db()->beginTransaction();
        $d=one('SELECT * FROM devices WHERE pairing_hash=? AND revoked=0'.(db()->getAttribute(PDO::ATTR_DRIVER_NAME)==='mysql'?' FOR UPDATE':''),[$hash]);
        if(!$d || (int)$d['pairing_consumed'] || (int)$d['pairing_expires_ms']<now_ms()) { db()->rollBack(); json_out(['ok'=>false,'message'=>'Kode pemasangan tidak berlaku. Minta kode baru dari admin.'],401); }
        $token=bin2hex(random_bytes(32));
        query('UPDATE devices SET token_hash=?,pairing_consumed=1,last_seen_ms=? WHERE id=?',[hash('sha256',$token),now_ms(),$d['id']]);
        db()->commit();
        json_out(['ok'=>true,'token'=>$token,'config'=>device_config($d)]);
    }
    $auth=$_SERVER['HTTP_AUTHORIZATION']??$_SERVER['REDIRECT_HTTP_AUTHORIZATION']??'';
    $token=str_starts_with($auth,'Bearer ')?substr($auth,7):(string)($body['token']??'');
    $d=one('SELECT * FROM devices WHERE token_hash=? AND revoked=0',[hash('sha256',$token)]);
    if(!$d) json_out(['ok'=>false,'message'=>'Perangkat tidak dikenal atau akses dicabut.'],401);
    if($action==='config') json_out(['ok'=>true,'config'=>device_config($d)]);
    if($_SERVER['REQUEST_METHOD']!=='POST') json_out(['ok'=>false],405);
    if($action==='upload') { if(!isset($body['data'])||!is_array($body['data'])) json_out(['ok'=>false,'message'=>'Daftar data diperlukan.'],400); json_out(ingest($d,$body['data'])); }
    if($action==='cancel' && $d['kind']==='manual') {
        $ids=$body['record_ids']??[];
        if(!is_array($ids)||count($ids)>100) json_out(['ok'=>false,'message'=>'Maksimal 100 pembatalan.'],400);
        db()->beginTransaction();
        try {
            lock_event((int)$d['event_id']); $accepted=[]; $rejected=[]; $changed=false; $affected=[];
            foreach($ids as $id) {
                if(!is_string($id)||!preg_match('/^[A-Za-z0-9:_-]{8,150}$/D',$id)){$rejected[]=['record_id'=>$id,'message'=>'ID pembatalan tidak valid.'];continue;}
                $o=one('SELECT id,device_id,cancelled,bib,epc FROM observations WHERE record_id=?',[$id]);
                if($o && (int)$o['device_id']!==(int)$d['id']){$rejected[]=['record_id'=>$id,'message'=>'Catatan milik perangkat lain.'];continue;}
                $newRequest=!one('SELECT id FROM cancel_requests WHERE record_id=? AND device_id=?',[$id,$d['id']]);
                if($newRequest){query('INSERT INTO cancel_requests(event_id,device_id,record_id,created_ms) VALUES(?,?,?,?)',[$d['event_id'],$d['id'],$id,now_ms()]);$changed=true;}
                if($o && !(int)$o['cancelled'] && $newRequest){query('UPDATE observations SET cancelled=1 WHERE id=?',[$o['id']]);$changed=true;}
                if($o && $newRequest) $affected=array_merge($affected,observation_categories((int)$d['event_id'],$o['bib'],$o['epc']));
                $accepted[]=$id;
            }
            if($changed){revise((int)$d['event_id'],array_values(array_unique($affected))); query('UPDATE devices SET manual_complete=0 WHERE id=?',[$d['id']]);audit((int)$d['event_id'],'operator_cancel',['device_id'=>$d['id'],'record_ids'=>$accepted]);}
            db()->commit();json_out(['ok'=>true,'accepted_ids'=>$accepted,'rejected'=>$rejected]);
        }catch(Throwable $e){db()->rollBack();throw $e;}
    }
    if($action==='heartbeat') {
        query('UPDATE devices SET last_seen_ms=?,pending_count=?,clock_quality=? WHERE id=?',[now_ms(),max(0,(int)($body['pending_count']??0)),substr((string)($body['clock_quality']??'unverified'),0,40),$d['id']]);
        json_out(['ok'=>true,'server_ms'=>now_ms()]);
    }
    json_out(['ok'=>false,'message'=>'Aksi tidak dikenal.'],404);
} catch(JsonException|InvalidArgumentException $e) { json_out(['ok'=>false,'message'=>$e->getMessage()],400); }
catch(Throwable $e) { error_log((string)$e); http_response_code(500); header('Content-Type: application/json'); echo json_encode(['ok'=>false,'message'=>'Server belum siap atau penyimpanan gagal. Data harus tetap disimpan di perangkat.']); }
