# Test fixtures

PRD §6 calls for three checked-in WAVs:

- `single_speaker_5min.wav` + ground-truth transcript JSON
- `four_speaker_meeting.wav` + ground-truth speaker labels + simulated calendar event JSON
- `noisy_meeting.wav` for VAD edge cases

These will be added in Phase 1 once the recording path can produce them. Until then, pipeline tests are deferred — Phase 0 verifies only the scaffold and schema.

Synthetic placeholder WAVs (TTS-generated) are not committed: they would lock in unrealistic acoustic characteristics and bias diarization tests.
