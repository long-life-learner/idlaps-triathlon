<?php
declare(strict_types=1);
require dirname(__DIR__).'/app/bootstrap.php';install_schema(db());
query('INSERT INTO users(username,password_hash) VALUES(?,?)',['tester',password_hash('local-only-test-password',PASSWORD_DEFAULT)]);
query('INSERT INTO events(name,timezone,created_ms) VALUES(?,?,?)',['Integration','Asia/Jakarta',now_ms()]);
query('INSERT INTO categories(event_id,name,scheduled_ms) VALUES(?,?,?)',[1,'Open',now_ms()-10000000]);
query('INSERT INTO participants(event_id,category_id,bib,name,epc) VALUES(?,?,?,?,?)',[1,1,'007','Test Athlete','ABCD']);
foreach(['rfid','manual'] as $kind) query('INSERT INTO devices(event_id,name,kind,checkpoint,token_hash,pairing_hash,pairing_expires_ms) VALUES(?,?,?,?,?,?,?)',[1,'Device '.$kind,$kind,1,hash('sha256','unused-'.$kind),hash('sha256','TEST-'.strtoupper($kind)),now_ms()+3600000]);
query('INSERT INTO readers(device_id,name,host,port,checkpoint) VALUES(?,?,?,?,?)',[1,'Reader','127.0.0.1',2022,1]);
