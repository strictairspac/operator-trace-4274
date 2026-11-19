import hashlib,json
def record(row):
 return {c.name:(getattr(row,c.name).isoformat() if hasattr(getattr(row,c.name),'isoformat') else getattr(row,c.name)) for c in row.__table__.columns if c.name!='password'}
def canonical(obj):return json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(obj):return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()
def dataset_content_hash(sensors,readings):return digest({'sensors':sensors,'readings':readings})
def plan_content_hash(steps,dataset_hash):return digest({'steps':steps,'dataset':dataset_hash})
