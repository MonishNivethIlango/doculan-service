import httpx
from fastapi import HTTPException
from config import config

API_KEY = config.AI_API_KEY
AI_SERVICE_URL = config.AI_SERVICE_URL


class AIService:
    @staticmethod
    async def summarize(pdf_file):
        try:
            async with httpx.AsyncClient(timeout=1000.0) as client:
                files = {"pdf": (pdf_file.filename, await pdf_file.read(), pdf_file.content_type)}
                headers = {"X-API-Key": API_KEY}
                resp = await client.post(f"{AI_SERVICE_URL}/summarize", files=files, headers=headers)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

            return resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Summarization service timed out.")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error connecting to summarization service: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Summarize failed: {str(e)}")

    @staticmethod
    async def ask_pdf(pdf_file, question: str):
        try:
            async with httpx.AsyncClient(timeout=1000.0) as client:
                files = {"pdf": (pdf_file.filename, await pdf_file.read(), pdf_file.content_type)}
                data = {"question": question}
                headers = {"X-API-Key": API_KEY}
                resp = await client.post(f"{AI_SERVICE_URL}/ask-pdf", files=files, data=data, headers=headers)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

            return resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Ask-PDF service timed out.")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error connecting to Ask-PDF service: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ask-PDF failed: {str(e)}")

    @staticmethod
    async def generate(prompt: str, type_: str):
        try:
            async with httpx.AsyncClient(timeout=1000.0) as client:
                json_data = {"prompt": prompt, "type": type_}
                headers = {"X-API-Key": API_KEY}
                resp = await client.post(f"{AI_SERVICE_URL}/generate", json=json_data, headers=headers)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

            return resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error connecting to Generate service: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Generate failed: {str(e)}")


ai_service = AIService()
