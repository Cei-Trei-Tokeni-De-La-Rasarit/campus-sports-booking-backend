---
name: code-review
description: Checklist pentru revizuirea codului în backend-ul Campus Sports Booking. Folosește-l când revizuiești un pull request al unui coleg sau propriile modificări înainte de a cere review.
---

# Code review

## Ce revizuiești
- Modificările branch-ului față de `main`: `git diff main...<branch>`.
- Citește fiecare fișier modificat integral, nu doar rezultatul testelor.
- Citește ticketul din Jira (numărul e în numele branch-ului) și compară
  ce cere ticketul cu ce s-a făcut.

## Checklist
**Ticket și scop**
- Face ce cere ticketul și nimic în plus; fără fișiere fără legătură.
- Respectă specificația API: adrese, câmpuri JSON, coduri de stare.

**Validări**
- Fiecare câmp primit este validat: obligatoriu sau opțional, `null`, text
  gol sau doar spații, lungime, interval numeric, valori permise.
- Nicio validare existentă nu a fost ștearsă sau slăbită.

**Securitate**
- Endpoint-urile care modifică date verifică utilizatorul și rolul.
- Resursele unui utilizator nu pot fi accesate de altul doar schimbând id-ul.
- Fără parole, chei sau date personale în cod ori în loguri.
- Fără SQL construit din text; doar SQLAlchemy sau parametri.
- Pachetele noi există, sunt întreținute și chiar sunt necesare.

**Structură și stil**
- Routerul nu lucrează direct cu baza de date; logica e în serviciu.
- Denumiri, adnotări de tip, docstring-uri și comentarii conform paginii
  „Coding style backend”.
- Fără cod mort, `print()`, `except:` fără tip sau abstracții inutile.

**Teste**
- Există teste pentru cazul reușit și pentru cazurile-limită (skill-ul `scrie-teste`).
- Testele ar pica dacă logica ar fi greșită.

## Rezultatul
- Listează observațiile, fiecare cu fișierul și linia, ce e problema și ce
  propui. Marchează-le: **obligatoriu** (trebuie corectat) sau **sugestie**.
- Spune la final dacă recomanzi approval sau modificări.
- Nu aproba și nu integra pull request-ul pe GitHub; decizia îi aparține
  colegului care face review-ul.
