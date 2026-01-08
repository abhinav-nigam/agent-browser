"""
Text-to-Speech tools for the Cinematic Engine.

Provides voiceover generation using OpenAI or ElevenLabs TTS APIs,
with caching to avoid redundant API costs during retakes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional


class TTSMixin:
    """
    Mixin class providing TTS (Text-to-Speech) tools.

    Expects the host class to have:
    - self._tts_client: Optional[Any] - Lazy-loaded TTS client
    - self._audio_cache_dir: Path - Directory for cached audio files
    """

    _tts_client: Optional[Any]
    _audio_cache_dir: Path

    async def generate_voiceover(
        self,
        text: str,
        provider: str = "openai",
        voice: str = "alloy",
        speed: float = 1.0,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Generate voiceover audio from text using TTS.

        Lazy-loads the TTS client on first call. Caches audio files to avoid
        redundant API costs during retakes.

        Args:
            text: The text to convert to speech
            provider: TTS provider - "openai" (default) or "elevenlabs"
            voice: Voice ID - OpenAI: alloy, echo, fable, onyx, nova, shimmer
                   ElevenLabs: use voice ID from their dashboard
            speed: Speech speed multiplier (0.25 to 4.0, default 1.0)

        Returns:
            {"success": True, "data": {"path": "/path/to/audio.mp3", "cached": bool}}

        Requires: pip install ai-agent-browser[video]
        """

        try:
            # Cache key based on content hash (same text+settings = same file)
            cache_key = hashlib.md5(
                f"{text}:{provider}:{voice}:{speed}".encode()
            ).hexdigest()[:12]
            cache_path = self._audio_cache_dir / f"{cache_key}.mp3"

            # Return cached file if exists
            if cache_path.exists():
                return {
                    "success": True,
                    "message": f"Using cached audio: {cache_path.name}",
                    "data": {"path": str(cache_path.resolve()), "cached": True},
                }

            # Ensure cache directory exists
            self._audio_cache_dir.mkdir(parents=True, exist_ok=True)

            if provider == "openai":
                # Lazy-load OpenAI client
                if self._tts_client is None:
                    try:
                        from openai import OpenAI

                        self._tts_client = OpenAI()
                    except ImportError:
                        return {
                            "success": False,
                            "message": "openai package not installed. Run: pip install ai-agent-browser[video]",
                        }

                response = self._tts_client.audio.speech.create(
                    model="tts-1-hd",
                    voice=voice,
                    input=text,
                    speed=speed,
                )
                response.stream_to_file(str(cache_path))

            elif provider == "elevenlabs":
                try:
                    from elevenlabs import ElevenLabs

                    client = ElevenLabs()
                    audio = client.text_to_speech.convert(
                        voice_id=voice,
                        text=text,
                        model_id="eleven_multilingual_v2",
                    )
                    # Write audio bytes to file
                    with open(cache_path, "wb") as f:
                        for chunk in audio:
                            f.write(chunk)
                except ImportError:
                    return {
                        "success": False,
                        "message": "elevenlabs package not installed. Run: pip install ai-agent-browser[video]",
                    }
            else:
                return {
                    "success": False,
                    "message": f"Unknown TTS provider: {provider}. Use 'openai' or 'elevenlabs'.",
                }

            return {
                "success": True,
                "message": f"Generated voiceover: {cache_path.name}",
                "data": {"path": str(cache_path.resolve()), "cached": False},
            }

        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"TTS generation failed: {exc}"}

    async def get_audio_duration(self, path: str) -> Dict[str, Any]:
        """
        [Cinematic Engine] Get the duration of an audio file in milliseconds.

        Use this to calculate timing for video recording - know how long a
        voiceover is BEFORE starting to record, so you can pace movements.

        Args:
            path: Absolute path to the audio file (MP3, WAV, etc.)

        Returns:
            {"success": True, "data": {"duration_ms": 3500, "duration_sec": 3.5}}

        Requires: pip install ai-agent-browser[video]
        """

        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(path)
            if audio is None:
                return {
                    "success": False,
                    "message": f"Could not read audio file: {path}",
                }

            duration_sec = audio.info.length
            duration_ms = int(duration_sec * 1000)

            return {
                "success": True,
                "message": f"Duration: {duration_ms}ms ({duration_sec:.2f}s)",
                "data": {
                    "duration_ms": duration_ms,
                    "duration_sec": round(duration_sec, 2),
                },
            }

        except ImportError:
            return {
                "success": False,
                "message": "mutagen package not installed. Run: pip install ai-agent-browser[video]",
            }
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Failed to get audio duration: {exc}"}
