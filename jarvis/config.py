"""Load `config.toml` with `JARVIS_*` env-var overrides."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import _paths

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"


@dataclass(frozen=True)
class AudioConfig:
    source: str
    sample_rate: int
    channels: int


@dataclass(frozen=True)
class WhisperConfig:
    model: str
    device: str
    compute_type: str


@dataclass(frozen=True)
class SpeakerResolverConfig:
    threshold_high: float
    threshold_low: float


@dataclass(frozen=True)
class OllamaConfig:
    host: str
    summary_model: str
    query_parse_model: str
    agent_model: str


@dataclass(frozen=True)
class CalendarConfig:
    google_oauth_secret_path: str
    sync_window_days: int


@dataclass(frozen=True)
class Config:
    audio: AudioConfig
    whisper: WhisperConfig
    speaker_resolver: SpeakerResolverConfig
    ollama: OllamaConfig
    calendar: CalendarConfig
    db_url: str
    audio_dir: Path
    hf_token: str | None


def load(path: Path | None = None) -> Config:
    config_path = path or Path(os.environ.get("JARVIS_CONFIG", DEFAULT_CONFIG_PATH))
    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    db_url = os.environ.get(raw["db"]["url_env"], "")
    hf_token = os.environ.get(raw["diarization"]["hf_token_env"])

    # If the config gives an explicit path, expand it; otherwise use the OS-default
    # data dir under `audio/`. Lets users override on either OS without editing code.
    raw_audio = raw.get("storage", {}).get("audio_dir")
    audio_dir = Path(os.path.expanduser(raw_audio)) if raw_audio else _paths.data_dir() / "audio"

    raw_calendar = raw.get("calendar", {})
    oauth_path = raw_calendar.get("google_oauth_secret_path")
    calendar = CalendarConfig(
        google_oauth_secret_path=(
            os.path.expanduser(oauth_path)
            if oauth_path
            else str(_paths.config_dir() / "oauth.json")
        ),
        sync_window_days=raw_calendar.get("sync_window_days", 14),
    )

    # Selective env-var overrides for the knobs that change between
    # interactive use and automated runs. The smoke test uses
    # JARVIS_WHISPER_MODEL=tiny.en to avoid a multi-GB large-v3 download.
    whisper_raw = dict(raw["whisper"])
    if env_model := os.environ.get("JARVIS_WHISPER_MODEL"):
        whisper_raw["model"] = env_model
    if env_device := os.environ.get("JARVIS_WHISPER_DEVICE"):
        whisper_raw["device"] = env_device
    if env_compute := os.environ.get("JARVIS_WHISPER_COMPUTE_TYPE"):
        whisper_raw["compute_type"] = env_compute

    return Config(
        audio=AudioConfig(**raw["audio"]),
        whisper=WhisperConfig(**whisper_raw),
        speaker_resolver=SpeakerResolverConfig(**raw["speaker_resolver"]),
        ollama=OllamaConfig(**raw["ollama"]),
        calendar=calendar,
        db_url=db_url,
        audio_dir=audio_dir,
        hf_token=hf_token,
    )
