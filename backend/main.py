from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from pattern_model import PropagandaDetector
from llm_service import LLMService
from rag_engine import RagEngine
import os

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Models
detector = PropagandaDetector()
llm_service = LLMService()
rag_engine = RagEngine()

class VerifyRequest(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {"status": "Fake News Bot Backend is Running"}

@app.post("/api/verify")
async def verify_message(request: VerifyRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # 1. Pattern Recognition
    pattern_result = detector.predict(text)
    
    # 2. RAG Retrieval
    retrieved_context = rag_engine.retrieve(text)
    
    # 3. LLM Verification
    # We pass the pattern result and retrieved context to the LLM to inform its response
    llm_response = await llm_service.analyze(text, pattern_result, retrieved_context)
    
    return {
        "pattern_analysis": pattern_result,
        "final_verdict": llm_response["verdict"],
        "explanation": llm_response["explanation"],
        "rag_match": retrieved_context is not None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
