<?php
declare(strict_types=1);

// Additive upgrade for existing shared-hosting installations; no terminal required.
function upgrade_publication_schema(PDO $db): void {
    $db->exec('CREATE TABLE IF NOT EXISTS app_updates (version VARCHAR(40) PRIMARY KEY)');
    if($db->query("SELECT version FROM app_updates WHERE version='2.2'")->fetchColumn()) return;
    $db->exec('CREATE TABLE IF NOT EXISTS category_versions (category_id BIGINT PRIMARY KEY, revision INTEGER NOT NULL)');
    $db->exec('CREATE TABLE IF NOT EXISTS result_category_versions (run_id BIGINT NOT NULL, category_id BIGINT NOT NULL, revision INTEGER NOT NULL, PRIMARY KEY(run_id,category_id))');
    $db->exec('CREATE TABLE IF NOT EXISTS category_publications (category_id BIGINT PRIMARY KEY, revision INTEGER NOT NULL, run_id BIGINT NOT NULL, created_ms BIGINT NOT NULL)');
    try { $db->exec("INSERT INTO app_updates(version) VALUES('2.2')"); }
    catch(PDOException $e) { if(!str_contains(strtolower($e->getMessage()),'unique')&&!str_contains(strtolower($e->getMessage()),'duplicate')) throw $e; }
}
function observation_categories(int $event,?string $bib,?string $epc): array {
    return array_map('intval',array_column(rows('SELECT category_id FROM participants WHERE event_id=? AND (bib=? OR epc=? OR id IN (SELECT participant_id FROM participant_tags WHERE event_id=? AND epc=?))',[$event,$bib,$epc,$event,$epc]),'category_id'));
}
function category_revision(int $id): int { return (int)(one('SELECT revision FROM category_versions WHERE category_id=?',[$id])['revision']??1); }
function result_category_states(int $event,?array $run): array {
    $states=[];
    foreach(rows('SELECT id,name,official_ms FROM categories WHERE event_id=?',[$event]) as $c) {
        $id=(int)$c['id']; $revision=category_revision($id);
        $snapshot=$run?one('SELECT revision FROM result_category_versions WHERE run_id=? AND category_id=?',[$run['id'],$id]):null;
        $publication=one('SELECT * FROM category_publications WHERE category_id=?',[$id]);
        $states[$id]=['name'=>$c['name'],'fresh'=>$snapshot && (int)$snapshot['revision']===$revision,
            'official'=>$publication && (int)$publication['revision']===$revision,'gun_official'=>$c['official_ms']!==null];
    }
    return $states;
}
function publish_category(int $event,int $category): void {
    $run=one('SELECT * FROM result_runs WHERE event_id=? ORDER BY id DESC LIMIT 1',[$event]);
    $state=result_category_states($event,$run)[$category]??null;
    if(!$state) throw new RuntimeException('Pilih kategori yang akan ditetapkan resmi.');
    if(!$state['fresh']) throw new RuntimeException('Hitung ulang hasil kategori ini terlebih dahulu.');
    if(!$state['gun_official']) throw new RuntimeException('Isi gun time resmi kategori ini.');
    $results=array_values(array_filter(json_decode($run['result_json'],true),fn($r)=>(int)$r['category_id']===$category));
    if(!$results) throw new RuntimeException('Kategori belum memiliki peserta.');
    $unresolved=array_filter($results,fn($r)=>$r['status']==='Perlu diperiksa');
    if($unresolved) throw new RuntimeException('Periksa BIB '.implode(', ',array_column($unresolved,'bib')).'. Gunakan Periksa catatan atau Atur status di bawah.');
    if(empty($_POST['manual_ready'])) throw new RuntimeException('Konfirmasikan catatan manual kategori ini sudah selesai dikirim.');
    if(empty($_POST['accept_rfid'])) throw new RuntimeException('Konfirmasikan hasil dan penggunaan RFID ketika manual tidak tersedia.');
    query('DELETE FROM category_publications WHERE category_id=?',[$category]);
    query('INSERT INTO category_publications(category_id,revision,run_id,created_ms) VALUES(?,?,?,?)',[$category,category_revision($category),$run['id'],now_ms()]);
    audit($event,'official_category',['category_id'=>$category,'run_id'=>$run['id'],'manual_ready'=>true]);
}
