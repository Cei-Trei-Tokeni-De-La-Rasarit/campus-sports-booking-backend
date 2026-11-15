---
name: scrie-teste
description: Cum se scriu testele pytest pentru backend-ul Campus Sports Booking, cu lista cazurilor-limită obligatorii. Folosește-l pentru orice endpoint nou sau modificat și când un ticket cere teste.
---

# Scrie teste

## Unde și cum
- Fișierul: `tests/test_<entitate>.py`, câte unul pentru fiecare router.
- Testele trimit cereri HTTP reale către aplicație, prin fixture-ul `client`
  din `tests/conftest.py`, pe baza de date de test. Nu folosi niciodată baza
  de date a echipei (Neon) sau cea de dezvoltare.
- Fiecare test pornește de la date cunoscute, create în test sau într-un
  fixture, și nu depinde de ordinea în care rulează testele.
- Numele testului spune ce verifică: `test_create_facility_with_empty_name_returns_400`.

## Ce verifică fiecare test
- Codul de stare HTTP (200, 201, 204, 400, 403, 404, 409).
- Conținutul răspunsului: câmpurile în română, valorile corecte,
  mesajul de eroare în formatul `{"mesaj": "..."}`.
- Efectul în baza de date, unde contează: după POST elementul există,
  după DELETE nu mai există, după o cerere respinsă nimic nu s-a schimbat.

## Cazuri obligatorii pentru fiecare endpoint
Cazul reușit, plus cele care se aplică:
- body gol (`{}`) sau lipsă;
- câmp obligatoriu lipsă;
- câmp cu valoarea `null`;
- text gol (`""`) sau doar din spații (`"   "`);
- text mai lung decât limita;
- număr în afara intervalului (0, negativ, prea mare);
- valoare care nu e în lista permisă (de exemplu un status inexistent);
- tip greșit (text în loc de număr);
- id inexistent în adresă (404);
- conflict cu regulile de business (409);
- utilizator neautentificat (401) sau cu rol greșit (403), după ce există autentificarea.

## Un test trebuie să poată pica
- Testul verifică comportamentul cerut în specificație, nu repetă codul.
- Verifică: dacă logica din cod ar fi greșită, testul ar pica? Dacă nu, rescrie-l.
- Nu modifica și nu slăbi codul aplicației ca să treacă un test.
  Dacă un test pică, explică de ce și propune corectura.

## La final

    pytest
    ruff format .
    ruff check --fix .

Spune câte teste ai adăugat și ce cazuri acoperă.
