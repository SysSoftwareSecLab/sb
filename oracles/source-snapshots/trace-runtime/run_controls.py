"""Finite prelisted development executions only. No model/API calls or human labels."""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from runtime import execute, PROFILE
from monitor import analyze

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=ROOT/'01_project/STAGE4_PLAN_2026-09-07/outputs'
GEO=ROOT/'01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src'
sys.path.insert(0,str(GEO))
from geometry_interface_v01 import evaluate_dynamic_evidence

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def inputs(n):
    batch='batch_01_06' if n==6 else 'batch_02_03_05'
    t=f'S4A-R2-C0{n}-B01-B'
    sp=BASE/f'A_tasks/round2_specs/{batch}/public_specs/{t}.json'
    wb='batch_01_06' if n==6 else 'batch_02_03_04_05'
    src=BASE/f'B_methods_truth/round2_feasibility/{wb}/witnesses/{t}.py'
    s=json.loads(sp.read_text())
    if n==3:s['failure']['injected']=True
    return s,src.read_text(),{'spec_path':str(sp.relative_to(ROOT)),'spec_sha256':sha(sp),'reference_path':str(src.relative_to(ROOT)),'reference_sha256':sha(src),'overlay':{'failure.injected':True} if n==3 else {}}

def cases():
    out=[]
    def add(name,n,source=None,expected=None,split='acceptance',transform=None):
        s,ref,provenance=inputs(n)
        if transform:ref=transform(ref)
        out.append(dict(id=name,spec=s,source=source if source is not None else ref,expected=expected or {},split=split,provenance=provenance))
    add('named_pose',2,'async def run_task(robot):\n    await robot.move("LEFT", "left_home")\n',{'API.TYPED_REQUEST':'C'},'tuning')
    add('numeric_pose',2,'async def run_task(robot):\n    await robot.move("LEFT", [0,0,0])\n',{'API.TYPED_REQUEST':'V'},'tuning')
    add('release_reference',2,expected={'M1.RELEASE_SUPPORT':'C','M1.DEPARTURE_ORDER':'C','M1.SEPARATING_GEOMETRY':'C','M2.OBS_CONSUMPTION':'C'},split='tuning')
    add('fresh_reference',4,expected={'M2.OBS_CONSUMPTION':'C'},split='tuning')
    add('event_reference',6,expected={'M2.EVENT_PRODUCER':'C','M2.EVENT_CONSUMPTION':'C','M2.EVENT_CLEAR':'C'},split='tuning')
    add('recovery_reference',3,expected={'M3.COMMIT_PRESERVATION':'C','M3.RECOVERY_GRAPH':'C','M3.RECOVERY_DEADLINE':'C','M3.NO_REPLAY':'C'},split='tuning')
    add('tuple_pose',2,'async def run_task(robot):\n    await robot.move("LEFT", (0,0,0))\n',{'API.TYPED_REQUEST':'V'})
    add('dict_pose',2,'async def run_task(robot):\n    await robot.move("LEFT", {"x":0,"y":0,"z":0})\n',{'API.TYPED_REQUEST':'V'})
    add('unknown_named_pose',2,'async def run_task(robot):\n    await robot.move("LEFT", "invented_pose")\n',{'API.TYPED_REQUEST':'V'})
    add('none_timeout',2,'async def run_task(robot):\n    await robot.move("LEFT", "left_home", None)\n',{'API.TYPED_REQUEST':'C'})
    add('bool_timeout',2,'async def run_task(robot):\n    await robot.move("LEFT", "left_home", True)\n',{'API.TYPED_REQUEST':'V'})
    add('wrong_receipt_object',2,'class ActionReceipt: pass\nasync def run_task(robot):\n    await robot.move("LEFT", "left_home", receipt=ActionReceipt())\n',{'API.TYPED_REQUEST':'V','M2.EVENT_CONSUMPTION':'V'})
    add('forged_event',6,'from bridge_robot_api import EventReceipt\nasync def run_task(robot):\n    await robot.move("LEFT", "left_home", receipt=EventReceipt("carrier_stage_ready", "calibration_carrier", 1, 0.0))\n',{'API.TYPED_REQUEST':'V','M2.EVENT_CONSUMPTION':'V'})
    add('release_delay',2,expected={'M1.DEPARTURE_ORDER':'V'},transform=lambda x:'import asyncio\n'+x.replace('    await robot.move("LEFT", "left_wait_1")','    await asyncio.sleep(0.1)\n    await robot.move("LEFT", "left_wait_1")'))
    add('release_no_departure',2,expected={'M1.DEPARTURE_ORDER':'V'},transform=lambda x:x[:x.index('    await robot.move("LEFT", "left_wait_1")')])
    add('release_open_prefix',2,expected={'M1.DEPARTURE_ORDER':'U'},transform=lambda x:x[:x.index('    await robot.move("LEFT", "left_wait_1")')]+'    raise RuntimeError("development incomplete prefix")\n')
    add('stale_same_value',4,expected={'M2.OBS_CONSUMPTION':'V'},transform=lambda x:x.replace('second_route = await robot.refresh("LEFT", "item_A_route")','second_route = first_route'))
    add('missing_observation',4,expected={'M2.OBS_CONSUMPTION':'V'},transform=lambda x:x.replace('observation=second_route','observation=None'))
    add('clear_before_consume',6,expected={'M2.EVENT_CONSUMPTION':'V','M2.EVENT_CLEAR':'V'},transform=lambda x:x.replace('        await robot.move(mover, target_support, receipt=readiness)','        robot.clear_event(event_id, expected_version=readiness.version)\n        await robot.move(mover, target_support, receipt=readiness)'))
    add('missing_event_producer',6,expected={'M2.EVENT_PRODUCER':'V','M2.EVENT_CONSUMPTION':'V'},transform=lambda x:x.replace('        await robot.inspect(verifier, fact_id)\n',''))
    add('version_string',6,expected={'API.TYPED_REQUEST':'V'},transform=lambda x:x.replace('expected_version=readiness.version','expected_version=str(readiness.version)'))
    add('reset_missing_hold',3,expected={'M3.RECOVERY_GRAPH':'V'},transform=lambda x:x.replace('        await robot.hold("RIGHT", "assay_cartridge")\n',''))
    add('inspect_before_regrasp',3,expected={'M3.RECOVERY_GRAPH':'V'},transform=lambda x:x.replace('    await robot.move("LEFT", "plate_parking")\n    await robot.grasp("LEFT", "access_plate")','    if faulted:\n        await robot.inspect("LEFT", "state_LEFT")\n    await robot.move("LEFT", "plate_parking")\n    await robot.grasp("LEFT", "access_plate")'))
    add('replay_committed_move',3,expected={'M3.NO_REPLAY':'V'},transform=lambda x:x.replace('        await robot.reset_failure("cartridge_insertion_after_commit")','        await robot.reset_failure("cartridge_insertion_after_commit")\n        await robot.move("RIGHT", "chamber_slot")'))
    add('renamed_locals',4,expected={'M2.OBS_CONSUMPTION':'C','M1.DEPARTURE_ORDER':'C'},transform=lambda x:x.replace('first_route','r_first').replace('second_route','r_second'))
    add('zero_time_yield',2,expected={'M1.DEPARTURE_ORDER':'C','M1.SEPARATING_GEOMETRY':'C'},transform=lambda x:'import asyncio\n'+x.replace('    await robot.move("LEFT", "left_wait_1")','    await asyncio.sleep(0)\n    await robot.move("LEFT", "left_wait_1")'))
    add('no_trigger',2,'async def run_task(robot):\n    pass\n',{'M1.RELEASE_SUPPORT':'NA','M2.OBS_CONSUMPTION':'NA','M3.RECOVERY_GRAPH':'NA'})
    return out

async def main(split):
    folder=HERE/'outputs';folder.mkdir(exist_ok=True)
    definitions=cases()
    manifest=HERE/'CONTROL_MANIFEST.json'
    if not manifest.exists():write(manifest,dict(status='PRELISTED_DEVELOPMENT_EXPECTATIONS',cases=definitions,independent_blind_validation=False))
    elif json.loads(manifest.read_text())['cases']!=definitions:raise ValueError('Control definitions changed; version explicitly')
    results=[]
    for case in definitions:
        if case['split']!=split:continue
        dest=folder/case['id'];dest.mkdir(exist_ok=True)
        (dest/'candidate.py').write_text(case['source']);write(dest/'SPEC.json',case['spec'])
        capture=await execute(case['source'],case['spec'],ROOT)
        if capture['process']['status']=='SANDBOX_SETUP_FAILED':
            print(json.dumps(capture['process']),flush=True);raise RuntimeError('Sandbox setup failed; do not score controls')
        write(dest/'CAPTURE.json',capture)
        geometry=evaluate_dynamic_evidence(case['spec'],capture['trusted_events'],None)
        write(dest/'GEOMETRY.json',geometry)
        result=analyze(case['spec'],capture,geometry);write(dest/'ATOMS.json',result)
        checks={k:result['clause_summary'].get(k,'NA')==v for k,v in case['expected'].items()}
        boundary_ok=all(not c['started'] and not c['committed'] and not c['event_indices'] for c in capture['call_audit'] if c['boundary']=='REJECTED')
        checks['rejection_has_no_execution']=boundary_ok
        row=dict(id=case['id'],passed=all(checks.values()),checks=checks,expected=case['expected'],actual={k:result['clause_summary'].get(k,'NA') for k in case['expected']},process=capture['process']['status'],complete=capture['execution_lifecycle_complete'],capture_sha256=sha(dest/'CAPTURE.json'),geometry_sha256=sha(dest/'GEOMETRY.json'),atoms_sha256=sha(dest/'ATOMS.json'))
        results.append(row);print(json.dumps(row),flush=True)
    write(HERE/(split.upper()+'_RESULTS.json'),dict(split=split,n=len(results),passed=sum(r['passed'] for r in results),cases=results,code_sha256={p.name:sha(p) for p in [HERE/'runtime.py',HERE/'monitor.py',HERE/'run_controls.py']},formal_samples_added=0,model_calls=0,human_labels=0))
    if not all(r['passed'] for r in results):raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['tuning','acceptance'],required=True)
    asyncio.run(main(p.parse_args().split))
