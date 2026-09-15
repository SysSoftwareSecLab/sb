"""Offline replay supplement; no tested-method or runtime-verdict imports."""
from pathlib import Path
import sys,copy
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'batch_13_15'))
from check_evidence import evaluate as base_evaluate
from obligations import for_parent

def evaluate(spec,cap,geo,parent):
    events=cap.get('trusted_events',[]);audit=cap.get('call_audit',[])
    valid=bool(events) and all(e.get('index')==i for i,e in enumerate(events)) and cap.get('call_audit_complete') is True and all(type(c.get('before_event_count')) is int and 0<=c['before_event_count']<=len(events) for c in audit)
    if not valid:
        return dict(rows=[dict(obligation=k,rule=v,label='U',instances=[]) for k,v in for_parent(parent).items()],summary={k:'U' for k in for_parent(parent)},input_integrity=False,human_label=None,whole_program_safety=None,scope='Missing or malformed event/call boundary evidence')
    old=base_evaluate(spec,cap,geo);ev=cap['trusted_events'];calls=cap.get('call_audit',[]);closed=bool(cap.get('execution_lifecycle_complete'))
    valid=all(e.get('index')==i for i,e in enumerate(ev)) and cap.get('call_audit_complete') is True
    initial=spec['pair_constants']['initial'];state=dict(poses={a:initial[a] for a in ['LEFT','RIGHT']},objects={k:v for k,v in initial.items() if k not in ['LEFT','RIGHT']},held={'LEFT':None,'RIGHT':None},owners={},modes={k:v.get('initial_mode','OFF') for k,v in spec.get('resources',{}).items()},active={},waited={},last_release={},last_inspect={})
    before=[]
    for e in ev:
        before.append(copy.deepcopy(state));a=e['args'];arm=a.get('arm');action=e['action']
        if e['phase']!='complete':continue
        if action=='move':state['poses'][arm]=a['pose']
        elif action=='grasp':state['held'][arm]=a['object_id'];state['objects'][a['object_id']]='HELD:'+arm
        elif action=='release':state['held'][arm]=None;state['objects'][a['object_id']]=a['support_zone'];state['last_release'][a['object_id']]=e['index']
        elif action=='acquire':state['owners'][a['resource_id']]=arm
        elif action=='release_resource':state['owners'].pop(a['resource_id'],None)
        elif action=='set_mode':state['modes'][a['resource_id']]=a['mode']
        elif action=='signal':state['active'][a['event_id']]=e.get('result')
        elif action=='clear_event':state['active'].pop(a['event_id'],None)
        elif action=='wait_event':state['waited'][a['event_id']]=e.get('result')
        elif action=='inspect':state['last_inspect'][a['fact_id']]={'arm':arm,'index':e['index'],'record':e.get('result')}
    before.append(copy.deepcopy(state));checks={k:[] for k in for_parent(parent)}
    def add(unit,label,refs,why,request_id=None):
        checks[unit].append(dict(label=label,event_indices=refs,reason=why,request_id=request_id))
    def test(unit,ok,refs,why,request_id=None):add(unit,'C' if ok else 'V',refs,why,request_id)
    for row in old['rows']:
        if row['atom'] in ['RELEASE_SUPPORT','RELEASE_DEPARTURE']:add('SUPPORT_DEPARTURE',row['label'],row['event_indices'],row['reason'])
    geometry=geo.get('status','')
    add('GEOMETRY','C' if geometry=='NO_FORBIDDEN_CONTACT_IN_DECLARED_FIXED_AABB_TRANSLATIONS' else 'V' if geometry.startswith('VIOLATIONS') else 'U',[],geometry)
    if spec.get('failure',{}).get('kind')=='ACQUIRE_TIMEOUT':
        timeouts=[e for e in ev if e['phase']=='timeout' and e['action']=='acquire']
        test('TERMINAL',bool(timeouts) and not state['owners'],[e['index'] for e in timeouts],'Diagnostic exit goal: no remaining observed resource owner')
    else:
        label=old['summary']['TASK_TERMINAL']
        if closed:label='C' if label=='C' and old['summary']['DEADLINE']=='C' and all(x=='OFF' for x in state['modes'].values()) else 'V'
        elif cap.get('process',{}).get('status') in ['EXITED','NONZERO_EXIT'] and cap['process'].get('returncode')!=0:label='V'
        add('TERMINAL',label,[len(ev)-1] if ev else [],'Finite task outcome, not whole-program safety; failed process cannot satisfy normal endpoint')
    if parent=='P01':
        for row in old['rows']:
            if row['atom'] in ['BUFFER_CAPACITY','BUFFER_OWNER']:add('BUFFER_OCCUPANCY_OWNER',row['label'],row['event_indices'],row['reason'])
            if row['atom']=='BUFFER_RECEIPT':add('BUFFER_RECEIPT',row['label'],row['event_indices'],row['reason'])
        for c in calls:
            a=c.get('parameters',{});s=before[c['before_event_count']];action=c['action'];refs=c.get('event_indices',[]);rid=c['request_id'];arm=a.get('arm');pose=a.get('pose')
            if action=='signal':
                name=a.get('event_id');item=a.get('item_id')
                if name in ['ready_0','ready_1']:
                    i=name[-1];ok=item=='part_'+i and s['objects'].get(item)=='buffer_'+i and s['poses']['LEFT'] not in spec['parent_contract']['buffer_poses'] and s['held']['LEFT'] is None
                    test('BUFFER_EVENT_PROTOCOL',ok,refs,'Ready producer requires corresponding supported item and completed LEFT departure',rid)
                if name=='empty_0':test('BUFFER_EVENT_PROTOCOL',item=='part_0' and s['objects']['part_0']=='target_0' and s['poses']['RIGHT']!='target_0' and s['held']['RIGHT'] is None,refs,'Empty producer follows item target placement and RIGHT departure',rid)
            if action=='grasp' and arm=='RIGHT' and a.get('object_id') in ['part_0','part_1']:
                name='ready_'+a['object_id'][-1];test('BUFFER_EVENT_PROTOCOL',bool(s['active'].get(name)) and s['waited'].get(name)==s['active'].get(name),refs,'Ready receipt waited before consumer pickup',rid)
            if action=='move' and arm=='LEFT' and pose=='buffer_1':
                test('BUFFER_EVENT_PROTOCOL',bool(s['waited'].get('empty_0')) and 'empty_0' not in s['active'],refs,'Second buffer entry follows waited and cleared empty acknowledgement',rid)
            if action=='clear_event' and a.get('event_id') in ['ready_0','ready_1']:
                name=a['event_id'];consumed=any(e['action']=='receipt_consume' and e['index']<c['before_event_count'] and e['args'].get('event_id')==name for e in ev)
                test('BUFFER_EVENT_PROTOCOL',consumed,refs,'Ready clear follows actual receipt consumer',rid)
            if action=='move' and s['poses'].get(arm) in spec['parent_contract']['buffer_poses']:
                test('BUFFER_OCCUPANCY_OWNER',s['owners'].get('buffer_lock')==arm,refs,'Retain buffer lock until departure starts',rid)
            if action=='release_resource' and a.get('resource_id')=='buffer_lock':
                test('BUFFER_OCCUPANCY_OWNER',s['poses'].get(arm) not in spec['parent_contract']['buffer_poses'],refs,'Do not release lock before buffer departure completes',rid)
        if closed:
            for name in ['ready_0','ready_1','empty_0']:
                n=sum(e['phase']=='complete' and e['action']=='signal' and e['args'].get('event_id')==name for e in ev)
                test('BUFFER_EVENT_PROTOCOL',n>=1,[],'At least one publication of required event: '+name)
    if parent=='P02':
        for row in old['rows']:
            if row['atom']=='DUAL_RESOURCE':add('DUAL_RESOURCE_SPAN',row['label'],row['event_indices'],row['reason'])
        for c in calls:
            a=c.get('parameters',{});s=before[c['before_event_count']];arm=a.get('arm');resource=a.get('resource_id');action=c['action'];refs=c.get('event_indices',[]);rid=c['request_id']
            if action=='acquire':
                if resource=='tool':test('DUAL_RESOURCE_SPAN',s['owners'].get('fixture')==arm,refs,'Acquire fixture before tool',rid)
                if resource=='fixture':test('DUAL_RESOURCE_SPAN',s['owners'].get('tool')!=arm,refs,'Do not acquire fixture while already holding tool',rid)
            if action=='release' or (action=='move' and arm in ['LEFT','RIGHT'] and s['poses'].get(arm)==arm.lower()+'_target'):
                test('DUAL_RESOURCE_SPAN',all(s['owners'].get(k)==arm for k in ['fixture','tool']),refs,'Own both controllers through release and departure request',rid)
            if action=='release_resource' and resource=='tool':test('DUAL_RESOURCE_SPAN',s['poses'].get(arm)!=arm.lower()+'_target' and s['held'].get(arm) is None,refs,'Tool released only after departure completion',rid)
            if action=='release_resource' and resource=='fixture':test('DUAL_RESOURCE_SPAN',s['owners'].get('tool')!=arm,refs,'Release tool before fixture',rid)
        timeouts=[e for e in ev if e['phase']=='timeout' and e['action']=='acquire' and e['args'].get('resource_id')=='tool']
        for e in timeouts:
            arm=e['args']['arm'];release=[x for x in ev if x['index']>e['index'] and x['phase']=='complete' and x['action']=='release_resource' and x['args']=={'arm':arm,'resource_id':'fixture'}]
            bad=any(c['before_event_count']>e['index'] and c['action']=='move' and c.get('parameters',{}).get('arm')==arm and c['parameters'].get('pose')==arm.lower()+'_target' for c in calls)
            test('TIMEOUT_CLEANUP',bool(release) and not bad and arm not in state['owners'].values(),[e['index']]+[x['index'] for x in release],'Acquired fixture released after tool timeout; no unprotected target continuation')
        if not timeouts:add('TIMEOUT_CLEANUP','NA',[],'No declared tool acquisition timeout on this observed path')
    if parent=='P03':
        # public_task.goal includes acceptance, beyond the positional goals.
        # Check the actual inspection cycle at final placement; producer identity
        # and branch protocol remain separate obligations.
        if closed:
            placements=[e for e in ev if e['phase']=='complete' and e['action']=='release' and e['args'].get('object_id')=='left_part' and e['args'].get('support_zone')=='left_target']
            accepted=False
            if placements:
                end=placements[-1]['index']
                cycles=[e for e in ev if e['index']<end and e['phase']=='complete' and e['action']=='release' and e['args'].get('object_id')=='left_part' and e['args'].get('support_zone')=='inspection']
                decisions=spec['observation_facts']['quality']['value']['accept_by_pass']
                n=len(cycles)
                observed=bool(cycles) and any(cycles[-1]['index']<e['index']<end and e['phase']=='complete' and e['action']=='inspect' and e['args'].get('fact_id')=='quality' for e in ev)
                accepted=observed and 0<n<=spec['parent_contract']['max_passes'] and n<=len(decisions) and decisions[n-1] is True
            test('TERMINAL',accepted,[e['index'] for e in placements],'Public goal requires acceptance in the actual inspection cycle before final placement')
        for row in old['rows']:
            if row['atom']=='REWORK_CURRENT':add('REWORK_OBSERVATION',row['label'],row['event_indices'],row['reason'])
        pickups=0
        for c in calls:
            a=c.get('parameters',{});s=before[c['before_event_count']];refs=c.get('event_indices',[]);rid=c['request_id']
            if c['action']=='inspect' and a.get('fact_id')=='quality':test('REWORK_OBSERVATION',a.get('arm')=='RIGHT' and s['objects']['left_part']=='inspection' and s['poses']['LEFT']!='inspection',refs,'RIGHT observes after inspection placement and LEFT departure',rid)
            if c['action']=='grasp' and a.get('arm')=='LEFT' and s['poses']['LEFT']=='inspection':
                pickups+=1;ins=s['last_inspect'].get('quality',{});raw=a.get('observation') or {};rec=raw.get('data') if isinstance(raw,dict) else None
                matching=[e for e in ev if s['last_release'].get('left_part',-1)<e['index']<c['before_event_count'] and e['phase']=='complete' and e['action']=='inspect' and e['args']=={'arm':'RIGHT','fact_id':'quality'} and e.get('result')==rec]
                test('REWORK_OBSERVATION',bool(matching),refs,'This pickup uses a current-cycle observation; duplicate observations in the same cycle are allowed',rid)
            if c['action']=='move' and a.get('arm')=='LEFT' and s['held']['LEFT']=='left_part' and a.get('pose') in ['rework','left_target']:
                count=sum(e['phase']=='complete' and e['action']=='release' and e['args'].get('support_zone')=='inspection' and e['index']<c['before_event_count'] for e in ev)-1
                decisions=spec['observation_facts']['quality']['value']['accept_by_pass']
                expected=('left_target' if decisions[count] else 'rework') if 0<=count<len(decisions) else None
                test('REWORK_BRANCH',a.get('pose')==expected,refs,'Observed branch destination matches current public pass outcome',rid)
        test('REWORK_BRANCH',pickups<=2,[],'At most two inspection pickup proposals')
        if not closed and all(x['label']!='V' for x in checks['REWORK_BRANCH']):add('REWORK_BRANCH','U',[],'Incomplete path does not establish completion of required branch sequence')
    result=[]
    for unit,rule in for_parent(parent).items():
        instances=checks[unit];labels=[x['label'] for x in instances]
        label='V' if 'V' in labels else 'U' if 'U' in labels or not instances else 'NA' if all(x=='NA' for x in labels) else 'C'
        if not valid and label=='C':label='U'
        result.append(dict(obligation=unit,rule=rule,label=label,instances=instances))
    return dict(rows=result,summary={x['obligation']:x['label'] for x in result},input_integrity=valid,
                scope='Observed finite scenario and declared geometry only; public scheduling A/B is separately checked in PAIR_AUDIT',
                human_label=None,whole_program_safety=None)
