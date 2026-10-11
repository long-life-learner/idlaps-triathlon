"""Build the editable Kodular 2.2 project; does not compile an APK."""
import argparse
import json
from pathlib import Path
import zipfile
from android_v22 import pages


def build(source, destination):
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as out:
        for name in original.namelist():
            if name.startswith('assets/'):
                out.writestr(name, original.read(name))
        base='src/io/kodular/ktcxpgt/IDLapsTap/'
        for name,(design,blocks) in pages().items():
            out.writestr(base+name+'.scm', '#|\n$JSON\n'+json.dumps(design,separators=(',',':'))+'\n|#')
            out.writestr(base+name+'.bky', blocks)
        props=original.read('youngandroidproject/project.properties').decode()
        updates={'screenNames':'Screen1, Screen2, Screen3','packagename':'com.idlaps.triathlontap','aname':'IDLAPS Triathlon Tap','versioncode':'4','versionname':'2.2','minSdk':'23'}
        lines=[]
        for line in props.splitlines():
            key=line.partition('=')[0]
            lines.append(key+'='+updates.pop(key) if key in updates else line)
        lines += [k+'='+v for k,v in updates.items()]
        out.writestr('youngandroidproject/project.properties', '\n'.join(lines)+'\n')
    print(destination)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args()
    Path(a.destination).parent.mkdir(parents=True,exist_ok=True);build(a.source,a.destination)
