"""Direct post-adjudication sensitivity analysis of frozen existing outputs."""
import ast
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[2]
ROOT=PROJECT/'paper3_bisafebench'
DESIGN=ROOT/'01_project/QUALITY_UPGRADE_2026-09-10/task3_design/main_study_v1'
RUN=ROOT/'05_formal/main_natural_384_v1'
METHODS=RUN/'methods'
INTAKE=HERE/'mac_followup_v1/return_intake_v1'
PACK=HERE/'mac_followup_v1/Paper3_仲裁定点核查与复算交接_v1'
OUT=HERE/'reanalysis_v1'
CHANNELS=('R1','R2','COMMON','R3')
PROFILES=('glm47','deepseek_flash','glm5')

def load(p): return json.loads(p.read_text())
def save(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def literal(p): return ast.literal_eval(ast.parse(p.read_text()).body[0].value)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def module(name):
    spec=importlib.util.spec_from_file_location(name,DESIGN/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def effective(j): return j['label'] if j['scope_status']=='RESOLVED' else 'U'
def state(js,names):
    labels=[effective(js[n]) for n in names if n in js]
    if not labels:return None
    return 'V' if 'V' in labels else 'U' if 'U' in labels else 'NA' if all(x=='NA' for x in labels) else 'C'

def main():
    OUT.mkdir(exist_ok=True)
    mainstats=module('analyze_main_tables')
    dynamic=module('analyze_t4_existing')
    judge=module('analyze_t4_source_judges')
    rq2=module('analyze_rq2_holdouts')
    rq4=module('analyze_rq4_grouped_error_migration')
    originals=[load(RUN/'human_review/received_2026-09-12/validated'/n) for n in ('Reviewer1.json','Reviewer2.json')]
    reviews={c:{r['review_id']:r for r in payload['records']} for c,payload in zip(CHANNELS,originals)}
    final=literal(PACK/'previous_return/FINAL_PASS.py')
    js3=defaultdict(dict)
    for j in final['judgments']: js3[j['review_id']][j['obligation']]=j
    p3={r['review_id']:r for r in final['programs']}
    mapping=load(RUN/'human_review/PRIVATE_MAP.json')
    generation={r['slot_id']:r for r in load(DESIGN/'GENERATION_MANIFEST.json')}
    programs=[]
    for rid,mp in mapping.items():
        slot=generation[mp['slot_id']]
        js={c:{j['obligation']:j for j in reviews[c][rid]['judgments']} for c in ('R1','R2')}
        assert js['R1'].keys()==js['R2'].keys()==js3[rid].keys()
        common={}
        for ob in js['R1']:
            a,b=js['R1'][ob],js['R2'][ob]
            match=a['scope_status']==b['scope_status']=='RESOLVED' and a['label']==b['label']
            common[ob]={'label':a['label'] if match else 'U','scope_status':'RESOLVED' if match else 'DISAGREEMENT_OR_UNRESOLVED'}
        js.update(COMMON=common,R3=js3[rid])
        labels={c:reviews[c][rid]['program_label'] for c in ('R1','R2')}
        labels['COMMON']=labels['R1'] if labels['R1']==labels['R2'] else 'UNKNOWN'
        labels['R3']=p3[rid]['program_label']
        programs.append({**slot,'review_id':rid,'judgments':js,'program_labels':labels,**labels})
    assert len(programs)==384
    byid={r['review_id']:r for r in programs}
    pairs={kind:mainstats.build_pairs(programs,kind) for kind in ('CONCURRENCY','DEPENDENCY_DISTANCE','CAPABILITY','PROMPT','LAYOUT')}
    summary={'role':'Post-hoc adjudication sensitivity; not new independent confirmation','programs':384,'channels':list(CHANNELS),
      'by_profile':{c:mainstats.group_distribution(programs,c,'profile') for c in CHANNELS},
      'by_family':{c:mainstats.group_distribution(programs,c,'family') for c in CHANNELS},
      'paired':{kind:{c:mainstats.analyze_pairs(ps,c) for c in CHANNELS} for kind,ps in pairs.items()}}
    old=load(RUN/'analysis/MAIN_TABLES.json')
    for kind,key in [('CONCURRENCY','T2_CONCURRENCY'),('DEPENDENCY_DISTANCE','T2_DEPENDENCY_DISTANCE'),('CAPABILITY','T3_CAPABILITY_MIGRATION'),('PROMPT','PROMPT_SECONDARY'),('LAYOUT','LAYOUT_SECONDARY')]:
        for c,name in [('R1','Reviewer1'),('R2','Reviewer2')]:
            expected=dict(old['paired'][key][name]);expected['reviewer']=c
            assert summary['paired'][kind][c]==expected,(kind,c)
    summary['original_program_statistics_exactly_reproduced']=True
    save('PROGRAM_COMPARISONS.json',summary)
    print('Program comparisons complete; original R1/R2 statistics exactly reproduced',flush=True)

    focal={}
    # Reuse original pair builders with the new channels, not the original narrative/gates.
    rq2.REVIEWERS=CHANNELS
    for name,ps in [
       ('CONCURRENCY_FOCAL',rq2.build_focal_pairs(programs,'CONCURRENCY','COMPOSITION_CONCURRENCY')),
       ('DEPENDENCY_DISTANCE_FOCAL',rq2.build_focal_pairs(programs,'DEPENDENCY_DISTANCE','LONG_RANGE_DEPENDENCY')),
       ('LAYOUT_SAFETY_ANY_V',rq2.build_layout_pairs(programs,{'C4_ALLOCATION'})),
       ('NESTED_ON_ATTRIBUTE',rq2.build_nested_attribute_pairs(programs))]:
        focal[name]={c:rq2.analyze_label_pairs(ps,c,name) for c in CHANNELS}
    registry=load(DESIGN/'HOLDOUT_REGISTRY.json')
    absolute={}
    for name,ob in [('attribute_combination','ATTRIBUTE_COMBINATION'),('control_flow','CONTROL_FLOW_HOLDOUT')]:
        subset=[p for p in programs if p['task_id'] in registry[name]['objects']]
        absolute[name]={'N':len(subset),'families':len({r['family'] for r in subset}),
          'channels':{c:dict(Counter(effective(r['judgments'][c][ob]) for r in subset)) for c in CHANNELS}}
    save('RQ2_MAIN384.json',{'focal_pairs':focal,'absolute_structural_OOD':absolute,
         'boundary':'Main384 only; no change to independent320, coherent-pair96 or structure-preserving360; structural OOD is benchmark-development novelty, not model-training novelty.'})

    groups=rq4.GROUPS
    model_groups={}; migration={}; exposure={}
    for group,obs in groups.items():
        model_groups[group]={};migration[group]={};exposure[group]={}
        for c in CHANNELS:
            model_groups[group][c]={}
            for profile in PROFILES:
                rows=[p for p in programs if p['profile']==profile and state(p['judgments'][c],obs) is not None]
                model_groups[group][c][profile]={'N':len(rows),'counts':dict(Counter(state(p['judgments'][c],obs) for p in rows))}
            data=[]
            for pair in pairs['CAPABILITY']:
                lo,hi=[state(pair[side]['judgments'][c],obs) for side in ('low','high')]
                if lo is not None and hi is not None:data.append({'family':pair['family'],'low':lo,'high':hi,'pair_id':pair['pair_id']})
            migration[group][c]=rq4.summarize_pair_rows(data,f'reviewer:{c}:{group}')
            migration[group][c]['pair_rows']=data
        for profile in PROFILES:
            rows=[j for p in programs if p['profile']==profile for ob,j in p['judgments']['R3'].items() if ob in obs]
            reached=[j for j in rows if j.get('exposure')=='REACHED']
            exposure[group][profile]={'unit':'requirement judgments, not programs','assigned':len(rows),
              'exposure_label_cross_counts':dict(Counter(j.get('exposure','MISSING')+'->'+effective(j) for j in rows)),
              'reported_REACHED':len(reached),'V_among_reported_REACHED':sum(effective(j)=='V' for j in reached),
              'V_not_reported_REACHED':sum(effective(j)=='V' and j.get('exposure')!='REACHED' for j in rows)}
    save('RQ4_CATEGORY_MIGRATION.json',{'by_profile':model_groups,'paired_GLM5_minus_GLM47':migration,
        'R3_reported_requirement_exposure':exposure,
        'limits':'Multi-label post-hoc groups; reported exposure is not a revalidated direct-P opportunity oracle. Do not equate F with physical-temporal errors or profile order with scalar capability. Old syntax/API composite is not relabeled shallow.'})
    print('RQ2 matching and RQ4 category transitions complete',flush=True)

    manifest=load(METHODS/'T4_METHOD_MANIFEST.json')
    objects=[r for r in manifest['objects'] if r['kind']=='NATURAL']
    methods=('dynamic','deepseek_flash','glm5')
    method_rows={m:{c:[] for c in CHANNELS} for m in methods}
    decisions={m:[] for m in methods if m!='dynamic'}
    for obj in objects:
        p=byid[obj['review_id']]
        assert sha(Path(obj['source']))==obj['source_sha256']
        assert sha(PACK/'cases'/p['review_id']/'candidate.py')==obj['source_sha256']
        for m in methods:
            if m=='dynamic':pred=dynamic.dynamic_predictions(obj['slot_id'])
            else:
                path=METHODS/'source_judge/results'/(obj['object_id']+'--'+m)/'RESULT.json'
                result=load(path) if path.exists() else None
                if result:
                    assert result['object_id']==obj['object_id'] and result['judge']==m and result['model_identity_matches']
                else:assert not obj['judge_eligible']
                pred={r['id']:r['label'] for r in result['predictions']} if result and result['status']=='VALID_STRUCTURED_PREDICTIONS' else {ob:'INVALID' if result else 'METHOD_INAPPLICABLE' for ob in obj['obligations']}
                decisions[m].append({'family':p['family'],'object_id':obj['object_id'],'decision':judge.program_decision(result,obj['obligations']),**{c:p[c] for c in CHANNELS}})
            for ob in obj['obligations']:
                for c in CHANNELS:
                    j=p['judgments'][c][ob]
                    method_rows[m][c].append({'review_id':p['review_id'],'slot_id':p['slot_id'],'obligation':ob,'family':p['family'],'truth':effective(j),'prediction':pred.get(ob,'METHOD_INAPPLICABLE'),'scope_status':j['scope_status']})
    method_out={}
    for m in methods:
        method_out[m]={}
        for c in CHANNELS:
            rows=method_rows[m][c];finite=[r for r in rows if r['truth'] in ('C','V')]
            perf=judge.performance(finite)
            byob={ob:judge.performance([r for r in finite if r['obligation']==ob]) for ob in sorted({r['obligation'] for r in rows})}
            gates=[]
            if c=='R3':
                gates=[judge.stable_gate(m,ob,[r for r in finite if r['obligation']==ob]) for ob in byob]
            method_out[m][c]={'all_requirement_count':len(rows),'all_truth_counts':dict(Counter(r['truth'] for r in rows)),
                'resolved_CV':perf,'by_obligation':byob,'R3_existing_threshold_screen':gates,
                'R3_screen_passed':[g['obligation'] for g in gates if g['admitted']]}
            if m!='dynamic':method_out[m][c]['program_comparison']=judge.program_comparison(decisions[m],c)
        # The unmodified common-evidence numerator/denominator must reproduce published results.
        if m=='dynamic':gold=load(METHODS/'analysis/PROMPT_DYNAMIC.json')['dynamic']['exact_agreed_resolved']
        else:gold=load(METHODS/'analysis/SOURCE_JUDGE.json')['judges'][m]['primary_exact_agreed_resolved']
        got=method_out[m]['COMMON']['resolved_CV']
        for k in gold:
            assert got[k]==gold[k],(m,k,got.get(k),gold[k])
        print('Recomputed '+m+'; original exact-agreement scores reproduced',flush=True)
    save('RQ3_METHOD_COMPARISONS.json',{'methods':method_out,
      'limits':'R3 threshold passes are post-hoc sensitivity, not new confirmatory blind spots. Program comparisons include supplementary endpoint mismatch and must not be presented as coverage of unasked API/geometry obligations. Invalid/inapplicable/U outputs retained as non-detection, not explicit false compliance.'})
    save('RQ3_SCORING_ROWS.json',method_rows)

    comparisons=load(METHODS/'guard/human_review/TRAJECTORY_COMPARISON.json')['rows']
    changed=[r for r in comparisons if r['needs_new_human_review']]
    same=[r for r in comparisons if r['reuse_original_human_channels']]
    assert len(changed)==53 and len(same)==55 and all(r['semantic_evidence_identical'] for r in same)
    pre=Counter(byid[r['original_review_id']]['R3'] for r in comparisons)
    chpre=Counter(byid[r['original_review_id']]['R3'] for r in changed)
    blocked=Counter()
    for r in comparisons:
        s=load(METHODS/'guard/results'/r['object_id']/'SUMMARY.json')
        if s['intervention_count']>0:blocked[byid[r['original_review_id']]['R3']]+=1
    guard={'N':108,'identical_trajectory_R3_inheritable':55,'changed_trajectory_R3_missing':53,
      'R3_pre_counts':dict(pre),'changed_pre_counts':dict(chpre),'blocked_by_R3_pre_label':dict(blocked),
      'R3_post_minus_pre_risk_identification_bound':[-(chpre['UNSAFE']+chpre['UNKNOWN'])/108,(53-chpre['UNSAFE'])/108],
      'bound_semantics':'53 changed post states unconstrained, original UNKNOWN unconstrained; 55 identical pairs cancel exactly. Not a confidence interval and not an observed R3 guard effect.',
      'original_dual_review_effect':load(METHODS/'analysis/GUARD_EFFECT.json')['program_effect'],
      'decision':'Do not publish a hybrid R3-pre/R1-or-R2-post effect. Original dual-review estimates may remain explicitly historical; no R3 improvement claim. Post-trajectories need same-scope adjudication only if an updated R3 effect is required.'}
    save('GUARD_COMPARABILITY.json',guard)
    save('INPUTS_AND_STATUS.json',{'status':'EXISTING_DATA_REANALYSIS_COMPLETE_GUARD_R3_POST_NOT_OBSERVED',
      'new_model_calls':0,'new_candidate_executions':0,'new_human_labels':0,
      'original_R1_R2_program_stats_reproduced':True,'original_common_method_scores_reproduced':True,
      'inputs':{str(p.relative_to(PROJECT)):sha(p) for p in [DESIGN/'GENERATION_MANIFEST.json',METHODS/'T4_METHOD_MANIFEST.json',PACK/'previous_return/FINAL_PASS.py',INTAKE/'AUDIT.json',HERE/'REANALYSIS_SCOPE.md']}})
    print('All scoped comparisons saved; guard R3-post gap explicitly retained',flush=True)

if __name__=='__main__':main()
