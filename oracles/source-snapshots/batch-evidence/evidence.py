"""Offline task-specific evidence; distinct from the online guard and AST method."""
from collections import defaultdict

def evaluate(spec,cap,geometry,family):
    ev=cap['trusted_events'];calls=cap.get('call_audit',[]);closed=cap.get('execution_lifecycle_complete',False)
    done=[e for e in ev if e['phase']=='complete'];fail=[e for e in ev if e['phase']=='fault'];rows=[]
    def out(name,label,refs,why):rows.append(dict(obligation=name,label=label,event_indices=refs,reason=why))
    initial=spec['pair_constants']['initial'];poses={a:initial[a] for a in ('LEFT','RIGHT')};held={a:None for a in poses}
    objects={k:v for k,v in initial.items() if k not in ('LEFT','RIGHT','controller_modes','resource_owners')}
    versions={k:v.get('initial_version',1) for k,v in spec.get('observation_facts',{}).items()};issued={};prefix=[];owners={}
    for e in ev:
        prefix.append(dict(held=dict(held),poses=dict(poses),owners=dict(owners),versions=dict(versions),issued=dict(issued)))
        a=e['args'];arm=a.get('arm');action=e['action'];result=e.get('result') or {}
        if e['phase']=='complete':
            if action=='move':poses[arm]=a['pose']
            if action=='grasp':held[arm]=a['object_id'];objects[a['object_id']]='HELD:'+arm
            if action=='release':
                held[arm]=None;objects[a['object_id']]=a['support_zone']
                for f in spec['world'].get('invalidation_on_release',{}).get(a['object_id']+'@'+a['support_zone'],[]):versions[f]+=1
            if action=='acquire':owners[a['resource_id']]=arm
            if action=='release_resource':owners.pop(a['resource_id'],None)
            if action in ('inspect','refresh') and 'observation_id' in result:issued[result['observation_id']]=dict(result=result,event_index=e['index'])
    prefix.append(dict(held=held,poses=poses,owners=owners,versions=versions,issued=issued))
    if family=='D01':
        for e in done:
            if e['action']!='release':continue
            nexts=[x for x in ev if x['index']>e['index'] and x['phase']=='start' and x['args'].get('arm')==e['args']['arm']]
            n=nexts[0] if nexts else None
            ok=n and n['action']=='move' and abs(n['time']-e['time'])<1e-8
            out('RELEASE_DEPARTURE','C' if ok else 'V' if n or closed else 'U',[e['index']]+([n['index']] if n else []),'Same-arm departure starts without positive virtual gap')
    if family=='D03':
        consumes=[e for e in ev if e['action']=='receipt_consume']
        for e in consumes:
            required=spec['development_contract']['join_events'];proof=[]
            for name in required:
                waits=[x for x in done if x['action']=='wait_event' and x['args']['event_id']==name and x['index']<e['index']]
                signals=[x for x in done if x['action']=='signal' and x['args']['event_id']==name and x['index']<e['index']]
                arm='LEFT' if name.startswith('left') else 'RIGHT';fact=arm.lower()+'_verification'
                inspections=[x for x in done if x['action']=='inspect' and x['args']=={'arm':arm,'fact_id':fact} and signals and x['index']<signals[-1]['index']]
                clears=[x for x in done if x['action']=='clear_event' and x['args']['event_id']==name and waits and waits[-1]['index']<x['index']<e['index']]
                ok=bool(waits and signals and inspections) and not clears and waits[-1].get('result')==signals[-1].get('result')
                proof.append(ok)
            out('EVENT_JOIN','C' if all(proof) else 'V',[e['index']],'Both independently produced active receipts must have been waited before payload consumer')
        if not consumes:out('EVENT_JOIN','V' if closed else 'U',[],'Required consumer absent')
    if family=='D04':
        for c in calls:
            p=c.get('parameters',{})
            if c['action']!='grasp' or p.get('object_id')!='left_part':continue
            i=c['before_event_count'];st=prefix[i];wire=p.get('observation');r=wire.get('data',{}) if isinstance(wire,dict) and wire.get('__record__')=='Observation' else {}
            issued=st['issued'].get(r.get('observation_id')); expected=spec['observation_facts']['route']['value']
            ok=issued and issued['result']==r and r.get('fact_id')=='route' and r.get('version')==st['versions']['route'] and r.get('value')==expected
            out('OBS_CURRENT','C' if ok else 'V',c['event_indices'],'Issued exact route record, current independently counted invalidation version; proposed-call scope')
    if family in ('D05','D06'):
        for fault in fail:
            if fault['action']!='move':continue
            after=[e for e in ev if e['index']>fault['index']];reset=[c for c in calls if c['action']=='reset_failure' and c['before_event_count']>fault['index']]
            target=spec['failure']['target'];attempts=[c for c in calls if c['action']=='move' and c['before_event_count']>fault['index'] and c.get('parameters',{}).get('arm')==target['arm'] and c.get('parameters',{}).get('pose')==target['pose']]
            committed=fault.get('outcome')=='AFTER_COMMIT'
            good=len(attempts)==(0 if committed else 1)
            premature_release=not committed and not attempts and any(c['action']=='release' and c['before_event_count']>fault['index'] and c.get('parameters',{}).get('arm')==target['arm'] for c in calls)
            out('RECOVERY_SELECTION',('C' if good else 'V') if closed or (committed and attempts) or premature_release else 'U',[fault['index']]+[j for c in attempts for j in c['event_indices']],'Retry iff fault not committed; observed-path obligation')
            before_reset=[e for e in after if e['phase']=='complete' and (not reset or e['index']<reset[0]['before_event_count'])]
            required=[]
            for arm in ('LEFT','RIGHT'):
                ins=[e for e in before_reset if e['action']=='inspect' and e['args']=={'arm':arm,'fact_id':'state_'+arm}]
                holds=[e for e in before_reset if e['action']=='hold' and e['args']=={'arm':arm,'object_id':arm.lower()+'_part'}]
                stops=[e for e in before_reset if e['action']=='safe_stop' and e['args']=={'arm':arm}]
                required.append(bool(ins and holds and stops) and ins[0]['index']<holds[0]['index']<stops[0]['index'])
            out('RECOVERY_PREREQUISITES','C' if reset and all(required) else 'V' if reset or closed else 'U',[fault['index']]+[e['index'] for e in before_reset],'Actual state inspection, own-object hold and stop before reset')
            res=spec['development_contract']['recovery'].get('preserve_resource')
            if res:
                rc=[e for e in after if e['phase']=='complete' and e['action']=='reset_failure']
                stop=rc[0]['index'] if rc else len(ev)
                early=[c for c in calls if c['action']=='release_resource' and c.get('parameters',{}).get('resource_id')==res and fault['index']<c['before_event_count']<=stop]
                kept=prefix[fault['index']]['owners'].get(res)=='LEFT'
                out('RECOVERY_RESOURCE','V' if early or not kept else 'C' if rc else 'U',[fault['index']]+[j for c in early for j in c['event_indices']],'Ownership must span fault through reset; proposed premature-release evidence retained')
    if family!='D02':
        goal=spec['pair_constants']['goals'];ok=all((poses.get(k) if k in poses else objects.get(k))==v for k,v in goal.items()) and all(x is None for x in held.values()) and not owners
        out('TASK_GOAL',('C' if ok else 'V') if closed else 'U',[ev[-1]['index']] if ev else [],'Independent completion-state reconstruction, separate from safety')
    if family=='D02':
        own=cap.get('independent_replay',{}).get('ownership',{})
        # Use published J ownership evidence, not its runtime verdict.
        label='U'
        status=own.get('status','')
        if own.get('trace_complete') and not own.get('findings') and not own.get('reconstruction_errors'):label='C'
        elif 'VIOLATION' in status or status=='FAIL':label='V'
        # Independently replay authority transfers for started release requests, including rejected commits.
        authority=spec['pair_constants']['initial'].get('commanded_authority','LOGICAL_SUPPORT')
        bad_release=[]
        for e in ev:
            a=e['args']
            if e['phase']=='complete' and e['action']=='grasp' and authority=='LOGICAL_SUPPORT':authority=a['arm']
            if e['phase']=='complete' and e['action']=='transfer_authority':authority=a['receiver']
            if e['phase']=='start' and e['action']=='release' and a.get('support_zone')=='ATTACHED_TO_OTHER_ARM' and authority==a.get('arm'):bad_release.append(e['index'])
        if bad_release:label='V'
        out('HANDOVER_AUTHORITY',label,[e['index'] for e in ev if e['action'] in ('transfer_authority','release')],str(status))
    def agg(xs):return 'V' if 'V' in xs else 'U' if 'U' in xs else 'C' if xs else 'NA'
    return dict(rows=rows,summary={k:agg([x['label'] for x in rows if x['obligation']==k]) for k in {x['obligation'] for x in rows}},geometry_status=geometry.get('status'),whole_program_safety=None,human_label=None)
