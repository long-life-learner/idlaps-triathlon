"""Generate an editable Kodular .aia from the supplied project, preserving its assets.

No APK is produced by this script. Import the resulting .aia into Kodular for device QA.
"""
import argparse
import json
from pathlib import Path
import uuid
import zipfile
import xml.etree.ElementTree as E

NS = 'https://developers.google.com/blockly/xml'
E.register_namespace('', NS)
def el(tag, attrs=None): return E.Element('{'+NS+'}'+tag, attrs or {})
def block(kind, fields=None, values=None, mutation=None):
    b=el('block', {'type':kind,'id':uuid.uuid4().hex})
    if mutation is not None: b.append(el('mutation',{k:str(v).lower() if isinstance(v,bool) else str(v) for k,v in mutation.items()}))
    for name,value in (fields or {}).items():
        f=el('field',{'name':name});f.text=str(value);b.append(f)
    for name,value in (values or {}).items():
        v=el('value',{'name':name});v.append(value);b.append(v)
    return b
def chain(*blocks):
    blocks=[b for b in blocks if b is not None]
    if not blocks:return None
    root=blocks[0]; last=root
    for b in blocks[1:]:
        n=el('next');n.append(b);last.append(n);last=b
    return root
def stmt(b,name,*blocks):
    s=el('statement',{'name':name});c=chain(*blocks)
    if c is not None:s.append(c)
    b.append(s);return b
def text(s=''):return block('text',{'TEXT':s})
def num(n):return block('math_number',{'NUM':n})
def boolean(v):return block('logic_boolean',{'BOOL':'TRUE' if v else 'FALSE'})
def var(n):return block('lexical_variable_get',{'VAR':n})
def setvar(n,v):return block('lexical_variable_set',{'VAR':n},{'VALUE':v})
def glob(n,v):return block('global_declaration',{'NAME':n},{'VALUE':v})
def seq(*items):return block('lists_create_with',values={f'ADD{i}':v for i,v in enumerate(items)},mutation={'items':len(items)})
def join(*items):return block('text_join',values={f'ADD{i}':v for i,v in enumerate(items)},mutation={'items':len(items)})
def op(kind,a,b):return block({'add':'math_add','sub':'math_subtract','div':'math_division','mul':'math_multiply'}[kind],values={'NUM0' if kind in ('add','mul') else 'A':a,'NUM1' if kind in ('add','mul') else 'B':b},mutation={'items':2} if kind in ('add','mul') else None)
def cmp(a,b,operator='EQ'):return block('math_compare',{'OP':operator},{'A':a,'B':b})
def eq(a,b):return block('logic_compare',{'OP':'EQ'},{'A':a,'B':b})
def both(a,b):return block('logic_operation',{'OP':'AND'},{'A':a,'B':b},mutation={'items':2})
def cond(test,yes,no=None):
    b=block('controls_if',values={'IF0':test},mutation={'else':1} if no is not None else None);stmt(b,'DO0',yes)
    if no is not None:stmt(b,'ELSE',no)
    return b
TYPES={}
def prop(instance,name,value=None):
    return block('component_set_get',{'COMPONENT_SELECTOR':instance,'PROP':name},{'VALUE':value} if value is not None else None,
                 {'component_type':TYPES[instance],'set_or_get':'set' if value is not None else 'get','property_name':name,'is_generic':False,'instance_name':instance})
def call(instance,method,*args):
    return block('component_method',{'COMPONENT_SELECTOR':instance},{f'ARG{i}':v for i,v in enumerate(args)},
                 {'component_type':TYPES[instance],'method_name':method,'is_generic':False,'instance_name':instance})
def event(instance,name,*body):
    return stmt(block('component_event',{'COMPONENT_SELECTOR':instance},mutation={'component_type':TYPES[instance],'is_generic':False,'instance_name':instance,'event_name':name}),'DO',*body)
def proc(name,*body):return stmt(block('procedures_defnoreturn',{'NAME':name}),'STACK',*body)
def run(name):return block('procedures_callnoreturn',{'PROCNAME':name},mutation={'name':name})
def lookup(obj,key,default=None):return block('lists_lookup_in_pairs',values={'KEY':text(key),'LIST':obj,'NOTFOUND':default if default is not None else text()})
def dictionary(pairs):
    vals={}
    for i,(k,v) in enumerate(pairs.items()):vals['ADD'+str(i)]=block('pair',values={'KEY':text(k),'VALUE':v})
    return block('dictionaries_create_with',values=vals,mutation={'items':len(vals)})
def index(obj,n):return block('lists_select_item',values={'LIST':obj,'NUM':num(n)})
def each(name,items,*body):return stmt(block('controls_forEach',{'VAR':name},{'LIST':items}),'DO',*body)
def local(name,value,*body):
    b=block('local_declaration_statement',{'VAR0':name},{'DECL0':value},mutation={})
    b.find('{'+NS+'}mutation').append(el('localname',{'name':name}));return stmt(b,'STACK',*body)
def gettag(name,default=None):return call('TinyDB1','GetValue',text(name),default if default is not None else text())
def storetag(name,value):return call('TinyDB1','StoreValue',text(name),value)
def notice(message):return call('Notifier1','ShowAlert',message)
def now():return call('Clock1','SystemTime')
def length(value):return block('lists_length',values={'LIST':value})
def open_screen(name):return block('controls_openAnotherScreen',values={'SCREEN':text(name)})
def components(names):
    TYPES.clear()
    def visit(c):
        TYPES[c['$Name']]=c['$Type']
        for child in c.get('$Components',[]):visit(child)
    for c in names:visit(c)
def component(name,typ,version,**props):
    return {'$Name':name,'$Type':typ,'$Version':str(version),'Uuid':str(uuid.uuid4().int%2000000000),**{k:str(v) for k,v in props.items()}}
def label(name,value):return component(name,'Label',10,Text=value,Width='-2',FontSize=16)
def button(name,value):return component(name,'Button',13,Text=value,Width='-2',Height=55,FontBold='True',BackgroundColor='&HFF176C65',TextColor='&HFFFFFFFF',Shape=1)
def inputbox(name,hint,**props):return component(name,'TextBox',13,**{'Hint':hint,'Width':'-2','FontSize':20,**props})
def screen(name,children):
    return {'authURL':['creator.kodular.io','creator-old.kodular.io','creator-new.kodular.io'],'YaVersion':'247','Source':'Form','Properties':{
        '$Name':name,'$Type':'Form','$Version':'46','Uuid':'0','AppName':'IDLAPS Triathlon Tap','Title':name,'TitleVisible':'False','ScreenOrientation':'portrait','Sizing':'Responsive','KeepScreenOn':'True','Scrollable':'True','AlignHorizontal':'3','ShowListsAsJson':'True','ShowOptionsMenu':'False','BackgroundColor':'&HFFF1F5F4','PrimaryColor':'&HFF176C65','AccentColor':'&HFF176C65','MinSdk':'23','$Components':children}}
def xml(blocks):
    root=el('xml',{'xmlns':'https://developers.google.com/blockly/xml'})
    # ElementTree already writes the namespace; do not duplicate its xmlns attribute.
    root.attrib.pop('xmlns')
    for i,b in enumerate(blocks):b.set('x',str((i%4)*600));b.set('y',str((i//4)*700));root.append(b)
    root.append(el('yacodeblocks',{'ya-version':'247','language-version':'36'}));return E.tostring(root,encoding='utf-8',xml_declaration=True)
