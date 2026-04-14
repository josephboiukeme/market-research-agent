-- db/init.sql
-- Optional manual initialisation script.
-- If you use `market-agent db init` (SQLAlchemy create_all), this file is
-- not required.  Include it if you prefer to manage the schema manually or
-- want to run it in a CI migration step.

CREATE TABLE IF NOT EXISTS runs (
    id           VARCHAR(64)  PRIMARY KEY,
    run_date     VARCHAR(10)  NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'pending',
    report_md    TEXT,
    error_message TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS recommendations (
    id               SERIAL       PRIMARY KEY,
    run_id           VARCHAR(64)  NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    ticker           VARCHAR(16)  NOT NULL,
    pct_change       FLOAT        NOT NULL,
    volume           BIGINT       NOT NULL,
    volume_anomaly   FLOAT        NOT NULL,
    composite_score  FLOAT        NOT NULL,
    action_note      TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feedback (
    id            SERIAL       PRIMARY KEY,
    run_id        VARCHAR(64)  NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    ticker        VARCHAR(16),
    action_taken  VARCHAR(128),
    rating        INTEGER      CHECK (rating BETWEEN 1 AND 5),
    notes         TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS behavior_tags (
    id         SERIAL      PRIMARY KEY,
    tag        VARCHAR(64) NOT NULL,
    count      INTEGER     NOT NULL DEFAULT 1,
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
