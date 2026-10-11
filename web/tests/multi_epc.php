<?php
declare(strict_types=1);
$dir=sys_get_temp_dir().'/idlaps-tags-'.bin2hex(random_bytes(5));mkdir($dir);
$config=$dir.'/config.php';file_put_contents($config,'<?php return '.var_export(['dsn'=>'sqlite:'.$dir.'/test.db','allow_http_local'=>true],true).';');
putenv('IDLAPS_CONFIG='.(getenv('IDLAPS_TEST_CONFIG')?:$config));
require dirname(__DIR__).'/app/bootstrap.php';require dirname(__DIR__).'/app/admin_actions.php';install_schema(db());
$checks=0;
function check(bool $ok,string $label): void {global $checks;if(!$ok)throw new RuntimeException('FAIL '.$label);$checks++;echo "PASS $label\n";}
function action(string $name,array $fields=[]): void {$_POST=$fields+['csrf'=>'test'];admin_action($name,1);}
$_SESSION['csrf']='test';$_SESSION['admin']='tester';$gun=1700000000000;
query('INSERT INTO events(name,timezone,created_ms) VALUES(?,?,?)',['Tags','Asia/Jakarta',$gun]);
query('INSERT INTO categories(event_id,name,scheduled_ms,official_ms) VALUES(?,?,?,?)',[1,'Elite',$gun,$gun]);
query('INSERT INTO participants(event_id,category_id,bib,name,epc) VALUES(?,?,?,?,?)',[1,1,'007','Ayu','AA01']);
query("DELETE FROM app_updates WHERE version='2.3-tags'");upgrade_tag_schema(db());upgrade_tag_schema(db());
check(rows('SELECT epc FROM participant_tags')===[['epc'=>'AA01']],'Existing single EPC migrated once');
$fields=['id'=>1,'bib'=>'007','name'=>'Ayu','category_id'=>1,'race_status'=>'active','epc'=>"aa01, 00 02\nAA03"];
action('participant',$fields);
$p=with_participant_tags(rows('SELECT * FROM participants WHERE event_id=1'),1)[0];
check(count($p['epcs'])===3&&in_array('0002',$p['epcs'],true)&&$p['epc']==='AA01','Multi EPC normalizes hex and preserves leading zeros');
query('INSERT INTO devices(event_id,name,kind,checkpoint,token_hash) VALUES(?,?,?,?,?)',[1,'Reader laptop','rfid',1,hash('sha256','token')]);
$d=one('SELECT * FROM devices WHERE id=1');
check(count(device_config($d)['participants'][0]['epcs'])===3,'Device config includes all tags and compatibility primary');
foreach([1,2,3,4] as $cp)query('INSERT INTO readers(device_id,name,host,port,checkpoint,detect_mode) VALUES(?,?,?,?,?,?)',[1,'Reader '.$cp,'127.0.0.1',2022,$cp,$cp===1?'single':'multi']);
query('INSERT INTO readers(device_id,name,host,port,checkpoint,detect_mode) VALUES(?,?,?,?,?,?)',[1,'Second swim reader','127.0.0.1',2023,1,'single']);
$route=[[1,600000],[2,660000],[3,1800000],[2,1860000],[4,2400000]];$data=[];
foreach($route as $n=>[$cp,$offset])foreach(['0002','AA03'] as $tag)for($i=0;$i<30;$i++){
    $data[]=['record_id'=>"tag-$n-$tag-$i",'event_id'=>1,'epc'=>$tag,'reader_id'=>$cp,'checkpoint'=>$cp,'captured_ms'=>$gun+$offset+$i*50+($tag==='AA03'?20:0),'clock_quality'=>'synced','detect_mode'=>$cp===1?'single':'multi','quiet_ms'=>2000,'interval_ms'=>10000];
}
$data[]=array_replace($data[0],['record_id'=>'second-swim-reader','reader_id'=>5,'captured_ms'=>$gun+600300]);
check(count(ingest($d,$data)['accepted_ids'])===301,'Dense secondary tag reads accepted');
$result=compute_event(1)[0];
check($result['status']==='Selesai'&&$result['total_ms']===2400000&&$result['swim_ms']===600000,'Secondary tags complete route without primary or duplicate passages');
check(count(rows('SELECT id FROM observations'))===301,'All raw tag evidence retained');
action('official',['category_id'=>1,'manual_ready'=>1,'accept_rfid'=>1]);
$late=array_replace($data[0],['record_id'=>'late-secondary-tag','captured_ms'=>$gun+600100]);ingest($d,[$late]);
$latest=one('SELECT * FROM result_runs ORDER BY id DESC LIMIT 1');
check(!result_category_states(1,$latest)[1]['official'],'Secondary tag upload invalidates corresponding official category');
$bad=$fields;$bad['id']=0;$bad['bib']='008';$bad['epc']='0002';
try{action('participant',$bad);$blocked=false;}catch(RuntimeException $e){$blocked=str_contains($e->getMessage(),'007');}
check($blocked&&!one("SELECT id FROM participants WHERE bib='008'"),'Secondary tag cannot be shared by another BIB; transaction rolls back');
$bad=$fields;$bad['epc']='AA01,aa01';
try{action('participant',$bad);$blocked=false;}catch(RuntimeException $e){$blocked=true;}
check($blocked&&count(rows('SELECT * FROM participant_tags'))===3,'Duplicate tag input rejected without changing mapping');
$book=excel_template();$sheet=$book->getActiveSheet();
foreach(['008','Budi','Elite',"BB01, 0004",'Club'] as $i=>$v)$sheet->setCellValueExplicit([$i+1,2],$v,\PhpOffice\PhpSpreadsheet\Cell\DataType::TYPE_STRING);
$path=$dir.'/import.xlsx';(new \PhpOffice\PhpSpreadsheet\Writer\Xlsx($book))->save($path);$preview=preview_import($path,1);
check(!$preview['errors']&&$preview['rows'][0]['epcs']===['BB01','0004'],'Excel previews multiple EPCs in one cell');
$_SESSION['import']=$preview;action('import_commit');
check(count(with_participant_tags(rows("SELECT * FROM participants WHERE bib='008'"),1)[0]['epcs'])===2,'Excel import persists all participant tags');
$sheet->setCellValueExplicit('A2','009',\PhpOffice\PhpSpreadsheet\Cell\DataType::TYPE_STRING);$sheet->setCellValue('D2','CC01, 0004');(new \PhpOffice\PhpSpreadsheet\Writer\Xlsx($book))->save($path);
check(count(preview_import($path,1)['errors'])>0,'Excel detects collision with secondary EPC');
$fields['epc']='AA01';$before=category_revision(1);action('participant',$fields);
check(category_revision(1)>$before&&count(with_participant_tags(rows('SELECT * FROM participants WHERE id=1'),1)[0]['epcs'])===1,'Removing tags updates mapping and invalidates results');
check(compute_event(1)[0]['status']==='Perlu diperiksa','Removed EPC evidence no longer silently assigned to old BIB');
$audit=json_decode(one("SELECT detail_json FROM audit WHERE action='participant' ORDER BY id DESC LIMIT 1")['detail_json'],true);
check(count($audit['before']['epcs'])===3&&$audit['epcs']===['AA01'],'Tag change audit includes old and new EPCs');
echo "\n$checks checks passed.\n";
