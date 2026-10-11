<?php
declare(strict_types=1);
$message=''; $done=false;
try {
    require dirname(__DIR__).'/app/bootstrap.php'; require_https(); session_start_safe();
    try { $exists=one('SELECT id FROM users LIMIT 1'); } catch(PDOException $e) { $exists=null; }
    if($exists) { http_response_code(403); exit('Pemasangan sudah selesai. Buka index.php untuk masuk.'); }
    if($_SERVER['REQUEST_METHOD']==='POST') {
        require_csrf(); $key=(string)config()['install_key'];
        if(strlen($key)<24 || str_starts_with($key,'GANTI') || !hash_equals($key,(string)($_POST['key']??''))) throw new RuntimeException('Kode pemasangan tidak cocok. Isi kode acak di config/local.php terlebih dahulu.');
        $user=trim((string)($_POST['username']??'')); $pass=(string)($_POST['password']??'');
        if(!preg_match('/^[A-Za-z0-9_.-]{3,100}$/D',$user)||strlen($pass)<12) throw new RuntimeException('Nama pengguna minimal 3 karakter dan password minimal 12 karakter.');
        install_schema(db()); query('INSERT INTO users(username,password_hash) VALUES(?,?)',[$user,password_hash($pass,PASSWORD_DEFAULT)]); $done=true;
    }
} catch(Throwable $e) { $message=$e instanceof RuntimeException?$e->getMessage():'Pemasangan gagal. Periksa konfigurasi database dan log PHP.'; }
?><!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="assets/app.css"><title>Pasang IDLAPS</title><main class="auth"><div class="brand">IDLAPS <span>TRIATHLON</span></div><h1>Siapkan pusat lomba</h1><p>Database MySQL/MariaDB harus sudah dibuat melalui cPanel. Konfigurasi diisi melalui File Manager.</p><?php if($message):?><p class="alert"><?=htmlspecialchars($message)?></p><?php endif;?><?php if($done):?><p>Admin berhasil dibuat.</p><a class="button" href="index.php">Masuk</a><?php elseif(function_exists('csrf')):?><form method="post"><input type="hidden" name="csrf" value="<?=csrf()?>"><label>Kode pemasangan<input name="key" type="password" required></label><label>Nama pengguna<input name="username" required></label><label>Password admin<input name="password" type="password" minlength="12" required></label><button>Pasang aplikasi</button></form><?php endif;?></main></html>
