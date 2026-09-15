"""Replay stored dev evidence and test missing-evidence boundaries; no executions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from monitor import analyze

P=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=read(P/'CONTROL_MANIFEST.json');rows=[]
for case in manifest['cases']:
    d=P/'outputs'/case['id'];cap=read(d/'CAPTURE.json');geo=read(d/'GEOMETRY.json')
    assert (d/'candidate.py').read_text()==case['source']
    assert read(d/'SPEC.json')==case['spec']
    result=analyze(case['spec'],cap,geo)
    expected=case['expected']; ok=all(result['clause_summary'].get(k,'NA')==v for k,v in expected.items())
    assert all(not c['started'] and not c['committed'] and not c['event_indices'] for c in cap['call_audit'] if c['boundary']=='REJECTED')
    (d/'FINAL_ATOMS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    rows.append(dict(id=case['id'],passed=ok,complete=cap['execution_lifecycle_complete'],capture_sha256=sha(d/'CAPTURE.json'),final_atoms_sha256=sha(d/'FINAL_ATOMS.json')))
# These are explicitly trace-damage tests, not generated programs or measured samples.
d=P/'outputs/release_reference';spec=read(d/'SPEC.json');cap=read(d/'CAPTURE.json');geo=read(d/'GEOMETRY.json')
checks={}
no_geo=analyze(spec,cap,{})
checks['missing_geometry_stays_U']=no_geo['clause_summary']['M1.SEPARATING_GEOMETRY']=='U'
cut=deepcopy(cap);cut['trusted_events'].pop()
checks['claimed_completion_without_return_stays_U']=all(x['label']=='U' for x in analyze(spec,cut,geo)['rows'])
missing=deepcopy(cap);missing['call_audit_complete']=False
checks['missing_call_coverage_stays_U']=all(x['label']=='U' for x in analyze(spec,missing,geo)['rows'])
bad=deepcopy(cap);bad['trusted_events'][0]['index']=99
checks['broken_event_order_stays_U']=all(x['label']=='U' for x in analyze(spec,bad,geo)['rows'])
# Expected invariance across actual separately executed semantic-preserving controls.
def atoms(name):return read(P/'outputs'/name/'FINAL_ATOMS.json')['clause_summary']
checks['local_rename_invariance']=atoms('fresh_reference')==atoms('renamed_locals')
checks['zero_yield_invariance']=atoms('release_reference')==atoms('zero_time_yield')
report=dict(status='PASS' if all(r['passed'] for r in rows) and all(checks.values()) else 'FAIL',
            executed_development_cases=len(rows),passed=sum(r['passed'] for r in rows),
            checks=checks,rows=rows,final_code_sha256={p.name:sha(p) for p in [P/'runtime.py',P/'monitor.py',P/'run_controls.py',P/'verify_outputs.py']},
            note='Final code includes a completion-evidence consistency guard added after first acceptance. All 27 stored captures replayed; original acceptance outputs preserved. No additional candidate execution.',
            model_calls=0,human_labels=0,formal_samples_added=0)
(P/'FINAL_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('rows','final_code_sha256')},ensure_ascii=False))
assert report['status']=='PASS'
