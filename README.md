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
6. Pentru aplicația completă, pornește și frontend-ul ([campus-sports-booking-frontend](https://github.com/Cei-Trei-Tokeni-De-La-Rasarit/campus-sports-booking-frontend)) cu `npm run dev`. Backend-ul acceptă cereri de la `http://localhost:5173` (variabila `CORS_ORIGINS` din `.env`).

## Stilul codului

Codul respectă PEP 8, verificat cu [Ruff](https://docs.astral.sh/ruff/) (regulile sunt în `pyproject.toml`).
Înainte de commit:
```powershell
pip install -r requirements-dev.txt
ruff check .
ruff format .
```
La fiecare pull request, aceleași verificări rulează automat pe GitHub (`.github/workflows/stil-cod.yml`).
