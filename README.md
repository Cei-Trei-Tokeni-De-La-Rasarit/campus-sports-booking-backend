# campus-sports-booking-backend

API-ul REST al aplicației Campus Sports Booking (Python, FastAPI, PostgreSQL).

## Pornire locală

1. Creează mediul virtual și instalează bibliotecile:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Copiază `.env.example` ca `.env` și completează parola de PostgreSQL.
3. Creează baza de date `campus_sports` (scriptul este adăugat prin KAN-71).
4. Pornește serverul:
   ```powershell
   uvicorn app.main:app --reload
   ```
5. Deschide http://localhost:8000/docs pentru documentația API.
