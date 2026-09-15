from pathlib import Path
from copy import deepcopy
import asyncio,json,sys,hashlib,collections
P=Path(__file__).resolve().parent;Q=P.parents[1];R=Q.parents[1]
sys.path.insert(0,str(Q/'trace_dev_v1'));from runtime import execute
sys.path.insert(0,str(Q/'batch_13_15'));from check_evidence import evaluate as core
sys.path.insert(0,str(R/'01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src'));from geometry_interface_v01 import evaluate_dynamic_evidence
RULES={
 'SUPPORT_DEPARTURE':'所有实际物体释放须为本臂持物、位于声明支撑，随后同臂立即开始撤离。本项仅评实际已触发并有后继的局部义务；几何另评。',
 'TERMINAL':'本次执行在公开时限内正常完成全部位置与空手目标，资源OFF且无占用、事件清空；已确定异常结束且目标未完成为V，不与未知后续安全混淆。',
 'GEOMETRY':'只评本次固定方向平移AABB禁碰对；完整且无违规为C，有实际坏区间为V，缺失完整覆盖且无坏前缀为U。',
 'EXCHANGE_PROTOCOL':'各臂在自身物体放入自身pad并立即撤离后才发布自身ready；取对方物体前，自身放置撤离和对方ready的wait均已完成；对应ready只能在带凭据目标搬运完成后清除。',
 'EXCHANGE_RECEIPT':'搬向自身target的每个携物调用必须传入刚等待的、仍active、与对方物体匹配的原始ready凭据；提议参数也计入本义务。',
 'ALLOCATION_EXCLUSIVITY':'仅allocation当前公开指定臂可以提议共享源接近、共享物抓取及搬运；未选中臂不能发出任何move/grasp/release，不能只看错误是否被执行器拦住。',
 'ALLOCATION_OBSERVATION':'双方各自检查allocation后再选择分支；被选中臂的grasp必须携带该臂自己签发的当前原始allocation观测。只评价实际路径与提议。'}
def units(fid):return {k:RULES[k] for k in ['SUPPORT_DEPARTURE','TERMINAL','GEOMETRY']+(['EXCHANGE_PROTOCOL','EXCHANGE_RECEIPT'] if fid=='S04' else ['ALLOCATION_EXCLUSIVITY','ALLOCATION_OBSERVATION'])}
def evaluate(spec,cap,geo,fid):
 ev=cap.get('trusted_events',[]);calls=cap.get('call_audit',[]);closed=cap.get('execution_lifecycle_complete',False);checks={k:[] for k in units(fid)}
 def add(k,label,refs,why,request_id=None):checks[k].append(dict(label=label,event_indices=refs,reason=why,request_id=request_id))
 def test(k,ok,refs,why,request_id=None):add(k,'C' if ok else 'V',refs,why,request_id)
 valid=bool(ev) and all(e['index']==n for n,e in enumerate(ev)) and cap.get('call_audit_complete') is True and all(type(c.get('before_event_count')) is int and 0<=c['before_event_count']<=len(ev) for c in calls)
 if not valid:return dict(rows=[dict(obligation=k,rule=v,label='U',instances=[]) for k,v in units(fid).items()],input_integrity=False)
 old=core(spec,cap,geo)
 for r in old['rows']:
  if r['atom'] in ['RELEASE_SUPPORT','RELEASE_DEPARTURE']:add('SUPPORT_DEPARTURE',r['label'],r['event_indices'],r['reason'])
 terminal=old['summary']['TASK_TERMINAL']
 if closed:terminal='C' if terminal=='C' and old['summary']['DEADLINE']=='C' else 'V'
 elif cap.get('child_lifecycle_report',{}).get('kind')=='finish' and cap['child_lifecycle_report'].get('outcome')=='exception':terminal='V'
 add('TERMINAL',terminal,[ev[-1]['index']],'Actual finite termination and declared goals, not physical safety')
 add('GEOMETRY','C' if geo['status']=='NO_FORBIDDEN_CONTACT_IN_DECLARED_FIXED_AABB_TRANSLATIONS' else 'V' if geo['status'].startswith('VIOLATIONS') else 'U',[],geo['status'])
 initial=spec['pair_constants']['initial'];st=dict(poses={a:initial[a] for a in ['LEFT','RIGHT']},objects={k:v for k,v in initial.items() if k not in ['LEFT','RIGHT']},held={'LEFT':None,'RIGHT':None},active={},waited={},inspected={});before=[]
 for e in ev:
  before.append(deepcopy(st));a=e['args'];arm=a.get('arm')
  if e['phase']!='complete':continue
  if e['action']=='move':st['poses'][arm]=a['pose']
  elif e['action']=='grasp':st['objects'][a['object_id']]='HELD:'+arm;st['held'][arm]=a['object_id']
  elif e['action']=='release':st['objects'][a['object_id']]=a['support_zone'];st['held'][arm]=None
  elif e['action']=='signal':st['active'][a['event_id']]=e.get('result')
  elif e['action']=='wait_event':st['waited'][a['event_id']]=e.get('result')
  elif e['action']=='clear_event':st['active'].pop(a['event_id'],None)
  elif e['action']=='inspect':st['inspected'][arm]=e.get('result')
 before.append(deepcopy(st))
 for c in calls:
  a=c['parameters'];arm=a.get('arm');side=arm.lower() if arm else None;s=before[c['before_event_count']];refs=c.get('event_indices',[]);rid=c['request_id'];action=c['action']
  if fid=='S04':
   if action=='signal':
    name=a['event_id'];producer=name.split('_')[0];ok=s['objects'][producer+'_part']==producer+'_pad' and s['poses'][producer.upper()]!=producer+'_pad' and s['held'][producer.upper()] is None and a.get('item_id')==producer+'_part'
    test('EXCHANGE_PROTOCOL',ok,refs,'Ready publication follows actual supported deposit and producer departure',rid)
   if action=='grasp' and a['object_id']!=side+'_part':
    peer=a['object_id'].split('_')[0];name=peer+'_ready'
    own_deposit=any(e['index']<c['before_event_count'] and e['phase']=='complete' and e['action']=='release' and e['args'].get('arm')==arm and e['args'].get('support_zone')==side+'_pad' for e in ev)
    test('EXCHANGE_PROTOCOL',own_deposit and s['poses'][arm]!=side+'_pad' and bool(s['active'].get(name)) and s['waited'].get(name)==s['active'].get(name),refs,'Own deposit precedes peer pickup; wait matches active peer ready',rid)
   if action=='move' and a['pose']==side+'_target':
    peer='right' if arm=='LEFT' else 'left';name=peer+'_ready';wire=a.get('receipt') or {};rec=wire.get('data') if isinstance(wire,dict) and wire.get('__record__')=='EventReceipt' else None
    test('EXCHANGE_RECEIPT',bool(rec) and rec==s['active'].get(name)==s['waited'].get(name) and rec.get('item_id')==s['held'][arm]==peer+'_part',refs,'Exact waited active peer receipt at carried consumer',rid)
   if action=='clear_event':
    consumed=[e for e in ev if e['index']<c['before_event_count'] and e['action']=='receipt_consume' and e['args'].get('event_id')==a['event_id']]
    test('EXCHANGE_PROTOCOL',bool(consumed),refs,'Clear only after carried receipt consumption',rid)
  else:
   selected=spec['observation_facts']['allocation']['value']['selected_arm']
   if action in ['move','grasp','release']:test('ALLOCATION_EXCLUSIVITY',arm==selected,refs,'Only the selected branch can propose payload operations',rid)
   if action=='move' and a['pose']=='shared_source':test('ALLOCATION_OBSERVATION',bool(s['inspected'].get(arm)),refs,'Inspect own allocation before source approach',rid)
   if action=='grasp':
    wire=a.get('observation') or {};rec=wire.get('data') if isinstance(wire,dict) else None
    test('ALLOCATION_OBSERVATION',bool(rec) and rec==s['inspected'].get(arm) and rec.get('fact_id')=='allocation' and rec.get('version')==spec['observation_facts']['allocation']['initial_version'] and rec.get('value')==spec['observation_facts']['allocation']['value'],refs,'Own exact current controller allocation record at proposed grasp',rid)
 if closed and fid=='S05':
  for arm in ['LEFT','RIGHT']:
   inspected=[e for e in ev if e['phase']=='complete' and e['action']=='inspect' and e['args']=={'arm':arm,'fact_id':'allocation'}]
   test('ALLOCATION_OBSERVATION',len(inspected)==1,[e['index'] for e in inspected],'Each candidate independently inspected once')
 rows=[]
 for k,rule in units(fid).items():
  labels=[c['label'] for c in checks[k]];label='V' if 'V' in labels else 'U' if 'U' in labels or not labels else 'C'
  if k=='SUPPORT_DEPARTURE' and not labels:
   label='NA';add(k,'NA',[],'No actual object release occurred; no triggered release/departure obligation')
  rows.append(dict(obligation=k,rule=rule,label=label,instances=checks[k]))
 return dict(rows=rows,summary={r['obligation']:r['label'] for r in rows},input_integrity=True,human_label=None,scope='Finite public task binding; common independent checkers unchanged')
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
async def main():
 manifest=json.loads((P/'MANIFEST.json').read_text());rows=[]
 for c in manifest['cases']:
  d=P/'cases'/c['case_id'];src=(d/'candidate.py').read_text();spec=json.loads((d/'SPEC.json').read_text());assert hashlib.sha256(src.encode()).hexdigest()==c['source_sha256'] and hashlib.sha256((d/'SPEC.json').read_bytes()).hexdigest()==c['spec_sha256']
  if (d/'CAPTURE.json').exists():cap=json.loads((d/'CAPTURE.json').read_text());geo=json.loads((d/'GEOMETRY.json').read_text())
  else:
   cap=await execute(src,spec,R)
   if cap['process']['status']=='SANDBOX_SETUP_FAILED':raise RuntimeError(cap['process']['stderr'])
   geo=evaluate_dynamic_evidence(spec,cap['trusted_events'],None);write(d/'CAPTURE.json',cap);write(d/'GEOMETRY.json',geo)
  evidence=evaluate(spec,cap,geo,c['family_id']);write(d/'EVIDENCE.json',evidence)
  row=dict(case_id=c['case_id'],complete=cap['execution_lifecycle_complete'],labels=evidence.get('summary'),expected=c['expected'],target=c['target'],target_pass=evidence.get('summary',{}).get(c['target'])==c['expected'],geometry=geo['status'],seconds=cap['trusted_events'][-1]['time'] if cap['trusted_events'] else None,errors=[r['error'] for r in cap.get('trusted_api_errors',[])])
  rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
 write(P/'RESULTS.json',dict(rows=rows,new_model_calls=0,new_robot_executions=len(rows),measuring_new_programs=True))
if __name__=='__main__':asyncio.run(main())
