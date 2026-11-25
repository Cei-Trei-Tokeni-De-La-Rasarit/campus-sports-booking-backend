-- ==========================================================================
-- Date de test pentru demo (KAN-97)
-- ==========================================================================
-- Scriptul GOLEȘTE toate tabelele și pune date noi. Se rulează DOAR pe o bază
-- de dezvoltare sau de demo, niciodată pe una cu date reale:
--
--     psql "<adresa bazei>" -f app/database/seed.sql
--
-- sau din pgAdmin / DBeaver (Query Tool, apoi Execute). Se poate rula de
-- oricâte ori; sloturile se calculează față de ziua rulării.
--
-- Conturi (toate au aceeași parolă de demo: Demo-Campus-2026):
--     admin.demo@usv.ro                  administrator
--     manager.demo@usv.ro                manager (sălile 1 și 2)
--     ana.popescu@student.usv.ro         client (are o rezervare)
--     mihai.ionescu@student.usv.ro       client (are o rezervare)
-- Parola e doar pentru demo; hash-ul de mai jos e generat cu bcrypt.
-- ==========================================================================

TRUNCATE "user", facility, regulation, maintenance, time_slot, booking,
    waitlist_entry, notification, feedback, facility_manager, facility_schedule,
    password_reset_token, login_attempt
    RESTART IDENTITY CASCADE;

-- 1. Utilizatori
INSERT INTO "user" (name, email, password_hash, role, email_notifications) VALUES
('Administrator Demo', 'admin.demo@usv.ro', '$2b$12$dD7SSd5/9Rs7VcmdlGOiq.h.gHDfgpl4LGcd8IsYxfbInF9B2bPPi', 'administrator', FALSE),
('Manager Demo', 'manager.demo@usv.ro', '$2b$12$dD7SSd5/9Rs7VcmdlGOiq.h.gHDfgpl4LGcd8IsYxfbInF9B2bPPi', 'manager', TRUE),
('Ana Popescu', 'ana.popescu@student.usv.ro', '$2b$12$dD7SSd5/9Rs7VcmdlGOiq.h.gHDfgpl4LGcd8IsYxfbInF9B2bPPi', 'user', TRUE),
('Mihai Ionescu', 'mihai.ionescu@student.usv.ro', '$2b$12$dD7SSd5/9Rs7VcmdlGOiq.h.gHDfgpl4LGcd8IsYxfbInF9B2bPPi', 'user', FALSE);

-- 2. Facilități (4 active, una în mentenanță)
INSERT INTO facility (name, sport, location, capacity, schedule, status) VALUES
('Sala de tenis Nr. 3', 'Tenis', 'Complexul sportiv, Corp A', 4, 'Luni-Duminică 08:00-20:00', 'active'),
('Teren sintetic 1', 'Fotbal', 'Exterior, lângă Corp E', 14, 'Luni-Duminică 08:00-20:00', 'active'),
('Sală fitness', 'Fitness', 'Complexul sportiv, Corp A', 15, 'Luni-Duminică 08:00-20:00', 'active'),
('Teren baschet', 'Baschet', 'Sala de sport, Corp D', 10, 'Luni-Duminică 08:00-20:00', 'active'),
('Bazin didactic', 'Înot', 'Complexul sportiv, Corp B', 20, 'Închis pentru renovare', 'under_maintenance');

-- 3. Regulamente
INSERT INTO regulation (facility_id, content) VALUES
(1, '1. Accesul este permis doar cu încălțăminte curată de sală.
2. Fiecare jucător își aduce propriul echipament (mingi, rachete).
3. Întârzierile se scad din timpul de joc.
4. Lasă terenul curat după folosire.'),
(2, '1. Se joacă doar cu ghete pentru gazon sintetic sau teniși.
2. Mingea se aduce de jucători.
3. Accesul pe teren se face doar în intervalul rezervat.'),
(3, '1. Prosopul este obligatoriu.
2. Aparatele se șterg după folosire.
3. Greutățile se pun la loc după antrenament.'),
(4, '1. Accesul este permis doar cu încălțăminte de sală.
2. Nu se consumă mâncare pe teren.
3. Lasă terenul curat după folosire.');

-- 4. Manager: sălile alocate
INSERT INTO facility_manager (manager_id, facility_id) VALUES (2, 1), (2, 2);

-- 5. Programul pe zile: sălile active sunt deschise zilnic 08:00-20:00, cu
--    intervale de 2 ore (durata implicită). Bazinul nu are program.
INSERT INTO facility_schedule (facility_id, weekday, opens_at, closes_at)
SELECT f.id, d, '08:00', '20:00'
FROM facility AS f
CROSS JOIN generate_series(1, 7) AS d
WHERE f.status = 'active';

-- 6. Sloturi de câte 2 ore, 08:00-20:00, de azi până peste 6 zile, pentru
--    toate sălile active. Aplicația le-ar genera oricum din program, dar le
--    punem aici ca să putem adăuga rezervările și mentenanța de mai jos.
INSERT INTO time_slot (facility_id, slot_date, start_time, end_time, status)
SELECT f.id, CURRENT_DATE + d, make_time(h, 0, 0), make_time(h + 2, 0, 0), 'free'
FROM facility AS f
CROSS JOIN generate_series(0, 6) AS d
CROSS JOIN generate_series(8, 18, 2) AS h
WHERE f.status = 'active';

-- 7. Câteva sloturi ocupate, cu rezervările lor.
UPDATE time_slot SET status = 'booked'
WHERE (facility_id = 1 AND slot_date = CURRENT_DATE + 1 AND start_time = '10:00')
   OR (facility_id = 2 AND slot_date = CURRENT_DATE + 2 AND start_time = '16:00');

INSERT INTO booking (user_id, slot_id, status)
SELECT 3, id, 'confirmed' FROM time_slot
WHERE facility_id = 1 AND slot_date = CURRENT_DATE + 1 AND start_time = '10:00';

INSERT INTO booking (user_id, slot_id, status)
SELECT 4, id, 'confirmed' FROM time_slot
WHERE facility_id = 2 AND slot_date = CURRENT_DATE + 2 AND start_time = '16:00';

-- 8. Mentenanță: sala de fitness e blocată o zi întreagă.
INSERT INTO maintenance (facility_id, start_date, end_date, reason)
VALUES (3, CURRENT_DATE + 3, CURRENT_DATE + 3, 'Revizia aparatelor');

UPDATE time_slot SET status = 'blocked'
WHERE facility_id = 3 AND slot_date = CURRENT_DATE + 3;
