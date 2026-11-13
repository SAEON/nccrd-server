from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from nccrd.db import get_db
from nccrd.db.models import Trees, Vocabulary, VocabularyXrefTree, VocabularyXrefVocabulary

router = APIRouter()


@router.get(
    "/{tree_name}",
    summary="List vocabulary terms belonging to a named taxonomy tree (e.g. 'mitigationSectors', 'hazards').",
)
def list_vocabulary_by_tree(tree_name: str, db: Session = Depends(get_db)):
    """
    Return the terms of the tree named ``tree_name`` (see ``nccrd.tree`` for
    the full list of tree names), each with its place in the tree:

    * ``parent``: the term it sits under, or null for a top-level term, so a
      form can offer e.g. the subsectors of the chosen sector;
    * ``group``: the heading it falls under, e.g. "National policy" or
      "Regional policy" in the policy trees;
    * ``level``: 1 for a top-level term, 2 for its children, and so on.

    The headings themselves (the tree's roots, e.g. "Mitigation sector") are
    not terms anyone records, and are left out.

    ``term`` is the value stored on submission records — Mitigation/Adaptation
    sector, hazard, policy, etc. are plain text columns holding the term
    itself, not a separate code — so unlike the region endpoints there's no
    distinct code to resolve.
    """
    tree = db.query(Trees).filter(Trees.name == tree_name).first()
    if tree is None:
        return JSONResponse(content=[])
    terms = {
        v.id: v for v in (
            db.query(Vocabulary)
            .join(VocabularyXrefTree, VocabularyXrefTree.vocabulary_id == Vocabulary.id)
            .filter(VocabularyXrefTree.tree_id == tree.id)
        )
    }
    parent_of = {
        e.child_id: e.parent_id
        for e in db.query(VocabularyXrefVocabulary).filter(VocabularyXrefVocabulary.tree_id == tree.id)
        if e.child_id in terms and e.parent_id in terms
    }

    def ancestors(term_id):
        """The term's ancestors, nearest first; the last one is its root."""
        chain, seen = [], {term_id}
        while term_id in parent_of and parent_of[term_id] not in seen:
            term_id = parent_of[term_id]
            seen.add(term_id)
            chain.append(term_id)
        return chain

    listed = []
    for v in terms.values():
        chain = ancestors(v.id)
        if not chain:
            continue  # a root: the tree's heading
        listed.append({
            "id": v.id,
            "term": v.term,
            "code": v.code,
            "parent": terms[chain[0]].term if len(chain) > 1 else None,
            "group": terms[chain[-1]].term,
            "level": len(chain),
        })
    listed.sort(key=lambda t: (t["term"] or "").lower())
    return JSONResponse(content=listed)
