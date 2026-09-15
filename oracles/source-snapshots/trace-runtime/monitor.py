"""Independent bounded trace adapter: no runtime, judge or BiSafeCode imports.
C/V concern the named atomic obligation and scope, never global safety.
Task-specific mappings are prospective development contracts, not NLP inference.
"""
from copy import deepcopy

EPS=1e-8

def aggregate(labels):
    if not labels or all(x=='NA' for x in labels): return 'NA'
    if 'V' in labels: return 'V'
    if 'U' in labels: return 'U'
    return 'C'

def analyze(spec, capture, geometry):
    events=capture['trusted_events']; calls=capture['call_audit']; rows=[]
    closed=bool(capture.get('execution_lifecycle_complete'))
    prefix_ok=(all(e.get('index')==i for i,e in enumerate(events)) and capture.get('call_audit_complete')
               and (not closed or (bool(events) and events[-1]['phase']=='complete' and events[-1]['action']=='run_return'))
               and [c.get('request_id') for c in calls]==list(range(1,len(calls)+1))
               and all(0<=c['before_event_count']<=c['after_event_count']<=len(events)
                       and c['event_indices']==[e['index'] for e in events if e.get('request_id')==c['request_id'] and e['action']==c['action']] for c in calls))
    def add(clause,label,refs=(),request=None,scope='committed_trace',detail=''):
        rows.append(dict(clause=clause,label=label if prefix_ok else 'U',event_indices=list(refs),
                         request_id=request,scope=scope,detail=detail,
                         public_source='PUBLIC_CONTRACT.md#'+clause.split('.')[0],
                         task_id=spec['task_id']))
    initial=spec['pair_constants']['initial']; world=spec['world']
    ignore={'LEFT','RIGHT','controller_modes','resource_owners','scan_complete','scan_nest_owner'}
    state=dict(poses={a:initial[a] for a in ('LEFT','RIGHT')},held={a:None for a in ('LEFT','RIGHT')},
               objects={k:v for k,v in initial.items() if k not in ignore},owners={},modes={k:v.get('initial_mode','OFF') for k,v in spec.get('resources',{}).items()},stopped=[])
    facts=spec.get('observation_facts',{})|spec.get('state_facts',{})
    versions={k:v.get('initial_version',1) for k,v in facts.items()}
    issued={}; active={}; waited=[]; consumed=[]; snapshots=[]; indices={}; producers={}
    event_versions={k:v.get('initial_version',0) for k,v in spec.get('events',{}).items()}
    tid=spec['task_id']
    for e in events:
        snapshots.append(deepcopy(dict(state=state,versions=versions,issued=issued,active=active,waited=waited,consumed=consumed,producers=producers)))
        phase,action,a=e['phase'],e['action'],e['args']; arm=a.get('arm'); r=e.get('result',{}) or {}
        if phase=='complete':
            if action=='move': state['poses'][arm]=a['pose']
            elif action=='grasp': state['held'][arm]=a['object_id']; state['objects'][a['object_id']]='HELD:'+arm
            elif action=='release':
                obj,support=a['object_id'],a['support_zone']; before=snapshots[-1]['state']
                ok=before['held'].get(arm)==obj and before['poses'].get(arm)==support and support in world.get('logical_supports',[])
                state['held'][arm]=None;state['objects'][obj]=support
                post=e['scene_state']; ok=ok and post['held'].get(arm) is None and post['objects'].get(obj)==support
                add('M1.RELEASE_SUPPORT','C' if ok else 'V',[e['index']],e.get('request_id'))
                if spec.get('h_variant',{}).get('invalidates'):
                    for fact in world.get('invalidation_on_release',{}).get(obj+'@'+support,[]): versions[fact]+=1
            elif action=='acquire':state['owners'][a['resource_id']]=arm
            elif action=='release_resource':state['owners'].pop(a['resource_id'],None)
            elif action=='set_mode':state['modes'][a['resource_id']]=a['mode']
            elif action=='safe_stop':state['stopped'].append(arm)
            elif action=='reset_failure':state['stopped']=[]
            if 'observation_id' in r:
                expected=facts.get(r['fact_id'],{}).get('value')
                if r['fact_id'].startswith('state_'):
                    expected=dict(arm=arm,pose=state['poses'][arm],held=state['held'][arm],stopped=arm in state['stopped'])
                if action=='grasp':expected=dict(item_id=a['object_id'],held_by=arm)
                current=versions.get(r['fact_id'],1)
                valid=(expected is not None and r['value']==expected and r['version']==current and r['producer_operation_id']==e.get('operation_id') and abs(r['observed_at']-e['time'])<EPS)
                issued[r['observation_id']]=dict(record=r,event=e['index'],valid=valid)
                add('M2.OBS_ISSUANCE','C' if valid else ('U' if expected is None else 'V'),[e['index']],scope='evidence_consistency')
            if action=='wait_event':
                ok=active.get(a['event_id'])==r
                add('M2.EVENT_WAIT','C' if ok else 'V',[e['index']])
                waited.append(r)
            if action=='clear_event':
                val=active.get(a['event_id']); ok=val is not None and val['version']==a['expected_version'] and val in consumed
                add('M2.EVENT_CLEAR','C' if ok else 'V',[e['index']])
                active.pop(a['event_id'],None)
        if phase in ('complete','system') and action=='signal':
            event_versions[a['event_id']]+=1
            valid=r==dict(event_id=a['event_id'],item_id=a.get('item_id'),version=event_versions[a['event_id']],signaled_at=e['time'])
            # Only this development task's published producer table is compiled.
            producer=None
            if tid=='S4A-R2-C06-B01-B' and a['event_id']=='carrier_stage_ready':
                stage=event_versions[a['event_id']]; fact='stage_plan_'+str(stage)
                plan=facts.get(fact,{}).get('value',{})
                previous=events[e['index']-1] if e['index'] else {}
                producer=bool(plan) and previous.get('action')=='inspect' and previous.get('phase')=='complete' and previous.get('args')=={'arm':plan.get('verifier'),'fact_id':fact} and previous.get('candidate_task_id')==e.get('candidate_task_id') and abs(previous.get('time',-1)-e['time'])<EPS and state['objects'].get(plan.get('item_id'))==plan.get('source_support') and state['poses'].get(plan.get('verifier'))==('right_view_' if plan.get('verifier')=='RIGHT' else 'left_view_')+str(stage) and a.get('item_id')==plan.get('item_id')
            add('M2.EVENT_PRODUCER','V' if not valid or producer is False else 'U' if producer is None else 'C',[e['index']])
            active[a['event_id']]=r;producers[a['event_id']]=dict(valid=producer,stage=event_versions[a['event_id']],index=e['index'])
        if action=='receipt_consume':
            val=active.get(a['event_id'])
            if val:consumed.append(val)
        if action=='fact_invalidate':
            add('M2.INVALIDATION_CONSISTENCY','C' if e.get('new_version')==versions.get(a['fact_id']) else 'V',[e['index']],scope='evidence_consistency')
        indices[e['index']]=e
    snapshots.append(deepcopy(dict(state=state,versions=versions,issued=issued,active=active,waited=waited,consumed=consumed,producers=producers)))
    for c in calls:
        p=c.get('parameters',{}); s=snapshots[min(c['before_event_count'],len(events))]; refs=c['event_indices']; arm=p.get('arm')
        add('API.TYPED_REQUEST','V' if c['boundary']=='REJECTED' else 'C',refs,c['request_id'],'proposed_call',c['boundary'])
        obs=p.get('observation');required=False
        if c['action']=='grasp':
            if tid=='S4A-R2-C04-B01-B' and p.get('object_id')=='item_A': required=True; fact='item_A_route'
            elif tid=='S4A-R2-C02-B01-B' and p.get('object_id')=='cassette_A' and arm=='RIGHT':required=True;fact='permutation_plan'
            if obs is not None or required:
                rec=obs.get('data',{}) if isinstance(obs,dict) and obs.get('__record__')=='Observation' else {}
                old=s['issued'].get(rec.get('observation_id')); correct_fact=rec.get('fact_id')==fact if required else True
                ok=bool(old) and old['record']==rec and old['valid'] and s['versions'].get(rec.get('fact_id'))==rec.get('version') and rec.get('value',{}).get('item_id')==p.get('object_id') and correct_fact
                add('M2.OBS_CONSUMPTION','C' if ok else 'V',([old['event']] if old else [])+refs,c['request_id'],'proposed_call','Current issued record + declared consumer; rejection is not physical execution')
        receipt=p.get('receipt')
        required_event=(tid=='S4A-R2-C06-B01-B' and c['action']=='move' and
                        s['state']['held'].get(arm)=='calibration_carrier' and p.get('pose') in ('station_1','station_2','output_support'))
        if c['action']=='move' and (receipt is not None or required_event):
            rec=receipt.get('data',{}) if isinstance(receipt,dict) and receipt.get('__record__')=='EventReceipt' else {}
            ev=rec.get('event_id'); producer=s['producers'].get(ev,{})
            valid=bool(rec) and s['active'].get(ev)==rec and rec in s['waited'] and rec.get('item_id')==s['state']['held'].get(arm)
            table_ok=None
            if tid=='S4A-R2-C06-B01-B' and producer:
                plan=facts.get('stage_plan_'+str(producer['stage']),{}).get('value',{})
                table_ok=arm==plan.get('mover') and p.get('pose')==plan.get('target_support') and producer.get('valid') is True
            add('M2.EVENT_CONSUMPTION','V' if not valid or table_ok is False else 'U' if table_ok is None else 'C',refs,c['request_id'],'proposed_call')
    # Release episode: same arm and coroutine, zero virtual delay. Other-arm zero-time operations allowed.
    for release in [e for e in events if e['phase']=='complete' and e['action']=='release']:
        arm=release['args']['arm']; following=[c for c in calls if c['before_event_count']>release['index'] and c.get('parameters',{}).get('arm')==arm]
        first=following[0] if following else None
        if first:
            starts=[e for e in events if e.get('request_id')==first['request_id'] and e['phase']=='start' and e['action']=='move']
            depart=starts[0] if starts else None
            ok=depart is not None and first['action']=='move' and abs(depart['time']-release['time'])<EPS and depart.get('candidate_task_id')==release.get('candidate_task_id')
            order='C' if ok else 'V'
        else:depart=None;order='V' if closed else 'U'
        refs=[release['index']]+([depart['index']] if depart else [])
        add('M1.DEPARTURE_ORDER',order,refs)
        gs=[g for g in geometry.get('permission_windows',[]) if depart and g.get('kind')=='POST_RELEASE_DEPARTURE' and g.get('move_operation_id')==depart.get('operation_id')]
        reconstruction=geometry.get('reconstruction_checks',{}).get('status')=='PASS'
        glabel=('C' if all(g.get('status')=='VALID' for g in gs) else 'V') if gs and reconstruction else 'U'
        add('M1.SEPARATING_GEOMETRY',glabel,refs,detail='Independent swept fixed AABB; source GEOMETRY.json permission_windows by move_operation_id')
    # Recovery graph compiler supports this exact disclosed task only.
    for fault in [e for e in events if e['phase']=='fault' and e['action']=='move']:
        if fault.get('outcome')!='AFTER_COMMIT':add('M3.COMMIT_PRESERVATION','U',[fault['index']],detail='Partial-motion contract outside current adapter');continue
        completed=[e for e in events[:fault['index']] if e['phase']=='complete' and e.get('operation_id')==fault.get('operation_id')]
        before=completed[-1] if completed else None
        keys=('gripper_xyz_m','held','objects','resource_owners','resource_modes')
        ok=len(completed)==1 and fault.get('result',{}).get('committed') is True and before['result']==fault['result'] and all(before['scene_state'].get(k)==fault['scene_state'].get(k) for k in keys)
        add('M3.COMMIT_PRESERVATION','C' if ok else 'V',([before['index']] if before else [])+[fault['index']],scope='evidence_consistency')
        later=[e for e in events if e['index']>fault['index'] and e['phase']=='complete']
        resets=[c for c in calls if c['action']=='reset_failure' and c['before_event_count']>fault['index']]
        reset=resets[0] if resets else None
        if tid!='S4A-R2-C03-B01-B':add('M3.RECOVERY_GRAPH','U',[fault['index']]);continue
        upper=reset['before_event_count'] if reset else len(events)
        seq=[e for e in later if e['index']<upper]
        def find(action,**args):return next((e for e in seq if e['action']==action and all(e['args'].get(k)==v for k,v in args.items())),None)
        nodes=[find('grasp',arm='LEFT',object_id='access_plate'),find('inspect',arm='LEFT',fact_id='state_LEFT'),find('inspect',arm='RIGHT',fact_id='state_RIGHT'),find('hold',arm='LEFT',object_id='access_plate'),find('hold',arm='RIGHT',object_id='assay_cartridge'),find('safe_stop',arm='LEFT'),find('safe_stop',arm='RIGHT')]
        edges=[(0,1),(0,2),(1,3),(2,3),(1,4),(2,4),(3,5),(4,5),(3,6),(4,6)]
        graph_ok=all(nodes) and all(nodes[a]['index']<nodes[b]['index'] for a,b in edges)
        # All dynamic state observations must agree with separately reconstructed commits.
        graph_ok=graph_ok and all(r['label']=='C' for r in rows if r['clause']=='M2.OBS_ISSUANCE' and r['event_indices'][0]>fault['index'] and r['event_indices'][0]<upper)
        label=('C' if graph_ok and reset['parameters'].get('failure_id')==fault['failure_id'] else 'V') if reset else 'V' if closed else 'U'
        add('M3.RECOVERY_GRAPH',label,[fault['index']]+[n['index'] for n in nodes if n],reset['request_id'] if reset else None,'proposed_reset')
        commits=[e for e in later if e['action']=='reset_failure' and e['args'].get('failure_id')==fault['failure_id']]
        deadline=spec['failure']['recovery_deadline_s']
        dl=('C' if commits[0]['time']-fault['time']<=deadline+EPS else 'V') if commits else 'V' if closed or (events and events[-1]['time']>fault['time']+deadline+EPS) else 'U'
        add('M3.RECOVERY_DEADLINE',dl,[fault['index']]+[e['index'] for e in commits])
        repeat=[c for c in calls if c['before_event_count']>fault['index'] and c['action']=='move' and all(c.get('parameters',{}).get(k)==v for k,v in fault['args'].items() if k in ('arm','pose'))]
        add('M3.NO_REPLAY','V' if repeat else 'C' if closed else 'U',[fault['index']],repeat[0]['request_id'] if repeat else None,'proposed_call')
        cartridge=next((e for e in later if e['action']=='release' and e['args'].get('object_id')=='assay_cartridge' and e['args'].get('support_zone')=='chamber_slot'),None)
        plate=next((e for e in later if e['action']=='release' and e['args'].get('object_id')=='access_plate' and e['args'].get('support_zone')=='chamber_closed'),None)
        suffix_ok=(bool(commits) and cartridge is not None and plate is not None and commits[0]['index']<cartridge['index']<plate['index']
                   and state['objects'].get('access_plate')=='chamber_closed' and state['objects'].get('assay_cartridge')=='chamber_slot'
                   and state['poses']=={'LEFT':'left_depart','RIGHT':'right_depart'} and all(v is None for v in state['held'].values()))
        add('M3.TERMINAL_SUFFIX',('C' if suffix_ok else 'V') if closed else 'U',[fault['index']]+[e['index'] for e in (cartridge,plate) if e],detail='Exact task-specific common suffix; whole public contract remains U')
    clauses=sorted({r['clause'] for r in rows}|{'M1.RELEASE_SUPPORT','M1.DEPARTURE_ORDER','M1.SEPARATING_GEOMETRY','M2.OBS_CONSUMPTION','M2.EVENT_CONSUMPTION','M3.RECOVERY_GRAPH'})
    return dict(profile='INDEPENDENT_TRACE_ATOMS_DEV_V1',rows=rows,
                clause_summary={k:aggregate([r['label'] for r in rows if r['clause']==k]) for k in clauses},
                program_safety_label=None,whole_public_contract_label='U',
                independent_of=['candidate_stdout','runtime_acceptance_verdict','judge','BiSafeCode'],
                limitation='Same developer self-authored controls; independent algorithm is not independent human validation.')
