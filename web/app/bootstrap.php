<?php
declare(strict_types=1);
define('APP_ROOT', dirname(__DIR__));
require_once APP_ROOT.'/vendor/autoload.php';
require_once __DIR__.'/schema.php';
require_once __DIR__.'/results.php';
require_once __DIR__.'/service.php';
require_once __DIR__.'/exports.php';
require_once __DIR__.'/legacy.php';
date_default_timezone_set('UTC');
function now_ms(): int { return (int)floor(microtime(true)*1000); }
function config(): array {
    static $config;
    if ($config === null) {
        $file = getenv('IDLAPS_CONFIG') ?: APP_ROOT.'/config/local.php';
        if (!is_file($file)) throw new RuntimeException('Konfigurasi belum tersedia. Salin config/example.php menjadi config/local.php dan isi akses database melalui File Manager.');
        $config = require $file;
    }
    return $config;
}
function db(): PDO {
    static $db;
    return $db ??= new PDO(config()['dsn'], config()['user'] ?? '', config()['password'] ?? '', [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC, PDO::ATTR_EMULATE_PREPARES=>false]);
}
function query(string $sql, array $params=[]): PDOStatement { $s=db()->prepare($sql); $s->execute($params); return $s; }
function rows(string $sql, array $params=[]): array { return query($sql,$params)->fetchAll(); }
function one(string $sql, array $params=[]): ?array { return query($sql,$params)->fetch() ?: null; }
function h(mixed $s): string { return htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
function json_out(array $data, int $code=200): never { http_response_code($code); header('Content-Type: application/json; charset=utf-8'); header('Cache-Control: no-store'); echo json_encode($data,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR); exit; }
function session_start_safe(): void { if(session_status()!==PHP_SESSION_ACTIVE) { session_name('idlaps_admin'); session_set_cookie_params(['httponly'=>true,'samesite'=>'Strict','secure'=>(!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS']!=='off')]); session_start(); } }
function csrf(): string { return $_SESSION['csrf'] ??= bin2hex(random_bytes(24)); }
function require_csrf(): void { if(!hash_equals(csrf(),(string)($_POST['csrf']??''))) throw new RuntimeException('Sesi formulir kedaluwarsa. Muat ulang halaman.'); }
function require_admin(): void { session_start_safe(); if(empty($_SESSION['admin'])) { header('Location: index.php?page=login'); exit; } }
function audit(int $event, string $action, array $detail): void { query('INSERT INTO audit(event_id,actor,action,detail_json,created_ms) VALUES(?,?,?,?,?)',[$event,$_SESSION['admin']??'device',$action,json_encode($detail,JSON_THROW_ON_ERROR),now_ms()]); }
function revise(int $event): void { query('UPDATE events SET revision=revision+1 WHERE id=?',[$event]); }
function lock_event(int $event): array { return one('SELECT * FROM events WHERE id=?'.(db()->getAttribute(PDO::ATTR_DRIVER_NAME)==='mysql'?' FOR UPDATE':''),[$event]) ?? throw new RuntimeException('Event tidak ditemukan.'); }
function local_time(?int $ms, string $tz, string $format='d M Y H:i:s'): string { if($ms===null) return '—'; return (new DateTimeImmutable('@'.intdiv($ms,1000)))->setTimezone(new DateTimeZone($tz))->format($format); }
function parse_local(string $value,string $tz): int { $d=DateTimeImmutable::createFromFormat('!Y-m-d\TH:i:s',$value,new DateTimeZone($tz)); if(!$d) $d=DateTimeImmutable::createFromFormat('!Y-m-d\TH:i',$value,new DateTimeZone($tz)); $errors=DateTimeImmutable::getLastErrors(); if(!$d || ($errors && ($errors['warning_count']||$errors['error_count']))) throw new RuntimeException('Tanggal/jam tidak valid.'); return $d->getTimestamp()*1000; }
