# Test fixtures

PRD §6 calls for three checked-in WAVs:

- `single_speaker_5min.wav` + ground-truth transcript JSON
- `four_speaker_meeting.wav` + ground-truth speaker labels + simulated calendar event JSON
- `noisy_meeting.wav` for VAD edge cases

These will be added in Phase 1 once the recording path can produce them. Until then, pipeline tests are deferred — Phase 0 verifies only the scaffold and schema.

Synthetic placeholder WAVs (TTS-generated) are not committed for *transcription quality* tests — they would lock in unrealistic acoustic characteristics and bias diarization tests.

## What *is* committed (Phase 1)

- `synthetic_5s.wav` (~160 KB) — amplitude-modulated tones with known voiced regions. Use only for VAD/plumbing tests, not transcription content. Sidecar `synthetic_5s.json` lists expected segment boundaries with a 0.2s tolerance.

The real-meeting fixtures listed above remain deferred and gitignored — they would need owner-supplied audio.
