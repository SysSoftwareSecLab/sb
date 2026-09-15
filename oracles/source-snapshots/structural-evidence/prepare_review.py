from pathlib import Path
import sys,json,hashlib,pprint,shutil,zipfile,collections,ast
P=Path(__file__).resolve().parent;Q=P.parents[1];R=Q.parents[1]
sys.path.insert(0,str(P));from measure import units

def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifest=json.loads((P/'MANIFEST.json').read_text());results=json.loads((P/'RESULTS.json').read_text());assert all(r['target_pass'] for r in results['rows']);assert all(r['complete'] and r['labels']['GEOMETRY']=='C' for r in results['rows'] if not r['case_id'].endswith('mutation'))
 baseline=json.loads((P.parent/'BASELINE_SNAPSHOT.json').read_text());assert all(sha(R/f['path'])==f['sha256'] for f in baseline['files'])
 pair=[]
 for fid in ['S04','S05']:
  counts=[];measurements=[]
  for v in ['A','B']:
   cap=json.loads((P/'cases'/f'{fid}-{v}-reference/CAPTURE.json').read_text());ev=cap['trusted_events'];counts.append(dict(collections.Counter(c['action'] for c in cap['call_audit'])));intervals=[]
   for e in ev:
    if e['phase']!='start' or e['args'].get('arm') not in ['LEFT','RIGHT']:continue
    end=next((x for x in ev if x['phase']=='complete' and x.get('operation_id')==e.get('operation_id') and x['action']==e['action']),None)
    if end:intervals.append((e['action'],e['args']['arm'],e['time'],end['time']))
   overlap=lambda motion:sum(a!=b and (not motion or act==act2=='move') and min(e,f)>max(s,t)+1e-9 for n,(act,a,s,e) in enumerate(intervals) for act2,b,t,f in intervals[n+1:])
   measurements.append(dict(variant=v,virtual_seconds=ev[-1]['time'],cross_arm_action_overlap_pairs=overlap(False),cross_arm_move_overlap_pairs=overlap(True)))
  assert counts[0]==counts[1];pair.append(dict(family=fid,identical_action_counts=counts[0],measurements=measurements))
 write(P/'PAIR_AUDIT.json',pair)
 lineage=[dict(family='S04',title='双向支持交换',nearest=['P01 单向容量一缓存生产—消费','D03 双验证汇合至单消费者'],difference='两个物体沿相反方向交叉，两个臂均先为生产者、再为消费者。双方先释放与撤离打破相互等待，随后分别依赖对方的物体凭据；并非同一LEFT生产/RIGHT消费链加长。',claim='在所列既有开发任务中，S04引入双角色、双物体交叉的依赖结构；可作为结构保留候选。此结论不等于文献创新性已证实。',qualification='主要串行/并发配对；参考实际两臂搬运重叠发生。'),dict(family='S05',title='共享物体排他分支',nearest=['D04 单一臂选择新旧观测','P02 两臂最终都执行的互斥资源作业'],difference='两臂检查同一分配事实，只有被选择的一条运输分支允许执行，另一分支不应发出运动；不同于两臂轮流都完成作业或仅替换同一消费者的观测。',claim='在所列既有开发任务中，S05引入竞争候选到单一执行者的排他分支；可作为结构保留候选。不能将其参考执行称为双臂搬运并发，因为未选中臂只有检查。',qualification='次要分支/调度对照；参考无跨臂move重叠，仅检查并行，不混入双臂物理并发主效应。')]
 write(P/'LINEAGE.json',{'families':lineage,'human_admission_pending':True,'formal_holdout_families_admitted':0,'tested_guard_modified':False,'old_baseline_files_unchanged':len(baseline['files'])})
 D=P/'review_package';D.mkdir(exist_ok=True);items=[];private=[]
 for c in manifest['cases']:
  if c['role']=='semantic':continue
  rid='N-'+hashlib.sha256(c['case_id'].encode()).hexdigest()[:12].upper();src=P/'cases'/c['case_id'];dest=D/'cases'/rid;dest.mkdir(parents=True,exist_ok=True)
  for file in ['candidate.py','SPEC.json','GEOMETRY.json']:shutil.copy(src/file,dest/file)
  cap=json.loads((src/'CAPTURE.json').read_text());write(dest/'EVENTS.json',cap['trusted_events']);write(dest/'CALLS.json',cap['call_audit']);write(dest/'EXECUTION.json',{k:cap.get(k) for k in ['process','execution_lifecycle_complete','child_lifecycle_report','call_audit_complete']})
  rules=units(c['family_id']);(dest/'审核要求.md').write_text('# '+rid+'\n\n'+'\n\n'.join('## '+k+'\n\n'+v for k,v in rules.items())+'\n')
  items.append(dict(review_id=rid,family=c['family_id'],obligations=rules,files={f.name:sha(f) for f in sorted(dest.iterdir())}));private.append(dict(review_id=rid,case_id=c['case_id'],role=c['role']))
 items.sort(key=lambda i:i['review_id']);package_id=hashlib.sha256(json.dumps({'items':items,'lineage':lineage},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 write(D/'PACKAGE.json',dict(package_id=package_id,items=items,lineage=lineage));write(P/'REVIEW_PRIVATE_MAP.json',private)
 for name in ['Reviewer1','Reviewer2']:
  data=dict(schema='STRUCTURAL_REVIEW_V1',package_id=package_id,reviewer_name=name,records=[dict(review_id=i['review_id'],duration_s=None,judgments=[dict(obligation=k,label=None,reason='',event_indices=[],request_ids=[]) for k in i['obligations']]) for i in items],structure_reviews=[dict(family=i['family'],assessment=None,reason='',duration_s=None) for i in lineage])
  (D/f'STRUCTURAL_REVIEW_{name}.py').write_text('# -*- coding: utf-8 -*-\n# 40项义务label填C/V/U/NA，reason写依据。2项结构assessment填支持/不支持/未决。\n# 不用运行本文件或candidate.py；未计时duration_s保持None。\nREVIEW = '+pprint.pformat(data,width=110,sort_dicts=False)+'\n')
 shutil.copy(Q/'trace_dev_v1/PUBLIC_CONTRACT.md',D/'公共API说明.md')
 references=[Q/'batch_13_15/library/P01-A-reference',Q/'batch_13_15/library/P02-B-reference',Q/'batch_7_9/library/D03-B-reference',Q/'batch_7_9/library/D04-A-reference']
 for src in references:
  dest=D/'lineage_sources'/src.name;dest.mkdir(parents=True,exist_ok=True)
  for file in ['SPEC.json','candidate.py']:shutil.copy(src/file,dest/file)
 (D/'结构对照.md').write_text('# 两项结构判断\n\n只核对相对于所附既有开发程序的具体结构差异，不要求重做文献检索或证明论文创新性。两人可判不支持/未决，并说明哪个旧结构等价或哪段定义不清。\n\n'+'\n\n'.join('## '+i['family']+' '+i['title']+'\n\n近邻：'+'；'.join(i['nearest'])+'\n\n差异：'+i['difference']+'\n\n请审核的陈述：'+i['claim']+'\n\n范围：'+i['qualification'] for i in lineage)+'\n')
 (D/'先读我.md').write_text('''# 新任务审核代码包：8份程序＋2项结构判断

这次是两个新任务的实际测量，不是重审原107项。语义改名对照已通过，只发8份非重复程序，每份5项义务，共40项；另有2项结构陈述。每人独立完成，不看对方答案。

1. 按自己的STRUCTURAL_REVIEW_姓名.py中review_id查看cases：读SPEC、代码、审核要求，再核对EVENTS、CALLS、EXECUTION和GEOMETRY。无需执行程序或安装Python。
2. 在自己的.py填40项label（C/V/U/NA）和reason；可填事件/请求编号，也可直接在reason引用编号或代码行。C限实际义务；未发生物体释放时相应释放义务可NA；明确异常退出与目标失败不等于未知后续安全，几何证据不足则保留U。
3. 读结构对照.md，必要时查看lineage_sources中的既有参考。填写2项structure_reviews：assessment为支持/不支持/未决，reason说明。只判断本项目已给来源中的结构区别，不负责认定学术首创。
4. 未实际计时就保持duration_s=None；可每次做4份。完成后返回两份STRUCTURAL_REVIEW_姓名.py即可，不必返还全部证据。

没有预填人审标签，不含逐项机器综合答案、变异身份或被测方法输出。结构说明是待核对的设计陈述，不是要求赞同。收到后只核对实际分歧，不要求重复审核一致且依据充分的项目。
''')
 zp=P/'新任务8程序双人审核.zip'
 with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
  for f in sorted(D.rglob('*')):
   if f.is_file():z.write(f,'新任务8程序双人审核/'+str(f.relative_to(D)))
 with zipfile.ZipFile(zp) as z:assert z.testzip() is None
 write(P/'REVIEW_MANIFEST.json',dict(package_id=package_id,programs_per_reviewer=8,obligation_judgments_per_reviewer=40,structure_assessments_per_reviewer=2,human_prefills=0,zip_sha256=sha(zp),zip=str(zp)))
 print(json.dumps({'zip':str(zp),'programs':8,'obligations':40,'structure_assessments':2,'pair_audit':pair},ensure_ascii=False))
if __name__=='__main__':main()
