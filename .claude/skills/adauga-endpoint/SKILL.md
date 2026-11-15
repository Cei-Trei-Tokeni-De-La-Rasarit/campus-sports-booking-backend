---
name: adauga-endpoint
description: Pașii pentru adăugarea sau modificarea unui endpoint în backend-ul Campus Sports Booking (model, schemă, serviciu, router, teste). Folosește-l ori de câte ori un ticket cere un endpoint nou sau schimbă unul existent.
---

# Adaugă un endpoint

Lucrează în pași mici. După fiecare pas, rulează codul înainte să treci mai departe.

## 1. Verifică cerința
- Citește în specificația API (pagina „Specificația API” din Confluence) adresa,
  metoda, câmpurile JSON și codurile de răspuns. Le respecți exact.
- Dacă specificația nu acoperă cazul, oprește-te și întreabă; nu inventa.

## 2. Modelul (`app/models/<entitate>.py`)
- Doar dacă tabelul nu are încă model. Coloanele trebuie să fie identice cu
  schema din baza de date (scripturile din `app/database/`); nu adăuga coloane
  care nu există în bază.

## 3. Schema Pydantic (`app/schemas/<entitate>.py`)
- Câmpuri în engleză, cu `alias` pentru numele în română din specificație.
- Validări pentru fiecare câmp primit:
  - obligatoriu sau opțional, exact ca în specificație;
  - text: fără spații la capete, minim 1 caracter, lungime maximă ca în bază;
  - numere: intervalul permis (de exemplu `ge=1`);
  - valori fixe: `Literal[...]`, traduse spre valorile din bază.
- Separat: schema pentru datele primite și schema pentru răspuns.

## 4. Serviciul (`app/services/<entitate>_service.py`)
- O funcție pentru fiecare operație, cu adnotări de tip și docstring.
- Regulile de business (de exemplu „slotul trebuie să fie liber”) stau aici
  și ridică excepții proprii (`...Error`), nu `HTTPException`.

## 5. Routerul (`app/routers/<entitate>_router.py`)
- Primește cererea, apelează serviciul, transformă excepțiile în
  `HTTPException` cu codul din specificație (400, 403, 404, 409).
- Codul de succes corect: 200 citire sau modificare, 201 creare, 204 ștergere.
- Endpoint-urile care modifică date verifică utilizatorul și rolul
  (după ce există autentificarea).
- Routerul nou se înregistrează în `app/main.py`.

## 6. Testele
- Folosește skill-ul `scrie-teste`: cazul reușit plus toate cazurile-limită.

## 7. Verificarea finală

    ruff format .
    ruff check --fix .
    pytest

- Pornește serverul (`uvicorn app.main:app --reload`) și încearcă endpoint-ul
  din `/docs`, inclusiv cu date greșite.
- Rezumă ce fișiere ai modificat și de ce.
