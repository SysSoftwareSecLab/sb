from pathlib import Path
import json,ast,hashlib
P=Path(__file__).resolve().parent;B=P.parent/'batch_13_15'
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def main():
    if (P/'CASES.json').exists():raise SystemExit('Prepared cases retained.')
    rows=[]
    for c in json.loads((B/'MANIFEST.json').read_text())['cases']:
        rows.append(dict(case_id=c['case_id'],parent=c['parent_id'],directory=str(B/'library'/c['case_id']),review=c['role']!='semantic',role=c['role']))
    for v in ['A','B']:rows.append(dict(case_id='P02-'+v+'-timeout',parent='P02',directory=str(B/'timeout_diagnostics'/v),review=True,role='timeout'))
    designs=[('early_ready','P01-A-reference','BUFFER_EVENT_PROTOCOL'),('early_empty','P01-A-reference','BUFFER_EVENT_PROTOCOL'),
             ('early_unlock','P01-A-reference','BUFFER_OCCUPANCY_OWNER'),('missing_timeout_cleanup','P02-A-timeout','TIMEOUT_CLEANUP'),
             ('wrong_branch','P03-B-reference','REWORK_BRANCH'),('wrong_observer','P03-A-reference','REWORK_OBSERVATION')]
    for name,source_id,target in designs:
        source=next(x for x in rows if x['case_id']==source_id);d=Path(source['directory']);src=(d/'candidate.py').read_text();spec=json.loads((d/'SPEC.json').read_text())
        if name=='early_ready':
            line='        robot.signal("ready_" + str(i), item_id=item)\n';hook='        await robot.move("LEFT", "buffer_" + str(i))\n';assert src.count(line)==src.count(hook)==1;src=src.replace(line,'').replace(hook,line+hook)
        elif name=='early_empty':
            line='        if i == 0:\n            robot.signal("empty_0", item_id=item)\n';hook='        await robot.move("RIGHT", "target_" + str(i), receipt=receipt)\n';assert src.count(line)==src.count(hook)==1;src=src.replace(line,'').replace(hook,line+hook)
        elif name=='early_unlock':
            line='        await robot.release_resource("LEFT", "buffer_lock")\n';hook='        await robot.move("LEFT", "buffer_" + str(i))\n';assert src.count(line)==src.count(hook)==1;src=src.replace(line,'').replace(hook,line+hook)
        elif name=='missing_timeout_cleanup':
            line='            await robot.release_resource(arm, "fixture")';assert src.count(line)==1;src=src.replace(line,'            if arm == "LEFT":\n                await robot.release_resource(arm, "fixture")')
        elif name=='wrong_branch':src=src.replace('if current.value["accept_by_pass"][attempt]:','if True:')
        elif name=='wrong_observer':src=src.replace('robot.inspect("RIGHT", "quality")','robot.inspect("LEFT", "quality")')
        ast.parse(src);dest=P/'boundaries'/name;write(dest/'SPEC.json',spec);(dest/'candidate.py').write_text(src)
        rows.append(dict(case_id='boundary-'+name,parent=source['parent'],directory=str(dest),review=True,role='boundary',expected_target=target,expected_label='V',source_sha256=hashlib.sha256(src.encode()).hexdigest()))
    write(P/'CASES.json',dict(rows=rows,review_cases=sum(x['review'] for x in rows),new_development_executions_prelisted=6,model_calls=0))
    print('Prepared 26 evidence cases, 20 human review cases, six new boundary executions.')
if __name__=='__main__':main()
