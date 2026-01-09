"""
Post-production tools for the Cinematic Engine.

Provides video/audio merging and processing using ffmpeg.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List


class PostProductionMixin:
    """
    Mixin class providing post-production tools.

    These tools require ffmpeg to be installed on the system.
    Use check_environment() to verify prerequisites.
    """

    async def check_environment(self) -> Dict[str, Any]:
        """
        [Cinematic Engine] Check if required tools and API keys are available.

        Verifies:
        - ffmpeg installation (required for video processing)
        - OPENAI_API_KEY environment variable (for TTS)
        - ELEVENLABS_API_KEY environment variable (optional, for ElevenLabs TTS)

        Returns:
            {
                "success": True,
                "data": {
                    "ffmpeg": True/False,
                    "ffmpeg_path": "/path/to/ffmpeg" or None,
                    "openai_key": True/False,
                    "elevenlabs_key": True/False,
                    "errors": ["list of issues"],
                    "warnings": ["list of optional missing items"]
                }
            }
        """
        ffmpeg_path = shutil.which("ffmpeg")
        ffmpeg_available = ffmpeg_path is not None
        openai_key = bool(os.environ.get("OPENAI_API_KEY"))
        elevenlabs_key = bool(os.environ.get("ELEVENLABS_API_KEY"))

        errors: List[str] = []
        warnings: List[str] = []

        if not ffmpeg_available:
            errors.append(
                "ffmpeg not found in PATH. Install from https://ffmpeg.org/ "
                "or via package manager (brew install ffmpeg, apt install ffmpeg)"
            )

        if not openai_key:
            warnings.append(
                "OPENAI_API_KEY not set. Required for generate_voiceover with OpenAI provider."
            )

        if not elevenlabs_key:
            warnings.append(
                "ELEVENLABS_API_KEY not set. Optional, only needed for ElevenLabs TTS."
            )

        # Get ffmpeg version if available
        ffmpeg_version = None
        if ffmpeg_available:
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # Extract first line (version info)
                ffmpeg_version = result.stdout.split("\n")[0] if result.stdout else None
            except Exception:  # pylint: disable=broad-except
                pass

        return {
            "success": len(errors) == 0,
            "message": "Environment ready" if len(errors) == 0 else f"{len(errors)} issue(s) found",
            "data": {
                "ffmpeg": ffmpeg_available,
                "ffmpeg_path": ffmpeg_path,
                "ffmpeg_version": ffmpeg_version,
                "openai_key": openai_key,
                "elevenlabs_key": elevenlabs_key,
                "errors": errors,
                "warnings": warnings,
            },
        }

    async def merge_audio_video(
        self,
        video: str,
        audio_tracks: List[Dict[str, Any]],
        output: str,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Merge video with multiple audio tracks.

        Combines a video file with one or more audio tracks (voiceovers),
        positioning each track at a specific timestamp.

        Args:
            video: Path to the input video file (WebM from recording)
            audio_tracks: List of audio tracks to merge:
                [
                    {"path": "/path/to/audio1.mp3", "start_ms": 0},
                    {"path": "/path/to/audio2.mp3", "start_ms": 5000},
                ]
            output: Path for the output video file (MP4 recommended)

        Returns:
            {"success": True, "data": {"path": "...", "duration_sec": ...}}

        Example:
            merge_audio_video(
                video="recording.webm",
                audio_tracks=[
                    {"path": "intro.mp3", "start_ms": 0},
                    {"path": "feature1.mp3", "start_ms": 3000},
                    {"path": "outro.mp3", "start_ms": 10000},
                ],
                output="final_video.mp4"
            )
        """
        # Validate inputs
        video_path = Path(video)
        if not video_path.exists():
            return {"success": False, "message": f"Video file not found: {video}"}

        if not audio_tracks:
            return {"success": False, "message": "No audio tracks provided"}

        # Validate all audio files exist
        for i, track in enumerate(audio_tracks):
            if "path" not in track:
                return {"success": False, "message": f"Audio track {i} missing 'path' field"}
            audio_path = Path(track["path"])
            if not audio_path.exists():
                return {"success": False, "message": f"Audio file not found: {track['path']}"}

        # Check ffmpeg is available
        if not shutil.which("ffmpeg"):
            return {
                "success": False,
                "message": "ffmpeg not found. Install from https://ffmpeg.org/",
            }

        try:
            # Build ffmpeg command
            cmd = ["ffmpeg", "-y", "-i", str(video_path)]

            # Add each audio input
            for track in audio_tracks:
                cmd.extend(["-i", track["path"]])

            # Build filter complex for audio mixing
            filter_parts = []
            for i, track in enumerate(audio_tracks):
                delay_ms = track.get("start_ms", 0)
                # adelay filter: delay audio by specified milliseconds
                # Format: adelay=delays|delays (left|right channels)
                filter_parts.append(f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

            # Mix all delayed audio tracks together
            if len(audio_tracks) == 1:
                # Single track - just use it directly
                filter_complex = filter_parts[0]
                audio_output = "[a0]"
            else:
                # Multiple tracks - mix them
                mix_inputs = "".join(f"[a{i}]" for i in range(len(audio_tracks)))
                filter_parts.append(
                    f"{mix_inputs}amix=inputs={len(audio_tracks)}:duration=longest[aout]"
                )
                filter_complex = ";".join(filter_parts)
                audio_output = "[aout]"

            cmd.extend(["-filter_complex", filter_complex])
            cmd.extend(["-map", "0:v", "-map", audio_output])

            # Output settings - use libx264 for wide compatibility
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                str(output),
            ])

            # Run ffmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                # Extract useful error info
                error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
                return {
                    "success": False,
                    "message": f"ffmpeg failed: {error_msg}",
                }

            # Verify output exists
            output_path = Path(output)
            if not output_path.exists():
                return {"success": False, "message": "Output file was not created"}

            # Get output file info
            file_size = output_path.stat().st_size

            return {
                "success": True,
                "message": f"Created {output_path.name}",
                "data": {
                    "path": str(output_path.resolve()),
                    "size_bytes": file_size,
                    "audio_tracks_merged": len(audio_tracks),
                },
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "message": "ffmpeg timed out (>5 minutes)"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Merge failed: {exc}"}

    async def add_background_music(
        self,
        video: str,
        music: str,
        output: str,
        volume: float = 0.3,
        duck_to: float = 0.1,
        duck_threshold: float = 0.02,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Add background music to a video.

        Adds a music track underneath existing audio, with optional
        "ducking" to lower music volume when speech is detected.

        Args:
            video: Path to input video (should already have voiceover audio)
            music: Path to background music file (MP3, WAV, etc.)
            output: Path for the output video file
            volume: Music volume level (0.0-1.0, default 0.3 = 30%)
            duck_to: Volume to duck to when speech detected (default 0.1 = 10%)
            duck_threshold: Audio level threshold for ducking (default 0.02)

        Returns:
            {"success": True, "data": {"path": "...", "music_volume": 0.3}}

        Example:
            add_background_music(
                video="video_with_voiceover.mp4",
                music="background_track.mp3",
                output="final_with_music.mp4",
                volume=0.25,  # 25% volume
                duck_to=0.1,  # Duck to 10% when speech detected
            )
        """
        # Validate inputs
        video_path = Path(video)
        if not video_path.exists():
            return {"success": False, "message": f"Video file not found: {video}"}

        music_path = Path(music)
        if not music_path.exists():
            return {"success": False, "message": f"Music file not found: {music}"}

        if not shutil.which("ffmpeg"):
            return {
                "success": False,
                "message": "ffmpeg not found. Install from https://ffmpeg.org/",
            }

        # Clamp volume values
        volume = max(0.0, min(1.0, volume))
        duck_to = max(0.0, min(1.0, duck_to))

        try:
            # Build ffmpeg command with sidechaincompress for ducking
            # This automatically lowers music when speech is detected
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-i", str(music_path),
                "-filter_complex",
                # Scale music volume, loop if shorter than video
                f"[1:a]volume={volume},aloop=loop=-1:size=2e+09[music];"
                # Use sidechaincompress: music ducks when video audio is present
                f"[music][0:a]sidechaincompress="
                f"threshold={duck_threshold}:ratio=20:attack=200:release=1000:"
                f"level_sc=1:mix=1[ducked];"
                # Mix the ducked music with original audio
                "[ducked][0:a]amix=inputs=2:duration=first:weights=1 1[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",  # Copy video stream (faster)
                "-c:a", "aac",
                "-b:a", "192k",
                str(output),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                # Fallback to simple mixing without ducking
                # (sidechaincompress may not be available in all ffmpeg builds)
                cmd_simple = [
                    "ffmpeg", "-y",
                    "-i", str(video_path),
                    "-i", str(music_path),
                    "-filter_complex",
                    f"[1:a]volume={volume}[music];"
                    "[0:a][music]amix=inputs=2:duration=first[aout]",
                    "-map", "0:v",
                    "-map", "[aout]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    str(output),
                ]

                result = subprocess.run(
                    cmd_simple,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode != 0:
                    error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
                    return {
                        "success": False,
                        "message": f"ffmpeg failed: {error_msg}",
                    }

            output_path = Path(output)
            if not output_path.exists():
                return {"success": False, "message": "Output file was not created"}

            return {
                "success": True,
                "message": f"Added background music to {output_path.name}",
                "data": {
                    "path": str(output_path.resolve()),
                    "size_bytes": output_path.stat().st_size,
                    "music_volume": volume,
                },
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "message": "ffmpeg timed out (>5 minutes)"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Add music failed: {exc}"}

    async def get_video_duration(self, path: str) -> Dict[str, Any]:
        """
        [Cinematic Engine] Get the duration of a video file.

        Uses ffprobe (part of ffmpeg) to extract video duration.

        Args:
            path: Path to the video file

        Returns:
            {"success": True, "data": {"duration_sec": 30.5, "duration_ms": 30500}}
        """
        video_path = Path(path)
        if not video_path.exists():
            return {"success": False, "message": f"Video file not found: {path}"}

        ffprobe_path = shutil.which("ffprobe")
        if not ffprobe_path:
            return {
                "success": False,
                "message": "ffprobe not found. Install ffmpeg from https://ffmpeg.org/",
            }

        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "message": f"ffprobe failed: {result.stderr}",
                }

            duration_sec = float(result.stdout.strip())
            duration_ms = int(duration_sec * 1000)

            return {
                "success": True,
                "message": f"Duration: {duration_sec:.2f}s",
                "data": {
                    "duration_sec": round(duration_sec, 2),
                    "duration_ms": duration_ms,
                },
            }

        except ValueError:
            return {"success": False, "message": "Could not parse duration from ffprobe"}
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "ffprobe timed out"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Failed to get duration: {exc}"}
