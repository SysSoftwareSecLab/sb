"""Receive actual calibration submissions; preserve bytes and explicit missing time."""
from collections import Counter
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import argparse
from intake_review import validate
P=Path(__file__).resolve().parent

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def receive(paths):
    loaded=[(Path(p),*validate(p)) for p in paths]
    if len({d['reviewer_name'] for _,d,_ in loaded})!=len(loaded):raise ValueError('Different actual reviewers required')
    out=P/'human_calibration';out.mkdir(exist_ok=True)
    old=json.loads((out/'RECEIPT.json').read_text()) if (out/'RECEIPT.json').exists() else None
    inputs={d['reviewer_name']:digest(p) for p,d,_ in loaded}
    if old:
        if old['input_sha256']==inputs:return old
        raise ValueError('Existing received batch differs; preserve it and handle the revision explicitly')
    pack={x['review_id']:x for x in json.loads((P/'review_20/DATA.json').read_text())}
    keys={x['review_id']:x for x in json.loads((P/'REVIEW_PRIVATE_KEY.json').read_text())}
    reviewers=[];byname={}
    for src,data,stats in loaded:
        alias='Reviewer1' if data['reviewer_name']=='Reviewer1' else 'Reviewer2'
        dest=out/(alias+'.received.json');dest.write_bytes(src.read_bytes())
        # A sum over no measurements must not become zero human work time.
        stats['actual_total_seconds']=stats['actual_total_seconds'] if stats['recorded_timings'] else None
        stats.update(received_file=dest.name,sha256=digest(dest),label_counts=dict(Counter(r['label'] for r in data['records'] if r['label'] is not None)))
        reviewers.append(stats);byname[data['reviewer_name']]={x['review_id']:x for x in data['records']}
    rows=[];disagreements=[]
    for rid,packet in pack.items():
        records={n:rs[rid] for n,rs in byname.items()};labels=[x['label'] for x in records.values()]
        agreed=len(labels)==2 and None not in labels and len(set(labels))==1
        if len(labels)==2 and None not in labels and not agreed:disagreements.append(rid)
        case=keys[rid]['case_id'];d=P/'library'/case
        development=json.loads((d/'ATOMS.json').read_text())['summary'].get(packet['target_obligation'],'NA')
        rows.append(dict(review_id=rid,case_id=case,target_obligation=packet['target_obligation'],public_rule=packet['public_rule'],
                         reviewers=records,agreed_label=labels[0] if agreed else None,
                         status='DUAL_AGREEMENT' if agreed else 'DISAGREEMENT' if rid in disagreements else 'PENDING',
                         development_label=development,agrees_with_development=agreed and development==labels[0],
                         source_sha256=digest(d/'candidate.py'),spec_sha256=digest(d/'SPEC.json'),capture_sha256=digest(d/'CAPTURE.json'),
                         whole_program_safety_label=None))
    write(out/'LEDGER.json',dict(scope='20_SELF_AUTHORED_DEVELOPMENT_CONTROLS_TARGET_ATOMS_ONLY',rows=rows,
                               no_new_natural_data=True,no_inferred_whole_program_labels=True,human_arbitration_performed=False))
    receipt=dict(status='DUAL_CALIBRATION_AGREEMENT_COMPLETE' if all(x['status']=='DUAL_AGREEMENT' for x in rows) else 'CALIBRATION_PENDING',
                 received_utc=datetime.now(timezone.utc).isoformat(),input_sha256=inputs,reviewers=reviewers,review_packets=len(rows),
                 paired_completed=sum(len([v for v in x['reviewers'].values() if v['label'] is not None])==2 for x in rows),
                 paired_agreements=sum(x['status']=='DUAL_AGREEMENT' for x in rows),disagreement_ids=disagreements,
                 agreed_label_counts=dict(Counter(x['agreed_label'] for x in rows if x['agreed_label'] is not None)),
                 times_policy='Unrecorded remains null; no zero-duration inference, no retrospective imputation',
                 reviewer_identity_basis='Anonymous reviewer aliases supplied with separate submissions; no legal-name collection',
                 independence_basis='Separate named submissions under issued independent-review instructions; process not inferred from textual similarity or label agreement',
                 scope='Calibration only, not natural risk rate or general oracle accuracy; same-developer control design and incomplete whole-contract coverage remain',
                 review_data_sha256=digest(P/'review_20/DATA.json'),review_archive_sha256=digest(P/'QUALITY_REVIEW_20.zip'),
                 ledger_sha256=digest(out/'LEDGER.json'),intake_code_sha256=digest(__file__),validation_code_sha256=digest(P/'intake_review.py'),
                 stage5_ledger_modified=False,model_calls=0)
    write(out/'RECEIPT.json',receipt)
    return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('files',nargs='+');a=p.parse_args()
    print(json.dumps(receive(a.files),ensure_ascii=False,indent=2))
