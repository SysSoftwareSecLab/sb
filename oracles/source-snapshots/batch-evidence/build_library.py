"""Six bounded development candidates; explicit lineage, no natural generations."""
from pathlib import Path
from itertools import combinations
from copy import deepcopy
import json, hashlib
P=Path(__file__).resolve().parent;R=P.parents[2]

def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def base(fid,variant):
    poses={}
    for arm,x in [('left',-2.0),('right',2.0)]:
        for name,coord in [('home',[x,-1,1.4]),('source',[x,0,1]),('target',[x,1,1]),('depart',[x,1,1.5])]:poses[f'{arm}_{name}']=coord
    solids=['LEFT_gripper','RIGHT_gripper','left_part','right_part']
    w=dict(geometry_model='TRANSLATION_AABB_FIXED_ORIENTATION',pose_coordinates_m=poses,modeled_solids=solids,
           gripper_half_size_m=[.03]*3,object_half_size_m={x:[.04]*3 for x in ['left_part','right_part']},
           logical_supports=['left_source','right_source','left_target','right_target'],
           collision_pairs=list(map(list,combinations(solids,2))),excluded_pairs=[],grasp_offsets_m={},invalidation_on_release={},
           contact_allowances=[dict(pair=[a+'_gripper',a.lower()+'_part'],when='declared approach/grasp, attachment, release and immediate separating departure') for a in ['LEFT','RIGHT']],
           approach_sequences=[dict(arm=a,start_pose=a.lower()+'_home',interaction_pose=a.lower()+'_source',object_id=a.lower()+'_part',required_next_robot_call='grasp',max_intervening_logical_time_s=0.0) for a in ['LEFT','RIGHT']])
    c=dict(initial=dict(LEFT='left_home',RIGHT='right_home',left_part='left_source',right_part='right_source'),
           goals=dict(LEFT='left_depart',RIGHT='right_depart',left_part='left_target',right_part='right_target'),
           deadline_s=30,default_move_timeout_s=4,explicit_move_timeout_range_s=[.05,30],
           durations_s={k:.1 for k in ['grasp','release','inspect','refresh','hold','safe_stop','reset_failure','acquire','release_resource','set_mode','wait_event','cure']})
    c['durations_s']['move']=1
    return dict(task_id=f'{fid}-{variant}',family_id=fid,axis_id='QUALITY_DEVELOPMENT',variant=variant,world=w,pair_constants=c,
                public_task=dict(deadline_s=30,scene='Two separate work lanes with two declared parts.',goal=['both parts at their own target; both arms at departure and empty'],required_order=[]),
                observation_facts={},state_facts={},events={},resources={},h_variant={'invalidates':True},failure={'injected':False},
                development_contract={})

def chain(arm,obs=None):
    l=arm.lower();o=', observation='+obs if obs else ''
    return f'await robot.move("{arm}", "{l}_source")\nawait robot.grasp("{arm}", "{l}_part"{o})\nawait robot.move("{arm}", "{l}_target")\nawait robot.release("{arm}", "{l}_part", "{l}_target")\nawait robot.move("{arm}", "{l}_depart")\n'
def indent(x,n=4):return ''.join(' '*n+l+'\n' for l in x.strip().splitlines())
def program(x,imports=''):return imports+'\nasync def run_task(robot):\n'+indent(x)

def build():
    families=[]
    for fid,title,lineage,contrast,admission in [
        ('D01','Fork/join of two release lifecycles','Stage4 concurrency + release components; not yet established independent of C01 families','serial versus concurrent independent attachment chains','CANDIDATE_PAIRED'),
        ('D02','Receiver attachment with observation carry across donor movement','J_SUP01_FRESH_HANDOVER; genuine dual attachment, reused structure','freshness boundary in real handover','REUSED_CALIBRATION_NOT_NEW_FAMILY'),
        ('D03','Two independent verifier branches joining before one payload consumer','new two-event join graph, based on generic H event primitives','serial versus concurrent verifier production','CANDIDATE_PAIRED'),
        ('D04','Version-selected observation after another arm releases an invalidator','extends old C04 invalidation; requires a version-dependent branch','preserve versus invalidate same closed-value observation','DERIVED_FAMILY_REQUIRES_DISTINCTNESS_REVIEW'),
        ('D05','Fault outcome selects retry versus preserve committed work','extends move fault recovery; before/after outcomes have different executed work','BEFORE_COMMIT versus AFTER_COMMIT fault outcomes','MECHANISM_CALIBRATION_NOT_PURE_COMPOSITION'),
        ('D06','Resource ownership spans or ends at a two-arm recovery boundary','new cross-resource recovery dependency over generic H primitives','resource must remain owned through reset versus may release before reset','CANDIDATE_PAIRED')]:
        families.append(dict(family_id=fid,title=title,lineage=lineage,contrast=contrast,admission=admission,split='DEVELOPMENT_ONLY',formal_holdout=False))
    allcases=[]
    for fam in families:
      fid=fam['family_id']
      for variant in ['A','B']:
        s=base(fid,variant); backend='H'
        if fid=='D01':
            if variant=='A':src=program(chain('LEFT')+chain('RIGHT'))
            else:src=program('async def left():\n'+indent(chain('LEFT'))+'async def right():\n'+indent(chain('RIGHT'))+'await asyncio.gather(left(), right())','import asyncio')
            mutation=src.replace('await robot.move("LEFT", "left_depart")','await asyncio.sleep(0.2)\n'+('        ' if variant=='B' else '    ')+'await robot.move("LEFT", "left_depart")')
            if 'import asyncio' not in mutation:mutation='import asyncio\n'+mutation
            expected='RELEASE_DEPARTURE'
        elif fid=='D02':
            backend='J';jr=R/'01_project/STAGE3_JKL_2026-09-06/outputs'
            sp=jr/f'J_handover_contract_evidence/specs/J_SUP01_FRESH_HANDOVER_{variant}.json'
            s=json.loads(sp.read_text());s['development_contract']={};s['development_alias']=f'{fid}-{variant}';s['world']['logical_supports'].append('parcel_terminal');s['development_contract']['spec_repair']='J reference and required_order name parcel_terminal; original logical_supports omitted it. New development copy explicitly declares it.'
            src=(jr/f'K_handover_execution/preparation/references/J_SUP01_FRESH_HANDOVER_{variant}.py').read_text()
            mutation=src.replace('    await robot.transfer_authority(', '    # Deliberately omit authority transfer\n    if False:\n        await robot.transfer_authority(')
            # Complete call indentation remains legal inside the parenthesized call.
            expected='HANDOVER_AUTHORITY'
        elif fid=='D03':
            for arm in ['LEFT','RIGHT']:
                l=arm.lower();s['observation_facts'][l+'_verification']=dict(initial_version=1,value={'item_id':'left_part','verified_by':arm})
                s['events'][l+'_ready']=dict(initial_version=0,system=False,program_signalable=True,program_clearable=True)
            verify=lambda a:f'await robot.inspect("{a}", "{a.lower()}_verification")\nrobot.signal("{a.lower()}_ready", item_id="left_part")\n'
            begin=(verify('LEFT')+verify('RIGHT')) if variant=='A' else 'async def verify_left():\n'+indent(verify('LEFT'))+'async def verify_right():\n'+indent(verify('RIGHT'))+'await asyncio.gather(verify_left(), verify_right())\n'
            body=begin+'l = await robot.wait_event("left_ready", 1)\nr = await robot.wait_event("right_ready", 1)\n'+chain('LEFT').replace('await robot.move("LEFT", "left_target")','await robot.move("LEFT", "left_target", receipt=l)')+'robot.clear_event("left_ready", expected_version=l.version)\nrobot.clear_event("right_ready", expected_version=r.version)\n'+chain('RIGHT')
            src=program(body,'import asyncio');mutation=src.replace('r = await robot.wait_event("right_ready", 1)','r = None').replace('robot.clear_event("right_ready", expected_version=r.version)','robot.clear_event("right_ready", expected_version=1)')
            s['development_contract']['join_events']=['left_ready','right_ready'];expected='EVENT_JOIN'
        elif fid=='D04':
            s['observation_facts']['route']=dict(initial_version=1,value={'item_id':'left_part','destination':'left_target'})
            s['world']['invalidation_on_release']={'right_part@right_target':['route']} if variant=='B' else {}
            body='old = await robot.inspect("LEFT", "route")\n'+chain('RIGHT')+'current = await robot.refresh("LEFT", "route")\nselected = old if old.version == current.version else current\n'+chain('LEFT','selected')
            src=program(body);mutation=src.replace('selected = old if old.version == current.version else current','selected = old' if variant=='B' else 'selected = None')
            s['development_contract']['observation']={'object_id':'left_part','fact_id':'route'};expected='OBS_CURRENT'
        else:
            s['state_facts']={f'state_{a}':{'initial_version':1} for a in ['LEFT','RIGHT']}
            s['failure']=dict(injected=True,kind='MotionFault',outcome='BEFORE_COMMIT' if fid=='D05' and variant=='A' else 'AFTER_COMMIT',failure_id='placement_fault',completion_fraction=.5 if fid=='D05' and variant=='A' else 1,maximum_occurrences=1,recovery_deadline_s=5,target={'method':'move','arm':'RIGHT','pose':'right_target'})
            prefix=''
            if fid=='D06':
                s['resources']={'fixture':{'initial_mode':'OFF'}};prefix='await robot.acquire("LEFT", "fixture", 1)\n'
            prefix+='await robot.move("LEFT", "left_source")\nawait robot.grasp("LEFT", "left_part")\nawait robot.move("RIGHT", "right_source")\nawait robot.grasp("RIGHT", "right_part")\n'
            recovery=''
            if fid=='D06' and variant=='A':recovery+='await robot.release_resource("LEFT", "fixture")\n'
            recovery+='await robot.inspect("LEFT", "state_LEFT")\nawait robot.inspect("RIGHT", "state_RIGHT")\nawait robot.hold("LEFT", "left_part")\nawait robot.hold("RIGHT", "right_part")\nawait robot.safe_stop("LEFT")\nawait robot.safe_stop("RIGHT")\nawait robot.reset_failure("placement_fault")\n'
            if fid=='D06' and variant=='B':recovery+='await robot.release_resource("LEFT", "fixture")\n'
            recovery+='if not fault.committed:\n    await robot.move("RIGHT", "right_target")\n'
            suffix='await robot.release("RIGHT", "right_part", "right_target")\nawait robot.move("RIGHT", "right_depart")\nawait robot.move("LEFT", "left_target")\nawait robot.release("LEFT", "left_part", "left_target")\nawait robot.move("LEFT", "left_depart")\n'
            src=program(prefix+'try:\n    await robot.move("RIGHT", "right_target")\nexcept MotionFault as fault:\n'+indent(recovery)+suffix,'from bridge_robot_api import MotionFault')
            if fid=='D05':mutation=src.replace('if not fault.committed:', 'if fault.committed:')
            else:mutation=src.replace('        await robot.release_resource("LEFT", "fixture")\n','').replace('    except MotionFault as fault:\n','    except MotionFault as fault:\n        await robot.release_resource("LEFT", "fixture")\n') if variant=='B' else src.replace('        await robot.hold("RIGHT", "right_part")\n','')
            s['development_contract']['recovery']=dict(preserve_resource='fixture' if fid=='D06' and variant=='B' else None,required_holds={'LEFT':'left_part','RIGHT':'right_part'})
            expected='RECOVERY_SELECTION' if fid=='D05' else 'RECOVERY_RESOURCE' if variant=='B' else 'RECOVERY_PREREQUISITES'
        s['public_task']=s.get('public_task',dict(deadline_s=s['pair_constants']['deadline_s']))
        s['public_task']['development_obligations']=dict(family=fam['title'],contrast=fam['contrast'],variant=variant,atomic=s['development_contract'])
        for role,code in [('reference',src),('mutation',mutation),('semantic',src.replace('robot','bot'))]:
            cid=f'{fid}-{variant}-{role}';dest=P/'library'/cid;dest.mkdir(parents=True,exist_ok=True)
            # rename only parameter and API variable, never imported bridge_robot_api module
            if role=='semantic':code=src.replace('run_task(robot)','run_task(bot)').replace('robot.','bot.')
            (dest/'candidate.py').write_text(code);write(dest/'SPEC.json',s)
            allcases.append(dict(case_id=cid,family_id=fid,variant=variant,role=role,backend=backend,target_obligation=expected,
                                 expected='V' if role=='mutation' else 'C',source_sha256=hashlib.sha256(code.encode()).hexdigest(),spec_sha256=hashlib.sha256((dest/'SPEC.json').read_bytes()).hexdigest()))
    write(P/'LIBRARY_MANIFEST.json',dict(status='PRELISTED_DEVELOPMENT_CANDIDATES_NOT_NOVELTY_CERTIFIED',families=families,cases=allcases,natural_samples=0,formal_mutations=0))
    print('Built',len(families),'candidate families,',len(allcases),'development cases')
if __name__=='__main__':
    if (P/'LIBRARY_MANIFEST.json').exists():raise SystemExit('Existing development library retained; rebuild into a new version, do not overwrite execution inputs.')
    build()
