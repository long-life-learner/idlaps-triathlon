<?php
declare(strict_types=1);

function device_config(array $device): array {
    $event=one('SELECT * FROM events WHERE id=?',[$device['event_id']]);
    return ['event'=>$event,'device'=>array_intersect_key($device,array_flip(['id','name','kind','checkpoint','config_version'])),'categories'=>rows('SELECT * FROM categories WHERE event_id=?',[$event['id']]),'participants'=>rows('SELECT bib,name,category_id,epc FROM participants WHERE event_id=?',[$event['id']]),'readers'=>rows('SELECT * FROM readers WHERE device_id=? AND enabled=1',[$device['id']]),'server_ms'=>now_ms()];
}
function canonical_json(array $value): string { $sort=function(&$a) use (&$sort) { if(!is_array($a)) return; if(!array_is_list($a)) ksort($a); foreach($a as &$v) if(is_array($v)) $sort($v); }; $sort($value); return json_encode($value,JSON_UNESCAPED_UNICODE|JSON_PRESERVE_ZERO_FRACTION|JSON_THROW_ON_ERROR); }
function normalize_observation(array $row,array $device): array {
    $id=(string)($row['record_id']??'');
    if(!preg_match('/^[A-Za-z0-9:_-]{8,150}$/D',$id)) throw new InvalidArgumentException('ID catatan tidak valid.');
    if((int)($row['event_id']??0)!==(int)$device['event_id']) throw new InvalidArgumentException('Event tidak cocok dengan penugasan perangkat.');
    $ms=filter_var($row['captured_ms']??null,FILTER_VALIDATE_INT);
    if($ms===false || $ms<946684800000 || $ms>now_ms()+86400000) throw new InvalidArgumentException('Timestamp tidak valid atau jauh di masa depan.');
    $cp=(int)($row['checkpoint']??0); $stage=null; $lap=null; $reader=null; $epc=null; $bib=null;
    if($device['kind']==='manual') {
        if($cp!==(int)$device['checkpoint']) throw new InvalidArgumentException('Checkpoint tidak sesuai perangkat.');
        $bib=trim((string)($row['bib']??''));
        $p=one('SELECT p.*,c.bike_laps,c.run_laps FROM participants p JOIN categories c ON c.id=p.category_id WHERE p.event_id=? AND p.bib=?',[$device['event_id'],$bib]);
        if(!$p) throw new InvalidArgumentException('BIB belum terdaftar dalam event.');
        $stage=(string)($row['stage']??''); $lap=(int)($row['lap']??1);
        if($cp===3 && $stage==='cycle') { if($lap<1||$lap>(int)$p['bike_laps']) throw new InvalidArgumentException('Putaran sepeda tidak valid.'); $stage=$lap===(int)$p['bike_laps']?'cycle_finish':'cycle_lap'; }
        if($cp===4 && $stage==='run') { if($lap<1||$lap>(int)$p['run_laps']) throw new InvalidArgumentException('Putaran lari tidak valid.'); $stage=$lap===(int)$p['run_laps']?'run_finish':'run_lap'; }
        $valid=[1=>['swim_finish'],2=>['cycle_start','run_start'],3=>['cycle_finish','cycle_lap'],4=>['run_finish','run_lap']];
        if(!in_array($stage,$valid[$cp]??[],true)) throw new InvalidArgumentException('Jenis lintasan tidak sesuai checkpoint.');
        if($cp<=2 && $lap!==1) throw new InvalidArgumentException('Tahap ini hanya memiliki satu lintasan.');
        if($cp===3 && (($stage==='cycle_finish' && $lap!==(int)$p['bike_laps']) || ($stage==='cycle_lap' && ($lap<1||$lap>=(int)$p['bike_laps'])))) throw new InvalidArgumentException('Putaran sepeda tidak sesuai rute.');
        if($cp===4 && (($stage==='run_finish' && $lap!==(int)$p['run_laps']) || ($stage==='run_lap' && ($lap<1||$lap>=(int)$p['run_laps'])))) throw new InvalidArgumentException('Putaran lari tidak sesuai rute.');
    } else {
        $reader=(int)($row['reader_id']??0); $r=one('SELECT * FROM readers WHERE id=? AND device_id=?',[$reader,$device['id']]);
        if(!$r || $cp!==(int)$r['checkpoint']) throw new InvalidArgumentException('Reader/checkpoint tidak sesuai penugasan.');
        $epc=strtoupper(trim((string)($row['epc']??'')));
        if(!preg_match('/^(?:[A-F0-9]{2}){1,64}$/D',$epc)) throw new InvalidArgumentException('EPC tidak valid.');
        // Unknown tags are retained; registration can be corrected before recalculation.
    }
    $quality=(string)($row['clock_quality']??'unverified');
    if(!in_array($quality,['synced','holdover','unverified','stale','jump'],true)) throw new InvalidArgumentException('Status jam tidak valid.');
    return [$id,(int)$device['event_id'],(int)$device['id'],$device['kind'],$bib,$epc,$reader,$cp,$stage,$lap,$ms,now_ms(),$quality,isset($row['uncertainty_ms'])?max(0,(int)$row['uncertainty_ms']):null,!empty($row['test'])?1:0,0,(int)($row['config_version']??1),hash('sha256',canonical_json($row)),canonical_json($row)];
}
function ingest(array $device,array $data): array {
    if(count($data)>500) throw new InvalidArgumentException('Maksimal 500 catatan per kiriman.');
    $accepted=[]; $rejected=[]; $changed=false;
    db()->beginTransaction();
    try {
        lock_event((int)$device['event_id']);
        foreach($data as $row) {
            $id=is_array($row)?(string)($row['record_id']??''):'';
            if(!is_array($row)) { $rejected[]=['record_id'=>$id,'message'=>'Catatan harus berupa objek.']; continue; }
            $existing=one('SELECT device_id,payload_hash FROM observations WHERE record_id=?',[$id]);
            if($existing) {
                if((int)$existing['device_id']===(int)$device['id'] && hash_equals($existing['payload_hash'],hash('sha256',canonical_json($row)))) $accepted[]=$id;
                else $rejected[]=['record_id'=>$id,'message'=>'ID sudah dipakai untuk isi berbeda.'];
                continue;
            }
            try { $values=normalize_observation($row,$device); }
            catch(InvalidArgumentException $e) { $rejected[]=['record_id'=>$id,'message'=>$e->getMessage()]; continue; }
            if(one('SELECT id FROM cancel_requests WHERE record_id=? AND device_id=?',[$id,$device['id']])) $values[15]=1;
            query('INSERT INTO observations(record_id,event_id,device_id,source,bib,epc,reader_id,checkpoint,stage,lap,captured_ms,received_ms,clock_quality,uncertainty_ms,test,cancelled,config_version,payload_hash,payload_json) VALUES('.implode(',',array_fill(0,19,'?')).')',$values);
            $accepted[]=$id; if(!$values[14]) $changed=true;
        }
        if($changed) { revise((int)$device['event_id']); query('UPDATE devices SET manual_complete=0 WHERE id=?',[$device['id']]); }
        query('UPDATE devices SET last_seen_ms=? WHERE id=?',[now_ms(),$device['id']]);
        db()->commit();
    } catch(Throwable $e) { db()->rollBack(); throw $e; }
    return ['ok'=>true,'accepted_ids'=>$accepted,'rejected'=>$rejected];
}
function compute_event(int $id): array {
    db()->beginTransaction();
    try {
        $event=lock_event($id);
        $participants=rows('SELECT * FROM participants WHERE event_id=?',[$id]);
        $categories=rows('SELECT * FROM categories WHERE event_id=?',[$id]);$categoryMap=array_column($categories,null,'id');
        $observations=rows('SELECT * FROM observations WHERE event_id=? AND source=? AND test=0 AND cancelled=0 ORDER BY captured_ms,id',[$id,'manual']);
        // Stream dense RF observations instead of loading the entire event into PHP memory.
        foreach($participants as $participant) {
            if(!$participant['epc']) continue;
            $mysql=db()->getAttribute(PDO::ATTR_DRIVER_NAME)==='mysql';
            if($mysql) db()->setAttribute(PDO::MYSQL_ATTR_USE_BUFFERED_QUERY,false);
            try {
                $category=$categoryMap[$participant['category_id']];$gun=(int)($category['official_ms']??$category['scheduled_ms']);
                $stmt=query('SELECT * FROM observations WHERE event_id=? AND epc=? AND source=? AND test=0 AND cancelled=0 AND captured_ms>=? ORDER BY captured_ms,id',[$id,$participant['epc'],'rfid',$gun]);
                $seen=[];
                while($o=$stmt->fetch()) {
                    $p=json_decode($o['payload_json'],true)?:[];$k=$o['reader_id'];$t=(int)$o['captured_ms'];$s=$seen[$k]??null;
                    $new=$s===null || (($p['detect_mode']??'multi')!=='single' && $t-$s['seen']>=max(100,(int)($p['quiet_ms']??2000)) && $t-$s['accepted']>=max(0,(int)($p['interval_ms']??10000)));
                    if($new){$observations[]=$o;$seen[$k]=['seen'=>$t,'accepted'=>$t];}else $seen[$k]['seen']=$t;
                }
                $stmt->closeCursor();
            } finally { if($mysql) db()->setAttribute(PDO::MYSQL_ATTR_USE_BUFFERED_QUERY,true); }
        }
        $results=calculate_results($categories,$participants,$observations,rows('SELECT * FROM decisions WHERE event_id=?',[$id]));
        query('INSERT INTO result_runs(event_id,revision,created_ms,official,result_json) VALUES(?,?,?,?,?)',[$id,$event['revision'],now_ms(),0,json_encode($results,JSON_THROW_ON_ERROR)]);
        audit($id,'calculate',['revision'=>$event['revision'],'participants'=>count($results)]);
        db()->commit(); return $results;
    } catch(Throwable $e) { db()->rollBack(); throw $e; }
}
