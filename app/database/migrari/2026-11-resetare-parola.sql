-- ==========================================================================
-- Migrare KAN-111: token-urile pentru resetarea parolei
-- ==========================================================================
-- Se rulează O SINGURĂ DATĂ pe o bază creată înainte de KAN-111 (de exemplu,
-- baza de dezvoltare de pe Neon), cu acordul echipei:
--
--     psql "<adresa bazei>" -f app/database/migrari/2026-11-resetare-parola.sql
--
-- O bază nouă nu are nevoie de el: shemas.sql conține deja aceste schimbări.
-- Totul rulează într-o tranzacție: dacă un pas dă eroare, nu se schimbă nimic.
-- ==========================================================================

BEGIN;

-- Se păstrează doar hash-ul SHA-256 al token-ului, nu token-ul din link.
CREATE TABLE password_reset_token (
    id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     INT         NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    token_hash  CHAR(64)    NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN     NOT NULL DEFAULT FALSE,
    CHECK (expires_at > created_at)
);
CREATE INDEX ix_password_reset_token_user ON password_reset_token (user_id, created_at);

COMMIT;
