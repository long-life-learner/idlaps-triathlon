<?php
declare(strict_types=1);

function install_schema(PDO $db): void {
    $id = $db->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite' ? 'INTEGER PRIMARY KEY AUTOINCREMENT' : 'BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY';
    $tables = [
        "users (id $id, username VARCHAR(100) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL)",
        "login_attempts (attempt_key VARCHAR(64) PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, last_ms BIGINT NOT NULL)",
        "events (id $id, name VARCHAR(150) NOT NULL, timezone VARCHAR(80) NOT NULL, revision INTEGER NOT NULL DEFAULT 1, created_ms BIGINT NOT NULL)",
        "categories (id $id, event_id BIGINT NOT NULL, name VARCHAR(100) NOT NULL, scheduled_ms BIGINT NOT NULL, official_ms BIGINT NULL, bike_laps INTEGER NOT NULL DEFAULT 1, run_laps INTEGER NOT NULL DEFAULT 1, bike_min_s INTEGER NOT NULL DEFAULT 60, run_min_s INTEGER NOT NULL DEFAULT 30, UNIQUE(event_id,name))",
        "participants (id $id, event_id BIGINT NOT NULL, category_id BIGINT NOT NULL, bib VARCHAR(30) NOT NULL, name VARCHAR(150) NOT NULL, team VARCHAR(150) NOT NULL DEFAULT '', epc VARCHAR(128) NULL, race_status VARCHAR(20) NOT NULL DEFAULT 'active', UNIQUE(event_id,bib), UNIQUE(event_id,epc))",
        "devices (id $id, event_id BIGINT NOT NULL, name VARCHAR(100) NOT NULL, kind VARCHAR(20) NOT NULL, checkpoint INTEGER NOT NULL, token_hash VARCHAR(64) NOT NULL UNIQUE, pairing_hash VARCHAR(64) NULL, pairing_expires_ms BIGINT NULL, pairing_consumed INTEGER NOT NULL DEFAULT 0, revoked INTEGER NOT NULL DEFAULT 0, last_seen_ms BIGINT NULL, pending_count INTEGER NULL, clock_quality VARCHAR(40) NULL, manual_complete INTEGER NOT NULL DEFAULT 0, config_version INTEGER NOT NULL DEFAULT 1)",
        "readers (id $id, device_id BIGINT NOT NULL, name VARCHAR(100) NOT NULL, host VARCHAR(253) NOT NULL, port INTEGER NOT NULL DEFAULT 2022, checkpoint INTEGER NOT NULL, detect_mode VARCHAR(10) NOT NULL DEFAULT 'multi', interval_ms INTEGER NOT NULL DEFAULT 10000, quiet_ms INTEGER NOT NULL DEFAULT 2000, power INTEGER NOT NULL DEFAULT 20, inventory_ms INTEGER NOT NULL DEFAULT 50, enabled INTEGER NOT NULL DEFAULT 1)",
        "observations (id $id, record_id VARCHAR(150) NOT NULL UNIQUE, event_id BIGINT NOT NULL, device_id BIGINT NOT NULL, source VARCHAR(15) NOT NULL, bib VARCHAR(30) NULL, epc VARCHAR(128) NULL, reader_id BIGINT NULL, checkpoint INTEGER NOT NULL, stage VARCHAR(30) NULL, lap INTEGER NULL, captured_ms BIGINT NOT NULL, received_ms BIGINT NOT NULL, clock_quality VARCHAR(40) NOT NULL, uncertainty_ms INTEGER NULL, test INTEGER NOT NULL DEFAULT 0, cancelled INTEGER NOT NULL DEFAULT 0, config_version INTEGER NOT NULL, payload_hash VARCHAR(64) NOT NULL, payload_json LONGTEXT NOT NULL)",
        "decisions (id $id, event_id BIGINT NOT NULL, bib VARCHAR(30) NOT NULL, step_key VARCHAR(60) NOT NULL, captured_ms BIGINT NOT NULL, reason TEXT NOT NULL, UNIQUE(event_id,bib,step_key))",
        "cancel_requests (id $id, event_id BIGINT NOT NULL, device_id BIGINT NOT NULL, record_id VARCHAR(150) NOT NULL, created_ms BIGINT NOT NULL, UNIQUE(device_id,record_id))",
        "result_runs (id $id, event_id BIGINT NOT NULL, revision INTEGER NOT NULL, created_ms BIGINT NOT NULL, official INTEGER NOT NULL DEFAULT 0, result_json LONGTEXT NOT NULL)",
        "audit (id $id, event_id BIGINT NULL, actor VARCHAR(100) NOT NULL, action VARCHAR(100) NOT NULL, detail_json LONGTEXT NOT NULL, created_ms BIGINT NOT NULL)",
    ];
    foreach ($tables as $table) $db->exec('CREATE TABLE IF NOT EXISTS '.$table);
    upgrade_tag_schema($db);
    foreach (['obs_event_time' => 'observations(event_id,captured_ms)', 'obs_epc_time'=>'observations(event_id,epc,captured_ms)', 'obs_bib'=>'observations(event_id,bib)', 'obs_device' => 'observations(device_id)', 'participants_category' => 'participants(category_id)', 'audit_event' => 'audit(event_id)'] as $name => $on) {
        try { $db->exec("CREATE INDEX $name ON $on"); } catch (PDOException $e) { if (!str_contains(strtolower($e->getMessage()), 'exist') && !str_contains(strtolower($e->getMessage()), 'duplicate')) throw $e; }
    }
}
