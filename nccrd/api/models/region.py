from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict,Any
from uuid import UUID

class ProvinceModel(BaseModel):
    PR_MDB_C: Optional[str] = None
    PR_CODE: Optional[int] = None
    PR_CODE_st: Optional[int] = None
    PR_NAME: Optional[str] = None
    ALBERS_ARE: Optional[float] = None
    SHAPE_Leng: Optional[float] = None
    X: Optional[float] = None
    Y: Optional[float] = None
    Shape__Area: Optional[float] = None
    Shape__Length: Optional[float] = None
    FID: int

class DistrictModel(BaseModel):
    FID: int
    PROVINCE: Optional[str] = None
    DISTRICT: Optional[str] = None
    DISTRICT_N: Optional[str] = None
    DATE: Optional[int] = None
    CATEGORY: Optional[str] = None
    geometry: Optional[str] = None

class LocalDistrictModel(BaseModel):
    FID: int
    OBJECTID: Optional[int] = None
    PROVINCE: Optional[str] = None
    CATEGORY: Optional[str] = None
    CAT2: Optional[str] = None
    CAT_B: Optional[str] = None
    MUNICNAME: Optional[str] = None
    NAMECODE: Optional[str] = None
    MAP_TITLE: Optional[str] = None
    DISTRICT: Optional[str] = None
    DISTRICT_N: Optional[str] = None
    DATE: Optional[int] = None
    geometry: Optional[str] = None

class CountryModel(BaseModel):
    shape0: Optional[str] = None
    shapeiso: Optional[str] = None
    shapeid: Optional[str] = None
    shapegroup: Optional[str] = None
    shapetype: Optional[str] = None
    gid: int
    geometry: Optional[str] = None

class NamedItemModel(BaseModel):
    id: int
    code: str
    name: str
