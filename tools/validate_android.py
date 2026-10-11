"""Structural AIA checks and regression execution of the Screen1 queue handler.

This is not an Android emulator or a replacement for a Kodular APK build.
"""
import argparse
import json
import sqlite3
import xml.etree.ElementTree as E
import zipfile

NS = {'b': 'https://developers.google.com/blockly/xml'}


def field(block, name):
    item = block.find(f"b:field[@name='{name}']", NS)
    return '' if item is None else (item.text or '')


def value(block, name):
    return block.find(f"b:value[@name='{name}']/b:block", NS)


def regression(screen):
    event = next(b for b in screen if b.find('b:mutation', NS) is not None and
                 b.find('b:mutation', NS).get('event_name') == 'AfterQuery')
    # Execute the actual generated event with both flat and nested result shapes.
    def execute(block, state):
        if block is None:
            return None
        kind = block.get('type')
        v = lambda key: execute(value(block, key), state)
        if kind == 'text': return field(block, 'TEXT')
        if kind == 'math_number': return float(field(block, 'NUM'))
        if kind == 'logic_boolean': return field(block, 'BOOL') == 'TRUE'
        if kind == 'lexical_variable_get': return state[field(block, 'VAR')]
        if kind in ('math_compare','logic_compare'):
            a, b = v('A'), v('B')
            return {'GT': lambda: a > b, 'NEQ': lambda: a != b}[field(block, 'OP')]()
        if kind == 'text_join':
            return ''.join(str(execute(x.find('b:block', NS), state)) for x in block.findall('b:value', NS))
        if kind == 'component_method':
            assert block.find('b:mutation', NS).get('method_name') == 'GetValue'
            return state.get('tags', {}).get(v('ARG0'), v('ARG1'))
        if kind == 'lexical_variable_set': state[field(block, 'VAR')] = v('VALUE')
        elif kind == 'component_set_get': state[field(block, 'COMPONENT_SELECTOR')+'.'+field(block, 'PROP')] = v('VALUE')
        elif kind == 'controls_if':
            branch = 'DO0' if v('IF0') else 'ELSE'
            execute(block.find(f"b:statement[@name='{branch}']/b:block", NS), state)
        else: raise AssertionError('Unexpected operation in queue handler: '+kind)
        execute(block.find('b:next/b:block', NS), state)

    cases = [([], 0), (['0'], 0), ([['0']], 0), (['manual-1-1'], 1), ([['manual-1-1']], 1)]
    for result, count in cases:
        state = {'result': result, 'numberOfRecords': count, 'tags': {'token': 'test'}}
        execute(event.find("b:statement[@name='DO']/b:block", NS), state)
        assert state['global pending'] == count
        assert state['Pair.Enabled'] and state['Continue.Enabled']
    print('PASS Screen1 queue handler: empty, flat, nested and pending results')
    sql = next(field(b, 'TEXT') for b in screen.findall('.//b:block', NS)
               if b.get('type') == 'text' and field(b, 'TEXT').startswith('SELECT record_id FROM'))
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE readings_v3(record_id TEXT,sent INTEGER,cancelled INTEGER,cancel_sent INTEGER)')
    assert len(db.execute(sql).fetchall()) == 0
    db.executemany('INSERT INTO readings_v3 VALUES(?,?,?,?)', [('a', 0, 0, 0), ('b', 1, 1, 0), ('c', 1, 0, 0)])
    assert len(db.execute(sql).fetchall()) == 2
    print('PASS Pending query counts unsent reads and unsent cancellations')


def validate(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        screens = {}
        for name in archive.namelist():
            if not name.endswith('.scm'): continue
            design = json.loads(archive.read(name).decode().split('$JSON\n', 1)[1].rsplit('\n|#', 1)[0])
            components = {}
            def walk(c):
                assert c['$Name'] not in components
                components[c['$Name']] = c['$Type']
                for child in c.get('$Components', []): walk(child)
            walk(design['Properties'])
            root = E.fromstring(archive.read(name[:-4]+'.bky'))
            blocks = root.findall('.//b:block', NS)
            ids = [b.get('id') for b in blocks]
            assert len(ids) == len(set(ids)), 'Duplicate block IDs'
            procedures = {field(b, 'NAME') for b in blocks if b.get('type') == 'procedures_defnoreturn'}
            for b in blocks:
                if b.get('type') == 'procedures_callnoreturn': assert field(b, 'PROCNAME') in procedures
                if b.get('type', '').startswith('component_'):
                    m = b.find('b:mutation', NS)
                    assert components[m.get('instance_name')] == m.get('component_type')
                    assert field(b, 'COMPONENT_SELECTOR') == m.get('instance_name')
                names = [v.get('name') for v in b.findall('b:value', NS)]
                assert len(names) == len(set(names)), 'Duplicate input names'
                for v in b.findall('b:value', NS): assert len(v) == 1, 'Disconnected value'
            screen_name = design['Properties']['$Name']
            screens[screen_name] = root
            print(f'PASS {screen_name}: {len(components)} components, {len(blocks)} blocks, valid references')
        assert set(screens) == {'Screen1', 'Screen2', 'Screen3'}
        regression(screens['Screen1'])
        props = archive.read('youngandroidproject/project.properties').decode()
        assert 'packagename=com.idlaps.triathlontap' in props
        assert 'versionname=2.2' in props
        assert not any('ScreenIdentitas' in name for name in archive.namelist())
        print('PASS Project manifest v2.2; original app uses a separate package')
    print('AIA validation passed. APK/device validation is still required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('path'); args = parser.parse_args()
    validate(args.path)
