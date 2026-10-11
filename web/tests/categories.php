<?php
declare(strict_types=1);
$dir=sys_get_temp_dir().'/idlaps-categories-'.bin2hex(random_bytes(5));mkdir($dir);
$config=$dir.'/config.php';file_put_contents($config,'<?php return '.var_export(['dsn'=>'sqlite:'.$dir.'/test.db','allow_http_local'=>true],true).';');
putenv('IDLAPS_CONFIG='.(getenv('IDLAPS_TEST_CONFIG')?:$config));
require dirname(__DIR__).'/app/bootstrap.php';
require dirname(__DIR__).'/app/admin_actions.php';
install_schema(db());
$checks=0;
function check(bool $ok,string $label): void {global $checks;if(!$ok)throw new RuntimeException('FAIL '.$label);$checks++;echo "PASS $label\n";}
function action(string $name,array $fields=[]): string {$_POST=$fields+['csrf'=>'test-csrf'];return admin_action($name,1);}
function refuses(callable $fn,string $message): bool {try{$fn();return false;}catch(RuntimeException $e){return str_contains($e->getMessage(),$message);}}
$_SESSION['csrf']='test-csrf';$_SESSION['admin']='test-admin';$gun=1700000000000;
query('INSERT INTO events(name,timezone,created_ms) VALUES(?,?,?)',['Multiday','Asia/Jakarta',$gun]);
query('INSERT INTO categories(event_id,name,scheduled_ms,official_ms) VALUES(?,?,?,?)',[1,'Day one',$gun,$gun]);
query('INSERT INTO categories(event_id,name,scheduled_ms) VALUES(?,?,?)',[1,'Day two',$gun+86400000]);
foreach([[1,'007'],[2,'008']] as [$cat,$bib])query('INSERT INTO participants(event_id,category_id,bib,name) VALUES(?,?,?,?)',[1,$cat,$bib,'Runner '.$bib]);
query('INSERT INTO devices(event_id,name,kind,checkpoint,token_hash) VALUES(?,?,?,?,?)',[1,'Phone','manual',1,hash('sha256','test')]);
$device=one('SELECT * FROM devices WHERE id=1');
compute_event(1);
check(refuses(fn()=>action('official',['category_id'=>1,'manual_ready'=>1,'accept_rfid'=>1]),'007'),'Unresolved publication identifies BIB');
check(refuses(fn()=>action('participant_status',['id'=>1,'race_status'=>'dsq']),'Alasan'),'DSQ requires reason');
action('participant_status',['id'=>1,'race_status'=>'dns','reason'=>'Did not start']);
check(one('SELECT race_status FROM participants WHERE id=1')['race_status']==='dns','DNS can be set from results');
compute_event(1);
check(refuses(fn()=>action('official',['category_id'=>1,'accept_rfid'=>1]),'catatan manual'),'Publication requires category manual confirmation');
action('official',['category_id'=>1,'manual_ready'=>1,'accept_rfid'=>1]);
$latest=fn()=>one('SELECT * FROM result_runs WHERE event_id=1 ORDER BY id DESC LIMIT 1');
$state=result_category_states(1,$latest());
check($state[1]['official']&&!$state[2]['official'],'One category official while another remains unresolved');
$revision=category_revision(1);
$row=['record_id'=>'later-category','event_id'=>1,'bib'=>'008','checkpoint'=>1,'stage'=>'swim_finish','lap'=>1,'captured_ms'=>$gun+86400000+600000,'clock_quality'=>'synced','config_version'=>1];
check(ingest($device,[$row])['accepted_ids']===['later-category'],'Later category upload accepted');
$state=result_category_states(1,$latest());
check($state[1]['official']&&$state[1]['fresh']&&category_revision(1)===$revision&&!$state[2]['fresh'],'Later upload only invalidates its category');
$results=compute_event(1);$state=result_category_states(1,$latest());
check($state[1]['official']&&$state[1]['fresh'],'Recalculation preserves unchanged official category');
$run=$latest();$run['category_official']=[1=>true,2=>false];
$book=result_book(one('SELECT * FROM events WHERE id=1'),$run,$results);
check(str_contains((string)$book->getSheet(0)->getCell('A2')->getValue(),'RESMI')&&str_contains((string)$book->getSheet(1)->getCell('A2')->getValue(),'SEMENTARA'),'Excel labels each category independently');
$row['record_id']='late-first-category';$row['bib']='007';$row['captured_ms']=$gun+600000;ingest($device,[$row]);
check(!result_category_states(1,$latest())[1]['official'],'Late data in published category invalidates its publication');
action('participant_status',['id'=>1,'race_status'=>'active','reason'=>'Corrected start decision']);
$audit=json_decode(one("SELECT detail_json FROM audit WHERE action='participant_status' ORDER BY id DESC LIMIT 1")['detail_json'],true);
check($audit['before']==='dns'&&$audit['after']==='active'&&$audit['reason']==='Corrected start decision','Status reversal preserves audit');
foreach(['1234','A7','-1','1.2'] as $bib){$row['record_id']='invalid-'.$bib;$row['bib']=$bib;check(count(ingest($device,[$row])['rejected'])===1,'Invalid BIB rejected: '.$bib);}
// Re-run the additive upgrade over existing data, as happens on an older hosting install.
query("DELETE FROM app_updates WHERE version='2.2'");upgrade_publication_schema(db());upgrade_publication_schema(db());
check(count(rows('SELECT * FROM participants'))===2&&category_revision(1)>$revision,'Repeated upgrade preserves existing participants and revisions');
action('participant',['bib'=>'009','name'=>'Added DNF','category_id'=>2,'race_status'=>'dnf','status_reason'=>'Test decision']);
check(one("SELECT race_status FROM participants WHERE bib='009'")['race_status']==='dnf','New participant preserves selected race status');
echo "\n$checks checks passed.\n";
