ALTER TABLE users ADD COLUMN entra_tenant_id text;
ALTER TABLE users ADD COLUMN entra_object_id text;
CREATE UNIQUE INDEX users_entra_identity ON users(entra_tenant_id, entra_object_id)
 WHERE entra_tenant_id IS NOT NULL AND entra_object_id IS NOT NULL;

CREATE TABLE auth_sessions (
 id text PRIMARY KEY,
 user_id text NOT NULL REFERENCES users(id),
 verifier_hash text NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(),
 last_seen_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 revoked_at timestamptz,
 user_version integer NOT NULL
);
CREATE INDEX auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX auth_sessions_expiry ON auth_sessions(expires_at);

CREATE TABLE auth_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 occurred_at timestamptz NOT NULL DEFAULT now(),
 event_type text NOT NULL,
 result text NOT NULL,
 user_id text REFERENCES users(id),
 session_id text,
 request_id text,
 origin_hash text,
 reason text NOT NULL DEFAULT ''
);
CREATE INDEX auth_events_occurred ON auth_events(occurred_at DESC);
CREATE INDEX auth_events_user ON auth_events(user_id, occurred_at DESC);
