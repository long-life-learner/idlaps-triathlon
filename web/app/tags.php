<?php
declare(strict_types=1);

function upgrade_tag_schema(PDO $db): void {
    if($db->query("SELECT version FROM app_updates WHERE version='2.3-tags'")->fetchColumn()) return;
    $db->exec('CREATE TABLE IF NOT EXISTS participant_tags (event_id BIGINT NOT NULL, participant_id BIGINT NOT NULL, epc VARCHAR(128) NOT NULL, PRIMARY KEY(event_id,epc))');
    try { $db->exec('CREATE INDEX tags_participant ON participant_tags(participant_id)'); }
    catch(PDOException $e) { if(!str_contains(strtolower($e->getMessage()),'exist')&&!str_contains(strtolower($e->getMessage()),'duplicate')) throw $e; }
    $exists=$db->getAttribute(PDO::ATTR_DRIVER_NAME)==='sqlite'
        ? $db->query("SELECT name FROM sqlite_master WHERE type='table' AND name='participants'")->fetchColumn()
        : $db->query("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='participants'")->fetchColumn();
    if(!$exists) return; // First install creates participants after the connection is opened.
    $insert=$db->getAttribute(PDO::ATTR_DRIVER_NAME)==='sqlite'?'INSERT OR IGNORE':'INSERT IGNORE';
    $db->exec("$insert INTO participant_tags(event_id,participant_id,epc) SELECT event_id,id,UPPER(epc) FROM participants WHERE epc IS NOT NULL AND epc<>''");
    $db->exec("$insert INTO app_updates(version) VALUES('2.3-tags')");
}

function parse_epcs(string $input): array {
    $epcs=[];
    foreach(preg_split('/[,;\r\n]+/',$input) as $item) {
        $epc=strtoupper(preg_replace('/[\t ]+/','',trim($item)));
        if($epc==='') continue;
        if(!preg_match('/^(?:[A-F0-9]{2}){1,64}$/D',$epc)) throw new RuntimeException('Setiap EPC harus hexadecimal dengan jumlah digit genap, maksimal 128 digit. Pisahkan tag dengan koma atau baris baru.');
        if(in_array($epc,$epcs,true)) throw new RuntimeException('EPC yang sama ditulis lebih dari sekali: '.$epc);
        $epcs[]=$epc;
    }
    return $epcs;
}

function with_participant_tags(array $participants,int $event): array {
    $tags=[];
    foreach(rows('SELECT participant_id,epc FROM participant_tags WHERE event_id=? ORDER BY epc',[$event]) as $tag) $tags[$tag['participant_id']][]=$tag['epc'];
    foreach($participants as &$p) {
        $p['epcs']=array_values(array_unique(array_merge(empty($p['epc'])?[]:[strtoupper($p['epc'])],$tags[$p['id']]??[])));
    }
    return $participants;
}

// Caller holds the event lock and transaction. Keep primary epc for old clients.
function save_participant_tags(int $event,int $participant,array $epcs): void {
    foreach($epcs as $epc) {
        $owner=one('SELECT p.bib FROM participants p WHERE p.event_id=? AND p.id<>? AND (p.epc=? OR p.id IN (SELECT participant_id FROM participant_tags WHERE event_id=? AND epc=?))',[$event,$participant,$epc,$event,$epc]);
        if($owner) throw new RuntimeException('EPC '.$epc.' sudah digunakan BIB '.$owner['bib'].' dalam event ini.');
    }
    query('DELETE FROM participant_tags WHERE event_id=? AND participant_id=?',[$event,$participant]);
    foreach($epcs as $epc) query('INSERT INTO participant_tags(event_id,participant_id,epc) VALUES(?,?,?)',[$event,$participant,$epc]);
    query('UPDATE participants SET epc=? WHERE id=? AND event_id=?',[$epcs[0]??null,$participant,$event]);
}
