from sqlalchemy import text
from src.config.database import Base,engine,Session
from src.models.identity import User,Audit
from src.models.dataset import Dataset
from src.models.plan import Plan
from src.models.trace import Trace
from src.utils.security import hash_password
from src.utils.serialization import dataset_content_hash,plan_content_hash
DEFAULT_STEPS=[{'op':'scan','source':'readings'},{'op':'filter','field':'value','compare':'gte','value':50},{'op':'hash_join','right':'sensors','left_key':'sensor_id','right_key':'sensor_id'},{'op':'group','keys':['zone'],'measure':'value','aggregate':'avg'}]
COLUMN_DDL=[('datasets','content_hash','VARCHAR(64)'),('plans','content_hash','VARCHAR(64)'),('traces','source',"VARCHAR(20) NOT NULL DEFAULT 'local'"),('traces','import_key','VARCHAR(80)')]
INDEX_DDL=["CREATE INDEX IF NOT EXISTS ix_datasets_content_hash ON datasets (content_hash)","CREATE INDEX IF NOT EXISTS ix_plans_content_hash ON plans (content_hash)","CREATE UNIQUE INDEX IF NOT EXISTS uq_traces_import_key ON traces (import_key)"]
def migrate():
 """建表 + 增量列/索引 + 内容哈希回填；幂等，可重复执行。"""
 Base.metadata.create_all(engine)
 with engine.begin() as c:
  pg=c.dialect.name=='postgresql'
  for table,column,ddl in COLUMN_DDL:
   if pg:c.execute(text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}'))
   elif column not in [r[1] for r in c.execute(text(f'PRAGMA table_info({table})'))]:c.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'))
  for stmt in INDEX_DDL:c.execute(text(stmt))
 with Session() as s:
  dirty=False
  for d in s.query(Dataset).filter(Dataset.content_hash.is_(None)).all():d.content_hash=dataset_content_hash(d.sensors,d.readings);dirty=True
  for p in s.query(Plan).filter(Plan.content_hash.is_(None)).all():
   d=s.get(Dataset,p.dataset_id)
   if d:p.content_hash=plan_content_hash(p.steps,d.content_hash or dataset_content_hash(d.sensors,d.readings));dirty=True
  if dirty:s.commit()
def seed():
 migrate()
 with Session() as s:
  for role in ('admin','operator','viewer'):
   if not s.query(User).filter_by(email=role+'@operator.local').first():s.add(User(email=role+'@operator.local',role=role,password=hash_password('Trace2026!')))
  sensors=[{'sensor_id':i,'zone':['北场','南场','试验间'][i%3],'device_type':['pump','motor','valve'][i%3]} for i in range(1,13)]
  readings=[{'sensor_id':i%12+1,'value':round(25+(i*13%800)/10,1),'recorded_at':f'2026-11-17T{8+i//60:02d}:{i%60:02d}:00'} for i in range(240)]
  seeds=[('松原日班温升采样',sensors,readings,'240条采样 / 12个传感器 / 区域温升复核'),('空数据边界',[],[],'验证空输入和空聚合'),('重复键校验',[{'sensor_id':1,'zone':'北场','device_type':'pump'},{'sensor_id':1,'zone':'复核点','device_type':'pump'}],[{'sensor_id':1,'value':80,'recorded_at':'2026-11-17T09:00:00'}],'右表重复键必须保留连接倍数')]
  for name,a,b,desc in seeds:
   if not s.query(Dataset).filter_by(name=name).first():s.add(Dataset(name=name,sensors=a,readings=b,description=desc,content_hash=dataset_content_hash(a,b)))
  s.flush()
  for i,(name,_,_,_) in enumerate(seeds):
   pname=['过滤-连接-分组基线','空输入管线','重复键内连接'][i]
   d=s.query(Dataset).filter_by(name=name).one()
   if not s.query(Plan).filter_by(name=pname).first():s.add(Plan(name=pname,dataset_id=d.id,steps=DEFAULT_STEPS,note='受限DSL，Python算子真实执行',content_hash=plan_content_hash(DEFAULT_STEPS,d.content_hash)))
  s.commit();counts={m.__tablename__:s.query(m).count() for m in (User,Dataset,Plan,Trace)};print(counts);return counts
if __name__=='__main__':seed()
