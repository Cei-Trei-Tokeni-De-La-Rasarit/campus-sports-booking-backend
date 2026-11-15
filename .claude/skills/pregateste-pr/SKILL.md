---
name: pregateste-pr
description: Verificările dinaintea unui pull request în proiectul Campus Sports Booking și redactarea descrierii lui. Folosește-l când munca pentru un ticket este gata și urmează commit, push și pull request.
---

# Pregătește pull request-ul

## 1. Branch-ul
- Numele branch-ului curent (`git branch --show-current`) are forma
  `KAN-<număr>-<titlu>`: `KAN` cu majuscule, titlul cu litere mici fără
  diacritice, cifre și cratime. Dacă nu, oprește-te și spune.
- Branch-ul pornește din `main` actualizat.

## 2. Doar codul ticketului
- Listează modificările: `git status` și `git diff main --stat`.
- Fiecare fișier modificat trebuie să țină de ticket. Pentru orice fișier
  care nu ține, spune ce e și propune să fie scos.
- Nu există fișiere care nu trebuie publicate: `.env`, `.venv`, `node_modules`,
  fișiere temporare, parole sau chei în cod.

## 3. Verificările
- Rulează comenzile din secțiunea „După fiecare modificare” din `AGENTS.md`
  și repară până trec toate. Aceleași verificări rulează pe GitHub și sunt
  obligatorii.

## 4. Commit
- Mesajul începe cu numărul ticketului: `KAN-<număr>: <ce s-a făcut>`.
- Nu face push, nu deschide și nu integra pull request-ul fără o cerere
  explicită; doar pregătește comenzile.

## 5. Descrierea pull request-ului
- Titlul: `KAN-<număr> <Titlul ticketului>`.
- Completează șablonul din `.github/pull_request_template.md`:
  - **Ticket**: numărul din Jira;
  - **Ce s-a schimbat**: pe scurt, pe fișiere sau pe funcționalități;
  - **Cum a fost testat**: comenzile rulate, testele noi, ce s-a încercat manual;
  - bifează doar căsuțele care sunt adevărate.
- Menționează dacă o parte a codului a fost generată cu AI și verificată.
