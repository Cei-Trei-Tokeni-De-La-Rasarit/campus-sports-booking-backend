# campus-sports-booking-backend

API-ul REST al aplicației Campus Sports Booking (Python, FastAPI, PostgreSQL).

Pentru aplicația completă ai nevoie și de frontend:
[campus-sports-booking-frontend](https://github.com/Cei-Trei-Tokeni-De-La-Rasarit/campus-sports-booking-frontend).
Pornește întâi backend-ul (pașii de mai jos), apoi frontend-ul.

## Ce trebuie instalat

| Program | Versiune | De ce |
|---|---|---|
| [Git](https://git-scm.com/downloads) | oricare recentă | clonarea repository-ului |
| [Python](https://www.python.org/downloads/) | **3.12** | aceeași versiune ca verificările de pe GitHub |
| [PostgreSQL](https://www.postgresql.org/download/) | **17** | baza de date; la instalare reține parola utilizatorului `postgres` |

Verifică în PowerShell:
```powershell
git --version
py -3.12 --version
psql --version
```
Dacă `psql` nu este găsit, adaugă `C:\Program Files\PostgreSQL\17\bin` în variabila
`Path` (Windows: „Edit the system environment variables”), apoi deschide un PowerShell nou.

## Instalare

Toate comenzile se rulează în PowerShell, în folderul repository-ului.

### 1. Clonează repository-ul
```powershell
git clone https://github.com/Cei-Trei-Tokeni-De-La-Rasarit/campus-sports-booking-backend.git
cd campus-sports-booking-backend
```

### 2. Mediul virtual și bibliotecile
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```
După activare, rândul din PowerShell începe cu `(.venv)`. Mediul se activează din
nou în fiecare fereastră nouă de PowerShell.

Dacă activarea dă eroarea „running scripts is disabled on this system”, ai două variante:
- permite scripturile semnate pentru contul tău (o singură dată):
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`;
- sau nu activa mediul și scrie calea completă: `.venv\Scripts\python -m uvicorn ...`,
  `.venv\Scripts\python -m pytest`.

### 3. Fișierul `.env`
```powershell
Copy-Item .env.example .env
```
Deschide `.env` și completează:
- `PAROLA_TA` (în `DATABASE_URL` și `TEST_DATABASE_URL`): parola utilizatorului `postgres`;
- `SECRET_KEY`: o valoare lungă și aleatorie, generată cu
  ```powershell
  py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
  Fără `SECRET_KEY` sau cu una mai scurtă de 32 de caractere, serverul nu pornește.

Fișierul `.env` nu se pune pe GitHub (este în `.gitignore`). Nu trimite parolele sau
cheile prin chat; fiecare membru își face propriul `.env`.

### 4. Baza de date
```powershell
$env:PGCLIENTENCODING = "UTF8"
psql -U postgres -c "CREATE DATABASE campus_sports;"
psql -U postgres -d campus_sports -f app/database/shemas.sql
psql -U postgres -d campus_sports -f app/database/seed.sql
```
- `PGCLIENTENCODING` îi spune lui `psql` că fișierele sunt în UTF-8, ca diacriticele
  să ajungă corect în bază indiferent de setările de limbă ale Windows-ului.
- `shemas.sql` creează tabelele (se rulează o singură dată, pe o bază goală).
- `seed.sql` **golește toate tabelele** și pune datele de demo: 4 conturi, 5 săli cu
  regulamente și intervale pe 7 zile de la ziua rulării. Se poate rula din nou
  oricând, de exemplu ca să ai intervale pentru săptămâna curentă.
- Conturile de demo și parola lor sunt în comentariul de la începutul `seed.sql`.

Dacă baza ta a fost creată înainte de programul pe zile (KAN-106), rulează o singură
dată migrarea, care adaugă tabelul `facility_schedule` și coloana `slot_minutes`:
```powershell
psql -U postgres -d campus_sports -f app/database/migrari/2026-11-program-sali.sql
```
Pe o bază nouă nu e nevoie: `shemas.sql` le conține deja.

Dacă vrei să o iei de la zero (șterge tot din bază):
```powershell
psql -U postgres -d campus_sports -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```
apoi rulează din nou `shemas.sql` și `seed.sql`.

## Rulare

```powershell
uvicorn app.main:app --reload
```
- `http://localhost:8000/` răspunde cu `{"status": "ok"}`;
- `http://localhost:8000/docs` este documentația API (Swagger), în care poți încerca
  cererile; pentru cele cu lacăt, autentifică-te cu `POST /auth/autentificare` și
  pune token-ul primit la „Authorize”.

`--reload` repornește serverul la fiecare modificare de cod. Oprirea: `Ctrl+C`.

Backend-ul acceptă cereri din browser doar de la adresele din `CORS_ORIGINS`
(implicit `http://localhost:5173`, adresa frontend-ului pornit cu `npm run dev`).
Dacă rulezi frontend-ul construit (`npm run preview`, port 4173), adaugă și acea adresă:
```
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
```

## Trimiterea emailurilor

Aplicația trimite emailuri (de exemplu, pentru resetarea parolei). Modul se alege în
`.env`, cu `EMAIL_MODE`:
- `consola` (implicit): emailurile **nu** pleacă; apar în terminalul serverului, cu tot
  textul lor. E suficient pentru dezvoltare și nu cere niciun cont de email.
- `smtp`: emailurile se trimit prin contul Gmail al echipei.

Pentru `smtp`:
1. Pe contul Gmail al echipei, pornește **verificarea în doi pași** (Security →
   2-Step Verification).
2. Creează o **parolă de aplicație** la `myaccount.google.com/apppasswords`. Google o
   afișează o singură dată; dacă o pierzi, creezi alta.
3. Completează în `.env` `SMTP_USER`, `SMTP_PASSWORD` (parola de aplicație, fără spații) și
   `EMAIL_FROM`, apoi pune `EMAIL_MODE=smtp` și repornește serverul.

Dacă lipsește o variabilă, serverul nu pornește și spune care. Parola de aplicație stă
doar în `.env`; nu o pune în cod, pe GitHub sau în chat. Testele nu trimit niciodată
emailuri reale, oricare ar fi `EMAIL_MODE`.

## Antetele de securitate

Fiecare răspuns al API-ului are antetele de securitate (`app/security_headers.py`):
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`
și un `Content-Security-Policy` strict (`default-src 'none'`). Paginile de documentație
(`/docs`, `/redoc`) primesc un CSP separat, care permite scripturile Swagger și ReDoc de pe
`cdn.jsdelivr.net`.

La publicarea aplicației, aceleași antete (plus `Strict-Transport-Security`, când e HTTPS)
se adaugă și în serverul care livrează frontend-ul (de exemplu, nginx sau setările
hosting-ului), pentru că backend-ul nu controlează paginile frontend-ului.

## Teste

Testele (pytest) folosesc o bază separată, golită la fiecare test, ca să nu atingă
datele tale. Creeaz-o o singură dată (tabelele le creează testele):
```powershell
psql -U postgres -c "CREATE DATABASE campus_sports_test;"
```
Verifică `TEST_DATABASE_URL` în `.env` (numele bazei trebuie să conțină „test”), apoi:
```powershell
pytest
```
La fiecare pull request, testele rulează automat pe GitHub (`.github/workflows/teste.yml`).

### Testele end-to-end (cu frontend-ul)

Testele end-to-end sunt în repository-ul frontend-ului (`npm run test:e2e`) și
parcurg aplicația completă într-un browser. Ele pornesc singure backend-ul cu
`scripts/e2e_server.py`, care:
- golește baza de test (`TEST_DATABASE_URL`) și o reîncarcă din `shemas.sql` și
  `seed.sql`, ca fiecare rulare să pornească de la aceleași date;
- pornește serverul pe portul **8001**, separat de cel de dezvoltare (8000).

Din backend trebuie doar mediul virtual (`.venv`) și `.env` cu `TEST_DATABASE_URL`,
ca mai sus. Pașii pentru rulare sunt în README-ul frontend-ului.

## Stilul codului

Codul respectă PEP 8, verificat cu [Ruff](https://docs.astral.sh/ruff/) (regulile sunt în `pyproject.toml`).
Înainte de commit:
```powershell
ruff format .
ruff check --fix .
```
La fiecare pull request, aceleași verificări rulează automat pe GitHub (`.github/workflows/stil-cod.yml`).
Fluxul complet (ticket, branch, pull request) este în [CONTRIBUTING.md](CONTRIBUTING.md).

## Probleme frecvente

| Mesaj | Cauza și soluția |
|---|---|
| `uvicorn : The term 'uvicorn' is not recognized` | Mediul virtual nu este activat: `.venv\Scripts\Activate.ps1` (vezi pasul 2). |
| `RuntimeError: Lipsește variabila SECRET_KEY` | Lipsește `.env` sau `SECRET_KEY` din el (pasul 3). |
| `RuntimeError: SECRET_KEY trebuie să aibă cel puțin 32 de caractere` | Cheia din `.env` e prea scurtă; generează una nouă (pasul 3). |
| `password authentication failed for user "postgres"` | Parola din `DATABASE_URL` nu este cea a utilizatorului `postgres`. |
| `database "campus_sports" does not exist` | Baza nu a fost creată (pasul 4). |
| `relation "user" does not exist` | Tabelele nu au fost create: rulează `shemas.sql` (pasul 4). |
| Calendarul nu are intervale libere | Datele de demo sunt pe 7 zile de la rulare; rulează din nou `seed.sql`. |
| În browser: „blocked by CORS policy” | Adresa frontend-ului lipsește din `CORS_ORIGINS`; după modificarea `.env`, repornește serverul. |
| Diacritice stricate în date (`Ã®`, `Äƒ`) | `seed.sql` a fost rulat fără `$env:PGCLIENTENCODING = "UTF8"`; rulează-l din nou cu el. |
