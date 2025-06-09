from sqlalchemy import Column, Integer, String, Float, DateTime
from nccrd.db import Base

class Province(Base):
    __tablename__ = "province"
    __table_args__ = {"schema": "nccrd"}

    FID = Column(Integer, primary_key=True)
    PR_MDB_C = Column(String)
    PR_CODE = Column(Integer)
    PR_CODE_st = Column(Integer)
    PR_NAME = Column(String)
    ALBERS_ARE = Column(Float)
    SHAPE_Leng = Column(Float)
    X = Column(Float)
    Y = Column(Float)
    Shape__Area = Column(Float)
    Shape__Length = Column(Float)

class District(Base):
    __tablename__ = "district"
    __table_args__ = {"schema": "nccrd"}

    FID = Column(Integer, primary_key=True)
    PROVINCE = Column(String)
    DISTRICT = Column(String)
    DISTRICT_N = Column(String)
    DATE = Column(Integer)
    CATEGORY = Column(String)
    geometry = Column(String)

class LocalDistrict(Base):
    __tablename__ = "local_district"
    __table_args__ = {"schema": "nccrd"}

    FID = Column(Integer, primary_key=True)
    OBJECTID = Column(Integer)
    PROVINCE = Column(String)
    CATEGORY = Column(String)
    CAT2 = Column(String)
    CAT_B = Column(String)
    MUNICNAME = Column(String)
    NAMECODE = Column(String)
    MAP_TITLE = Column(String)
    DISTRICT = Column(String)
    DISTRICT_N = Column(String)
    DATE = Column(Integer)
    geometry = Column(String)

class Country(Base):
    __tablename__ = "country"
    __table_args__ = {"schema": "nccrd"}

    gid = Column(Integer, primary_key=True)
    shape0 = Column(String)
    shapeiso = Column(String)
    shapeid = Column(String)
    shapegroup = Column(String)
    shapetype = Column(String)
    geometry = Column(String)

