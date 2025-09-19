import pytest
from repositories.drill_queries import get_drill_query, list_available_queries, DRILL_QUERIES

def test_get_drill_query_replaces_bucket():
    query_name = 'completed_documents'
    bucket = 'my-bucket'
    query = get_drill_query(query_name, bucket)
    assert bucket in query
    assert 'bucket-name' not in query
    assert DRILL_QUERIES[query_name].strip().split()[0] in query

def test_get_drill_query_invalid():
    with pytest.raises(ValueError):
        get_drill_query('not_a_query')

def test_list_available_queries():
    queries = list_available_queries()
    assert isinstance(queries, list)
    assert 'completed_documents' in queries
    assert set(queries) == set(DRILL_QUERIES.keys())
