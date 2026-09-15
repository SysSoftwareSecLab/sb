"""Offline aggregation checks. No network, model code execution, or external packages."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'results/final-revalidation/LOCAL_REVALIDATION.json'
CHECKS = {}

CATEGORY_MAP = {
    'SUPPORT_DEPARTURE':'MOTION_LIFECYCLE',
    'RELEASE_DEPARTURE':'MOTION_LIFECYCLE',
    'TIMEOUT_CLEANUP':'MOTION_LIFECYCLE',
    'ATTRIBUTE_COMBINATION':'COMPOSITION_STRUCTURE',
    'CONTROL_FLOW_HOLDOUT':'COMPOSITION_STRUCTURE',
    'COMPOSITION_CONCURRENCY':'COMPOSITION_STRUCTURE',
    'BUFFER_OCCUPANCY_OWNER':'RESOURCE_OWNERSHIP',
    'DUAL_RESOURCE_SPAN':'RESOURCE_OWNERSHIP',
    'ALLOCATION_EXCLUSIVITY':'RESOURCE_OWNERSHIP',
    'BUFFER_EVENT_PROTOCOL':'EVENT_DEPENDENCY_PROTOCOL',
    'BUFFER_RECEIPT':'EVENT_DEPENDENCY_PROTOCOL',
    'LONG_RANGE_DEPENDENCY':'EVENT_DEPENDENCY_PROTOCOL',
    'EVENT_JOIN':'EVENT_DEPENDENCY_PROTOCOL',
    'EXCHANGE_PROTOCOL':'EVENT_DEPENDENCY_PROTOCOL',
    'EXCHANGE_RECEIPT':'EVENT_DEPENDENCY_PROTOCOL',
    'OBS_CURRENT':'OBSERVATION_BRANCHING',
    'ALLOCATION_OBSERVATION':'OBSERVATION_BRANCHING',
    'REWORK_OBSERVATION':'OBSERVATION_BRANCHING',
    'REWORK_BRANCH':'OBSERVATION_BRANCHING',
}

def load(path): return json.loads((ROOT/path).read_text())
def require(condition, message):
    if not condition: raise AssertionError(message)
def count(rows,key): return dict(Counter(r[key] for r in rows))

def manifest():
    p=ROOT/'MANIFEST.sha256.json'
    if not p.exists(): return {'status':'NOT_YET_SEALED'}
    records=json.loads(p.read_text())
    for name,expected in records.items():
        path=ROOT/name
        require(path.is_file(), 'Missing: '+name)
        require(hashlib.sha256(path.read_bytes()).hexdigest()==expected, 'Hash mismatch: '+name)
    return {'status':'PASS','checked_files':len(records)}

def assignments():
    answer={}
    for study,n in [('main384',384),('factorial320',320),('coherent96',96)]:
        rows=load(f'datasets/{study}/program-index.json')
        require(len(rows)==n and len({r['slot_id'] for r in rows})==n, study+' assignments')
        for row in rows:
            p=ROOT/f'llm-generation/{study}/outputs'/row['slot_id']
            require((p/'RESULT.json').exists() and (p/'MODEL_TEXT.txt').exists(),study+' missing answer')
        answer[study]=n
    for study,n in [('main384',64),('factorial320',80)]:
        tasks=load(f'datasets/{study}/design/TASK_CATALOG.json')
        require(len(tasks)==n,'task count')
        for row in tasks:
            for key in ['spec_path','reference_path','graph_path']:
                require((ROOT/row[key]).is_file(),'task file binding: '+key)
    judge_dirs=list((ROOT/'baselines/source-judge/results').glob('*/RESULT.json'))
    require(len(judge_dirs)==798,'judge slots')
    require(all(p.with_name('MODEL_RESPONSE.json').exists() for p in judge_dirs),'stored judge messages')
    answer['judge_slots']=798
    return answer

def main384():
    mapping=load('datasets/main384/review-to-program.json')
    ledger=load('datasets/main384/labels/adjudicated/program-attribution.json')
    final=load('datasets/main384/labels/adjudicated/final-pass.json')
    require(len(ledger)==len(mapping)==384,'main384 size')
    require({r['review_id'] for r in ledger}==set(mapping),'review binding')
    totals=count(ledger,'adjudicated_program_label')
    require(totals=={'UNSAFE':248,'SAFE':72,'UNKNOWN':64},'adjudicated totals')
    require(sum(r['safe_and_task_complete'] for r in ledger)==69,'safe+task')
    final_labels={r['review_id']:r['program_label'] for r in final['programs']}
    require(all(final_labels[r['review_id']]==r['adjudicated_program_label'] for r in ledger),'final pass binding')
    require(len(final['judgments'])==2184,'requirement count')
    bases=Counter(r['exclusive_unsafe_basis'] for r in ledger if r['adjudicated_program_label']=='UNSAFE')
    require(sorted(bases.values())==[2,8,55,183],'unsafe attribution')
    originals={}
    for name in ['reviewer1','reviewer2']:
        data=load(f'datasets/main384/labels/original/{name}.json')['records']
        require({r['review_id'] for r in data}==set(mapping),'original label binding')
        originals[name]=count(data,'program_label')
    return {'adjudicated':totals,'safe_and_task_complete':69,'unsafe_bases':dict(bases),'original':originals,'judgments':2184}

def methods():
    rows=load('results/final-revalidation/main384/RQ3_SCORING_ROWS.json')
    expected=load('results/final-revalidation/main384/RQ3_METHOD_COMPARISONS.json')['methods']
    checked=0
    for method,channels in rows.items():
        for channel,rs in channels.items():
            subsets={'resolved_CV':[r for r in rs if r['truth'] in ('C','V')]}
            for obligation in {r['obligation'] for r in rs}:
                subsets[obligation]=[r for r in rs if r['obligation']==obligation and r['truth'] in ('C','V')]
            for name,subset in subsets.items():
                exp=expected[method][channel]['resolved_CV'] if name=='resolved_CV' else expected[method][channel]['by_obligation'][name]
                confusion=dict(Counter(r['truth']+'->'+r['prediction'] for r in subset))
                require(confusion==exp['confusion'],f'method confusion: {method}/{channel}/{name}')
                require(len(subset)==exp['n'],'method N')
                checked+=1
    return {'confusion_tables_recomputed':checked,'scope':'Aggregation of supplied independently bound scoring rows, not a new truth audit'}

def factorial():
    path=ROOT/'results/final-revalidation/factorial320/BOUND_LONGFORM.csv'
    with path.open(newline='') as f: rows=list(csv.DictReader(f))
    require(len({r['slot_id'] for r in rows})==320,'factorial assigned slots')
    expected=load('results/final-revalidation/factorial320/RQ2_RESULTS.json')['factorial']['channels']
    checked=0
    for channel,value in expected.items():
        for cell in value['cells']:
            selected=[r for r in rows if r['channel']==channel and r['block']=='RQ2_FACTORIAL'
                      and all(r[k]==cell[k] for k in ['coupling','schedule','dependency_distance'])]
            for category in ['P_direct_base','structure_fidelity']:
                rs=[r for r in selected if r['category']==category]
                if not rs: continue
                actual=Counter(r['verdict'] for r in rs)
                target={k:v for k,v in cell[category].items() if v}
                require(dict(actual)==target,'factorial cell '+channel+'/'+category)
                require(len(rs)==cell['n'],'factorial cell N')
                if category=='P_direct_base':
                    exposed=sum(r['exposed']=='True' for r in rs)
                    require(exposed==cell['P_exposed'],'factorial exposure')
                checked+=1
    require(checked>0,'No factorial cells checked')
    return {'assigned':320,'cell_endpoints_checked':checked}

def coherent():
    prefix='results/final-revalidation/coherent96/'
    rows=load(prefix+'FINAL_ROWS.json')
    require(len(rows)==6144,'coherent records')
    grouped=defaultdict(list)
    for r in rows:
        require(r['F']==int(r['P']!='C'),'F definition')
        grouped[r['task_id'],r['profile'],r['arm'],r['condition']].append(r)
    rates={}
    for key,rs in grouped.items():
        require(len(rs)==16 and {r['seed'] for r in rs}==set(range(16)),'coherent schedule assignment')
        rates[key]=sum(r['F'] for r in rs)/16
    def interaction(task,model,arm):
        return rates[task,model,arm,'CONCURRENT_LONG']-rates[task,model,arm,'CONCURRENT_SHORT']-rates[task,model,arm,'SERIAL_LONG']+rates[task,model,arm,'SERIAL_SHORT']
    frozen=load(prefix+'FINAL_FAMILY_EFFECTS.json')
    effects=[]
    for row in frozen:
        t=row['task_id']
        b=sum(interaction(t,m,'BASE') for m in ['deepseek_flash','glm5'])/2
        e=sum(interaction(t,m,'EXPLICIT') for m in ['deepseek_flash','glm5'])/2
        require(b==row['base_I_F'] and e==row['explicit_I_F'] and b-e==row['D_F'],'context effect')
        effects.append(b-e)
    require(len(effects)==24,'24 context clusters')
    rng=random.Random(26091404)
    boot=sorted(sum(rng.choice(effects) for _ in effects)/24 for _ in range(10000))
    interval=[boot[int(.025*9999)],boot[int(.975*9999)]]
    delta=sum(effects)/24
    require(delta==.671875 and interval==[.609375,.734375],'interaction/bootstrap')
    cells={a:{c:sum(r['F'] for r in rows if r['arm']==a and r['condition']==c)
              for c in ['SERIAL_SHORT','SERIAL_LONG','CONCURRENT_SHORT','CONCURRENT_LONG']}
           for a in ['BASE','EXPLICIT']}
    require(list(cells['BASE'].values())==[64,64,240,768],'BASE cells')
    require(list(cells['EXPLICIT'].values())==[0,0,4,16],'EXPLICIT cells')
    return {'assigned_rows':6144,'F_counts_each_out_of_768':cells,'interaction_reduction':delta,'bootstrap95':interval}

def recomposition():
    rows=load('results/final-revalidation/recomposition360/EXECUTION_ROWS_SCORING_CORRECTION_002.json')
    bindings=load('datasets/recomposition360/trace-index.json')
    require(len(rows)==len(bindings)==5760,'recomposition trace count')
    require(len({(r['slot_id'],r['condition']) for r in rows})==360,'recomposition programs')
    # P_amendment_001 is the superseded label retained for provenance;
    # correction 002 writes its operative result to P_new.
    require(all(r['measurement_revision']=='SCORING_CORRECTION_002' and r['P_new']=='C' and r['P_new_exposed'] for r in rows),'final P/exposure')
    for row in bindings:
        for key in ['composed_source_path','capture_path']:
            require((ROOT/row[key]).is_file(),'missing bound '+key)
    human=load('datasets/recomposition360/labels/HUMAN_PROGRAM_ROWS.json')
    require(len(human)==360,'recomposition human objects')
    for r in human:
        for who in ['Reviewer1','Reviewer2']:
            require(r[who+'_P_label']=='C' and r[who+'_P_exposure']=='EXPOSED' and r[who+'_treatment_integrity']=='MET','human supplement state')
    return {'trace_rows':5760,'program_conditions':360,'direct_P_V':0,'scope':'Fixed qualified exploratory pool; not equivalence'}

def manuscript_tables():
    """Recompute the three numerical tables printed in the current manuscript."""
    originals={}
    for name in ['reviewer1','reviewer2']:
        originals[name]=load(f'datasets/main384/labels/original/{name}.json')['records']
    left={r['review_id']:r for r in originals['reviewer1']}
    right={r['review_id']:r for r in originals['reviewer2']}
    require(set(left)==set(right) and len(left)==384,'Table I original binding')

    outcomes={
        'R1':dict(Counter(r['program_label'] for r in originals['reviewer1'])),
        'R2':dict(Counter(r['program_label'] for r in originals['reviewer2'])),
    }
    joint=Counter()
    for review_id in left:
        a,b=left[review_id]['program_label'],right[review_id]['program_label']
        joint[a if a==b else 'DISAGREE']+=1
    outcomes['Joint']=dict(joint)

    def original_categories(records):
        values=defaultdict(set)
        for record in records:
            for judgment in record['judgments']:
                obligation=judgment['obligation']
                if obligation in CATEGORY_MAP and judgment['label']=='V':
                    values[CATEGORY_MAP[obligation]].add(record['review_id'])
        return {key:len(value) for key,value in values.items()}

    categories={
        'R1':original_categories(originals['reviewer1']),
        'R2':original_categories(originals['reviewer2']),
    }
    joint_categories=defaultdict(set)
    for review_id in left:
        a={j['obligation']:j for j in left[review_id]['judgments']}
        b={j['obligation']:j for j in right[review_id]['judgments']}
        require(set(a)==set(b),'Table I obligation binding')
        for obligation in a:
            if obligation not in CATEGORY_MAP: continue
            same_resolved_v=(a[obligation]['label']==b[obligation]['label']=='V'
                             and a[obligation]['scope_status']==b[obligation]['scope_status']=='RESOLVED')
            if same_resolved_v: joint_categories[CATEGORY_MAP[obligation]].add(review_id)
    categories['Joint']={key:len(value) for key,value in joint_categories.items()}

    final=load('datasets/main384/labels/adjudicated/final-pass.json')
    outcomes['R3']=dict(Counter(r['program_label'] for r in final['programs']))
    r3_categories=defaultdict(set); assigned=defaultdict(set)
    for judgment in final['judgments']:
        obligation=judgment['obligation']
        if obligation not in CATEGORY_MAP: continue
        category=CATEGORY_MAP[obligation]
        assigned[category].add(judgment['review_id'])
        if judgment['label']=='V': r3_categories[category].add(judgment['review_id'])
    categories['R3']={key:len(value) for key,value in r3_categories.items()}
    assigned={key:len(value) for key,value in assigned.items()}

    expected_outcomes={
        'R1':{'UNSAFE':278,'SAFE':73,'UNKNOWN':33},
        'R2':{'UNSAFE':217,'SAFE':71,'UNKNOWN':96},
        'Joint':{'UNSAFE':204,'SAFE':67,'UNKNOWN':26,'DISAGREE':87},
        'R3':{'UNSAFE':248,'SAFE':72,'UNKNOWN':64},
    }
    expected_categories={
        'R1':{'COMPOSITION_STRUCTURE':100,'EVENT_DEPENDENCY_PROTOCOL':143,'OBSERVATION_BRANCHING':26,'RESOURCE_OWNERSHIP':52,'MOTION_LIFECYCLE':112},
        'R2':{'COMPOSITION_STRUCTURE':102,'EVENT_DEPENDENCY_PROTOCOL':117,'OBSERVATION_BRANCHING':26,'RESOURCE_OWNERSHIP':55,'MOTION_LIFECYCLE':16},
        'Joint':{'COMPOSITION_STRUCTURE':81,'EVENT_DEPENDENCY_PROTOCOL':99,'OBSERVATION_BRANCHING':26,'RESOURCE_OWNERSHIP':51,'MOTION_LIFECYCLE':15},
        'R3':{'COMPOSITION_STRUCTURE':97,'EVENT_DEPENDENCY_PROTOCOL':69,'OBSERVATION_BRANCHING':8,'RESOURCE_OWNERSHIP':52,'MOTION_LIFECYCLE':16},
    }
    require(outcomes==expected_outcomes,'Manuscript Table I program outcomes')
    require(categories==expected_categories,'Manuscript Table I category counts')
    require(assigned=={'COMPOSITION_STRUCTURE':240,'EVENT_DEPENDENCY_PROTOCOL':312,'OBSERVATION_BRANCHING':96,'RESOURCE_OWNERSHIP':240,'MOTION_LIFECYCLE':384},'Table I assigned denominators')

    capability=load('results/final-revalidation/factorial320/CAPABILITY_RESULTS_V2.json')['profiles']
    dimensions=['task_graph','state_and_identity','async_timing','long_context_program_discrimination']
    table3={profile:[capability[profile]['dimensions'][dimension]['correct'] for dimension in dimensions]
            for profile in ['glm46','glm47','glm5','glm52']}
    require(table3=={'glm46':[4,5,0,15],'glm47':[4,5,1,14],'glm5':[13,13,12,5],'glm52':[12,12,15,10]},'Manuscript Table III')

    with (ROOT/'results/final-revalidation/factorial320/BOUND_LONGFORM.csv').open(newline='') as handle:
        rows=list(csv.DictReader(handle))
    table4={}
    for profile in ['glm46','glm47','glm5','glm52']:
        table4[profile]={}
        for channel in ['machine','Reviewer1','Reviewer2']:
            subset=[r for r in rows if r['profile']==profile and r['channel']==channel and r['category']=='P_direct_base']
            require(len(subset)==80,f'Table IV denominator {profile}/{channel}')
            table4[profile][channel]=[sum(r['verdict']=='V' for r in subset),sum(r['exposed']=='True' for r in subset)]
    expected_table4={
        'glm46':{'machine':[9,34],'Reviewer1':[8,33],'Reviewer2':[8,33]},
        'glm47':{'machine':[10,33],'Reviewer1':[8,31],'Reviewer2':[8,31]},
        'glm5':{'machine':[11,26],'Reviewer1':[9,26],'Reviewer2':[6,22]},
        'glm52':{'machine':[10,24],'Reviewer1':[7,25],'Reviewer2':[6,22]},
    }
    require(table4==expected_table4,'Manuscript Table IV')
    return {'table1':{'outcomes':outcomes,'categories':categories,'assigned':assigned},'table3':table3,'table4':table4}

def rq4_supporting():
    sys.path.insert(0,str(ROOT/'oracles/source-snapshots/rq4-supporting-cohorts'))
    from analyze import analyze
    result=analyze()
    require(result['status']=='PASS','RQ4 supporting cohorts')
    return result

def figures():
    provenance=load('final-build/figures/FIGURE_PROVENANCE.json')
    require(len(provenance['figures'])==4,'four manuscript figures')
    for name,record in provenance['figures'].items():
        path=ROOT/'final-build/figures'/name
        require(path.is_file(),'missing manuscript figure: '+name)
        require(hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256'],'figure hash: '+name)
        require(record['paper_role'] and record['evidence_sources'],'figure provenance: '+name)
    with (ROOT/'results/final-revalidation/factorial320/BOUND_LONGFORM.csv').open(newline='') as handle:
        rows=list(csv.DictReader(handle))
    panel_a={}
    for channel in ['machine','Reviewer1','Reviewer2']:
        panel_a[channel]={}
        for schedule in ['SERIAL','CONCURRENT']:
            structure=[r for r in rows if r['channel']==channel and r['block']=='RQ2_FACTORIAL'
                       and r['schedule']==schedule and r['category']=='structure_fidelity']
            direct=[r for r in rows if r['channel']==channel and r['block']=='RQ2_FACTORIAL'
                    and r['schedule']==schedule and r['category']=='P_direct_base']
            require(len(structure)==len(direct)==128,'Figure 3a denominator')
            panel_a[channel][schedule]=[sum(r['verdict']=='V' for r in structure),sum(r['exposed']=='True' for r in direct)]
    expected_a={
        'machine':{'SERIAL':[54,58],'CONCURRENT':[85,38]},
        'Reviewer1':{'SERIAL':[47,55],'CONCURRENT':[123,38]},
        'Reviewer2':{'SERIAL':[48,51],'CONCURRENT':[70,38]},
    }
    require(panel_a==expected_a,'Figure 3a numbers')

    effects=load('results/final-revalidation/coherent96/FINAL_FAMILY_EFFECTS.json')
    panel_b={}
    for stratum in sorted({r['stratum'] for r in effects}):
        subset=[r for r in effects if r['stratum']==stratum]
        require(len(subset)==4,'Figure 3b stratum size')
        panel_b[stratum]=[
            sum(r['base_I_F'] for r in subset)/4,
            sum(r['explicit_I_F'] for r in subset)/4,
        ]
    require(panel_b=={
        'assembly':[.75,0.0],'handover':[.65625,0.0],'insertion':[.65625,0.0],
        'inspection':[.65625,0.0],'packaging':[.65625,0.0],'shared_resource':[.75,.09375],
    },'Figure 3b numbers')

    scoring=load('results/final-revalidation/main384/RQ3_SCORING_ROWS.json')
    obligations=['BUFFER_EVENT_PROTOCOL','BUFFER_OCCUPANCY_OWNER','LONG_RANGE_DEPENDENCY','ATTRIBUTE_COMBINATION']
    panel4={}
    for method in ['dynamic','deepseek_flash','glm5']:
        panel4[method]={}
        for obligation in obligations:
            subset=[r for r in scoring[method]['R3'] if r['obligation']==obligation and r['truth']=='V']
            panel4[method][obligation]=[len(subset),sum(r['prediction']!='V' for r in subset),sum(r['prediction']=='C' for r in subset)]
    expected4={
        'dynamic':{'BUFFER_EVENT_PROTOCOL':[27,1,1],'BUFFER_OCCUPANCY_OWNER':[48,0,0],'LONG_RANGE_DEPENDENCY':[31,14,1],'ATTRIBUTE_COMBINATION':[69,64,8]},
        'deepseek_flash':{'BUFFER_EVENT_PROTOCOL':[27,19,17],'BUFFER_OCCUPANCY_OWNER':[48,41,34],'LONG_RANGE_DEPENDENCY':[31,28,17],'ATTRIBUTE_COMBINATION':[69,59,38]},
        'glm5':{'BUFFER_EVENT_PROTOCOL':[27,15,5],'BUFFER_OCCUPANCY_OWNER':[48,34,22],'LONG_RANGE_DEPENDENCY':[31,26,16],'ATTRIBUTE_COMBINATION':[69,51,27]},
    }
    require(panel4==expected4,'Figure 4 numbers')
    return {
        'checked_images':4,
        'figure3a_structure_V_and_exposure':panel_a,
        'figure3b_base_and_explicit_interactions':panel_b,
        'figure4_denominator_nondetection_false_compliance':panel4,
        'scope':'Image-byte integrity, evidence-source binding, and printed numerical payload; not deterministic figure regeneration',
    }

def main():
    failures=[]
    for name,fn in [('manifest',manifest),('assignments',assignments),('main384',main384),('methods',methods),('factorial320',factorial),('coherent96',coherent),('recomposition360',recomposition),('manuscript_tables',manuscript_tables),('rq4_supporting_cohorts',rq4_supporting),('figures',figures)]:
        try:
            CHECKS[name]={'status':'PASS','result':fn()}
            print(name+': PASS')
        except Exception as e:
            CHECKS[name]={'status':'FAIL','reason':str(e)};failures.append(name)
            print(name+': FAIL: '+str(e))
    result={'status':'FAIL' if failures else 'PASS','python':sys.version.split()[0],
            'scope':'Offline aggregation and file integrity; no new generations, execution, or human review','checks':CHECKS}
    REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return bool(failures)

if __name__=='__main__':sys.exit(main())
