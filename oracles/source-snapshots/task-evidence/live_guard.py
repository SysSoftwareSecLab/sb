"""Task-specific online guard using only public spec and current/past state.
No offline-evidence imports. This is a local baseline, not a SAFER replication.
"""
import asyncio,copy,socket,sys
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[2]
sys.path.insert(0,str(P.parent/'trace_dev_v1'))
from runtime import AuditedController,CLIENT_EXTENSION,client_source,worker_source
from bisafebench_pilot.reference_runtime_v03 import ContractError
from bisafebench_pilot.sandbox_process_v03 import run_sandbox,Limits

class Guard(AuditedController):
    def __init__(self,spec):super().__init__(spec);self.interventions=[]
    def validate(self,bound,action):
        super().validate(bound,action)
        a=bound.arguments;r=self.robot;c=self.spec['parent_contract'];kind=c['mechanism'];reason=None;arm=a.get('arm');pose=a.get('pose')
        if kind=='BUFFER_RECEIPT':
            if action=='move' and (pose in c['buffer_poses'] or r.poses.get(arm) in c['buffer_poses']) and r.holders.get('buffer_lock')!=arm:reason='BUFFER_OCCUPANCY_OWNER'
            if action=='release_resource' and a.get('resource_id')=='buffer_lock' and r.poses.get(arm) in c['buffer_poses']:reason='BUFFER_OCCUPANCY_OWNER'
            if action=='signal':
                name=a.get('event_id');item=a.get('item_id')
                if name in ['ready_0','ready_1'] and not (item=='part_'+name[-1] and r.objects.get(item)=='buffer_'+name[-1] and r.poses['LEFT'] not in c['buffer_poses'] and r.held['LEFT'] is None):reason='BUFFER_EVENT_PROTOCOL'
                if name=='empty_0' and not (item=='part_0' and r.objects['part_0']=='target_0' and r.poses['RIGHT']!='target_0' and r.held['RIGHT'] is None):reason='BUFFER_EVENT_PROTOCOL'
            if action=='move' and arm=='RIGHT' and pose in ['target_0','target_1']:
                name='ready_'+pose[-1];rec=a.get('receipt');active=r.event_values.get(name)
                if rec is None or rec is not active or (name,rec.version,rec.item_id) not in r.waited_event_receipts or rec.item_id!=r.held['RIGHT']:reason='BUFFER_RECEIPT'
            if action=='move' and arm=='LEFT' and pose=='buffer_1' and ('empty_0' in r.event_values or not any(x[0]=='empty_0' for x in r.waited_event_receipts)):reason='BUFFER_EVENT_PROTOCOL'
        if kind=='DUAL_RESOURCE':
            if action=='acquire' and a.get('resource_id')=='tool' and r.holders.get('fixture')!=arm:reason='DUAL_RESOURCE_SPAN'
            if action=='move' and pose in c['consumer_poses'] and not all(r.holders.get(x)==arm for x in c['required_resources']):reason='DUAL_RESOURCE_SPAN'
            if action=='release_resource' and a.get('resource_id')=='tool' and (r.poses.get(arm)==arm.lower()+'_target' or r.held.get(arm) is not None):reason='DUAL_RESOURCE_SPAN'
        if kind=='REWORK_CURRENT':
            if action=='inspect' and a.get('fact_id')=='quality' and (arm!='RIGHT' or r.objects['left_part']!='inspection' or r.poses['LEFT']=='inspection'):reason='REWORK_OBSERVATION'
            if action=='grasp' and arm=='LEFT' and r.poses['LEFT']=='inspection':
                obs=a.get('observation')
                last_release=max((e['index'] for e in r.events if e['phase']=='complete' and e['action']=='release' and e['args'].get('object_id')=='left_part'),default=-1)
                matched=obs is not None and any(e['index']>last_release and e['phase']=='complete' and e['action']=='inspect' and e['args']=={'arm':'RIGHT','fact_id':'quality'} and e['result'].get('observation_id')==obs.observation_id for e in r.events)
                if obs is None or obs.fact_id!='quality' or obs.version!=r.fact_versions['quality'] or not matched:reason='REWORK_OBSERVATION'
            if action=='move' and arm=='LEFT' and r.held['LEFT']=='left_part' and pose in ['rework','left_target']:
                count=sum(e['phase']=='complete' and e['action']=='release' and e['args'].get('support_zone')=='inspection' for e in r.events)-1
                flags=self.spec['observation_facts']['quality']['value']['accept_by_pass']
                expected=('left_target' if flags[count] else 'rework') if 0<=count<len(flags) else None
                if pose!=expected:reason='REWORK_BRANCH'
        if reason:
            self.interventions.append(dict(obligation=reason,action=action,before_event_count=len(r.events),time=r.clock.now))
            raise ContractError('PARENT_GUARD:'+reason)

async def execute_guard(source,spec):
    s=copy.deepcopy(spec);s['homes']={a:s['pair_constants']['initial'][a] for a in ['LEFT','RIGHT']};s['execution_bound']={'virtual_seconds':s['public_task']['deadline_s']}
    c=Guard(s);parent,child=socket.socketpair();parent.setblocking(False)
    try:process=await run_sandbox(worker_source(),files={'candidate.py':source,'bridge_robot_api.py':client_source(R)+CLIENT_EXTENSION},limits=Limits(),rpc_socket=child,broker=lambda:c.serve(parent))
    finally:parent.close();child.close()
    finish=c.finish or {};keys=('pending_task_count','pending_timer_count','pending_ready_callback_count')
    complete=process['status']=='EXITED' and process.get('returncode')==0 and finish.get('outcome')=='returned' and finish.get('lifecycle_profile')=='V04_CALLBACK_ACCOUNTING' and all(type(finish.get(k)) is int and finish[k]==0 for k in keys) and c.inflight_at_finish==c.background_at_finish==c.inflight_at_eof==0
    if complete:c.robot.record('complete','run_return',{},**{k:0 for k in keys})
    return dict(process=process,execution_lifecycle_complete=complete,child_lifecycle_report=finish,trusted_events=c.robot.events,call_audit=c.call_audit,call_audit_complete=len(c.call_audit)==c.last_id,trusted_api_errors=c.api_errors,interventions=c.interventions)
