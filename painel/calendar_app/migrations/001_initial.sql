CREATE TABLE resorts (id text PRIMARY KEY, name text NOT NULL);
INSERT INTO resorts VALUES ('cs','Costa do Sauípe'),('rq','Rio Quente');
CREATE TABLE teams (id text PRIMARY KEY, name text NOT NULL);
INSERT INTO teams VALUES ('commercial','Comercial MICE'),('operations','Operacional');
CREATE TABLE users (
 id text PRIMARY KEY, username text UNIQUE NOT NULL, name text NOT NULL,
 password_hash text NOT NULL, team_id text NOT NULL REFERENCES teams,
 scopes jsonb NOT NULL, can_catalog boolean NOT NULL DEFAULT false,
 can_schedule boolean NOT NULL DEFAULT false, can_manage_users boolean NOT NULL DEFAULT false,
 active boolean NOT NULL DEFAULT true, version integer NOT NULL DEFAULT 1
);
CREATE TABLE resources (
 id text PRIMARY KEY, name text NOT NULL, resort_id text REFERENCES resorts,
 location text NOT NULL DEFAULT '', validated boolean NOT NULL DEFAULT false,
 active boolean NOT NULL DEFAULT true, evidence text NOT NULL DEFAULT '', version integer NOT NULL DEFAULT 1
);
CREATE TABLE configurations (
 id text PRIMARY KEY, name text NOT NULL, kind text NOT NULL, group_name text,
 resort_id text REFERENCES resorts, location text NOT NULL DEFAULT '',
 validated boolean NOT NULL DEFAULT false, active boolean NOT NULL DEFAULT true,
 options jsonb NOT NULL DEFAULT '[]', suggested_options jsonb NOT NULL DEFAULT '[]',
 source_codes jsonb NOT NULL, technical jsonb NOT NULL DEFAULT '{}', notes text NOT NULL DEFAULT '',
 module_count integer, version integer NOT NULL DEFAULT 1
);
CREATE TABLE source_items (
 id text PRIMARY KEY, code integer UNIQUE NOT NULL, page integer NOT NULL,
 name text NOT NULL, kind text NOT NULL, payload jsonb NOT NULL,
 configuration_id text REFERENCES configurations
);
CREATE TABLE imports (digest text PRIMARY KEY, imported_at timestamptz NOT NULL DEFAULT now(), item_count integer NOT NULL);
CREATE TABLE bookings (
 id text PRIMARY KEY, queue_number bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 team_id text NOT NULL REFERENCES teams, title text NOT NULL, responsible text NOT NULL,
 notes text NOT NULL DEFAULT '', status text NOT NULL CHECK (status IN ('pending','waiting','option','confirmed','cancelled')),
 created_by text NOT NULL REFERENCES users, updated_by text NOT NULL REFERENCES users,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 version integer NOT NULL DEFAULT 1
);
CREATE TABLE allocations (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, booking_id text NOT NULL REFERENCES bookings,
 configuration_id text NOT NULL REFERENCES configurations, phase text NOT NULL CHECK (phase IN ('setup','event','teardown')),
 start_date date NOT NULL, end_exclusive date NOT NULL,
 resources jsonb NOT NULL DEFAULT '[]',
 CHECK (start_date >= DATE '2026-01-01' AND end_exclusive <= DATE '2029-01-01' AND start_date < end_exclusive)
);
CREATE INDEX allocations_period ON allocations(start_date,end_exclusive);
CREATE TABLE occupations (
 resource_id text NOT NULL REFERENCES resources, day date NOT NULL, booking_id text NOT NULL REFERENCES bookings,
 PRIMARY KEY (resource_id,day), CHECK (day BETWEEN DATE '2026-01-01' AND DATE '2028-12-31')
);
CREATE INDEX occupations_booking ON occupations(booking_id);
CREATE TABLE audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, actor_id text REFERENCES users,
 entity_type text NOT NULL, entity_id text NOT NULL, action text NOT NULL,
 before_data jsonb, after_data jsonb, note text NOT NULL DEFAULT '', occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE idempotency (
 user_id text NOT NULL REFERENCES users, key text NOT NULL, request_hash text NOT NULL,
 response jsonb NOT NULL, PRIMARY KEY(user_id,key)
);
CREATE TABLE login_attempts (key text PRIMARY KEY, attempts integer NOT NULL, last_at timestamptz NOT NULL);
