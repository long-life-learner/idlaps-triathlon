"""SQLite statements shared by generated Kodular blocks and regression tests."""
V2 = 'CREATE TABLE IF NOT EXISTS readings_v2(record_id TEXT PRIMARY KEY,bib TEXT,stage TEXT,lap INTEGER,captured_ms INTEGER,payload TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,cancelled INTEGER NOT NULL DEFAULT 0,cancel_sent INTEGER NOT NULL DEFAULT 0)'
V3 = "CREATE TABLE IF NOT EXISTS readings_v3(record_id TEXT PRIMARY KEY,bib TEXT,stage TEXT,lap INTEGER,captured_ms INTEGER,payload TEXT NOT NULL,assignment TEXT NOT NULL,sent INTEGER NOT NULL DEFAULT 0,cancelled INTEGER NOT NULL DEFAULT 0,cancel_sent INTEGER NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '',attempt TEXT NOT NULL DEFAULT '',replaces TEXT NOT NULL DEFAULT '')"
AUDIT = 'CREATE TABLE IF NOT EXISTS local_changes(old_id TEXT,new_id TEXT,action TEXT,created_ms INTEGER)'
PENDING = '(cancelled=0 AND sent=0) OR (cancelled=1 AND cancel_sent=0)'
QUEUE = f'SELECT record_id FROM readings_v3 WHERE {PENDING}'
ELIGIBLE = f"(({PENDING}) AND attempt<>? AND (replaces='' OR EXISTS(SELECT 1 FROM readings_v3 old WHERE old.record_id=readings_v3.replaces AND old.cancel_sent=1)))"
NEXT = f'SELECT record_id,payload,assignment,cancelled FROM readings_v3 WHERE {ELIGIBLE} AND assignment=(SELECT assignment FROM readings_v3 WHERE {ELIGIBLE} ORDER BY rowid LIMIT 1) AND cancelled=(SELECT cancelled FROM readings_v3 WHERE {ELIGIBLE} ORDER BY rowid LIMIT 1) ORDER BY rowid LIMIT 100'
REVIEW = "SELECT record_id,bib,stage,lap,captured_ms,payload,assignment,sent,cancelled,error FROM readings_v3 ORDER BY CASE WHEN cancelled=0 AND sent=0 THEN 0 ELSE 1 END,rowid DESC LIMIT 300"
HISTORY = 'SELECT bib,stage,lap,captured_ms,sent,cancelled,error FROM readings_v3 WHERE assignment=? ORDER BY rowid DESC LIMIT 12'


def migration(assignment):
    assert assignment.startswith('p') and assignment[1:].isdigit()
    return f"INSERT OR IGNORE INTO readings_v3(record_id,bib,stage,lap,captured_ms,payload,assignment,sent,cancelled,cancel_sent) SELECT record_id,bib,stage,lap,captured_ms,payload,'{assignment}',sent,cancelled,cancel_sent FROM readings_v2"
