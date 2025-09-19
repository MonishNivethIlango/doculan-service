import pytest
from pydantic import ValidationError
from app.schemas.template_schema import Field, Party, TemplateCreate, TemplateUpdate

def test_field():
    f = Field(
        id='1', type='text', x=10, y=20, width=100, height=50, page=1,
        color='red', style='bold', partyId='p1', required=False, options=[]
    )
    assert f.type == 'text'
    assert f.x == 10
    assert f.required is False

def test_party():
    p = Party(id='p1', name='Alice', email='alice@example.com', color='blue', priority=1)
    assert p.email == 'alice@example.com'
    assert p.priority == 1

def test_template_create():
    f = Field(
        id='1', type='text', x=0, y=0, width=10, height=10, page=1,
        color='black', style='normal', partyId='p1', required=False, options=[]
    )
    p = Party(id='p1', name='Bob', email='bob@example.com', color='green', priority=1)
    tc = TemplateCreate(template_name='T', fields=[f], parties=[p], document_id='doc1')
    assert tc.template_name == 'T'
    assert tc.fields[0].id == '1'
    assert tc.parties[0].name == 'Bob'
    assert tc.document_id == 'doc1'

def test_template_update():
    f = Field(
        id='2', type='date', x=1, y=2, width=3, height=4, page=1,
        color='gray', style='normal', partyId='p2', required=False, options=[]
    )
    tu = TemplateUpdate(fields=[f])
    assert tu.fields[0].id == '2'

def test_invalid_party_email():
    with pytest.raises(ValidationError):
        Party(id='p2', name='Eve', email='not-an-email', color='red', priority=1)