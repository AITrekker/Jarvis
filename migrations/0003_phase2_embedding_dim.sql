-- Phase 2 fix: widen speaker_embeddings.embedding from VECTOR(192) to VECTOR(512).
-- PRD §3.4 originally specified 192-dim ECAPA-TDNN, but the pyannote release
-- we depend on ships pyannote/embedding as a 512-dim X-vector model. The
-- 192-dim reference was outdated; verified empirically against the cached
-- pyannote/embedding checkpoint on 2026-05-15.
--
-- This is destructive on existing speaker_embeddings rows. That's fine because
-- every prior row is dimensionally incompatible with the new model (you can't
-- cosine-compare a 192-dim vector against a 512-dim one anyway), so they would
-- need to be re-enrolled regardless. In practice the table is empty at this
-- point in the rollout.
--
-- Idempotent: re-running on an already-512 column is a no-op via DROP IF EXISTS.

DROP INDEX IF EXISTS speaker_embeddings_embedding_idx;

ALTER TABLE speaker_embeddings DROP COLUMN IF EXISTS embedding;
ALTER TABLE speaker_embeddings ADD COLUMN embedding VECTOR(512) NOT NULL;

CREATE INDEX speaker_embeddings_embedding_idx
    ON speaker_embeddings USING ivfflat (embedding vector_cosine_ops);
