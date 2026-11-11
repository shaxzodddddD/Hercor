import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
import edge_tts
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY topilmadi! Environment variable'ni sozlang.")

client = Groq(api_key=GROQ_API_KEY)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("✅ Hercor Voice AI ishga tushdi")
    yield
    print("❌ Hercor Voice AI to'xtatildi")


app = FastAPI(
    title="Hercor AI Voice Assistant",
    description="Ovozli suhbat tizimi (Groq Whisper + Llama3 + Edge TTS)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — barcha domendan ruxsat (Render URL'ga ulanish uchun shart!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-User-Text", "X-AI-Text"],
)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "Hercor Voice AI",
        "endpoints": {
            "voice_chat": "POST /api/voice-chat (audio fayl yuboring)",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


def transcribe_audio(file_path: str) -> str:
    try:
        with open(file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(file_path), file.read()),
                model="whisper-large-v3",
                response_format="text",
                language="uz",
            )
        return transcription.strip()
    except Exception as e:
        print(f"STT Xatosi: {e}")
        raise HTTPException(status_code=500, detail=f"Ovozni matnga aylantirishda xatolik: {str(e)}")


def generate_ai_response(user_text: str) -> str:
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Siz Hercor platformasining ovozli AI yordamchisisiz. "
                        "Vazifangiz: foydalanuvchilarga ish topish, rezyumeni tahlil qilish "
                        "va kompaniyalar bilan bog'lanishda yordam berish. "
                        "Javoblar qisqa (2-3 gap), tushunarli va do'stona bo'lsin. "
                        "O'zbek tilida javob bering."
                    )
                },
                {"role": "user", "content": user_text}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=500,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"LLM Xatosi: {e}")
        raise HTTPException(status_code=500, detail=f"AI javob yaratishda xatolik: {str(e)}")


async def text_to_speech(text: str, output_path: str):
    try:
        voice = "uz-UZ-MadinaNeural"  # yoki "uz-UZ-SardorNeural"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
    except Exception as e:
        print(f"TTS Xatosi: {e}")
        raise HTTPException(status_code=500, detail=f"Matnni ovozga aylantirishda xatolik: {str(e)}")


def cleanup_files(*paths):
    for p in paths:
        try:
            if os.path.exists(p):
                os.remove(p)
            parent = os.path.dirname(p)
            if parent and os.path.exists(parent) and not os.listdir(parent):
                os.rmdir(parent)
        except Exception as e:
            print(f"Tozalash xatosi: {e}")


@app.post("/api/voice-chat")
async def voice_chat(background_tasks: BackgroundTasks, audio: UploadFile = File(...)):
    """
    Foydalanuvchidan audio fayl qabul qiladi → STT → LLM → TTS → ovoz qaytaradi.
    """
    temp_dir = tempfile.mkdtemp()
    input_audio_path = os.path.join(temp_dir, "input.webm")
    output_audio_path = os.path.join(temp_dir, "output.mp3")

    try:
        with open(input_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        if os.path.getsize(input_audio_path) == 0:
            raise HTTPException(status_code=400, detail="Bo'sh audio fayl yuborildi.")

        user_text = transcribe_audio(input_audio_path)
        print(f"🎤 Foydalanuvchi: {user_text}")

        if not user_text:
            raise HTTPException(status_code=400, detail="Ovoz aniqlanmadi.")

        ai_reply = generate_ai_response(user_text)
        print(f"🤖 AI: {ai_reply}")

        await text_to_speech(ai_reply, output_audio_path)

        background_tasks.add_task(cleanup_files, input_audio_path, output_audio_path)

        return FileResponse(
            output_audio_path,
            media_type="audio/mpeg",
            filename="ai_reply.mp3",
            headers={
                "X-User-Text": user_text.encode("utf-8").decode("latin-1"),
                "X-AI-Text": ai_reply.encode("utf-8").decode("latin-1"),
                "Access-Control-Expose-Headers": "X-User-Text, X-AI-Text",
            }
        )

    except HTTPException:
        background_tasks.add_task(cleanup_files, input_audio_path, output_audio_path)
        raise
    except Exception as e:
        background_tasks.add_task(cleanup_files, input_audio_path, output_audio_path)
        print(f"Umumiy xatolik: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})