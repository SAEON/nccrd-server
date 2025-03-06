from math import ceil
from typing import Callable, Generic, List, TypeVar

from fastapi import HTTPException, Query
from pydantic import BaseModel
from pydantic.generics import GenericModel
from sqlalchemy import func, select, text
from sqlalchemy.engine import Row
from sqlalchemy.exc import CompileError
from sqlalchemy.sql import Select
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from nccrd.db import Base, Session

ModelT = TypeVar('ModelT', bound=BaseModel)


class Page(GenericModel, Generic[ModelT]):
    items: List[ModelT]
    total: int
    page: int
    pages: int


class Paginator:
    def __init__(
            self,
            page: int = Query(1, ge=1, title='Page number'),
            size: int = Query(50, ge=0, title='Page size; 0=unlimited'),
            sort: str = Query('id', title='Sort column'),
    ):
        self.page = page
        self.size = size
        self.sort = sort

    def paginate(
            self,
            query: Select,
            item_factory: Callable[[Row], ModelT],
            *,
            sort: str = None,
            sort_model: Base = None,
    ) -> Page[ModelT]:
        """Return a page of API models of type ModelT.

        :param query: the select query for the total (unpaged) result set
        :param item_factory: a callable that takes a row from the result set
            and produces an object of type ModelT
        :param sort: a custom sort column/clause; overrides the 'sort' request
            param and the API default
        :param sort_model: the ORM class associated with a given sort column,
            in case the query selects from multiple tables
        """
        total = Session.execute(
            select(func.count()).
            select_from(query.subquery())
        ).scalar_one()

        try:
            sort_col = text(sort) if sort else self.sort
            if sort_model:
                sort_col = getattr(sort_model, sort_col)

            limit = self.size or total

            items = [
                item_factory(row) for row in Session.execute(
                    query.
                    order_by(sort_col).
                    offset(limit * (self.page - 1)).
                    limit(limit)
                )
            ]
        except (AttributeError, CompileError):
            raise HTTPException(HTTP_422_UNPROCESSABLE_ENTITY, 'Invalid sort column')

        return Page(
            items=items,
            total=total,
            page=self.page,
            pages=ceil(total / limit) if limit else 0,
        )
