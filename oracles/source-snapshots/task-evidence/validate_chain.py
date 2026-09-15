import asyncio,copy,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[2]
sys.path.insert(0,str(P.parent/'trace_dev_v1'))
from runtime import execute
from live_guard import execute_guard
from evaluate import evaluate
sys.path.insert(0,str(R/'01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src'))
from geometry_interface_v01 import evaluate_dynamic_evidence
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
async def main():
    d=P.parent/'batch_13_15/library/P03-B-reference';spec=json.loads((d/'SPEC.json').read_text());src=(d/'candidate.py').read_text()
    line='        current = await robot.inspect("RIGHT", "quality")\n';assert src.count(line)==1
    src=src.replace(line,line+'        unused_current_copy = await robot.inspect("RIGHT", "quality")\n')
    out=P/'validation/duplicate_current_observation';out.mkdir(parents=True,exist_ok=True);(out/'candidate.py').write_text(src);write(out/'SPEC.json',spec)
    results=[]
    for mode,run in [('plain',lambda:execute(src,spec,R)),('guard',lambda:execute_guard(src,spec))]:
        dest=out/(mode+'.json')
        cap=json.loads(dest.read_text()) if dest.exists() else await run()
        if cap['process']['status']=='SANDBOX_SETUP_FAILED':raise RuntimeError(cap['process']['stderr'])
        write(dest,cap);geo=evaluate_dynamic_evidence(spec,cap['trusted_events'],None);e=evaluate(spec,cap,geo,'P03')
        assert all(x in ['C','NA'] for x in e['summary'].values()) and not cap.get('interventions')
        results.append(dict(check='same_cycle_duplicate_'+mode,passed=True))
    cap=json.loads((d/'CAPTURE.json').read_text());geo=json.loads((d/'GEOMETRY.json').read_text())
    for name in ['missing_call_audit','invalid_event_index','invalid_call_boundary']:
        bad=copy.deepcopy(cap)
        if name=='missing_call_audit':bad['call_audit_complete']=False
        elif name=='invalid_event_index':bad['trusted_events'][0]['index']=99
        else:bad['call_audit'][0]['before_event_count']=-1
        result=evaluate(spec,bad,geo,'P03');assert all(x=='U' for x in result['summary'].values())
        results.append(dict(check=name,passed=True))
    write(P/'CHAIN_VALIDATION.json',dict(results=results,real_additional_executions=2,synthetic_missing_evidence_checks=3,not_human_labels=True))
    print('Two real benign-observation executions and three missing-evidence checks passed.')
if __name__=='__main__':asyncio.run(main())
