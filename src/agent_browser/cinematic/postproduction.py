"""
Post-production tools for the Cinematic Engine.

Provides video/audio merging and processing using ffmpeg.
Includes stock music integration via Pixabay Audio API.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class PostProductionMixin:
    """
    Mixin class providing post-production tools.

    These tools require ffmpeg to be installed on the system.
    Use check_environment() to verify prerequisites.
    """

    async def check_environment(self) -> Dict[str, Any]:
        """
        [Cinematic Engine] CALL THIS FIRST! Check environment and get workflow guide.

        Returns environment status AND complete workflow guide for creating videos.
        This is the entry point for the Cinematic Engine - always call first!

        Returns:
            {
                "success": True,
                "data": {
                    "ffmpeg": True/False,
                    "openai_key": True/False,
                    "elevenlabs_key": True/False,
                    "jamendo_key": True/False,
                    "errors": [...],
                    "warnings": [...],
                    "workflow": {
                        "phase1_preparation": [...],
                        "phase2_recording": [...],
                        "phase3_postproduction": [...]
                    },
                    "best_practices": [...]
                }
            }
        """
        ffmpeg_path = shutil.which("ffmpeg")
        ffmpeg_available = ffmpeg_path is not None
        openai_key = bool(os.environ.get("OPENAI_API_KEY"))
        elevenlabs_key = bool(os.environ.get("ELEVENLABS_API_KEY"))
        jamendo_key = bool(os.environ.get("JAMENDO_CLIENT_ID"))

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

        if not jamendo_key:
            warnings.append(
                "JAMENDO_CLIENT_ID not set. Required for list_stock_music. "
                "Get a free key at https://devportal.jamendo.com/"
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

        # Workflow guide for agents
        workflow = {
            "phase1_preparation": {
                "description": "Do this BEFORE recording! Audio timing drives video pacing.",
                "steps": [
                    "1. generate_voiceover(text, provider='elevenlabs', voice='21m00Tcm4TlvDq8ikWAM') - Create narration",
                    "2. get_audio_duration(path) - Know exact timing (e.g., 8 seconds)",
                    "3. list_stock_music(query='corporate', instrumental=True) - Find background music",
                    "4. download_stock_music(url) - Download selected track",
                ]
            },
            "phase2_recording": {
                "description": "Record browser with effects. Pace actions to match voiceover duration.",
                "steps": [
                    "1. start_recording(width=1920, height=1080) - Begin capture",
                    "2. set_presentation_mode(enabled=True) - Hide scrollbars for clean visuals",
                    "3. goto(url) - Navigate to your page",
                    "4. annotate(text, style='dark', position='top-right') - Add floating callouts",
                    "5. spotlight(selector, style='focus', color='#3b82f6') - Highlight elements",
                    "6. camera_zoom(selector, level=1.5, duration_ms=1000) - Cinematic zoom",
                    "7. wait(2000) - CRITICAL: Wait longer than animation duration!",
                    "8. clear_spotlight() - Clear before applying new effects",
                    "9. smooth_scroll(direction='down', amount=300) - Professional scrolling",
                    "10. stop_recording() - End capture, get video path",
                ]
            },
            "phase3_postproduction": {
                "description": "Add audio and polish. Order matters!",
                "steps": [
                    "1. merge_audio_video(video, audio_tracks=[{path, start_ms}]) - Add voiceover",
                    "2. add_background_music(video, music, music_volume=0.15, voice_volume=1.3) - Layer music",
                    "3. add_text_overlay(video, text, position='center', start_sec=0, end_sec=3) - Add titles",
                    "4. concatenate_videos(videos, transition='fade') - Join multiple scenes",
                ]
            },
        }

        best_practices = [
            "ALWAYS generate voiceover FIRST - audio duration determines video pacing",
            "Use set_presentation_mode(True) for cleaner visuals without scrollbars",
            "Wait LONGER than animation duration: camera_zoom(duration_ms=1000) needs wait(1500)",
            "Combine spotlight() + annotate() for maximum viewer impact",
            "Use spotlight(style='focus') for dramatic emphasis (ring + dim combined)",
            "Keep music_volume at 0.10-0.15 (10-15%), boost voice_volume to 1.3 (130%)",
            "Always clear_spotlight() before applying a new spotlight effect",
            "Use add_text_overlay() in post-production (more flexible than annotate)",
            "Record at 1920x1080 for professional quality",
        ]

        return {
            "success": len(errors) == 0,
            "message": "Environment ready" if len(errors) == 0 else f"{len(errors)} issue(s) found",
            "data": {
                "ffmpeg": ffmpeg_available,
                "ffmpeg_path": ffmpeg_path,
                "ffmpeg_version": ffmpeg_version,
                "openai_key": openai_key,
                "elevenlabs_key": elevenlabs_key,
                "jamendo_key": jamendo_key,
                "errors": errors,
                "warnings": warnings,
                "workflow": workflow,
                "best_practices": best_practices,
            },
        }

    async def merge_audio_video(
        self,
        video: str,
        audio_tracks: List[Dict[str, Any]],
        output: str,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine - PHASE 3] Merge video with multiple audio tracks.

        Combines a video file with one or more audio tracks (voiceovers),
        positioning each track at a specific timestamp. Call AFTER stop_recording().

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
            # Get video duration to ensure audio matches
            video_duration_sec = None
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(video_path)
                ]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                if probe_result.returncode == 0:
                    video_duration_sec = float(probe_result.stdout.strip())
            except Exception:
                pass

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
                # Single track - pad to video duration
                if video_duration_sec:
                    # Use apad to extend audio to video duration
                    filter_complex = f"{filter_parts[0]};[a0]apad=whole_dur={video_duration_sec}[apadded]"
                    audio_output = "[apadded]"
                else:
                    filter_complex = filter_parts[0]
                    audio_output = "[a0]"
            else:
                # Multiple tracks - mix them and pad
                mix_inputs = "".join(f"[a{i}]" for i in range(len(audio_tracks)))
                if video_duration_sec:
                    filter_parts.append(
                        f"{mix_inputs}amix=inputs={len(audio_tracks)}:duration=longest[amixed];"
                        f"[amixed]apad=whole_dur={video_duration_sec}[aout]"
                    )
                else:
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
        music_volume: float = 0.15,
        voice_volume: float = 1.0,
        fade_in_sec: float = 1.0,
        fade_out_sec: float = 2.0,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine - PHASE 3] Add background music to a video.

        Adds a music track underneath existing audio (voiceover). The music
        is set to a low volume so it doesn't overpower speech.
        Call AFTER merge_audio_video() for best results.

        Args:
            video: Path to input video (should already have voiceover audio)
            music: Path to background music file (MP3, WAV, etc.)
            output: Path for the output video file
            music_volume: Music volume level (0.0-1.0, default 0.15 = 15%)
            voice_volume: Voice volume level (0.0-2.0, default 1.0 = 100%)
            fade_in_sec: Fade in duration for music (default 1.0s)
            fade_out_sec: Fade out duration for music at end (default 2.0s)

        Returns:
            {"success": True, "data": {"path": "...", "music_volume": 0.15}}

        Example:
            add_background_music(
                video="video_with_voiceover.mp4",
                music="background_track.mp3",
                output="final_with_music.mp4",
                music_volume=0.15,  # 15% - quiet background
                voice_volume=1.2,   # 120% - boost voice slightly
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
        music_volume = max(0.0, min(1.0, music_volume))
        voice_volume = max(0.0, min(2.0, voice_volume))

        try:
            # Get video duration for proper audio trimming
            video_duration_sec = None
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(video_path)
                ]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                if probe_result.returncode == 0:
                    video_duration_sec = float(probe_result.stdout.strip())
            except Exception:
                pass

            # Build audio filter
            # 1. Loop music if needed, trim to video duration
            # 2. Apply volume and fade in/out to music
            # 3. Boost voice if needed, pad to video duration
            # 4. Mix voice and music together
            if video_duration_sec:
                fade_out_start = max(0, video_duration_sec - fade_out_sec)
                audio_filter = (
                    # Music: loop, trim, volume, fade in/out
                    f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={video_duration_sec},"
                    f"volume={music_volume},"
                    f"afade=t=in:st=0:d={fade_in_sec},"
                    f"afade=t=out:st={fade_out_start}:d={fade_out_sec}[music];"
                    # Voice: volume boost, pad to video duration
                    f"[0:a]volume={voice_volume},apad=whole_dur={video_duration_sec}[voice];"
                    # Mix: voice first (louder), then music
                    "[voice][music]amix=inputs=2:duration=first:normalize=0[aout]"
                )
            else:
                # No duration known - use simpler filter
                audio_filter = (
                    f"[1:a]aloop=loop=-1:size=2e+09,volume={music_volume},"
                    f"afade=t=in:st=0:d={fade_in_sec}[music];"
                    f"[0:a]volume={voice_volume}[voice];"
                    "[voice][music]amix=inputs=2:duration=first:normalize=0[aout]"
                )

            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-i", str(music_path),
                "-filter_complex", audio_filter,
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
                    "music_volume": music_volume,
                    "voice_volume": voice_volume,
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

    async def add_text_overlay(
        self,
        video: str,
        text: str,
        output: str,
        position: str = "center",
        start_sec: float = 0,
        end_sec: Optional[float] = None,
        font_size: int = 48,
        font_color: str = "white",
        bg_color: Optional[str] = "black@0.5",
        bg_padding: int = 20,
        fade_in_sec: float = 0.5,
        fade_out_sec: float = 0.5,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine - PHASE 3] Add text overlay/title to a video.

        Burns text onto the video at a specified position and time range.
        Perfect for titles, captions, lower thirds, and call-to-action text.
        Call AFTER add_background_music() or merge_audio_video().

        Args:
            video: Path to input video file
            text: Text to display (supports \\n for line breaks)
            output: Path for the output video file
            position: Text position:
                - "center": Center of screen (default)
                - "top": Top center
                - "bottom": Bottom center (good for captions)
                - "top-left", "top-right", "bottom-left", "bottom-right"
                - "lower-third": Professional lower third position
            start_sec: When to show text (seconds from start, default 0)
            end_sec: When to hide text (None = until end of video)
            font_size: Font size in pixels (default 48)
            font_color: Text color (default "white")
            bg_color: Background box color with opacity (default "black@0.5", None for no background)
            bg_padding: Padding around text for background box (default 20)
            fade_in_sec: Fade in duration (default 0.5s)
            fade_out_sec: Fade out duration (default 0.5s)

        Returns:
            {"success": True, "data": {"path": "...", "text": "..."}}

        Example:
            # Title at start
            add_text_overlay(
                video="demo.mp4",
                text="Welcome to Our Product",
                output="titled.mp4",
                position="center",
                start_sec=0,
                end_sec=3,
                font_size=64,
            )

            # Lower third caption
            add_text_overlay(
                video="demo.mp4",
                text="John Smith\\nCEO, Acme Corp",
                output="captioned.mp4",
                position="lower-third",
                start_sec=5,
                end_sec=10,
            )
        """
        # Validate inputs
        video_path = Path(video)
        if not video_path.exists():
            return {"success": False, "message": f"Video file not found: {video}"}

        if not shutil.which("ffmpeg"):
            return {
                "success": False,
                "message": "ffmpeg not found. Install from https://ffmpeg.org/",
            }

        try:
            # Get video duration if end_sec not specified
            if end_sec is None:
                duration_result = await self.get_video_duration(video)
                if duration_result["success"]:
                    end_sec = duration_result["data"]["duration_sec"]
                else:
                    end_sec = 9999  # Fallback

            # Calculate position coordinates based on position name
            # Uses ffmpeg expression syntax for dynamic positioning
            position_map = {
                "center": ("(w-text_w)/2", "(h-text_h)/2"),
                "top": ("(w-text_w)/2", f"{bg_padding}"),
                "bottom": ("(w-text_w)/2", f"(h-text_h-{bg_padding})"),
                "top-left": (f"{bg_padding}", f"{bg_padding}"),
                "top-right": (f"(w-text_w-{bg_padding})", f"{bg_padding}"),
                "bottom-left": (f"{bg_padding}", f"(h-text_h-{bg_padding})"),
                "bottom-right": (f"(w-text_w-{bg_padding})", f"(h-text_h-{bg_padding})"),
                "lower-third": (f"{bg_padding * 2}", f"(h-text_h-{bg_padding * 3})"),
            }

            x_expr, y_expr = position_map.get(position, position_map["center"])

            # Escape text for ffmpeg (colons, backslashes, quotes)
            escaped_text = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

            # Build drawtext filter
            # Enable expression controls when text is visible
            enable_expr = f"between(t,{start_sec},{end_sec})"

            # Alpha for fade in/out
            fade_in_end = start_sec + fade_in_sec
            fade_out_start = end_sec - fade_out_sec
            alpha_expr = (
                f"if(lt(t,{start_sec}),0,"
                f"if(lt(t,{fade_in_end}),(t-{start_sec})/{fade_in_sec},"
                f"if(lt(t,{fade_out_start}),1,"
                f"if(lt(t,{end_sec}),({end_sec}-t)/{fade_out_sec},0))))"
            )

            # Build filter components
            filter_parts = [
                f"fontsize={font_size}",
                f"fontcolor={font_color}",
                f"x={x_expr}",
                f"y={y_expr}",
                f"alpha='{alpha_expr}'",
            ]

            # Add background box if specified
            if bg_color:
                filter_parts.extend([
                    f"box=1",
                    f"boxcolor={bg_color}",
                    f"boxborderw={bg_padding}",
                ])

            # Use default font (system will find one)
            drawtext_filter = f"drawtext=text='{escaped_text}':{':'.join(filter_parts)}"

            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", drawtext_filter,
                "-c:a", "copy",  # Copy audio unchanged
                str(output),
            ]

            result = subprocess.run(
                cmd,
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
                "message": f"Added text overlay to {output_path.name}",
                "data": {
                    "path": str(output_path.resolve()),
                    "text": text,
                    "position": position,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                },
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "message": "ffmpeg timed out (>5 minutes)"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Add text overlay failed: {exc}"}

    async def concatenate_videos(
        self,
        videos: List[str],
        output: str,
        transition: str = "fade",
        transition_duration_sec: float = 0.5,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine - PHASE 3] Concatenate multiple video clips with transitions.

        Joins video segments together with professional transitions between them.
        Perfect for combining multiple recording scenes into one final video.
        Use when you have recorded multiple scenes separately.

        Args:
            videos: List of video file paths to concatenate (in order)
            output: Path for the output video file
            transition: Transition effect between clips:
                - "none": Hard cut (no transition)
                - "fade": Crossfade (default)
                - "wipeleft", "wiperight", "wipeup", "wipedown"
                - "slideleft", "slideright", "slideup", "slidedown"
                - "dissolve": Soft dissolve
            transition_duration_sec: Duration of each transition (default 0.5s)

        Returns:
            {"success": True, "data": {"path": "...", "clips": 3, "duration_sec": ...}}

        Example:
            # Combine intro, main content, and outro with fades
            concatenate_videos(
                videos=["intro.mp4", "demo.mp4", "outro.mp4"],
                output="final.mp4",
                transition="fade",
                transition_duration_sec=0.8,
            )
        """
        # Validate inputs
        if not videos or len(videos) < 1:
            return {"success": False, "message": "At least one video is required"}

        for video in videos:
            if not Path(video).exists():
                return {"success": False, "message": f"Video file not found: {video}"}

        if not shutil.which("ffmpeg"):
            return {
                "success": False,
                "message": "ffmpeg not found. Install from https://ffmpeg.org/",
            }

        try:
            # For single video, just copy it
            if len(videos) == 1:
                cmd = ["ffmpeg", "-y", "-i", videos[0], "-c", "copy", str(output)]
                subprocess.run(cmd, capture_output=True, timeout=300)
                return {
                    "success": True,
                    "message": "Copied single video",
                    "data": {"path": str(Path(output).resolve()), "clips": 1},
                }

            # Get durations for each video
            durations = []
            for video in videos:
                dur_result = await self.get_video_duration(video)
                if dur_result["success"]:
                    durations.append(dur_result["data"]["duration_sec"])
                else:
                    return {"success": False, "message": f"Could not get duration for {video}"}

            if transition == "none":
                # Simple concat without transitions using concat demuxer
                concat_file = Path(output).parent / "concat_list.txt"
                with open(concat_file, "w") as f:
                    for video in videos:
                        # Use forward slashes for ffmpeg compatibility
                        video_path = str(Path(video).resolve()).replace("\\", "/")
                        f.write(f"file '{video_path}'\n")

                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_file),
                    "-c", "copy",
                    str(output),
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                concat_file.unlink(missing_ok=True)  # Clean up

                if result.returncode != 0:
                    return {"success": False, "message": f"Concat failed: {result.stderr[-500:]}"}
            else:
                # Use xfade filter for transitions
                # Build complex filter graph
                inputs = []
                for i, video in enumerate(videos):
                    inputs.extend(["-i", video])

                # Map transition names to xfade effects
                xfade_map = {
                    "fade": "fade",
                    "dissolve": "dissolve",
                    "wipeleft": "wipeleft",
                    "wiperight": "wiperight",
                    "wipeup": "wipeup",
                    "wipedown": "wipedown",
                    "slideleft": "slideleft",
                    "slideright": "slideright",
                    "slideup": "slideup",
                    "slidedown": "slidedown",
                }
                xfade_effect = xfade_map.get(transition, "fade")

                # Build xfade filter chain
                # For n videos, we need n-1 xfade filters
                filter_parts = []
                current_output = "[0:v]"
                offset = durations[0] - transition_duration_sec

                for i in range(1, len(videos)):
                    next_input = f"[{i}:v]"
                    out_label = f"[v{i}]" if i < len(videos) - 1 else "[vout]"

                    filter_parts.append(
                        f"{current_output}{next_input}xfade=transition={xfade_effect}:"
                        f"duration={transition_duration_sec}:offset={offset}{out_label}"
                    )

                    current_output = out_label
                    if i < len(videos) - 1:
                        offset += durations[i] - transition_duration_sec

                # Also concatenate audio
                audio_inputs = "".join(f"[{i}:a]" for i in range(len(videos)))
                filter_parts.append(f"{audio_inputs}concat=n={len(videos)}:v=0:a=1[aout]")

                filter_complex = ";".join(filter_parts)

                cmd = [
                    "ffmpeg", "-y",
                    *inputs,
                    "-filter_complex", filter_complex,
                    "-map", "[vout]",
                    "-map", "[aout]",
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    str(output),
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

                if result.returncode != 0:
                    error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
                    return {"success": False, "message": f"Transition concat failed: {error_msg}"}

            output_path = Path(output)
            if not output_path.exists():
                return {"success": False, "message": "Output file was not created"}

            # Get final duration
            final_dur = await self.get_video_duration(str(output_path))
            final_duration = final_dur["data"]["duration_sec"] if final_dur["success"] else sum(durations)

            return {
                "success": True,
                "message": f"Concatenated {len(videos)} clips with {transition} transition",
                "data": {
                    "path": str(output_path.resolve()),
                    "clips": len(videos),
                    "duration_sec": round(final_duration, 2),
                    "transition": transition,
                },
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "message": "ffmpeg timed out (>10 minutes)"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Concatenate failed: {exc}"}

    async def list_stock_music(
        self,
        query: Optional[str] = None,
        tags: Optional[str] = None,
        instrumental: bool = True,
        speed: Optional[str] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Search for royalty-free stock music from Jamendo.

        Returns a list of tracks that can be downloaded with download_stock_music().
        Requires JAMENDO_CLIENT_ID environment variable.
        Get a free API key at: https://devportal.jamendo.com/

        Args:
            query: Free text search (e.g., "upbeat corporate", "cinematic epic")
            tags: Music tags/genres (e.g., "rock+electronic", "ambient+relaxing")
            instrumental: If True, only instrumental tracks (default: True for background music)
            speed: Track tempo - "verylow", "low", "medium", "high", "veryhigh"
            min_duration: Minimum duration in seconds
            max_duration: Maximum duration in seconds
            limit: Max results to return (1-200, default 10)

        Returns:
            {
                "success": True,
                "data": {
                    "tracks": [
                        {
                            "id": "1532771",
                            "name": "Upbeat Corporate",
                            "duration_sec": 120,
                            "artist": "Paul Werner",
                            "album": "Corporate Vibes",
                            "audio_url": "https://...",  # Streaming URL
                            "download_url": "https://...",  # Direct download
                            "image_url": "https://...",
                            "license": "CC BY-NC-SA"
                        },
                        ...
                    ],
                    "total": 150,
                    "source": "Jamendo (Creative Commons licensed)"
                }
            }

        Example:
            # Find background music for a product demo
            list_stock_music(query="corporate", tags="pop+funk", instrumental=True)

            # Find cinematic music
            list_stock_music(tags="cinematic+epic", speed="medium", min_duration=60)

            # Find upbeat electronic
            list_stock_music(tags="electronic", speed="high")
        """
        if not AIOHTTP_AVAILABLE:
            return {
                "success": False,
                "message": "aiohttp not installed. Run: pip install aiohttp",
            }

        client_id = os.environ.get("JAMENDO_CLIENT_ID")
        if not client_id:
            return {
                "success": False,
                "message": "JAMENDO_CLIENT_ID not set. Get a free key at https://devportal.jamendo.com/",
            }

        # Build API URL - Jamendo tracks endpoint
        params: Dict[str, Any] = {
            "client_id": client_id,
            "format": "json",
            "limit": min(max(1, limit), 200),
            "include": "musicinfo+licenses",
            "audioformat": "mp32",  # High quality MP3
        }

        if query:
            params["search"] = query
        if tags:
            params["fuzzytags"] = tags.replace(",", "+")  # OR logic for tags
        if instrumental:
            params["vocalinstrumental"] = "instrumental"
        if speed:
            params["speed"] = speed
        if min_duration is not None or max_duration is not None:
            min_d = min_duration if min_duration is not None else 0
            max_d = max_duration if max_duration is not None else 9999
            params["durationbetween"] = f"{min_d}_{max_d}"

        url = "https://api.jamendo.com/v3.0/tracks/"

        # Avoid brotli encoding which can cause issues with some aiohttp versions
        request_headers = {"Accept-Encoding": "gzip, deflate"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=request_headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 401:
                        return {
                            "success": False,
                            "message": "Invalid JAMENDO_CLIENT_ID. Get a key at https://devportal.jamendo.com/",
                        }
                    if response.status != 200:
                        return {
                            "success": False,
                            "message": f"Jamendo API error: HTTP {response.status}",
                        }

                    data = await response.json()

                    # Check for API-level errors
                    headers = data.get("headers", {})
                    if headers.get("status") != "success":
                        error_msg = headers.get("error_message", "Unknown API error")
                        return {"success": False, "message": f"Jamendo error: {error_msg}"}

                    # Transform results
                    tracks = []
                    for hit in data.get("results", []):
                        # Extract license info from license_ccurl or licenses dict
                        license_info = "CC"
                        if hit.get("license_ccurl"):
                            # Parse from URL like "http://creativecommons.org/licenses/by-nc/3.0/"
                            cc_url = hit["license_ccurl"]
                            if "/by-nc-nd/" in cc_url:
                                license_info = "CC BY-NC-ND"
                            elif "/by-nc-sa/" in cc_url:
                                license_info = "CC BY-NC-SA"
                            elif "/by-nc/" in cc_url:
                                license_info = "CC BY-NC"
                            elif "/by-sa/" in cc_url:
                                license_info = "CC BY-SA"
                            elif "/by/" in cc_url:
                                license_info = "CC BY"

                        track = {
                            "id": str(hit.get("id", "")),
                            "name": hit.get("name", "Untitled"),
                            "duration_sec": hit.get("duration", 0),
                            "artist": hit.get("artist_name", "Unknown"),
                            "album": hit.get("album_name", ""),
                            "audio_url": hit.get("audio", ""),
                            "download_url": hit.get("audiodownload", ""),
                            "image_url": hit.get("album_image", "") or hit.get("image", ""),
                            "license": license_info,
                            "share_url": hit.get("shareurl", ""),
                        }
                        tracks.append(track)

                    return {
                        "success": True,
                        "message": f"Found {len(tracks)} tracks",
                        "data": {
                            "tracks": tracks,
                            "total": headers.get("results_fullcount", len(tracks)),
                            "source": "Jamendo (Creative Commons licensed - free for non-commercial use)",
                        },
                    }

        except aiohttp.ClientError as exc:
            return {"success": False, "message": f"Network error: {exc}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Failed to search music: {exc}"}

    async def download_stock_music(
        self,
        url: str,
        output: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Download a stock music track.

        Downloads a music file from a URL (e.g., from list_stock_music results)
        to the local music cache directory.

        Args:
            url: URL to download (preview_url or download_url from list_stock_music)
            output: Output directory (default: "music_cache")
            filename: Output filename (default: derived from URL)

        Returns:
            {
                "success": True,
                "data": {
                    "path": "/path/to/downloaded/track.mp3",
                    "size_bytes": 1234567
                }
            }

        Example:
            # Search for music
            result = list_stock_music(query="upbeat corporate")
            track = result["data"]["tracks"][0]

            # Download it
            download_stock_music(url=track["preview_url"], filename="background.mp3")

            # Use in video
            add_background_music(video="demo.mp4", music="music_cache/background.mp3", output="final.mp4")
        """
        if not AIOHTTP_AVAILABLE:
            return {
                "success": False,
                "message": "aiohttp not installed. Run: pip install aiohttp",
            }

        if not url:
            return {"success": False, "message": "URL is required"}

        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return {"success": False, "message": "Invalid URL: must start with http:// or https://"}

        # Determine output path
        output_dir = Path(output) if output else Path("music_cache")
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            output_path = output_dir / filename
        else:
            # Extract filename from URL
            url_path = url.split("?")[0]  # Remove query params
            url_filename = url_path.split("/")[-1]
            if not url_filename or "." not in url_filename:
                url_filename = "track.mp3"
            output_path = output_dir / url_filename

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "message": f"Download failed: HTTP {response.status}",
                        }

                    # Stream to file
                    content = await response.read()
                    output_path.write_bytes(content)

                    return {
                        "success": True,
                        "message": f"Downloaded to {output_path.name}",
                        "data": {
                            "path": str(output_path.resolve()),
                            "size_bytes": len(content),
                        },
                    }

        except aiohttp.ClientError as exc:
            return {"success": False, "message": f"Network error: {exc}"}
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Download failed: {exc}"}
