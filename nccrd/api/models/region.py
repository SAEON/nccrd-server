from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict,Any
from uuid import UUID

class ProvinceModel(BaseModel):
    PR_MDB_C: Optional[str]
    PR_CODE: Optional[int]
    PR_CODE_st: Optional[int]
    PR_NAME: Optional[str]
    ALBERS_ARE: Optional[float]
    SHAPE_Leng: Optional[float]
    X: Optional[float]
    Y: Optional[float]
    Shape__Area: Optional[float]
    Shape__Length: Optional[float]
    FID: int

class DistrictModel(BaseModel):
    FID: int
    PROVINCE: Optional[str]
    DISTRICT: Optional[str]
    DISTRICT_N: Optional[str]
    DATE: Optional[int]
    CATEGORY: Optional[str]
    geometry: Optional[str]

class LocalDistrictModel(BaseModel):
    FID: int
    OBJECTID: Optional[int]
    PROVINCE: Optional[str]
    CATEGORY: Optional[str]
    CAT2: Optional[str]
    CAT_B: Optional[str]
    MUNICNAME: Optional[str]
    NAMECODE: Optional[str]
    MAP_TITLE: Optional[str]
    DISTRICT: Optional[str]
    DISTRICT_N: Optional[str]
    DATE: Optional[int]
    geometry: Optional[str]

class CountryModel(BaseModel):
    shape0: Optional[str]
    shapeiso: Optional[str]
    shapeid: Optional[str]
    shapegroup: Optional[str]
    shapetype: Optional[str]
    gid: int
    geometry: Optional[str]

class NamedItemModel(BaseModel):
    id: int
    code: str
    name: str
