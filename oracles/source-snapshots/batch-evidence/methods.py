"""Development baselines. No offline truth imports, no future trace access."""
import ast
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'trace_dev_v1'))
from runtime import AuditedController
from bisafebench_pilot.reference_runtime_v03 import ContractError

class GuardedController(AuditedController):
    def __init__(self,spec):super().__init__(spec);self.interventions=[]
    def validate(self,bound,action):
        super().validate(bound,action)
        p=bound.arguments;contract=self.spec.get('development_contract',{});reason=None
        if action=='grasp' and contract.get('observation') and p.get('object_id')==contract['observation']['object_id']:
            obs=p.get('observation');fact=contract['observation']['fact_id']
            if obs is None or obs.fact_id!=fact or obs.version!=self.robot.fact_versions[fact]:reason='OBS_CURRENT'
        if action=='move' and p.get('receipt') is not None and contract.get('join_events'):
            for name in contract['join_events']:
                active=self.robot.event_values.get(name)
                if active is None or (name,active.version,active.item_id) not in self.robot.waited_event_receipts:reason='EVENT_JOIN'
        recovery=contract.get('recovery',{})
        if action=='release_resource' and recovery.get('preserve_resource')==p.get('resource_id') and self.robot.failure_active:reason='RECOVERY_RESOURCE'
        if action=='move' and recovery:
            # Past committed receipt, not inspection of future candidate actions.
            for e in self.robot.events:
                if e['phase']=='fault' and e.get('outcome')=='AFTER_COMMIT' and e['args'].get('arm')==p.get('arm') and e['args'].get('pose')==p.get('pose'):reason='RECOVERY_SELECTION'
        if action=='release' and recovery:
            if self.robot.poses.get(p.get('arm'))!=p.get('support_zone'):reason='RECOVERY_SELECTION'
        if action=='reset_failure' and recovery:
            if self.robot.post_fault_inspections!={'LEFT','RIGHT'} or self.robot.post_fault_holds!={'LEFT','RIGHT'} or self.robot.stopped!={'LEFT','RIGHT'}:reason='RECOVERY_PREREQUISITES'
        if reason:
            self.interventions.append(dict(obligation=reason,time=self.robot.clock.now,before_event_count=len(self.robot.events),action=action))
            raise ContractError('DEVELOPMENT_GUARD:'+reason)

def plan_check(source,obligation):
    tree=ast.parse(source);functions=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='run_task']
    if len(functions)!=1:return dict(status='UNSUPPORTED',reason='entry')
    body=functions[0].body
    if any(isinstance(n,(ast.If,ast.For,ast.While,ast.Try,ast.AsyncFunctionDef,ast.FunctionDef)) for n in body):return dict(status='UNSUPPORTED',reason='branch/loop/exception/concurrent helper projection not soundly implemented')
    ops=[]
    for node in body:
        value=getattr(node,'value',None)
        if isinstance(value,ast.Await):value=value.value
        if not isinstance(value,ast.Call):continue
        if isinstance(value.func,ast.Attribute):
            args=[]
            for arg in value.args:
                args.append(arg.value if isinstance(arg,ast.Constant) else '?')
            ops.append((value.func.attr,args,node.lineno))
    if obligation=='RELEASE_DEPARTURE':
        for i,(name,args,line) in enumerate(ops):
            if name=='release':
                later=ops[i+1:];next_arm=next((x for x in later if x[1] and x[1][0]==args[0]),None)
                delay=any(x[0]=='sleep' and x[1] and isinstance(x[1][0],(float,int)) and x[1][0]>0 for x in later[:later.index(next_arm)+1] if next_arm) if next_arm else False
                if delay or not next_arm or next_arm[0]!='move':return dict(status='FLAG',line=line,reason='literal departure gap/order')
        return dict(status='NO_FINDING',reason='literal request order only; geometry and coroutine timing unproved')
    if obligation=='EVENT_JOIN':
        wait={a[0] for n,a,l in ops if n=='wait_event' and a}
        return dict(status='NO_FINDING' if {'left_ready','right_ready'}<=wait else 'FLAG',reason='literal two-wait presence only; issuance/currentness unproved')
    return dict(status='UNSUPPORTED',reason='target obligation outside literal-plan checker')
