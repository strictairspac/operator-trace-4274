from fastapi import HTTPException
from src.config.database import Session
from src.models.plan import Plan
from src.utils.serialization import record,dataset_content_hash,plan_content_hash
from src.models.dataset import Dataset

def list_items():
 with Session() as s:return [record(r) for r in s.query(Plan).order_by(Plan.id.desc()).all()]
def save(data,item_id=None):
 with Session() as s:
  d=s.get(Dataset,data.dataset_id)
  if not d:raise HTTPException(404,'未找到数据集')
  row=s.get(Plan,item_id) if item_id else Plan()
  if not row:raise HTTPException(404,'未找到记录')
  for k,v in data.model_dump().items():setattr(row,k,v)
  row.content_hash=plan_content_hash(row.steps,d.content_hash or dataset_content_hash(d.sensors,d.readings))
  s.add(row);s.commit();s.refresh(row);return record(row)
