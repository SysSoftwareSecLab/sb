import asyncio,ast,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[2]
sys.path.insert(0,str(P.parent/'trace_dev_v1'))
from runtime import execute
from evidence import evaluate
sys.path.insert(0,str(R/'01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src'))
from geometry_interface_v01 import evaluate_dynamic_evidence
K=R/'01_project/STAGE3_JKL_2026-09-06/outputs/K_handover_execution/proposed_src';sys.path.insert(0,str(K))
from j_execute_v01 import execute_j_isolated
from bisafebench_pilot.handover_evidence_v01.handover_monitor_v02 import evaluate_handover_evidence
from bisafebench_pilot.handover_evidence_v01.dual_attachment_geometry_v01 import evaluate_dual_geometry
from build_library import write
async def main():
    manifest=json.loads((P/'LIBRARY_MANIFEST.json').read_text());rows=[]
    for case in manifest['cases']:ast.parse((P/'library'/case['case_id']/'candidate.py').read_text())
    for case in manifest['cases']:
        d=P/'library'/case['case_id'];spec=json.loads((d/'SPEC.json').read_text());src=(d/'candidate.py').read_text()
        if (d/'CAPTURE.json').exists():cap=json.loads((d/'CAPTURE.json').read_text());geo=json.loads((d/'GEOMETRY.json').read_text())
        else:
            if case['backend']=='H':
                cap=await execute(src,spec,R);geo=evaluate_dynamic_evidence(spec,cap['trusted_events'],None)
            else:
                cap=await execute_j_isolated(src,spec,{},project_root=R,k_source_root=K,handover_evaluator=evaluate_handover_evidence,geometry_evaluator=evaluate_dual_geometry);geo=cap['independent_replay']['geometry']
            if cap['process']['status']=='SANDBOX_SETUP_FAILED':raise RuntimeError(cap['process']['stderr'])
            write(d/'CAPTURE.json',cap);write(d/'GEOMETRY.json',geo)
        truth=evaluate(spec,cap,geo,case['family_id']);write(d/'ATOMS.json',truth)
        actual=truth['summary'].get(case['target_obligation'],'NA')
        row=dict(case_id=case['case_id'],expected=case['expected'],actual=actual,check=actual==case['expected'],complete=cap.get('execution_lifecycle_complete'),process=cap['process']['status'],geometry=geo.get('status'),task=truth['summary'].get('TASK_GOAL','J_SEPARATE'),errors=cap.get('trusted_api_errors',[])[:1]);rows.append(row);print(json.dumps(row),flush=True)
    write(P/'LIBRARY_RESULTS.json',dict(rows=rows,passed=sum(r['check'] for r in rows),n=len(rows),model_calls=0))
if __name__=='__main__':asyncio.run(main())
