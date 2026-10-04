<?php
// Salin menjadi local.php di File Manager cPanel. Jangan letakkan folder ini di public_html.
return [
    'dsn' => 'mysql:host=localhost;dbname=GANTI_DATABASE;charset=utf8mb4',
    'user' => 'GANTI_USER',
    'password' => 'GANTI_PASSWORD',
    // Buat kalimat acak panjang. Hanya dipakai saat pemasangan admin pertama.
    'install_key' => 'GANTI_DENGAN_KODE_RAHASIA_MINIMAL_24_KARAKTER',
    'allow_http_local' => false,
    // Opsional jika result_logs ada di database lain yang dapat diakses hosting ini.
    // 'legacy' => ['dsn'=>'mysql:host=localhost;dbname=DATABASE_MANUAL;charset=utf8mb4', 'user'=>'USER_BACA', 'password'=>'PASSWORD'],
];
