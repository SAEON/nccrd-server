from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from nccrd.db import get_db
from nccrd.api.models import NamedItemModel
from nccrd.db.models import Province, District, LocalDistrict, Country

router = APIRouter()


@router.get(
    "/names/provinces",
    response_model=List[NamedItemModel],
    summary="List all provinces"
)
async def list_province_names(db: Session = Depends(get_db)):
    """
    Return all province names.

    Example:
      GET /names/provinces
    """
    provinces = db.query(Province).order_by(Province.PR_NAME).all()
    return JSONResponse(content=[{"id": p.FID, "code": p.PR_MDB_C, "name": p.PR_NAME} for p in provinces])


@router.get(
    "/names/districts/by_province/{province_name}",
    response_model=List[NamedItemModel],
    summary="List all districts within a given province"
)
async def list_districts_by_province(province_name: str, db: Session = Depends(get_db)):
    """
    Return all districts within a given province.

    Example:
      GET /names/districts/by_province/{province_name}
    """
    districts = db.query(District).filter(District.PROVINCE == province_name).order_by(District.DISTRICT).all()
    print(f"Querying districts for province: {province_name}")
    return JSONResponse(content=[{"id": d.FID, "code": d.DISTRICT, "name": d.DISTRICT_N} for d in districts])


@router.get(
    "/names/local_districts/by_district/{district_name}",
    response_model=List[NamedItemModel],
    summary="List all local districts within a given district"
)
async def list_local_districts_by_district(district_name: str, db: Session = Depends(get_db)):
    """
    Return all local districts within a given district.

    Example:
      GET /names/local_districts/by_district/{district_name}
    """
    local_districts = db.query(LocalDistrict).filter(LocalDistrict.DISTRICT == district_name).order_by(
        LocalDistrict.MUNICNAME).all()
    return JSONResponse(content=[{"id": ld.FID, "code": ld.CAT_B, "name": ld.MUNICNAME} for ld in local_districts])


@router.get(
    "/names/local_districts/by_province/{province_name}",
    response_model=List[NamedItemModel],
    summary="List all local districts within a given province"
)
async def list_local_districts_by_province(province_name: str, db: Session = Depends(get_db)):
    """
    Return all local districts within a given province.

    Example:
      GET /names/local_districts/by_province/{province_name}
    """
    local_districts = db.query(LocalDistrict).filter(LocalDistrict.PROVINCE == province_name).order_by(
        LocalDistrict.MUNICNAME).all()
    return JSONResponse(content=[{"id": ld.FID, "code": ld.CAT_B, "name": ld.MUNICNAME} for ld in local_districts])
@router.get(
    "/names/countries",
    response_model=List[NamedItemModel],
    summary="List all countries"
)
async def list_countries(db: Session = Depends(get_db)):
    """
    Return all country names.
    
    Example:
      GET /names/countries
    """
    countries = db.query(Country).order_by(Country.shape0).all()
    return JSONResponse(content=[{"id": c.gid, "code": c.shapeiso, "name": c.shape0} for c in countries])