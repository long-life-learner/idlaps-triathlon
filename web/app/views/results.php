<?php
$participantMap=array_column(rows('SELECT id,bib,race_status FROM participants WHERE event_id=?',[$eventId]),null,'bib');
function result_status_form(array $p): void {
    form_start('participant_status'); hidden('id',$p['id']);
    select_field('Status lomba','race_status',['active'=>'Aktif · hitung dari catatan','dns'=>'DNS · tidak start','dnf'=>'DNF · tidak selesai','dsq'=>'DSQ · diskualifikasi'],$p['race_status']);
    field('Alasan (wajib untuk diskualifikasi)','reason','','text',false);
    echo '<button>Simpan status</button></form>';
}
?>
<section class="card"><div class="row"><?php form_start('calculate');?><button>Hitung Hasil</button></form><?php if($run):?><small>Dihitung <?=h(local_time((int)$run['created_ms'],$event['timezone']))?></small><?php endif;?></div>
<p class="muted">Manual menjadi prioritas. Kategori dikenali dari BIB. Hasil resmi ditetapkan per kategori setelah pemeriksaan.</p>
<form method="get" class="row"><?php hidden('page','results');select_field('Kategori','category',[0=>'Semua kategori']+array_column($cats,'name','id'),$categoryFilter);?><button class="secondary">Tampilkan</button></form>
<?php if($run&&!$stale):?><div class="actions"><a class="button secondary" href="?page=excel&category=<?=$categoryFilter?>">Ekspor Excel</a><a class="button secondary" href="?page=pdf&category=<?=$categoryFilter?>">Ekspor PDF</a></div><?php endif;?></section>
<?php if($stale):?><div class="alert">Ada perubahan pada kategori yang ditampilkan. Tekan Hitung Hasil. Kategori lain yang masih valid tetap dapat diekspor dengan memilih kategori tersebut.</div><?php endif;?>
<?php $unresolved=array_filter($filtered,fn($r)=>$r['status']==='Perlu diperiksa'); if($unresolved):?>
<section class="card"><h2><?=count($unresolved)?> peserta perlu diperiksa</h2><p>Periksa catatan yang kurang atau ubah status jika peserta memang tidak start, tidak selesai, atau didiskualifikasi.</p>
<?php foreach($unresolved as $r):?><div class="alert"><strong><?=h($r['bib'].' · '.$r['name'])?></strong><p><?=h(implode('; ',$r['issues']))?></p><div class="actions"><a href="?page=observations&bib=<?=urlencode($r['bib'])?>">Periksa catatan</a><a href="#status-<?=$participantMap[$r['bib']]['id']?>" onclick="document.getElementById(this.hash.slice(1)).open=true">Atur status peserta</a></div></div><?php endforeach;?></section><?php endif;?>
<section class="card"><div class="table-wrap"><table><tr><th>#</th><th>Peserta</th><th>Swim</th><th>T1</th><th>Cycle</th><th>T2</th><th>Run</th><th>Total</th><th>Status</th></tr>
<?php foreach($filtered as $r):?><tr><td><?=h($r['rank']??'—')?></td><td><strong><?=h($r['bib'].' · '.$r['name'])?></strong><br><small><?=h($r['category'])?></small></td><?php foreach(['swim_ms','t1_ms','cycle_ms','t2_ms','run_ms','total_ms'] as $key):?><td><?=h(duration_text($r[$key]))?></td><?php endforeach;?><td><span class="badge <?=$r['status']==='Perlu diperiksa'?'warn':''?>"><?=h($r['status'])?></span></td></tr>
<tr><td></td><td colspan="8" class="wrap"><details><summary>Bukti waktu & sumber</summary><p>Gun time <?=h(local_time($r['gun_ms'],$event['timezone']))?> (<?=$r['gun_official']?'resmi':'sementara'?>)</p><?php foreach($r['times'] as $key=>$ms):?><div><?=h(step_label($key))?> · <?=h(local_time($ms,$event['timezone']))?> · <?=h($r['sources'][$key])?></div><?php endforeach;?><a href="?page=observations&bib=<?=urlencode($r['bib'])?>">Periksa / koreksi catatan</a></details>
<details id="status-<?=$participantMap[$r['bib']]['id']?>"><summary>Atur status · <?=h($r['bib'])?></summary><?php result_status_form($participantMap[$r['bib']]);?></details></td></tr><?php endforeach;?></table></div><?php if(!$filtered):?><div class="empty">Tambahkan peserta dan tekan Hitung Hasil.</div><?php endif;?></section>
<?php foreach($selectedStates as $id=>$state): $categoryRows=array_filter($results,fn($r)=>$r['category_id']===$id); $needsReview=array_filter($categoryRows,fn($r)=>$r['status']==='Perlu diperiksa'); ?>
<section class="card"><h2><?=h($state['name'])?></h2><span class="badge <?=$state['fresh']?'':'warn'?>"><?=$state['official']?'Hasil resmi':($state['fresh']?'Hasil sementara':'Perlu dihitung ulang')?></span>
<?php if($state['official']):?><p>Hasil resmi kategori ini tetap berlaku selama tidak ada perubahan pada kategori ini.</p>
<?php else:?>
<?php if(!$state['gun_official']):?><p><a href="?page=categories">Isi gun time resmi kategori ini</a>.</p><?php endif;?>
<?php if($needsReview):?><p><?=count($needsReview)?> peserta belum terselesaikan. Gunakan Periksa catatan atau Atur status di atas.</p><?php endif;?>
<?php if($state['fresh'] && $state['gun_official'] && $categoryRows && !$needsReview): form_start('official'); hidden('category_id',$id); ?>
<label><input type="checkbox" name="manual_ready" required> Saya sudah memastikan seluruh catatan manual untuk kategori ini selesai dikirim, termasuk antrean dari penugasan sebelumnya.</label>
<label><input type="checkbox" name="accept_rfid" required> Saya sudah memeriksa hasil dan menyetujui penggunaan RFID jika catatan manual tidak tersedia.</label>
<button>Tetapkan resmi · <?=h($state['name'])?></button></form>
<?php else:?><p class="muted">Penetapan resmi tersedia setelah hasil dihitung, gun time resmi diisi, dan pemeriksaan peserta selesai.</p><?php endif;?>
<?php endif;?></section><?php endforeach;?>
