-- ==========================================================================
-- Migrare KAN-106: programul sălii pe zile
-- ==========================================================================
-- Se rulează O SINGURĂ DATĂ pe o bază creată înainte de KAN-106 (de exemplu,
-- baza de dezvoltare de pe Neon), cu acordul echipei:
--
--     psql "<adresa bazei>" -f app/database/migrari/2026-11-program-sali.sql
--
-- O bază nouă nu are nevoie de el: shemas.sql conține deja aceste schimbări.
-- Totul rulează într-o tranzacție: dacă un pas dă eroare, nu se schimbă nimic.
-- ==========================================================================

BEGIN;

ALTER TABLE facility
    ADD COLUMN slot_minutes INT NOT NULL DEFAULT 120
    CHECK (slot_minutes IN (60, 90, 120));

CREATE TABLE facility_schedule (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    facility_id  INT      NOT NULL REFERENCES facility(id) ON DELETE CASCADE,
    weekday      SMALLINT NOT NULL CHECK (weekday BETWEEN 1 AND 7),
    opens_at     TIME     NOT NULL,
    closes_at    TIME     NOT NULL,
    CHECK (closes_at > opens_at),
    UNIQUE (facility_id, weekday)
);

-- Sălile din datele de demo au textul „Luni-Duminică 08:00-20:00”; le dăm
-- același program, pe zile. Celelalte rămân fără program (se setează din API).
INSERT INTO facility_schedule (facility_id, weekday, opens_at, closes_at)
SELECT f.id, d, '08:00', '20:00'
FROM facility AS f
CROSS JOIN generate_series(1, 7) AS d
WHERE f.schedule = 'Luni-Duminică 08:00-20:00';

COMMIT;
