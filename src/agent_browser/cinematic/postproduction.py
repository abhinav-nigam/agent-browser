"""
Post-production tools for the Cinematic Engine.

Provides fast utility tools for video/audio inspection and stock music.
For video processing (merging, converting, effects), use ffmpeg directly
via shell commands - this avoids MCP timeout issues with long operations.
"""

from __future__ import annotations

import asyncio
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
    Mixin class providing post-production utility tools.

    For video processing (merging audio, converting formats, adding effects),
    agents should use ffmpeg directly via shell commands. This avoids MCP
    timeout issues that occur with long-running video operations.

    Use check_environment() to verify ffmpeg is installed and get workflow guidance.
    """

    async def _run_ffmpeg_async(
        self,
        cmd: List[str],
        timeout_sec: int = 30,
    ) -> tuple[int, str, str]:
        """
        Run ffmpeg/ffprobe command asynchronously without blocking the event loop.

        Args:
            cmd: Command and arguments list
            timeout_sec: Timeout in seconds (default 30 for quick operations)

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            asyncio.TimeoutError: If command exceeds timeout
        """
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_sec,
            )
            return (
                process.returncode or 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
        except asyncio.TimeoutError:
            # Kill the process on timeout
            process.kill()
            await process.wait()
            raise

    async def check_environment(self) -> Dict[str, Any]:
        """
        [Cinematic Engine] Check environment and get workflow guide.

        Verifies ffmpeg is installed and returns a complete workflow guide
        for creating professional videos. This is the entry point for the
        Cinematic Engine - always call first!

        IMPORTANT: For post-production (Phase 3), use ffmpeg directly via shell
        commands. This avoids MCP timeout issues with long video operations.

        Returns:
            {
                "success": True,
                "data": {
                    "ffmpeg": True/False,
                    "ffmpeg_path": "/usr/bin/ffmpeg",
                    "ffmpeg_version": "ffmpeg version 6.0...",
                    "openai_key": True/False,
                    "elevenlabs_key": True/False,
                    "jamendo_key": True/False,
                    "errors": [...],
                    "warnings": [...],
                    "workflow": {...},
                    "ffmpeg_examples": {...},
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
                    "1. generate_voiceover(text, provider='elevenlabs', voice='H2JKG8QcEaH9iUMauArc') - Create narration",
                    "2. get_audio_duration(path) - Know exact timing (e.g., 8 seconds)",
                    "3. list_stock_music(query='corporate', instrumental=True) - Find background music",
                    "4. download_stock_music(url) - Download selected track",
                ],
                "voiceover_tips": {
                    "recommended_voices": {
                        "H2JKG8QcEaH9iUMauArc": "Abhinav - warm, natural tone",
                        "qr9D67rNgxf5xNgv46nx": "Tarun - expressive delivery",
                    },
                    "voice_modulation": {
                        "stability": "0.0-1.0: Lower = more expressive/variable. Default 0.4",
                        "similarity_boost": "0.0-1.0: Voice clarity. Default 0.65",
                        "style": "0.0-1.0: Emotion/expressiveness. Default 0.2",
                        "use_speaker_boost": "bool: Enhance clarity. Default True",
                    },
                    "for_natural_speech": "Use stability=0.35, style=0.3 for less robotic output",
                    "for_consistent_speech": "Use stability=0.7, style=0.0 for predictable output",
                }
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
                "description": "Use ffmpeg directly via shell for video processing (avoids MCP timeouts).",
                "note": "Run these commands in your shell/terminal, NOT as MCP tools.",
                "steps": [
                    "1. Convert WebM to MP4: ffmpeg -i recording.webm -c:v libx264 -preset fast -crf 23 output.mp4",
                    "2. Add voiceover: ffmpeg -i video.mp4 -i voice.mp3 -c:v copy -c:a aac output.mp4",
                    "3. Add background music: ffmpeg -i video.mp4 -i music.mp3 -filter_complex '[1:a]volume=0.15[bg];[0:a][bg]amix=inputs=2' -c:v copy output.mp4",
                    "4. Add text overlay: ffmpeg -i video.mp4 -vf \"drawtext=text='Title':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2\" output.mp4",
                    "5. Concatenate videos: ffmpeg -f concat -safe 0 -i files.txt -c copy output.mp4",
                ]
            },
            "ken_burns_workflow": {
                "description": "Alternative to recording: Create videos from high-quality screenshots with pan/zoom effects.",
                "when_to_use": "Best for polished marketing videos, tutorials, or when you need precise control over each frame.",
                "steps": [
                    "1. screenshot(name='scene1', quality='full') - CRITICAL: Use quality='full' to prevent compression",
                    "2. screenshot(name='scene2', quality='full') - Take screenshots for each scene",
                    "3. Use ffmpeg zoompan filter for Ken Burns effect (see ken_burns_ffmpeg below)",
                    "4. Concatenate scenes and add voiceover",
                ],
                "screenshot_quality": {
                    "full": "Original resolution, no compression. USE THIS FOR VIDEO PRODUCTION.",
                    "optimized": "Auto-resizes to 2000px max. Good for debugging/LLM analysis, BAD for video.",
                },
                "ken_burns_ffmpeg": "ffmpeg -loop 1 -i screenshot.png -vf \"zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=125:s=1920x1080\" -t 5 -c:v libx264 -pix_fmt yuv420p output.mp4",
                "warning": "Default screenshot(quality='optimized') resizes images >2000px - this causes visible quality loss in final video!"
            },
        }

        # Common ffmpeg command examples for agents
        ffmpeg_examples = {
            "convert_webm_to_mp4": {
                "description": "Convert WebM recording to MP4 (required for most editing)",
                "command": "ffmpeg -i recording.webm -c:v libx264 -preset fast -crf 23 -c:a aac output.mp4",
                "notes": "Use -preset ultrafast for speed, -preset slow for quality"
            },
            "merge_audio_video": {
                "description": "Add voiceover to silent video",
                "command": "ffmpeg -i video.mp4 -i voiceover.mp3 -c:v copy -c:a aac -shortest output.mp4",
                "notes": "-shortest ends when shortest stream ends"
            },
            "multiple_audio_tracks": {
                "description": "Add multiple voiceovers at different timestamps",
                "command": "ffmpeg -i video.mp4 -i audio1.mp3 -i audio2.mp3 -filter_complex \"[1:a]adelay=0|0[a1];[2:a]adelay=5000|5000[a2];[a1][a2]amix=inputs=2[aout]\" -map 0:v -map \"[aout]\" -c:v copy output.mp4",
                "notes": "adelay=5000|5000 delays audio by 5 seconds (left|right channels)"
            },
            "add_background_music": {
                "description": "Mix background music with existing audio",
                "command": "ffmpeg -i video_with_voice.mp4 -i music.mp3 -filter_complex \"[1:a]volume=0.15[music];[0:a]volume=1.0[voice];[voice][music]amix=inputs=2:duration=first[aout]\" -map 0:v -map \"[aout]\" -c:v copy output.mp4",
                "notes": "volume=0.15 sets music to 15%, duration=first matches video length"
            },
            "add_text_overlay": {
                "description": "Burn text/title onto video",
                "command": "ffmpeg -i video.mp4 -vf \"drawtext=text='Welcome':fontsize=64:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,3)'\" -c:a copy output.mp4",
                "notes": "enable='between(t,0,3)' shows text from 0-3 seconds"
            },
            "concatenate_videos": {
                "description": "Join multiple video clips",
                "command": "ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4",
                "notes": "list.txt format: file 'clip1.mp4'\\nfile 'clip2.mp4'"
            },
            "extract_audio": {
                "description": "Extract audio track from video",
                "command": "ffmpeg -i video.mp4 -vn -c:a libmp3lame -q:a 2 audio.mp3",
                "notes": "-vn removes video, -q:a 2 is high quality"
            },
            "trim_video": {
                "description": "Cut a section from video",
                "command": "ffmpeg -i video.mp4 -ss 00:00:10 -to 00:00:30 -c copy output.mp4",
                "notes": "-ss is start time, -to is end time"
            },
        }

        best_practices = [
            "ALWAYS generate voiceover FIRST - audio duration determines video pacing",
            "For natural-sounding voiceover: use provider='elevenlabs' with stability=0.35, style=0.3",
            "Recommended voices: H2JKG8QcEaH9iUMauArc (Abhinav - warm), qr9D67rNgxf5xNgv46nx (Tarun - expressive)",
            "For Ken Burns videos: use screenshot(quality='full') to prevent compression artifacts",
            "Default screenshot(quality='optimized') resizes to 2000px max - good for debugging, bad for video",
            "Use ffmpeg via shell for post-production (avoids MCP timeout issues)",
            "For WebM to MP4: ffmpeg -i input.webm -c:v libx264 -preset fast output.mp4",
            "Keep background music at 10-15% volume (volume=0.15 in ffmpeg)",
            "Use -c:v copy when possible to skip re-encoding (much faster)",
            "Use set_presentation_mode(True) for cleaner visuals without scrollbars",
            "Wait LONGER than animation duration: camera_zoom(duration_ms=1000) needs wait(1500)",
            "Combine spotlight() + annotate() for maximum viewer impact",
            "Use spotlight(style='focus') for dramatic emphasis (ring + dim combined)",
            "Always clear_spotlight() before applying a new spotlight effect",
            "Record at 1920x1080 for professional quality",
            "Use get_video_duration() and get_audio_duration() to check file lengths",
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
                "ffmpeg_examples": ffmpeg_examples,
                "best_practices": best_practices,
            },
        }

    async def get_video_duration(self, path: str) -> Dict[str, Any]:
        """
        [Cinematic Engine] Get the duration of a video file.

        Uses ffprobe (part of ffmpeg) to extract video duration.
        This is a fast operation suitable for MCP tools.

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

            # Run ffprobe asynchronously
            try:
                returncode, stdout, stderr = await self._run_ffmpeg_async(
                    cmd,
                    timeout_sec=30,
                )
            except asyncio.TimeoutError:
                return {"success": False, "message": "ffprobe timed out"}

            if returncode != 0:
                return {
                    "success": False,
                    "message": f"ffprobe failed: {stderr}",
                }

            duration_sec = float(stdout.strip())
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
        except Exception as exc:  # pylint: disable=broad-except
            return {"success": False, "message": f"Failed to get duration: {exc}"}

    async def list_stock_music(
        self,
        query: Optional[str] = None,
        tags: Optional[str] = None,
        instrumental: bool = True,
        speed: Optional[str] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        limit: int = 10,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        [Cinematic Engine] Search for royalty-free stock music from Jamendo.

        Returns a list of tracks that can be downloaded with download_stock_music().
        Requires either client_id parameter OR JAMENDO_CLIENT_ID environment variable.
        Get a free API key at: https://devportal.jamendo.com/

        Args:
            query: Free text search (e.g., "upbeat corporate", "cinematic epic")
            tags: Music tags/genres (e.g., "rock+electronic", "ambient+relaxing")
            instrumental: If True, only instrumental tracks (default: True for background music)
            speed: Track tempo - "verylow", "low", "medium", "high", "veryhigh"
            min_duration: Minimum duration in seconds
            max_duration: Maximum duration in seconds
            limit: Max results to return (1-200, default 10)
            client_id: Jamendo API client ID (optional, falls back to JAMENDO_CLIENT_ID env var)

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
                            "audio_url": "https://...",
                            "download_url": "https://...",
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
        """
        if not AIOHTTP_AVAILABLE:
            return {
                "success": False,
                "message": "aiohttp not installed. Run: pip install aiohttp",
            }

        # Use provided client_id or fall back to environment variable
        api_client_id = client_id or os.environ.get("JAMENDO_CLIENT_ID")
        if not api_client_id:
            return {
                "success": False,
                "message": "client_id parameter or JAMENDO_CLIENT_ID env var required. Get a free key at https://devportal.jamendo.com/",
            }

        # Build API URL - Jamendo tracks endpoint
        params: Dict[str, Any] = {
            "client_id": api_client_id,
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
            url: URL to download (download_url from list_stock_music)
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
            download_stock_music(url=track["download_url"], filename="background.mp3")

            # Use with ffmpeg in shell:
            # ffmpeg -i video.mp4 -i music_cache/background.mp3 -filter_complex "[1:a]volume=0.15[bg];[0:a][bg]amix" -c:v copy output.mp4
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
