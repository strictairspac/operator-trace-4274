import copy
import redis
from fastapi import HTTPException
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models.dataset import Dataset
from src.models.plan import Plan
from src.models.trace import Trace
from src.utils.serialization import record
queue=redis.Redis.from_url(REDIS_URL)
def list_items():
 with Session() as s:return [record(r) for r in s.query(Trace).order_by(Trace.id.desc()).limit(100).all()]
def detail(item_id):
 with Session() as s:
  row=s.get(Trace,item_id)
  if not row:raise HTTPException(404,'未找到执行轨迹')
  return record(row)
def _enqueue(row_id):
 try:queue.rpush('operator-traces',row_id)
 except redis.RedisError:
  with Session() as s:r=s.get(Trace,row_id);r.status='failed';r.error='队列不可用，请创建新任务';s.commit()
  raise HTTPException(503,'队列不可用，请稍后重试')
def create(data):
 with Session() as s:
  p=s.get(Plan,data.plan_id)
  if not p:raise HTTPException(404,'未找到算子计划')
  d=s.get(Dataset,p.dataset_id)
  row=Trace(name=data.name,plan_id=p.id,dataset_id=d.id,status='queued',snapshot={'dataset':record(d),'plan':record(p)})
  s.add(row);s.commit();s.refresh(row);result=record(row)
 _enqueue(result['id'])
 return result
def rerun(item_id):
 """按剖面保存的输入快照重新排队；本地表和计划的后续编辑不影响复跑内容。"""
 with Session() as s:
  orig=s.get(Trace,item_id)
  if not orig:raise HTTPException(404,'未找到执行轨迹')
  if orig.status not in ('completed','failed'):raise HTTPException(400,'排队中或执行中的剖面不能复跑，请等待执行结束')
  base=(orig.name+'-复跑')[:120];name=base
  for n in range(2,500):
   if not s.query(Trace).filter_by(name=name).first():break
   suffix=f'-{n}';name=base[:120-len(suffix)]+suffix
  else:raise HTTPException(409,'复跑记录过多，请清理后重试')
  row=Trace(name=name,plan_id=orig.plan_id,dataset_id=orig.dataset_id,status='queued',snapshot=copy.deepcopy(orig.snapshot))
  s.add(row);s.commit();s.refresh(row);result=record(row)
 _enqueue(result['id'])
 return result
