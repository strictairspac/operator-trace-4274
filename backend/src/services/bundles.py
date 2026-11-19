"""剖面包：把已完成剖面连同当时的表、计划、结果打成内容寻址的JSON包，跨库迁移。

导入按内容哈希共用目的库已有表/计划；同名不同内容改名另存，只插不改。
整包校验（结构/逐条校验和/依赖/复算核对）全部通过后才在单事务内落库，
失败整体回滚；traces.import_key唯一约束与PG咨询锁保证并发与重试不重复建档。
"""
import copy
from datetime import datetime,timezone
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from src.config.database import Session
from src.models.dataset import Dataset
from src.models.plan import Plan
from src.models.trace import Trace
from src.schemas.business import Bundle
from src.services.operators import execute,validate_steps
from src.utils.serialization import record,digest,dataset_content_hash,plan_content_hash
FORMAT='operator-trace-bundle'
IMPORT_LOCK_KEY=73620261117
def _ds_entry(name,description,sensors,readings):
 return {'key':'ds-'+dataset_content_hash(sensors,readings)[:16],'name':name,'description':description,'sensors':sensors,'readings':readings,'checksum':digest({'name':name,'description':description,'sensors':sensors,'readings':readings})}
def _pl_entry(name,note,steps,ds_key,ds_hash):
 return {'key':'pl-'+plan_content_hash(steps,ds_hash)[:16],'name':name,'note':note,'dataset_key':ds_key,'steps':steps,'checksum':digest({'name':name,'note':note,'steps':steps,'dataset_key':ds_key})}
def _tr_entry(name,status,result,error,created_at,ds_key,pl_key):
 body={'name':name,'status':status,'result':result,'error':error,'created_at':created_at,'dataset_key':ds_key,'plan_key':pl_key}
 return {'key':'tr-'+digest(body)[:16],'checksum':digest(body),**body}
def export_bundle(trace_ids):
 ids=list(dict.fromkeys(trace_ids))
 with Session() as s:
  rows=[]
  for i in ids:
   t=s.get(Trace,i)
   if not t:raise HTTPException(404,f'未找到执行轨迹 {i}')
   if t.status!='completed':raise HTTPException(400,f'仅已完成的剖面可以打包：{t.name} 尚未完成')
   rows.append(t)
  rows.sort(key=lambda r:r.id)
  datasets,plans,traces={},{},[]
  for t in rows:
   snap=t.snapshot or {}
   ds,pl=snap.get('dataset'),snap.get('plan')
   if not isinstance(ds,dict) or not isinstance(pl,dict) or not isinstance(ds.get('sensors'),list) or not isinstance(ds.get('readings'),list) or not isinstance(pl.get('steps'),list):
    raise HTTPException(400,f'剖面 {t.name} 缺少完整输入快照，无法打包')
   d=_ds_entry(ds.get('name',''),ds.get('description',''),ds['sensors'],ds['readings'])
   datasets.setdefault(d['key'],d)
   p=_pl_entry(pl.get('name',''),pl.get('note',''),pl['steps'],d['key'],dataset_content_hash(ds['sensors'],ds['readings']))
   plans.setdefault(p['key'],p)
   created=t.created_at.isoformat() if t.created_at else datetime.now(timezone.utc).isoformat()
   traces.append(_tr_entry(t.name,t.status,t.result,t.error,created,d['key'],p['key']))
  body={'format':FORMAT,'version':1,'datasets':list(datasets.values()),'plans':list(plans.values()),'traces':traces}
  return {**body,'exported_at':datetime.now(timezone.utc).isoformat(),'bundle_id':digest(body)}
def _free_name(s,model,base):
 for suffix in ['','·导入']+[f'·导入{n}' for n in range(2,500)]:
  name=base[:120-len(suffix)]+suffix if suffix else base[:120]
  if not s.query(model).filter_by(name=name).first():return name
 raise HTTPException(409,'名称冲突过多，无法为导入记录命名')
def _verify(bundle):
 if bundle.version!=1:raise HTTPException(400,f'不支持的剖面包版本 {bundle.version}')
 ds_by_key={}
 for e in bundle.datasets:
  sensors=[x.model_dump() for x in e.sensors];readings=[x.model_dump() for x in e.readings]
  if e.key!='ds-'+dataset_content_hash(sensors,readings)[:16] or e.checksum!=digest({'name':e.name,'description':e.description,'sensors':sensors,'readings':readings}):
   raise HTTPException(400,f'剖面包已损坏：数据集 {e.key} 校验失败')
  if e.key in ds_by_key:raise HTTPException(400,f'剖面包已损坏：数据集条目 {e.key} 重复')
  ds_by_key[e.key]=e
 pl_by_key={}
 for e in bundle.plans:
  ds=ds_by_key.get(e.dataset_key)
  if not ds:raise HTTPException(400,f'剖面包缺少依赖：计划 {e.name} 引用的数据集 {e.dataset_key} 不在包内')
  ds_hash=dataset_content_hash([x.model_dump() for x in ds.sensors],[x.model_dump() for x in ds.readings])
  if e.key!='pl-'+plan_content_hash(e.steps,ds_hash)[:16] or e.checksum!=digest({'name':e.name,'note':e.note,'steps':e.steps,'dataset_key':e.dataset_key}):
   raise HTTPException(400,f'剖面包已损坏：计划 {e.key} 校验失败')
  if e.key in pl_by_key:raise HTTPException(400,f'剖面包已损坏：计划条目 {e.key} 重复')
  try:validate_steps(e.steps)
  except ValueError as err:raise HTTPException(400,f'剖面包已损坏：计划 {e.name} 的算子序列无效（{err}）')
  pl_by_key[e.key]=e
 seen=set()
 for e in bundle.traces:
  if e.status!='completed':raise HTTPException(400,f'剖面包已损坏：轨迹 {e.name} 不是已完成状态')
  if e.dataset_key not in ds_by_key:raise HTTPException(400,f'剖面包缺少依赖：轨迹 {e.name} 引用的数据集 {e.dataset_key} 不在包内')
  if e.plan_key not in pl_by_key:raise HTTPException(400,f'剖面包缺少依赖：轨迹 {e.name} 引用的计划 {e.plan_key} 不在包内')
  body={'name':e.name,'status':e.status,'result':e.result,'error':e.error,'created_at':e.created_at.isoformat(),'dataset_key':e.dataset_key,'plan_key':e.plan_key}
  if e.checksum!=digest(body) or e.key!='tr-'+e.checksum[:16]:raise HTTPException(400,f'剖面包已损坏：轨迹 {e.name} 校验失败')
  if e.key in seen:raise HTTPException(400,f'剖面包已损坏：轨迹条目 {e.key} 重复')
  seen.add(e.key)
 body={'format':FORMAT,'version':bundle.version,'datasets':[e.model_dump() for e in bundle.datasets],'plans':[e.model_dump() for e in bundle.plans],'traces':[{**e.model_dump(),'created_at':e.created_at.isoformat()} for e in bundle.traces]}
 if bundle.bundle_id!=digest(body):raise HTTPException(400,'剖面包已损坏：整体校验失败')
 for e in bundle.traces:
  ds,pl=ds_by_key[e.dataset_key],pl_by_key[e.plan_key]
  data={'sensors':[x.model_dump() for x in ds.sensors],'readings':[x.model_dump() for x in ds.readings]}
  try:fresh=execute(data,copy.deepcopy(pl.steps))
  except Exception:raise HTTPException(400,f'剖面包校验失败：轨迹 {e.name} 的随包输入无法复算')
  old=e.result
  if fresh['checksum']!=old.get('checksum') or fresh['row_visits']!=old.get('row_visits') or fresh['output_rows']!=old.get('output_rows'):
   raise HTTPException(400,f'剖面包校验失败：轨迹 {e.name} 的结果与随包输入不一致')
  ops=old.get('operators')
  if not isinstance(ops,list) or len(ops)!=len(fresh['operators']) or any(o.get('op')!=n['op'] or o.get('input_rows')!=n['input_rows'] or o.get('output_rows')!=n['output_rows'] or o.get('checksum')!=n['checksum'] for o,n in zip(ops,fresh['operators'])):
   raise HTTPException(400,f'剖面包校验失败：轨迹 {e.name} 的逐步摘要与随包输入不一致')
 return ds_by_key,pl_by_key
def import_bundle(payload):
 try:bundle=Bundle.model_validate(payload)
 except ValidationError as exc:
  err=exc.errors()[0];loc='.'.join(str(x) for x in err['loc'])
  raise HTTPException(400,f'剖面包结构不合法（{loc}：{err["msg"]}）')
 ds_by_key,pl_by_key=_verify(bundle)
 try:
  with Session() as s:
   if s.get_bind().dialect.name=='postgresql':s.execute(text('SELECT pg_advisory_xact_lock(:k)'),{'k':IMPORT_LOCK_KEY})
   ds_map={}
   for e in bundle.datasets:
    sensors=[x.model_dump() for x in e.sensors];readings=[x.model_dump() for x in e.readings]
    ch=dataset_content_hash(sensors,readings)
    row=s.query(Dataset).filter_by(content_hash=ch).first();shared=bool(row)
    if not row:
     row=Dataset(name=_free_name(s,Dataset,e.name),description=e.description,sensors=sensors,readings=readings,content_hash=ch)
     s.add(row);s.flush()
    ds_map[e.key]=(row,shared)
   pl_map={}
   for e in bundle.plans:
    ds_row=ds_map[e.dataset_key][0]
    ch=plan_content_hash(e.steps,ds_row.content_hash)
    row=s.query(Plan).filter_by(content_hash=ch).first();shared=bool(row)
    if not row:
     row=Plan(name=_free_name(s,Plan,e.name),note=e.note,steps=e.steps,dataset_id=ds_row.id,content_hash=ch)
     s.add(row);s.flush()
    pl_map[e.key]=(row,shared)
   out=[]
   for e in bundle.traces:
    ikey='bundle-v1:'+e.checksum
    row=s.query(Trace).filter_by(import_key=ikey).first();reused=bool(row)
    if not row:
     ds_row=ds_map[e.dataset_key][0];pl_row=pl_map[e.plan_key][0]
     ds_e,pl_e=ds_by_key[e.dataset_key],pl_by_key[e.plan_key]
     snapshot={'dataset':{'id':ds_row.id,'name':ds_e.name,'description':ds_e.description,'sensors':[x.model_dump() for x in ds_e.sensors],'readings':[x.model_dump() for x in ds_e.readings]},
      'plan':{'id':pl_row.id,'name':pl_e.name,'dataset_id':ds_row.id,'steps':pl_e.steps,'note':pl_e.note}}
     row=Trace(name=_free_name(s,Trace,e.name),dataset_id=ds_row.id,plan_id=pl_row.id,status='completed',result=e.result,error=e.error,snapshot=snapshot,source='imported',import_key=ikey,created_at=e.created_at)
     s.add(row);s.flush()
    out.append({'id':row.id,'name':row.name,'reused':reused})
   summary={'bundle_id':bundle.bundle_id,'traces':out,
    'datasets':[{'key':k,'id':r.id,'name':r.name,'shared':sh} for k,(r,sh) in ds_map.items()],
    'plans':[{'key':k,'id':r.id,'name':r.name,'shared':sh} for k,(r,sh) in pl_map.items()]}
   s.commit()
   return summary
 except IntegrityError:
  raise HTTPException(409,'导入与并发写入冲突，未留下部分数据；请直接重试，已导入的内容不会重复建档')
