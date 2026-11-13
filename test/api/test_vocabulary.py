"""
GET /vocabulary/{tree} gives each term its place in the tree, so the form can
offer the subsectors of the chosen sector, or only the national policies,
and leaves out the tree's headings, which nobody records.
"""
from nccrd.db.models import Trees, Vocabulary, VocabularyXrefTree, VocabularyXrefVocabulary
from test.factories import FactorySession


def _tree(name, edges):
    """A tree from (parent, child) term pairs; parents without a parent are its roots."""
    tree = Trees(name=name)
    FactorySession.add(tree)
    FactorySession.commit()
    ids = {}
    for term in dict.fromkeys(t for edge in edges for t in edge):
        v = Vocabulary(term=term)
        FactorySession.add(v)
        FactorySession.commit()
        FactorySession.add(VocabularyXrefTree(vocabulary_id=v.id, tree_id=tree.id))
        ids[term] = v.id
    for parent, child in edges:
        FactorySession.add(VocabularyXrefVocabulary(parent_id=ids[parent], child_id=ids[child], tree_id=tree.id))
    FactorySession.commit()


def test_terms_come_with_their_parent_group_and_level(api):
    _tree('mitigationSectors', [
        ('Mitigation sector', 'Energy'), ('Mitigation sector', 'Waste'),
        ('Energy', 'Transport'), ('Transport', 'Road'),
    ])
    terms = {t['term']: t for t in api().get('/vocabulary/mitigationSectors').json()}

    assert 'Mitigation sector' not in terms                       # the heading
    assert (terms['Energy']['parent'], terms['Energy']['group'], terms['Energy']['level']) == (None, 'Mitigation sector', 1)
    assert (terms['Transport']['parent'], terms['Transport']['level']) == ('Energy', 2)
    assert (terms['Road']['parent'], terms['Road']['level']) == ('Transport', 3)
    assert list(terms) == ['Energy', 'Road', 'Transport', 'Waste']  # alphabetical


def test_a_tree_with_two_headings_groups_its_terms(api):
    _tree('mitigationPolicies', [('National policy', 'Climate Change Act'), ('Regional policy', 'Provincial Plan')])
    groups = {t['term']: t['group'] for t in api().get('/vocabulary/mitigationPolicies').json()}
    assert groups == {'Climate Change Act': 'National policy', 'Provincial Plan': 'Regional policy'}


def test_an_unknown_tree_is_empty(api):
    assert api().get('/vocabulary/noSuchTree').json() == []
