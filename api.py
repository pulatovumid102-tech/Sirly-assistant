from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import os
import json
import threading

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ubakgpkcemlchpfejmke.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InViYWtncGtjZW1sY2hwZmVqbWtlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMjc3NzUsImV4cCI6MjA5NTkwMzc3NX0.wkKSmoTB9RwREFjcJfe0dNBzZDEw2DHxNM3G6erHSJU")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

if not os.path.isdir("webapp"):
    if os.path.exists("webapp"):
        os.remove("webapp")
    os.makedirs("webapp")

app.mount("/webapp", StaticFiles(directory="webapp", html=True), name="webapp")

@app.get("/")
async def root():
    return FileResponse("webapp/index.html")

@app.get("/api/data")
async def get_data():
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/biznes_data?id=eq.main",
            headers=HEADERS
        )
        rows = r.json()
        if rows:
            return rows[0]["data"]
        return {}

@app.post("/api/data")
async def save_data(request: Request):
    body = await request.json()
    async with httpx.AsyncClient() as client:
        r = await client.patch(
            f"{SUPABASE_URL}/rest/v1/biznes_data?id=eq.main",
            headers=HEADERS,
            json={"data": body, "updated_at": "now()"}
        )
        if r.status_code not in (200, 201, 204):
            raise HTTPException(status_code=500, detail="Supabase error")
        return {"ok": True}

def start_api_thread():
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    thread = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "0.0.0.0", "port": port},
        daemon=True
    )
    thread.start()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
