import pytest
from pydantic import ValidationError
from app.schemas.tracking_schemas import (
    Party, Field, PdfSize, EmailResponse, DocumentRequest, DocumentFieldRequest,
    OTPVerification, Fields, UserFields, SignField, FieldSubmission, SubmitFieldsRequest,
    SignatureStatusResponse, LogActionRequest, ClientInfo
)

client_info = ClientInfo(
    ip="1.1.1.1", city="C", region="R", country="X", timezone="UTC",
    timestamp="2025-01-01T00:00:00Z", browser="Chrome", device="PC", os="Windows"
)

def test_party():
    p = Party(id='p1', name='Alice', email='alice@example.com', color='red', priority=1)
    assert p.email == 'alice@example.com'
    assert p.priority == 1

def test_field():
    f = Field(
        id='f1', type='signature', x=10, y=20, width=100, height=50, page=1,
        color='blue', style='normal', partyId='p1', required=False, options=[]
    )
    assert f.type == 'signature'
    assert f.required is False

def test_pdf_size():
    ps = PdfSize(pdfWidth=595, pdfHeight=842)
    assert ps.pdfWidth == 595
    assert ps.pdfHeight == 842

def test_email_response():
    er = EmailResponse(email_subject='sub', email_body='body')
    assert er.email_subject == 'sub'
    assert er.email_body == 'body'

def test_document_request():
    p = Party(id='p1', name='Bob', email='bob@example.com', color='green', priority=1)
    f = Field(
        id='f1', type='text', x=0, y=0, width=10, height=10, page=1,
        color='black', partyId='p1', required=False, options=[], style='normal'
    )
    ps = PdfSize(pdfWidth=100, pdfHeight=200)
    er = EmailResponse(email_subject='s', email_body='b')
    dr = DocumentRequest(
        document_id='d', validityDate='2025-01-01', remainder=1, pdfSize=ps,
        parties=[p], fields=[f], email_response=[er],
        client_info=client_info, holder=None
    )
    assert dr.document_id == 'd'
    assert dr.parties[0].name == 'Bob'
    assert dr.fields[0].id == 'f1'

def test_sign_field():
    uf = UserFields(fields_ids=[Fields(field_id='f1', font='Arial', style='bold', value='sig')])
    sf = SignField(
        tracking_id='t', document_id='d', party_id='p', fields=[uf],
        client_info=client_info
    )
    assert sf.fields[0].fields_ids[0].field_id == 'f1'

def test_field_submission():
    fs = FieldSubmission(id='f1', type='text', x=1.0, y=2.0, page=1, value='v', font='Arial')
    assert fs.value == 'v'

def test_submit_fields_request():
    fs = FieldSubmission(id='f1', type='text', x=1.0, y=2.0, page=1, value='v', font='Arial')
    sfr = SubmitFieldsRequest(document_id='d', tracking_id='t', party_id='p', fields=[fs])
    assert sfr.fields[0].id == 'f1'

def test_signature_status_response():
    ssr = SignatureStatusResponse(signatures={'p1': True}, signed_pdf=None)
    assert ssr.signatures['p1'] is True
    assert ssr.signed_pdf is None

def test_log_action_request():
    holder = {
        "name": "Holder",
        "email": "holder@example.com",
        "address": {
            "address_line_1": "123 Main St",
            "address_line_2": "Apt 1",
            "city": "Metropolis",
            "state": "ST",
            "country": "X",
            "zipcode": "12345"
        }
    }
    lar = LogActionRequest(
        document_id='d',
        tracking_id='t',
        action='CANCELLED',
        holder=holder,
        client_info=client_info
    )
    assert lar.action == 'CANCELLED'

def test_invalid_party_email():
    with pytest.raises(ValidationError):
        Party(id='p2', name='Eve', email='not-an-email', color='red', priority=1)