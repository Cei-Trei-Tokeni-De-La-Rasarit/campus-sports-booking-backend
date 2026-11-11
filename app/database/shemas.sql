-- 1. user
CREATE TABLE "user" (
    id                  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    email               VARCHAR(150) NOT NULL UNIQUE,
    password_hash       VARCHAR(255) NOT NULL,
    role                VARCHAR(20)  NOT NULL DEFAULT 'user'
                        CHECK (role IN ('user', 'administrator', 'manager')),
    email_notifications BOOLEAN      NOT NULL DEFAULT FALSE
);

-- 2. facility
CREATE TABLE facility (
    id        INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name      VARCHAR(100) NOT NULL,
    sport     VARCHAR(50)  NOT NULL,
    location  VARCHAR(150) NOT NULL,
    capacity  INT          NOT NULL CHECK (capacity > 0),
    schedule  VARCHAR(200),
    status    VARCHAR(20)  NOT NULL DEFAULT 'active'
              CHECK (status IN ('active', 'inactive', 'under_maintenance'))
);

-- 3. regulation (1:1 with facility)
CREATE TABLE regulation (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    facility_id  INT  NOT NULL UNIQUE
                 REFERENCES facility(id) ON DELETE CASCADE,
    content      TEXT NOT NULL
);

-- 4. maintenance
CREATE TABLE maintenance (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    facility_id  INT  NOT NULL REFERENCES facility(id) ON DELETE CASCADE,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    reason       VARCHAR(255),
    CHECK (end_date >= start_date)
);

-- 5. time_slot
CREATE TABLE time_slot (
    id           INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    facility_id  INT  NOT NULL REFERENCES facility(id) ON DELETE CASCADE,
    slot_date    DATE NOT NULL,
    start_time   TIME NOT NULL,
    end_time     TIME NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'free'
                 CHECK (status IN ('free', 'booked', 'blocked')),
    CHECK (end_time > start_time),
    UNIQUE (facility_id, slot_date, start_time)
);

-- 6. booking
CREATE TABLE booking (
    id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES "user"(id)    ON DELETE CASCADE,
    slot_id     INT NOT NULL REFERENCES time_slot(id) ON DELETE CASCADE,
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    status      VARCHAR(20) NOT NULL DEFAULT 'confirmed'
                CHECK (status IN ('confirmed', 'cancelled'))
);

-- no double booking: only one confirmed booking per slot
CREATE UNIQUE INDEX uq_booking_active_slot
    ON booking (slot_id) WHERE status = 'confirmed';

-- 7. waitlist_entry
CREATE TABLE waitlist_entry (
    id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    INT NOT NULL REFERENCES "user"(id)    ON DELETE CASCADE,
    slot_id    INT NOT NULL REFERENCES time_slot(id) ON DELETE CASCADE,
    position   INT NOT NULL CHECK (position > 0),
    joined_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (slot_id, user_id)
);

-- 8. notification
CREATE TABLE notification (
    id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    type        VARCHAR(50) NOT NULL,
    message     TEXT        NOT NULL,
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    is_read     BOOLEAN     NOT NULL DEFAULT FALSE
);

-- 9. feedback
CREATE TABLE feedback (
    id             INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        INT NOT NULL REFERENCES "user"(id)   ON DELETE CASCADE,
    facility_id    INT NOT NULL REFERENCES facility(id) ON DELETE CASCADE,
    rating         INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment        TEXT,
    manager_reply  TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 10. facility_manager (many-to-many: user <-> facility)
CREATE TABLE facility_manager (
    manager_id   INT NOT NULL REFERENCES "user"(id)   ON DELETE CASCADE,
    facility_id  INT NOT NULL REFERENCES facility(id) ON DELETE CASCADE,
    PRIMARY KEY (manager_id, facility_id)
);