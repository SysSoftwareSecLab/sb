"""Prospective typed boundary. Development only; frozen H execution untouched."""
import asyncio
from contextvars import ContextVar
from copy import deepcopy
import inspect
import math
import socket
from bisafebench_pilot.h_candidate_runtime import HRobot, H_PUBLIC
from bisafebench_pilot.forward_calibration_v01.forward_controller_v01_candidate import ForwardController
from bisafebench_pilot.forward_calibration_v01.forward_runtime_v01_candidate import CANDIDATE_TASK_ID, Observation
from bisafebench_pilot.reference_runtime_v03 import EventReceipt, ContractError, MotionFault
from bisafebench_pilot.sandbox_controller_v03 import ProtocolError
from bisafebench_pilot.sandbox_process_v03 import Limits, run_sandbox
from bisafebench_pilot.stage6_runtime_compat_v1 import client_source, worker_source

REQUEST = ContextVar('quality_request', default=None)
PROFILE = 'QUALITY_TYPED_TRACE_DEV_V1'

class AuditedRobot(HRobot):
    def record(self, phase, action, args, **extra):
        super().record(phase, action, args, request_id=REQUEST.get(), **extra)

class AuditedController(ForwardController):
    def __init__(self, spec):
        super().__init__(spec, {}, allowed_methods=set(H_PUBLIC), robot_factory=AuditedRobot, public_methods=H_PUBLIC)
        self.call_audit = []

    def validate(self, bound, action):
        world = self.spec['world']
        domains = {'arm': {'LEFT','RIGHT'}, 'pose': set(world['pose_coordinates_m']),
                   'support_zone': set(world.get('logical_supports', world.get('supports',[]))),
                   'object_id': set(self.robot.objects), 'resource_id': set(self.spec.get('resources',{})),
                   'fact_id': set(self.spec.get('observation_facts',{})) | set(self.spec.get('state_facts',{})),
                   'event_id': set(self.spec.get('events',{}))}
        for name, value in bound.arguments.items():
            if name == 'self': continue
            if name == 'timeout_s':
                if value is None and action == 'move': continue
                if type(value) not in (int,float) or not math.isfinite(value): raise ContractError('TYPE: finite timeout required')
                lo,hi = self.spec['pair_constants']['explicit_move_timeout_range_s'] if action=='move' else (0,120)
                if not lo <= value <= hi: raise ContractError('DOMAIN: timeout outside public range')
            elif name == 'expected_version':
                if type(value) is not int or value < 1: raise ContractError('TYPE: positive integer version required')
            elif name in ('observation','receipt'):
                expected = Observation if name=='observation' else EventReceipt
                if value is not None and not isinstance(value, expected): raise ContractError('TYPE: issued '+expected.__name__+' required')
            else:
                if value is None and name == 'item_id': continue
                if type(value) is not str or not 1 <= len(value) <= 128: raise ContractError('TYPE: nonempty named ID required for '+name)
                if name in domains and value not in domains[name]: raise ContractError('DOMAIN: undeclared '+name)
                if name=='item_id' and value not in self.robot.objects: raise ContractError('DOMAIN: undeclared item_id')
                if name=='failure_id' and value != self.spec.get('failure',{}).get('failure_id'): raise ContractError('DOMAIN: undeclared failure_id')
                if name=='mode' and value not in ('OFF','LEFT_PROFILE','RIGHT_PROFILE'): raise ContractError('DOMAIN: undeclared mode')

    async def operation(self, message):
        rid, action = message['id'], message['action']
        row = dict(request_id=rid, action=action, proposed_at=self.robot.clock.now,
                   before_event_count=len(self.robot.events), wire_args=deepcopy(message.get('args')),
                   wire_kwargs=deepcopy(message.get('kwargs')), boundary='PROPOSED')
        self.call_audit.append(row)
        task = message.get('caller_task_id')
        token = CANDIDATE_TASK_ID.set(task if isinstance(task,str) and task.startswith('candidate_task_') and len(task)<=128 else None)
        reqtoken = REQUEST.set(rid)
        try:
            if action not in self.allowed_methods: raise ContractError('DOMAIN: undeclared method')
            # Preserve raw bound parameters, including rejected/forged record arguments.
            sig = inspect.signature(self.public_methods[action])
            raw = sig.bind(self.robot,*message.get('args',[]),**message.get('kwargs',{}))
            raw.apply_defaults()
            row['parameters'] = {k:deepcopy(v) for k,v in raw.arguments.items() if k!='self'}
            args, kwargs = self.decode(message.get('args')), self.decode(message.get('kwargs'))
            bound = sig.bind(self.robot,*args,**kwargs); bound.apply_defaults()
            self.validate(bound, action)
            row['boundary'] = 'ACCEPTED'
            result = self.public_methods[action](*bound.args,**bound.kwargs)
            if inspect.isawaitable(result): result = await result
            response = dict(kind='result',id=rid,result=self.encode(result))
            row['outcome'] = 'RETURNED'
        except (ContractError, MotionFault, TimeoutError, TypeError, KeyError, ValueError, ProtocolError, asyncio.CancelledError) as exc:
            error = dict(type=type(exc).__name__,message=str(exc)[:500])
            if isinstance(exc,MotionFault): error['committed'] = exc.committed
            row['outcome'] = 'ERROR'; row['error'] = error
            if row['boundary']=='PROPOSED': row['boundary']='REJECTED'
            self.api_errors.append(dict(id=rid,action=action,time=self.robot.clock.now,error=error))
            response = dict(kind='result',id=rid,error=error)
        finally:
            REQUEST.reset(reqtoken); CANDIDATE_TASK_ID.reset(token)
        events = [e for e in self.robot.events if e.get('request_id')==rid and e['action']==action]
        row.update(started=any(e['phase']=='start' for e in events),
                   committed=any(e['phase']=='complete' for e in events),
                   event_indices=[e['index'] for e in events], finished_at=self.robot.clock.now,
                   after_event_count=len(self.robot.events))
        self.reply(rid,response)

CLIENT_EXTENSION = '''
# Unknown objects are represented only by a rejected marker, never serialized as receipts.
_quality_old_encode = encode
def encode(value):
    if type(value) in (Observation, EventReceipt):
        return dict(__record__=type(value).__name__, data=value.record())
    if type(value) in (list,tuple): return [encode(v) for v in value]
    if type(value) is dict:
        if not all(type(k) is str for k in value): return {"__unsupported_type__":"non_string_key_dict"}
        return {k:encode(v) for k,v in value.items()}
    if value is None or type(value) in (str,int,bool): return value
    if type(value) is float and math.isfinite(value): return value
    return {"__unsupported_type__":type(value).__name__[:80]}
'''

async def execute(source, spec, root):
    spec = deepcopy(spec)
    spec['homes'] = {a:spec['pair_constants']['initial'][a] for a in ('LEFT','RIGHT')}
    spec['execution_bound'] = {'virtual_seconds':spec['public_task']['deadline_s']}
    parent,child=socket.socketpair(); parent.setblocking(False)
    controller=AuditedController(spec)
    try:
        process=await run_sandbox(worker_source(), files={'candidate.py':source,
            'bridge_robot_api.py':client_source(root)+CLIENT_EXTENSION}, limits=Limits(),
            rpc_socket=child,broker=lambda:controller.serve(parent))
    finally: parent.close(); child.close()
    finish=controller.finish or {}
    counts=('pending_task_count','pending_timer_count','pending_ready_callback_count')
    complete=(process['status']=='EXITED' and process.get('returncode')==0 and finish.get('outcome')=='returned'
              and finish.get('lifecycle_profile')=='V04_CALLBACK_ACCOUNTING'
              and all(type(finish.get(k)) is int and finish[k]==0 for k in counts)
              and controller.inflight_at_finish==controller.background_at_finish==controller.inflight_at_eof==0)
    if complete: controller.robot.record('complete','run_return',{},**{k:0 for k in counts})
    return dict(profile=PROFILE,process=process,child_lifecycle_report=finish,
                execution_lifecycle_complete=complete,trusted_events=controller.robot.events,
                call_audit=controller.call_audit, call_audit_complete=(len(controller.call_audit)==controller.last_id),
                trusted_api_errors=controller.api_errors, safety_label=None,
                source_scope='SELF_AUTHORED_DEVELOPMENT_ONLY')
