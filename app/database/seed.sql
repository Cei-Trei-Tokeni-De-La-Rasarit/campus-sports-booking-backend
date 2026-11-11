-- ==========================================
-- SEED DATA (INSERT STATEMENTS)
-- ==========================================

-- 1. Insert Users (1 Admin, 2 Managers, 3 Regular Users)
INSERT INTO "user" (name, email, password_hash, role, email_notifications) VALUES
('Admin Super', 'admin@sports.com', 'hashed_pw_1', 'administrator', true),
('Manager Mike', 'mike@sports.com', 'hashed_pw_2', 'manager', true),
('Manager Sarah', 'sarah@sports.com', 'hashed_pw_3', 'manager', true),
('John Doe', 'john.doe@gmail.com', 'hashed_pw_4', 'user', true),
('Alice Smith', 'alice.smith@gmail.com', 'hashed_pw_5', 'user', false),
('Bob Wilson', 'bob.wilson@yahoo.com', 'hashed_pw_6', 'user', true);

-- 2. Insert Facilities
INSERT INTO facility (name, sport, location, capacity, schedule, status) VALUES
('Downtown Tennis Court A', 'Tennis', 'Central Park', 4, '08:00 - 22:00', 'active'),
('Downtown Tennis Court B', 'Tennis', 'Central Park', 4, '08:00 - 22:00', 'under_maintenance'),
('City Arena Basketball', 'Basketball', 'Westside Gym', 15, '09:00 - 23:00', 'active'),
('Olympic Pool Main', 'Swimming', 'Eastside Aquatic', 50, '06:00 - 20:00', 'active');

-- 3. Insert Regulations
INSERT INTO regulation (facility_id, content) VALUES
(1, 'Proper tennis shoes required. Max 4 players.'),
(2, 'Proper tennis shoes required. Max 4 players.'),
(3, 'No food or drinks on the court. Indoor shoes only.'),
(4, 'Swim caps mandatory. Shower before entering the pool.');

-- 4. Insert Maintenance Records
INSERT INTO maintenance (facility_id, start_date, end_date, reason) VALUES
(2, CURRENT_DATE - INTERVAL '2 days', CURRENT_DATE + INTERVAL '5 days', 'Resurfacing the court'),
(4, CURRENT_DATE + INTERVAL '10 days', CURRENT_DATE + INTERVAL '12 days', 'Quarterly pump inspection');

-- 5. Insert Time Slots (for today and tomorrow)
INSERT INTO time_slot (facility_id, slot_date, start_time, end_time, status) VALUES
(1, CURRENT_DATE, '10:00', '11:00', 'booked'),
(1, CURRENT_DATE, '11:00', '12:00', 'free'),
(1, CURRENT_DATE, '18:00', '19:00', 'booked'),
(3, CURRENT_DATE, '19:00', '21:00', 'free'),
(4, CURRENT_DATE + INTERVAL '1 day', '07:00', '08:00', 'booked');

-- 6. Insert Bookings
INSERT INTO booking (user_id, slot_id, status) VALUES
(4, 1, 'confirmed'),
(5, 3, 'confirmed'),
(6, 5, 'confirmed');

-- 7. Insert Waitlist Entries (John wants slot 3, which Alice has booked)
INSERT INTO waitlist_entry (user_id, slot_id, position) VALUES
(4, 3, 1);

-- 8. Insert Notifications
INSERT INTO notification (user_id, type, message) VALUES
(4, 'booking_confirmed', 'Your tennis court booking for 10:00 is confirmed.'),
(6, 'booking_reminder', 'Reminder: You have a swimming session tomorrow at 07:00.');

-- 9. Insert Feedback
INSERT INTO feedback (user_id, facility_id, rating, comment, manager_reply) VALUES
(4, 1, 5, 'Great court conditions!', 'Thank you, John!'),
(5, 3, 3, 'A bit dusty on the sidelines.', NULL);

-- 10. Assign Facility Managers
INSERT INTO facility_manager (manager_id, facility_id) VALUES
(2, 1),
(2, 2),
(3, 3),
(3, 4);
