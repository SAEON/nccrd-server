from sqlalchemy import Column, Integer, String,DateTime,Float,Boolean,ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from nccrd.db import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Vocabulary(Base):

    __tablename__ = "vocabulary"
    __table_args__ = {"schema": "nccrd"}
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Project Overview
    term = Column(String)
    properties = Column(String)
    description = Column(String)
    code = Column(String)

class Trees(Base):
    __tablename__ = "tree"
    __table_args__ = {"schema": "nccrd"}
    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String)
    description = Column(String)


class VocabularyXrefTree(Base):
    __tablename__ = "vocabulary_xref_tree"
    __table_args__ = {"schema": "nccrd"}
    id = Column(Integer, primary_key=True, autoincrement=True)

    vocabulary_id = Column(Integer, ForeignKey("nccrd.vocabulary.id"))
    tree_id = Column(Integer, ForeignKey("nccrd.tree.id"))

class VocabularyXrefVocabulary(Base):
    __tablename__ = "vocabulary_xref_vocabulary"
    __table_args__ = {"schema": "nccrd"}
    id = Column(Integer, primary_key=True, autoincrement=True)

    parent_id = Column(Integer, ForeignKey("nccrd.vocabulary.id"))
    child_id = Column(Integer, ForeignKey("nccrd.vocabulary.id"))
    tree_id = Column(Integer, ForeignKey("nccrd.tree.id"))