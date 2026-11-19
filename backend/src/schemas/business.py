from pydantic import BaseModel,Field,model_validator,ConfigDict
from typing import Literal
from datetime import datetime
from src.services.operators import validate_steps
class Login(BaseModel):
 email:str;password:str
class Sensor(BaseModel):
 model_config=ConfigDict(extra='forbid')
 sensor_id:int=Field(ge=1,le=100000)
 zone:str=Field(min_length=1,max_length=40)
 device_type:Literal['pump','motor','valve']
class Reading(BaseModel):
 model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
 sensor_id:int=Field(ge=1,le=100000)
 value:float=Field(ge=-1000000,le=1000000)
 recorded_at:str=Field(min_length=1,max_length=40)
class DatasetInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 description:str=Field(default='',max_length=500)
 sensors:list[Sensor]=Field(max_length=100)
 readings:list[Reading]=Field(max_length=2000)
class PlanInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 dataset_id:int
 steps:list[dict]
 note:str=Field(default='',max_length=500)
 @model_validator(mode='after')
 def validate(self):validate_steps(self.steps);return self
class TraceInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 plan_id:int
class BundleExportInput(BaseModel):
 ids:list[int]=Field(min_length=1,max_length=100)
class BundleSensor(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 sensor_id:int=Field(ge=1,le=100000)
 zone:str=Field(min_length=1,max_length=40)
 device_type:Literal['pump','motor','valve']
class BundleReading(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
 sensor_id:int=Field(ge=1,le=100000)
 value:int|float=Field(ge=-1000000,le=1000000)
 recorded_at:str=Field(min_length=1,max_length=40)
class BundleDataset(BaseModel):
 model_config=ConfigDict(extra='forbid')
 key:str=Field(min_length=4,max_length=40)
 name:str=Field(min_length=2,max_length=120)
 description:str=Field(default='',max_length=500)
 sensors:list[BundleSensor]=Field(max_length=100)
 readings:list[BundleReading]=Field(max_length=2000)
 checksum:str=Field(min_length=64,max_length=64)
class BundlePlan(BaseModel):
 model_config=ConfigDict(extra='forbid')
 key:str=Field(min_length=4,max_length=40)
 name:str=Field(min_length=2,max_length=120)
 note:str=Field(default='',max_length=500)
 dataset_key:str=Field(min_length=4,max_length=40)
 steps:list[dict]
 checksum:str=Field(min_length=64,max_length=64)
class BundleTrace(BaseModel):
 model_config=ConfigDict(extra='forbid')
 key:str=Field(min_length=4,max_length=40)
 name:str=Field(min_length=2,max_length=120)
 status:str
 result:dict
 error:str|None=Field(default=None,max_length=1000)
 created_at:datetime
 dataset_key:str=Field(min_length=4,max_length=40)
 plan_key:str=Field(min_length=4,max_length=40)
 checksum:str=Field(min_length=64,max_length=64)
class Bundle(BaseModel):
 model_config=ConfigDict(extra='forbid')
 format:Literal['operator-trace-bundle']
 version:int
 exported_at:datetime|None=None
 bundle_id:str=Field(min_length=64,max_length=64)
 datasets:list[BundleDataset]=Field(max_length=100)
 plans:list[BundlePlan]=Field(max_length=100)
 traces:list[BundleTrace]=Field(min_length=1,max_length=100)
