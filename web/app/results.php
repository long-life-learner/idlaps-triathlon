<?php
declare(strict_types=1);
function step_label(string $key): string {
    [$stage,$lap]=array_pad(explode(':',$key,2),2,'1');
    $names=['swim_finish'=>'Finish swim','cycle_start'=>'Mulai sepeda','cycle_lap'=>'Lintasan sepeda','cycle_finish'=>'Finish sepeda','run_start'=>'Mulai lari','run_lap'=>'Lintasan lari','run_finish'=>'Finish lari'];
    return ($names[$stage]??$stage).(in_array($stage,['cycle_lap','cycle_finish','run_lap','run_finish'],true)?' · putaran '.$lap:'');
}

function route_steps(array $category): array {
    $steps=[['key'=>'swim_finish:1','stage'=>'swim_finish','lap'=>1,'checkpoint'=>1,'min_ms'=>0],['key'=>'cycle_start:1','stage'=>'cycle_start','lap'=>1,'checkpoint'=>2,'min_ms'=>0]];
    for($i=1;$i<=(int)$category['bike_laps'];$i++) { $stage=$i===(int)$category['bike_laps']?'cycle_finish':'cycle_lap'; $steps[]=['key'=>"$stage:$i",'stage'=>$stage,'lap'=>$i,'checkpoint'=>3,'min_ms'=>(int)$category['bike_min_s']*1000]; }
    $steps[]=['key'=>'run_start:1','stage'=>'run_start','lap'=>1,'checkpoint'=>2,'min_ms'=>0];
    for($i=1;$i<=(int)$category['run_laps'];$i++) { $stage=$i===(int)$category['run_laps']?'run_finish':'run_lap'; $steps[]=['key'=>"$stage:$i",'stage'=>$stage,'lap'=>$i,'checkpoint'=>4,'min_ms'=>(int)$category['run_min_s']*1000]; }
    return $steps;
}

// Keep all observations in storage. These are derived passage candidates only.
function rfid_passages(array $observations): array {
    usort($observations,fn($a,$b)=>[(int)$a['captured_ms'],$a['record_id']]<=>[(int)$b['captured_ms'],$b['record_id']]);
    $readers=[]; $passages=[];
    foreach($observations as $o) {
        $p=json_decode($o['payload_json']??'{}',true) ?: [];
        $k=(string)$o['reader_id']; $t=(int)$o['captured_ms'];
        $s=$readers[$k]??null;
        $quiet=max(100,(int)($p['quiet_ms']??2000)); $interval=max(0,(int)($p['interval_ms']??10000));
        $new=$s===null || (($p['detect_mode']??'multi')!=='single' && $t-$s['seen']>=$quiet && $t-$s['accepted']>=$interval);
        if($new) { $passages[]=$o; $readers[$k]=['seen'=>$t,'accepted'=>$t]; }
        else $readers[$k]['seen']=$t;
    }
    usort($passages,fn($a,$b)=>(int)$a['captured_ms']<=>(int)$b['captured_ms']);
    $merged=[];
    foreach($passages as $o) {
        $last=array_key_last($merged);
        if($last!==null && (int)$o['captured_ms']-(int)$merged[$last]['captured_ms']<=2000 && (int)$o['reader_id']!==(int)$merged[$last]['reader_id']) continue;
        $merged[]=$o;
    }
    return $merged;
}

function calculate_results(array $categories,array $participants,array $observations,array $decisions): array {
    $cats=array_column($categories,null,'id'); $byBib=[]; $epcs=[];
    foreach($participants as $p) if(!empty($p['epc'])) $epcs[strtoupper($p['epc'])]=$p['bib'];
    foreach($observations as $o) {
        if((int)$o['test'] || (int)$o['cancelled']) continue;
        $bib=$o['source']==='rfid'?($epcs[strtoupper($o['epc']??'')]??null):$o['bib'];
        if($bib!==null) $byBib[(string)$bib][]=$o;
    }
    $overrides=[]; foreach($decisions as $d) $overrides[(string)$d['bib']][$d['step_key']]=$d;
    $result=[];
    foreach($participants as $p) {
        $cat=$cats[$p['category_id']]; $gun=(int)($cat['official_ms']??$cat['scheduled_ms']); $route=route_steps($cat);
        $chosen=[]; $issues=[]; $manual=[]; $rfid=[];
        foreach($byBib[(string)$p['bib']]??[] as $o) {
            if($o['source']==='manual') $manual[($o['stage']??'').':'.($o['lap']??1)][]=$o;
            elseif((int)$o['captured_ms']>=$gun) $rfid[(int)$o['checkpoint']][]=$o;
        }
        foreach($route as $step) {
            $key=$step['key'];
            if(isset($overrides[(string)$p['bib']][$key])) { $d=$overrides[(string)$p['bib']][$key]; $chosen[$key]=['captured_ms'=>(int)$d['captured_ms'],'source'=>'admin','record_id'=>'decision:'.$d['id'],'clock_quality'=>'reviewed']; }
            elseif(count($manual[$key]??[])===1) $chosen[$key]=$manual[$key][0];
            elseif(count($manual[$key]??[])>1) $issues[]='Catatan manual ganda: '.step_label($key);
        }
        foreach([1,2,3,4] as $cp) {
            $expected=array_values(array_filter($route,fn($s)=>$s['checkpoint']===$cp));
            $candidates=rfid_passages($rfid[$cp]??[]);
            // Remove RFID corroboration near an explicit manual/admin crossing.
            $remaining=[];
            foreach($candidates as $candidate) {
                $matched=false;
                foreach($expected as $s) if(isset($chosen[$s['key']]) && abs((int)$candidate['captured_ms']-(int)$chosen[$s['key']]['captured_ms'])<=3000) { $matched=true; break; }
                if(!$matched) $remaining[]=$candidate;
            }
            $missing=array_values(array_filter($expected,fn($s)=>!isset($chosen[$s['key']]) && count($manual[$s['key']]??[])===0));
            if(count($remaining)===count($missing)) {
                foreach($missing as $i=>$s) $chosen[$s['key']]=$remaining[$i];
            } elseif(count($remaining)>0) $issues[]="RFID titik $cp belum dapat dipastikan (".count($remaining).' lintasan untuk '.count($missing).' tahap).';
        }
        $prev=$gun; $times=[]; $sources=[]; $records=[];
        foreach($route as $s) {
            $key=$s['key']; $o=$chosen[$key]??null;
            if(!$o) { $issues[]='Belum tercatat: '.step_label($key); $prev=null; continue; }
            $t=(int)$o['captured_ms']; $times[$key]=$t; $sources[$key]=$o['source']; $records[$key]=$o['record_id'];
            if($t<$gun || ($prev!==null && $t-$prev<$s['min_ms'])) $issues[]='Waktu/urutan tidak sesuai: '.step_label($key);
            if(!in_array($o['clock_quality'],['synced','holdover','reviewed'],true)) $issues[]='Jam perlu diperiksa: '.step_label($key);
            $prev=$t;
        }
        // Verify chronology even across missing intermediate steps.
        $previous=$gun; foreach($times as $t) { if($t<$previous) { $issues[]='Urutan waktu mundur'; break; } $previous=$t; }
        $swim=$times['swim_finish:1']??null; $bikeStart=$times['cycle_start:1']??null;
        $bikeEnd=$times['cycle_finish:'.$cat['bike_laps']]??null; $runStart=$times['run_start:1']??null; $finish=$times['run_finish:'.$cat['run_laps']]??null;
        $diff=fn($end,$start)=>$end!==null&&$start!==null ? $end-$start : null;
        $issues=array_values(array_unique($issues));
        $status=$p['race_status']!=='active'?strtoupper($p['race_status']):($issues?'Perlu diperiksa':'Selesai');
        $result[]=['bib'=>$p['bib'],'name'=>$p['name'],'team'=>$p['team'],'category_id'=>(int)$cat['id'],'category'=>$cat['name'],'gun_ms'=>$gun,'gun_official'=>$cat['official_ms']!==null,'rank'=>null,'status'=>$status,'issues'=>$issues,'times'=>$times,'sources'=>$sources,'records'=>$records,'swim_ms'=>$diff($swim,$gun),'t1_ms'=>$diff($bikeStart,$swim),'cycle_ms'=>$diff($bikeEnd,$bikeStart),'t2_ms'=>$diff($runStart,$bikeEnd),'run_ms'=>$diff($finish,$runStart),'total_ms'=>$diff($finish,$gun)];
    }
    usort($result,fn($a,$b)=>[$a['category_id'],$a['status']==='Selesai'?0:1,$a['total_ms']??PHP_INT_MAX,$a['bib']]<=>[$b['category_id'],$b['status']==='Selesai'?0:1,$b['total_ms']??PHP_INT_MAX,$b['bib']]);
    $counts=[]; $last=[];
    foreach($result as &$r) if($r['status']==='Selesai') { $c=$r['category_id']; $counts[$c]=($counts[$c]??0)+1; $r['rank']=isset($last[$c])&&$last[$c]['time']===$r['total_ms']?$last[$c]['rank']:$counts[$c]; $last[$c]=['time'=>$r['total_ms'],'rank'=>$r['rank']]; }
    return $result;
}
function duration_text(?int $ms): string { if($ms===null) return '—'; $sign=$ms<0?'-':''; $s=intdiv(abs($ms),1000); return $sign.sprintf('%02d:%02d:%02d',intdiv($s,3600),intdiv($s%3600,60),$s%60); }
