# Reguli pentru asistenții AI: campus-sports-booking-backend

API-ul REST al aplicației Campus Sports Booking: Python 3.12, FastAPI,
SQLAlchemy 2, Pydantic 2, PostgreSQL. Specificația API este în Confluence
(pagina „Specificația API”); adresele și câmpurile JSON se respectă exact.

## Înainte de orice modificare
- Lucrezi doar pentru ticketul Jira din numele branch-ului (KAN-<număr>-<titlu>).
  Nu modifica fișiere care nu țin de acel ticket; dacă e nevoie de altceva, spune.
- Nu citi, nu afișa și nu modifica fișierul `.env`. Folosește `.env.example`.
- Nu adăuga pachete noi fără să spui ce pachet, de ce și ce versiune.
  Verifică întâi că pachetul există și este întreținut.

## Structura
- `app/models/`: modelele SQLAlchemy (tabelele, nume în engleză)
- `app/schemas/`: modelele Pydantic; câmpurile JSON în română, prin `alias`
- `app/services/`: logica aplicației; doar aici se lucrează cu baza de date
- `app/routers/`: endpoint-urile; apelează serviciile, nu baza de date direct
- `tests/`: teste pytest, câte un fișier `test_<modul>.py`

## Reguli de cod (detalii: pagina „Coding style backend”)
- PEP 8, verificat cu Ruff: 4 spații, max. 88 de caractere, ghilimele duble.
- `snake_case` pentru funcții și variabile, `PascalCase` pentru clase.
- Adnotări de tip pe toate funcțiile; docstring scurt în `services/`.
- Comentariile în română; codul în engleză.
- Erorile către client: `HTTPException`, cu formatul `{"mesaj": "..."}`;
  400 date invalide, 404 resursă inexistentă, 409 conflict.
- Fără `print()` (folosește `logging`) și fără `except:` fără tip.

## Validări și securitate
- Orice date primite se validează în schema Pydantic: câmpuri obligatorii,
  text gol sau doar spații respins, numere în intervalul permis.
- Nu șterge și nu slăbi o validare ca să treacă un test.
- Pentru resursele unui utilizator, verifică mereu că îi aparțin
  sau că are rolul potrivit.
- Interogări doar prin SQLAlchemy sau cu parametri; niciodată SQL construit din text.

## După fiecare modificare
Rulează și repară până trec:

    ruff format .
    ruff check --fix .
    pytest

Orice endpoint nou sau modificat are teste, inclusiv pentru cazurile-limită.

## Skill-uri
Pentru sarcinile de mai jos, folosește skill-urile din `.claude/skills/`:
`adauga-endpoint`, `scrie-teste`, `pregateste-pr`, `code-review`.
