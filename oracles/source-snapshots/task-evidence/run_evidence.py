import asyncio,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[2]
sys.path.insert(0,str(P.parent/'trace_dev_v1'))
from runtime import execute
sys.path.insert(0,str(R/'01_project/STAGE3_GHI_2026-09-06/outputs/G_dynamic_geometry/proposed_src'))
from geometry_interface_v01 import evaluate_dynamic_evidence
from evaluate import evaluate
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
async def main():
    rows=[]
    for case in json.loads((P/'CASES.json').read_text())['rows']:
        d=Path(case['directory']);spec=json.loads((d/'SPEC.json').read_text());src=(d/'candidate.py').read_text()
        if (d/'CAPTURE.json').exists():cap=json.loads((d/'CAPTURE.json').read_text())
        else:
            cap=await execute(src,spec,R)
            if cap['process']['status']=='SANDBOX_SETUP_FAILED':raise RuntimeError(cap['process']['stderr'])
            write(d/'CAPTURE.json',cap)
        geo=json.loads((d/'GEOMETRY.json').read_text()) if (d/'GEOMETRY.json').exists() else evaluate_dynamic_evidence(spec,cap['trusted_events'],None)
        # New task2 derivatives never overwrite task1 files.
        out=P/'evaluations'/case['case_id'];write(out/'GEOMETRY.json',geo)
        result=evaluate(spec,cap,geo,case['parent']);write(out/'EVIDENCE.json',result)
        row=dict(case_id=case['case_id'],summary=result['summary'],integrity=result['input_integrity']);rows.append(row)
        print(json.dumps(row),flush=True)
    write(P/'EVIDENCE_RESULTS.json',dict(rows=rows,new_model_calls=0))
    for c in json.loads((P/'CASES.json').read_text())['rows']:
        row=next(x for x in rows if x['case_id']==c['case_id'])
        if c['role'] in ['reference','semantic']:assert all(v in ['C','NA'] for v in row['summary'].values()),c['case_id']
        if c['role']=='boundary':assert row['summary'][c['expected_target']]=='V',c['case_id']
if __name__=='__main__':asyncio.run(main())
