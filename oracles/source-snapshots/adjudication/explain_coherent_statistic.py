"""Recalculate the separate 67.19pp estimand from stored rows; no replay."""
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]/'paper3_bisafebench'
RUN=ROOT/'05_formal/rq2_coherent_pair_confirmation_v1'
OUT=HERE/'coherent_statistic_transparency'
CONDS=('SERIAL_SHORT','SERIAL_LONG','CONCURRENT_SHORT','CONCURRENT_LONG')

def load(p):return json.loads(p.read_text())
def mean(xs):return sum(xs)/len(xs)
def main():
    rows=load(RUN/'FINAL_ROWS.json');assert len(rows)==6144
    grouped=defaultdict(list)
    for r in rows:
        assert r['P'] in ('C','V','NE','S0') and r['F']==int(r['P']!='C')
        grouped[(r['task_id'],r['profile'],r['arm'],r['condition'])].append(r)
    assert len(grouped)==384
    rates={}
    for key,rs in grouped.items():
        assert len(rs)==16 and {r['seed'] for r in rs}==set(range(16))
        rates[key]=Fraction(sum(r['F'] for r in rs),16)
    tasks=sorted({r['task_id'] for r in rows})
    profiles=('deepseek_flash','glm5')
    def interaction(t,p,a):
        return rates[t,p,a,'CONCURRENT_LONG']-rates[t,p,a,'CONCURRENT_SHORT']-rates[t,p,a,'SERIAL_LONG']+rates[t,p,a,'SERIAL_SHORT']
    effects=[]
    for t in tasks:
        b=mean([interaction(t,p,'BASE') for p in profiles])
        e=mean([interaction(t,p,'EXPLICIT') for p in profiles])
        effects.append({'task_id':t,'base_I_F':float(b),'explicit_I_F':float(e),'D_F':float(b-e)})
    frozen=load(RUN/'FINAL_FAMILY_EFFECTS.json')
    for e in effects:
        f=next(f for f in frozen if f['task_id']==e['task_id'])
        assert all(e[k]==f[k] for k in e)
    def boot(key,seed):
        rng=random.Random(seed)
        # Preserve frozen context order and order-statistic percentile rule.
        draws=sorted(mean([rng.choice(frozen)[key] for _ in frozen]) for _ in range(10000))
        return [draws[int(.025*(len(draws)-1))],draws[int(.975*(len(draws)-1))]]
    base=mean([e['base_I_F'] for e in effects]);explicit=mean([e['explicit_I_F'] for e in effects]);delta=base-explicit
    machine=load(RUN/'FINAL_MACHINE_RESULT.json')
    ci=boot('D_F',26091404)
    assert delta==machine['mitigation_mean_D_F']==.671875 and ci==machine['mitigation_cluster_bootstrap_95_CI']
    cells={}
    for a in ('BASE','EXPLICIT'):
        cells[a]={}
        for c in CONDS:
            rs=[r for r in rows if r['arm']==a and r['condition']==c]
            cells[a][c]={'assigned_rows':len(rs),'F':sum(r['F'] for r in rs),'P_counts':dict(Counter(r['P'] for r in rs)),'F_rate':sum(r['F'] for r in rs)/len(rs)}
    result={'status':'EXACT_REPRODUCTION_FROM_FROZEN_ROWS_NO_NEW_EXECUTION','contexts':24,'models':2,'interface_conditions':2,'scheduling_window_cells':4,'seeds_per_cell':16,'assigned_rows':6144,
      'unit':'24 context clusters, each containing two matched model pairs and all four schedule/window cells in both interfaces',
      'equal_weighting':'1/16 per seed, 1/2 per model within context, 1/24 per context; no additional stratum weights',
      'cells':cells,'base_interaction':base,'explicit_interaction':explicit,'interaction_reduction':delta,
      'interaction_reduction_exact_fraction':str(Fraction(delta)),
      'bootstrap_95':ci,'bootstrap_reps':10000,'bootstrap_seed':26091404,'bootstrap_percentile_rule':'sorted_draws[int(p*(9999))], no interpolation',
      'context_effects':effects,'retained_invalid_BASE_programs':sum(not x['interface_valid'] for x in load(RUN/'FINAL_PROGRAM_EFFECTS.json') if x['arm']=='BASE'),
      'human_pair_counts':load(RUN/'FINAL_HUMAN_VALIDATED_RQ2_RESULT.json')['paired_mitigation'],
      'human_matched_count_reduction':41/48,
      'scope':'Machine interaction reduction is not human matched repair fraction, direct physical safety reduction, or a percentage relative reduction.',
      'input_sha256':{n:hashlib.sha256((RUN/n).read_bytes()).hexdigest() for n in ['FINAL_ROWS.json','FINAL_FAMILY_EFFECTS.json','FINAL_MACHINE_RESULT.json','FINAL_HUMAN_VALIDATED_RQ2_RESULT.json']}}
    OUT.mkdir(exist_ok=True)
    (OUT/'RECOMPUTED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('context_effects','input_sha256')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
