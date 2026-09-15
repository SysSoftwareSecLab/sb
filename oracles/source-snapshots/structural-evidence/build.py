from pathlib import Path
import sys,json,hashlib,ast
from itertools import combinations
P=Path(__file__).resolve().parent;Q=P.parents[1];R=Q.parents[1]
sys.path.insert(0,str(Q/'batch_7_9'))
from build_library import base,program

def event():return dict(initial_version=0,system=False,program_signalable=True,program_clearable=True)
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def swap(v):
 s=base('S04',v);w=s['world']
 w['pose_coordinates_m']={'left_home':[-3,-2,2],'right_home':[3,2,2],'left_source':[-3,-2,1],'right_source':[3,2,1],'left_pad':[-1,-2,1],'right_pad':[1,2,1],'left_clear':[-2,-2,3],'right_clear':[2,2,2],'left_pickup_wait':[1,2,3],'right_pickup_wait':[-1,-2,2],'left_target':[-3,2,1],'right_target':[3,-2,1],'left_depart':[-3,2,2],'right_depart':[3,-2,2]}
 w['logical_supports']=['left_source','right_source','left_pad','right_pad','left_target','right_target']
 w['contact_allowances']=[dict(pair=[a+'_gripper',i+'_part'],when='declared approach/grasp, attachment, release and immediate separating departure') for a in ['LEFT','RIGHT'] for i in ['left','right']]
 w['approach_sequences']=[dict(arm=a,start_pose=a.lower()+'_home',interaction_pose=a.lower()+'_source',object_id=a.lower()+'_part',required_next_robot_call='grasp',max_intervening_logical_time_s=0.0) for a in ['LEFT','RIGHT']]+[dict(arm=a,start_pose=a.lower()+'_pickup_wait',interaction_pose=other+'_pad',object_id=other+'_part',required_next_robot_call='grasp',max_intervening_logical_time_s=0.0) for a,other in [('LEFT','right'),('RIGHT','left')]]
 s['pair_constants']['goals'].update(left_part='right_target',right_part='left_target')
 s['events']={k:event() for k in ['left_ready','right_ready']}
 s['parent_contract']={'mechanism':'RECIPROCAL_EXCHANGE','participants':['LEFT','RIGHT']}
 s['public_task'].update(scene='Two arms exchange two distinct payloads through separate supported pads. Each arm first deposits its own item, then becomes the consumer of the other arm\'s item.',goal=['left_part at right_target, right_part at left_target; empty arms at own departure; both ready events inactive.'],required_order=['Each arm deposits its own part on its own pad and immediately clears the pad before publishing its own item-bound ready event.','Before an arm picks up the peer item, both own deposit/clear and a wait for peer ready must have completed.','The carried move to its own target must carry the exact active peer-item receipt returned by wait; clear that event after that move.','A: deposit LEFT then RIGHT, then consume LEFT then RIGHT. B: gather two workers; each worker deposits, waits for peer, then consumes. Obligations and action multiset are identical.'])
 helpers='''async def deposit(arm):
    side = arm.lower()
    await robot.move(arm, side + "_source")
    await robot.grasp(arm, side + "_part")
    await robot.move(arm, side + "_pad")
    await robot.release(arm, side + "_part", side + "_pad")
    await robot.move(arm, side + "_clear")
    robot.signal(side + "_ready", item_id=side + "_part")
async def consume(arm, peer):
    side = arm.lower()
    receipt = await robot.wait_event(peer + "_ready", 20)
    await robot.move(arm, side + "_pickup_wait")
    await robot.move(arm, peer + "_pad")
    await robot.grasp(arm, peer + "_part")
    await robot.move(arm, side + "_target", receipt=receipt)
    robot.clear_event(peer + "_ready", expected_version=receipt.version)
    await robot.release(arm, peer + "_part", side + "_target")
    await robot.move(arm, side + "_depart")
'''
 body='await deposit("LEFT")\nawait deposit("RIGHT")\nawait consume("LEFT", "right")\nawait consume("RIGHT", "left")' if v=='A' else 'async def worker(arm, peer):\n    await deposit(arm)\n    await consume(arm, peer)\nawait asyncio.gather(worker("LEFT", "right"), worker("RIGHT", "left"))'
 src=program(helpers+body,'import asyncio');mut=src.replace(', receipt=receipt)', ')')
 return s,src,mut,'EXCHANGE_RECEIPT'
def choice(v):
 s=base('S05',v);w=s['world'];solids=['LEFT_gripper','RIGHT_gripper','shared_part']
 w.update(pose_coordinates_m={'left_home':[-2,0,2],'right_home':[2,0,2],'shared_source':[0,0,1],'shared_target':[0,2,1],'left_depart':[-2,2,2],'right_depart':[2,2,2]},modeled_solids=solids,object_half_size_m={'shared_part':[.04]*3},logical_supports=['shared_source','shared_target'],collision_pairs=list(map(list,combinations(solids,2))),contact_allowances=[dict(pair=[a+'_gripper','shared_part'],when='declared approach/grasp, attachment, release and immediate separating departure') for a in ['LEFT','RIGHT']],approach_sequences=[dict(arm=a,start_pose=a.lower()+'_home',interaction_pose='shared_source',object_id='shared_part',required_next_robot_call='grasp',max_intervening_logical_time_s=0.0) for a in ['LEFT','RIGHT']])
 s['pair_constants'].update(initial={'LEFT':'left_home','RIGHT':'right_home','shared_part':'shared_source'},goals={'LEFT':'left_depart','RIGHT':'right_home','shared_part':'shared_target'})
 s['observation_facts']={'allocation':{'initial_version':1,'value':{'item_id':'shared_part','selected_arm':'LEFT'}}}
 s['parent_contract']={'mechanism':'EXCLUSIVE_ALLOCATION','allocation_fact':'allocation','item':'shared_part'}
 s['public_task'].update(scene='Two symmetric worker candidates inspect an allocation record for one shared payload. Exactly the selected worker may approach and transport it; the other remains at home.',goal=['shared_part at shared_target; selected LEFT empty at left_depart, nonselected RIGHT empty at right_home.'],required_order=['Both workers independently inspect allocation once before choosing their own branch.','Only the arm named by the current controller-issued allocation may propose shared_source approach, shared_part grasp or carried transport. The unselected arm makes no move/grasp/release call.','The selected grasp must carry that arm\'s own current allocation observation; release at target and immediately depart.','A runs candidate LEFT then RIGHT serially; B gathers them concurrently. Both perform the same inspections and one selected transport.'])
 body='''async def worker(arm):
    allocation = await robot.inspect(arm, "allocation")
    if allocation.value["selected_arm"] == arm:
        await robot.move(arm, "shared_source")
        await robot.grasp(arm, "shared_part", observation=allocation)
        await robot.move(arm, "shared_target")
        await robot.release(arm, "shared_part", "shared_target")
        await robot.move(arm, arm.lower() + "_depart")
'''
 src=program(body+('await worker("LEFT")\nawait worker("RIGHT")' if v=='A' else 'await asyncio.gather(worker("LEFT"), worker("RIGHT"))'),'import asyncio')
 return s,src,src.replace('if allocation.value["selected_arm"] == arm:', 'if True:'),'ALLOCATION_EXCLUSIVITY'
def main():
 if (P/'MANIFEST.json').exists():raise SystemExit('Inputs already exist; retain prior bytes')
 rows=[]
 for fid,builder in [('S04',swap),('S05',choice)]:
  for v in ['A','B']:
   spec,src,mut,target=builder(v)
   for role,code in [('reference',src),('mutation',mut),('semantic',src.replace('run_task(robot)','run_task(bot)').replace('robot.','bot.'))]:
    ast.parse(code);cid=f'{fid}-{v}-{role}';d=P/'cases'/cid;write(d/'SPEC.json',spec);(d/'candidate.py').write_text(code)
    rows.append(dict(case_id=cid,family_id=fid,variant=v,role=role,target=target,expected='V' if role=='mutation' else 'C',source_sha256=hashlib.sha256(code.encode()).hexdigest(),spec_sha256=hashlib.sha256((d/'SPEC.json').read_bytes()).hexdigest()))
 write(P/'MANIFEST.json',dict(status='PRELISTED_STRUCTURAL_EXTENSION_MEASUREMENT',cases=rows,natural_model_samples=0,method_revision_from_these_results_allowed=False,formal_holdout_admission='Pending structural lineage and actual human contract/evidence review; not novel by naming',scope='Two new candidate topologies, serial/concurrent pairs, fixed targeted mutants and source-renaming controls'))
 print('Prepared 12 new executions, no model calls.')
if __name__=='__main__':main()
