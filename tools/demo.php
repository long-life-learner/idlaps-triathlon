<?php
declare(strict_types=1);
// Local-only demonstration. Never deploy this configuration to public hosting.
$root=dirname(__DIR__);$dir=$root.'/web/storage/demo';if(!is_dir($dir))mkdir($dir,0700,true);
$path=$dir.'/local.php';file_put_contents($path,'<?php return '.var_export(['dsn'=>'sqlite:'.$dir.'/demo.db','allow_http_local'=>true,'install_key'=>bin2hex(random_bytes(24))],true).';');putenv('IDLAPS_CONFIG='.$path);
require $root.'/web/app/bootstrap.php';install_schema(db());
if(!one('SELECT id FROM users LIMIT 1')){
    $password=bin2hex(random_bytes(8));query('INSERT INTO users(username,password_hash) VALUES(?,?)',['admin',password_hash($password,PASSWORD_DEFAULT)]);file_put_contents($dir.'/login.txt',"admin\n$password\n");chmod($dir.'/login.txt',0600);
    $gun=(new DateTimeImmutable('2026-10-04 07:00:00',new DateTimeZone('Asia/Jakarta')))->getTimestamp()*1000;
    query('INSERT INTO events(name,timezone,created_ms) VALUES(?,?,?)',['IDLAPS Triathlon · Demo','Asia/Jakarta',now_ms()]);
    query('INSERT INTO categories(event_id,name,scheduled_ms,official_ms) VALUES(?,?,?,?)',[1,'Men Elite',$gun,$gun]);
    query('INSERT INTO categories(event_id,name,scheduled_ms) VALUES(?,?,?)',[1,'Women Open',$gun+14400000]);
    foreach([['007','Arif Pratama',1,'ABCD'],['021','Dimas Saputra',1,'ABCE'],['108','Nadia Putri',2,'ABCF']] as $p) query('INSERT INTO participants(event_id,bib,name,category_id,epc,team) VALUES(?,?,?,?,?,?)',[1,$p[0],$p[1],$p[2],$p[3],'IDLAPS Club']);
    query('INSERT INTO devices(event_id,name,kind,checkpoint,token_hash,pairing_hash,pairing_expires_ms) VALUES(?,?,?,?,?,?,?)',[1,'Laptop Finish Swim','rfid',1,hash('sha256','demo-desktop-token'),hash('sha256','DEMO-DESKTOP-2026'),now_ms()+86400000]);
    query('INSERT INTO readers(device_id,name,host,port,checkpoint) VALUES(?,?,?,?,?)',[1,'Reader Swim Kiri','127.0.0.1',2022,1]);
    for($cp=1;$cp<=4;$cp++){
        query('INSERT INTO devices(event_id,name,kind,checkpoint,token_hash,pairing_hash,pairing_expires_ms) VALUES(?,?,?,?,?,?,?)',[1,'Android Titik '.$cp,'manual',$cp,hash('sha256','demo-manual-'.$cp),hash('sha256','DEMO-MANUAL-2026-'.$cp),now_ms()+86400000]);
    }
    foreach([['swim_finish',1,900000],['cycle_start',2,990000],['cycle_finish',3,3600000],['run_start',2,3690000],['run_finish',4,5100000]] as $i=>$point) {
        $d=one('SELECT * FROM devices WHERE kind=? AND checkpoint=?',['manual',$point[1]]);
        ingest($d,[['record_id'=>'demo-arif-'.$i,'event_id'=>1,'bib'=>'007','checkpoint'=>$point[1],'stage'=>$point[0],'lap'=>1,'captured_ms'=>$gun+$point[2],'clock_quality'=>'synced','config_version'=>1]]);
    }
    compute_event(1);
}
echo "Local config: $path\nLogin stored in: $dir/login.txt\n";
