# Cum contribui

Regulile complete sunt în Confluence, în paginile [GitHub](https://trei-tokeni-rasarit.atlassian.net/wiki/spaces/CTTDLR/pages/20676609/GitHub) și [Coding style backend](https://trei-tokeni-rasarit.atlassian.net/wiki/spaces/CTTDLR/pages/20643842/Coding+style+backend). Mai jos este rezumatul.

## Fluxul pentru un ticket

1. Treci ticketul din Jira pe *In Progress*.
2. Pornești de la `main` actualizat și creezi un branch pentru ticket:
   ```powershell
   git checkout main
   git pull
   git checkout -b KAN-<număr>-<titlu>
   ```
3. Branch-ul conține **doar codul pentru acel ticket**. Un ticket început nu se extinde la alte părți din cod; dacă e nevoie de altceva, se creează un ticket nou.
4. Mesajele de commit încep cu numărul ticketului: `KAN-<număr>: descriere`.
5. Deschizi un pull request către `main`, cu titlul `KAN-<număr> <Titlul ticketului>`, și completezi șablonul.
6. Un **alt membru al echipei** aprobă pull request-ul (self-approval nu este permis).
7. După approval și după ce trec verificările automate, pull request-ul se integrează cu **Squash and merge**.
8. Ticketul din Jira trece pe *Done* după integrare.

## Numele branch-ului

`KAN-<număr>-<titlu>`, doar cu litere mici, cifre și cratime. Exemplu: `KAN-79-crud-facilitate-backend`.

## Verificări automate

La fiecare pull request rulează, pe GitHub, verificările de mai jos. Un pull request nu poate fi integrat dacă una dintre ele pică.

| Verificare | Ce verifică |
|---|---|
| Nume branch | numele branch-ului respectă convenția de mai sus |
| Ruff | stilul codului Python (PEP 8), conform paginii „Coding style backend” |

Înainte de commit, rulează local:
```powershell
pip install -r requirements-dev.txt
ruff format .
ruff check --fix .
```
