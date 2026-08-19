from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from nccrd.db import get_db
from nccrd.db.models import Trees, Vocabulary, VocabularyXrefTree

router = APIRouter()


@router.get(
    "/{tree_name}",
    summary="List vocabulary terms belonging to a named taxonomy tree (e.g. 'mitigationSectors', 'hazards').",
)
def list_vocabulary_by_tree(tree_name: str, db: Session = Depends(get_db)):
    """
    Return every ``nccrd.vocabulary`` term linked to the tree named
    ``tree_name`` (see ``nccrd.tree`` for the full list of tree names).

    ``term`` is the value stored on submission records — Mitigation/Adaptation
    sector, hazard, policy, etc. are plain text columns holding the term
    itself, not a separate code — so unlike the region endpoints there's no
    distinct code to resolve.
    """
    terms = (
        db.query(Vocabulary)
        .join(VocabularyXrefTree, VocabularyXrefTree.vocabulary_id == Vocabulary.id)
        .join(Trees, Trees.id == VocabularyXrefTree.tree_id)
        .filter(Trees.name == tree_name)
        .order_by(Vocabulary.term)
        .all()
    )
    return JSONResponse(
        content=[{"id": v.id, "term": v.term, "code": v.code} for v in terms]
    )
