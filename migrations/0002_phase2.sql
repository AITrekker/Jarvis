-- Phase 2: extend event_attendees to carry the raw calendar payload.
-- PRD §3.5, §4.
--
-- Why the PK change:
--   The original schema keyed event_attendees on (event_id, person_id), which
--   assumed every attendee is already a known `people` row. In practice, calendar
--   sync sees attendees Jarvis has never met before — their email is the only
--   stable identifier the calendar gives us. We promote `email` to the natural
--   key and let `person_id` be NULL until the speaker_resolver (or `people add`)
--   links it. The new PK is (event_id, email).
--
-- Idempotent: re-running this migration on an already-patched DB is safe (uses
-- IF NOT EXISTS / IF EXISTS guards).

ALTER TABLE event_attendees
    ADD COLUMN IF NOT EXISTS email TEXT,
    ADD COLUMN IF NOT EXISTS display_name TEXT;

-- Drop the old composite PK and rebuild on (event_id, email).
ALTER TABLE event_attendees
    DROP CONSTRAINT IF EXISTS event_attendees_pkey;

-- person_id was implicitly NOT NULL via the old PK; make it explicitly nullable
-- so unmatched calendar attendees can be persisted.
ALTER TABLE event_attendees
    ALTER COLUMN person_id DROP NOT NULL;

-- Existing rows (if any from a prior run) need an email value to satisfy the
-- new PK. We backfill from the linked person's email; the email column is NOT
-- NULL once the new PK is in place. In practice this table is empty at the
-- time this migration runs (calendar_sync is not yet wired in Phase 1), so the
-- UPDATE is a no-op on first run.
UPDATE event_attendees ea
   SET email = p.email
  FROM people p
 WHERE ea.person_id = p.id
   AND ea.email IS NULL
   AND p.email IS NOT NULL;

-- Drop any straggler rows that still lack an email (e.g. orphaned person_ids).
DELETE FROM event_attendees WHERE email IS NULL;

ALTER TABLE event_attendees
    ALTER COLUMN email SET NOT NULL;

ALTER TABLE event_attendees
    ADD CONSTRAINT event_attendees_pkey PRIMARY KEY (event_id, email);

-- Helpful index for the speaker_resolver path: "given a person_id, what events
-- are they on?". The PK already covers (event_id, email); we want the inverse.
CREATE INDEX IF NOT EXISTS event_attendees_person_idx
    ON event_attendees (person_id);
