# v1 reference — kept for the patterns, not for re-use

These files come from `v1-2025` (commit `fe1335b`). They are **frozen reference**, not live code.
Rebuild on `main` follows `PRD.md`; do not import from this directory.

If you need to roll back to running v1, check out the tag: `git checkout v1-2025`.

## Why these are kept

The setup and start scripts solved a handful of cross-platform problems that took real time to get right last time. Re-derive these patterns in the rebuild rather than re-discovering them.

### `setup_Jarvis.py`
- Python 3.11 detection that works on **Windows (`py -3.11`) and Unix (`python3.11`)** with clear error messages pointing at the install URL.
- Creates `.venv`, then **patches the activate script** to prepend a project-local `binaries/` dir to `PATH` (this is how v1 shipped a vendored `ffmpeg`). Drop this if Phase 0 doesn't vendor binaries; preserve the pattern if it does.
- Uses `uv pip install` once the venv exists — keep that, the cold-install speedup is real.

### `start_Jarvis.py`
- **`ensure_venv()`** — uses three checks (`sys.real_prefix`, `sys.base_prefix != sys.prefix`, `VIRTUAL_ENV` env var) because none of them alone is reliable across macOS/Linux/Windows. Worth lifting verbatim into the new launcher.
- **Banner + loading spinner** while heavy imports happen — UX detail, but the thread-with-stop-event pattern is the right shape for any boot sequence with multi-second imports.
- **Windows UTF-8 reconfigure** (`sys.stdout.reconfigure(encoding='utf-8')`) so emoji/box-drawing in the banner don't crash `cp1252` consoles. Wrapped in try/except for embedded terminals where `reconfigure` isn't available.
- **MCP subprocess lifecycle** — `Popen` + `terminate()` + `wait()` in a `finally` block. The new agent layer will likely run MCP servers similarly; reuse the lifecycle, not the implementation.
- **Logging configuration** clears existing handlers before re-adding them — necessary because Python's `logging.basicConfig` is a no-op if any handler is already attached (e.g. by an imported library).

### `start_Jarvis.sh`
- Trivial wrapper. Kept only so the muscle memory of `./start_Jarvis.sh` still works if someone re-creates it.

### `config.py`
- Old single-file config (paths, log dir, model names). The rebuild moves to `config.toml` per PRD §5; this file is here only to remind us which env vars and paths v1 exposed.

### `requirements.txt`
- v1 dependency snapshot. Useful as a sanity check when the new `pyproject.toml` is being written ("did we forget pyannote?"), nothing more.

## Rules

- **Do not import from this directory.** Nothing under `docs/` is on the package path.
- If a pattern here is worth keeping, copy it into the new code with a comment explaining *why* — don't add a `from docs.v1_reference import ...`.
- When the rebuild's launcher and setup are stable and these patterns have been re-applied, this directory can be deleted. Until then, it stays.
