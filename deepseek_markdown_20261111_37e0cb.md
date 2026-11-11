# Hercor Voice AI

Ovozli AI suhbat tizimi — Groq Whisper + Llama 3 + Edge TTS.

## Deploy qilish (Render)

1. GitHub'ga shu repo'ni yuklang
2. Render.com'ga kiring → **New +** → **Web Service**
3. GitHub repo'ni ulang
4. Sozlamalar:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Environment Variables** bo'limida qo'shing:
   - `GROQ_API_KEY` = `gsk_sizning_kalitingiz`
6. **Create Web Service** → 2-3 daqiqada tayyor

## API Endpoints

- `GET /` — status
- `GET /health` — health check
- `GET /docs` — Swagger UI (test qilish uchun)
- `POST /api/voice-chat` — audio yuborib, ovozli javob olish

## Frontend ulash

```javascript
const formData = new FormData();
formData.append("audio", audioBlob, "voice.webm");

const res = await fetch("https://hercor-voice-ai.onrender.com/api/voice-chat", {
  method: "POST",
  body: formData
});
const audioBlob = await res.blob();
new Audio(URL.createObjectURL(audioBlob)).play();

console.log("Foydalanuvchi:", res.headers.get("X-User-Text"));
console.log("AI:", res.headers.get("X-AI-Text"));