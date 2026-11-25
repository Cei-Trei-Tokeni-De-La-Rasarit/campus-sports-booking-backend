-- ==========================================================================
-- Migrare KAN-127: încercările de autentificare eșuate
-- ==========================================================================
-- Se rulează O SINGURĂ DATĂ pe o bază creată înainte de KAN-127 (de exemplu,
-- baza de dezvoltare de pe Neon), cu acordul echipei:
--
--     psql "<adresa bazei>" -f app/database/migrari/2026-11-limita-login.sql
--
-- O bază nouă nu are nevoie de el: shemas.sql conține deja aceste schimbări.
-- Totul rulează într-o tranzacție: dacă un pas dă eroare, nu se schimbă nimic.
-- ==========================================================================

BEGIN;

-- După email, nu după utilizator: limita se aplică la fel și adreselor fără
-- cont, ca răspunsul să nu arate ce conturi există.
CREATE TABLE login_attempt (
    id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email       VARCHAR(150) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX ix_login_attempt_email ON login_attempt (email, created_at);

COMMIT;
