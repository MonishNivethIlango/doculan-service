from fastapi import APIRouter, UploadFile, File, Form, Depends
from app.schemas.ai_schema import AiRequest
from app.services.ai_service import ai_service
from auth_app.app.api.routes.deps import dynamic_permission_check

router = APIRouter()


@router.post("/ai-assistants/summarize", dependencies=[Depends(dynamic_permission_check)])
async def summarize(pdf: UploadFile = File(...)):
    return await ai_service.summarize(pdf)


@router.post("/ai-assistants/ask-pdf", dependencies=[Depends(dynamic_permission_check)])
async def ask_pdf(pdf: UploadFile = File(...), question: str = Form(...)):
    return await ai_service.ask_pdf(pdf, question)


@router.post("/ai-assistants/generate", dependencies=[Depends(dynamic_permission_check)])
async def generate(data: AiRequest):
    return await ai_service.generate(data.prompt, data.type)
