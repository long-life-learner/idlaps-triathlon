<?php
declare(strict_types=1);
use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Cell\DataType;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;
use PhpOffice\PhpSpreadsheet\Reader\Xlsx as XlsxReader;
use Dompdf\Dompdf;
use Dompdf\Options;

function excel_template(): Spreadsheet {
    $book=new Spreadsheet(); $s=$book->getActiveSheet(); $s->setTitle('Peserta');
    foreach(['BIB','Nama','Kategori','EPC','Tim'] as $i=>$v) $s->setCellValue([$i+1,1],$v);
    $s->getStyle('A2:E1001')->getNumberFormat()->setFormatCode('@');
    $s->freezePane('A2'); foreach(range('A','E') as $col) $s->getColumnDimension($col)->setWidth($col==='D'?32:24);
    $s->getStyle('A1:E1')->getFont()->setBold(true); return $book;
}
function preview_import(string $path,int $event): array {
    if(filesize($path)>5000000) throw new RuntimeException('File maksimal 5 MB.');
    $zip=new ZipArchive(); if($zip->open($path)!==true) throw new RuntimeException('Gunakan file .xlsx.');
    $expanded=0; for($i=0;$i<$zip->numFiles;$i++) $expanded+=(int)$zip->statIndex($i)['size']; $zip->close();
    if($expanded>30000000) throw new RuntimeException('Isi workbook terlalu besar.');
    $reader=new XlsxReader(); $reader->setReadDataOnly(false); $book=$reader->load($path); $sheet=$book->getSheet(0);
    if($sheet->getHighestDataRow()>5001) throw new RuntimeException('Maksimal 5.000 peserta per file.');
    $header=[]; foreach(range('A','E') as $col) $header[]=strtolower(trim((string)$sheet->getCell($col.'1')->getValue()));
    if($header!==['bib','nama','kategori','epc','tim']) throw new RuntimeException('Kolom harus BIB, Nama, Kategori, EPC, Tim. Gunakan template.');
    $categories=[]; foreach(rows('SELECT id,name FROM categories WHERE event_id=?',[$event]) as $c) $categories[mb_strtolower($c['name'])]=(int)$c['id'];
    $bibs=[]; $epcs=[];
    foreach(rows('SELECT bib,epc FROM participants WHERE event_id=?',[$event]) as $p) { $bibs[$p['bib']]=true; if($p['epc']) $epcs[$p['epc']]=true; }
    $out=[]; $errors=[];
    for($r=2;$r<=$sheet->getHighestDataRow();$r++) {
        $v=[]; $formula=false;
        foreach(range('A','E') as $col) { $cell=$sheet->getCell($col.$r); if($cell->getDataType()===DataType::TYPE_FORMULA) $formula=true; $v[]=trim((string)$cell->getFormattedValue()); }
        if(implode('',$v)==='') continue;
        [$bib,$name,$category,$epc,$team]=$v; $epc=strtoupper(str_replace(' ','',$epc)); $reason=[];
        if($formula) $reason[]='Formula tidak diperbolehkan; tempel sebagai nilai.';
        if(!preg_match('/^[A-Za-z0-9-]{1,30}$/D',$bib)) $reason[]='BIB wajib, maksimal 30 karakter huruf/angka/tanda hubung.';
        if($name===''||mb_strlen($name)>150||mb_strlen($team)>150) $reason[]='Nama wajib dan panjang nama/tim maksimal 150 karakter.';
        $catId=$categories[mb_strtolower($category)]??null; if(!$catId) $reason[]='Kategori belum terdaftar.';
        if(isset($bibs[$bib])) $reason[]='BIB sudah ada atau berulang dalam file.';
        if($epc!=='' && !preg_match('/^(?:[A-F0-9]{2}){1,64}$/D',$epc)) $reason[]='EPC harus hexadecimal dengan jumlah digit genap.';
        if($epc!=='' && isset($epcs[$epc])) $reason[]='EPC sudah dipakai.';
        $bibs[$bib]=true; if($epc!=='') $epcs[$epc]=true;
        if($reason) $errors[]=['row'=>$r,'message'=>implode(' ',$reason)];
        $out[]=['bib'=>$bib,'name'=>$name,'category_id'=>$catId,'category'=>$category,'epc'=>$epc?:null,'team'=>$team];
    }
    if(!$out) $errors[]=['row'=>0,'message'=>'File belum berisi peserta.'];
    return ['event_id'=>$event,'rows'=>$out,'errors'=>$errors];
}
function result_book(array $event,array $run,array $results): Spreadsheet {
    $book=new Spreadsheet(); $book->removeSheetByIndex(0); $groups=[];
    foreach($results as $r) $groups[$r['category_id']][]=$r;
    if(!$groups) $groups[0]=[];
    foreach($groups as $id=>$group) {
        $s=$book->createSheet(); $s->setTitle('Kategori '.$id);
        $s->setCellValueExplicit('A1',$event['name'].' — '.($group[0]['category']??'Belum ada peserta'),DataType::TYPE_STRING); $s->mergeCells('A1:K1');
        $s->setCellValue('A2',((int)$run['official']?'RESMI':'SEMENTARA').' · Dihitung '.local_time((int)$run['created_ms'],$event['timezone']).' '.$event['timezone']); $s->mergeCells('A2:K2');
        $s->setCellValue('A3','Gun time: '.(isset($group[0])?local_time($group[0]['gun_ms'],$event['timezone']):'—')); $s->mergeCells('A3:K3');
        $headers=['Peringkat','BIB','Nama','Tim','Swim','T1','Cycle','T2','Run','Total','Status','Sumber per tahap','Catatan'];
        foreach($headers as $i=>$label) $s->setCellValue([$i+1,5],$label);
        foreach($group as $i=>$r) {
            $n=$i+6; $s->setCellValue([1,$n],$r['rank']);
            foreach([2=>$r['bib'],3=>$r['name'],4=>$r['team'],11=>$r['status'],12=>implode('; ',array_map(fn($key)=>step_label($key).': '.$r['sources'][$key],array_keys($r['sources']))),13=>implode('; ',$r['issues'])] as $col=>$v) $s->setCellValueExplicit([$col,$n],$v,DataType::TYPE_STRING);
            foreach(['swim_ms','t1_ms','cycle_ms','t2_ms','run_ms','total_ms'] as $j=>$key) {
                $v=$r[$key]; if($v!==null && $v>=0) { $s->setCellValue([$j+5,$n],$v/86400000); $s->getStyle([$j+5,$n])->getNumberFormat()->setFormatCode('[h]:mm:ss'); }
                elseif($v!==null) $s->setCellValueExplicit([$j+5,$n],duration_text($v),DataType::TYPE_STRING);
            }
        }
        $s->freezePane('E6'); $s->setAutoFilter('A5:M'.max(6,count($group)+5));
        $s->getStyle('A5:M5')->getFont()->setBold(true)->getColor()->setARGB('FFFFFFFF'); $s->getStyle('A5:M5')->getFill()->setFillType('solid')->getStartColor()->setARGB('FF153B46');
        foreach(range('A','M') as $col) $s->getColumnDimension($col)->setWidth(in_array($col,['C','D','K'])?25:(in_array($col,['L','M'])?55:14));
    }
    return $book;
}
function result_pdf(array $event,array $run,array $results): string {
    $html='<html><head><meta charset="utf-8"><style>@page{margin:28px}body{font-family:DejaVu Sans,sans-serif;font-size:9px;color:#17313b}h1{font-size:20px}h2{font-size:14px;margin-top:24px}table{width:100%;border-collapse:collapse}th{background:#17313b;color:white;text-align:left}th,td{padding:6px;border-bottom:1px solid #dde5e7}thead{display:table-header-group}tr{page-break-inside:avoid}.note{font-size:8px;color:#53636b}</style></head><body><h1>'.h($event['name']).'</h1><p>'.((int)$run['official']?'HASIL RESMI':'HASIL SEMENTARA').' · '.h(local_time((int)$run['created_ms'],$event['timezone'])).' '.h($event['timezone']).'</p><p class="note">M = manual, R = RFID, A = koreksi admin. Sumber berurutan mengikuti tahap/putaran rute. Peringkat memakai durasi penuh; tampilan sampai detik.</p>';
    $groups=[]; foreach($results as $r) $groups[$r['category_id']][]=$r;
    foreach($groups as $group) {
        $first=$group[0]; $html.='<h2>'.h($first['category']).'</h2><p>Gun time '.h(local_time($first['gun_ms'],$event['timezone'])).' · '.($first['gun_official']?'resmi':'jadwal sementara').'</p><table><thead><tr>';
        foreach(['#','BIB / Nama','Swim','T1','Cycle','T2','Run','Total','Status / sumber'] as $v) $html.='<th>'.h($v).'</th>';
        $html.='</tr></thead><tbody>';
        foreach($group as $r) {
            $html.='<tr><td>'.h($r['rank']??'—').'</td><td>'.h($r['bib']).' · '.h($r['name']).'<br><span class="note">'.h($r['team']).'</span></td>';
            foreach(['swim_ms','t1_ms','cycle_ms','t2_ms','run_ms','total_ms'] as $k) $html.='<td>'.h(duration_text($r[$k])).'</td>';
            $src=array_map(fn($s)=>['manual'=>'M','rfid'=>'R','admin'=>'A'][$s],array_values($r['sources']));
            $html.='<td>'.h($r['status']).'<br>'.h(implode('/',$src)).'</td></tr>';
            if($r['issues']) $html.='<tr><td></td><td colspan="8" class="note">'.h(implode('; ',$r['issues'])).'</td></tr>';
        }
        $html.='</tbody></table>';
    }
    $options=new Options(); $options->set('isRemoteEnabled',false); $options->set('isPhpEnabled',false);
    $pdf=new Dompdf($options); $pdf->loadHtml($html.'</body></html>'); $pdf->setPaper('A4','landscape'); $pdf->render(); return $pdf->output();
}
