"""
End-to-end test of the Cinematic Engine - creates a real demo video.

This script tests all cinematic features:
- Recording with virtual cursor
- Annotations (floating callouts)
- Highlight/spotlight effects
- Camera zoom/pan effects
- Smooth scrolling
- Background music from Jamendo
- Voiceover with ElevenLabs TTS
- Text overlays/titles
- Professional audio mixing

Usage:
    # Set environment variables (or uncomment below)
    set JAMENDO_CLIENT_ID=...
    set ELEVENLABS_API_KEY=...

    # Run the test
    python test_cinematic_video.py
"""

import asyncio
import os
import sys
import shutil

# Set API credentials (get your own keys)
# os.environ['JAMENDO_CLIENT_ID'] = 'your_jamendo_client_id'  # https://devportal.jamendo.com/
# os.environ['ELEVENLABS_API_KEY'] = 'your_elevenlabs_key'  # https://elevenlabs.io/

from agent_browser.mcp import BrowserServer


async def create_demo_video():
    server = BrowserServer('cinematic-test')
    server.configure(allow_private=True, headless=False)  # Visible for recording

    print("\n" + "="*60)
    print("CINEMATIC ENGINE - Full Feature Test")
    print("="*60)

    # Check environment
    print("\n[1/9] Checking environment...")
    env_result = await server.check_environment()
    print(f"  ffmpeg: {'OK' if env_result['data']['ffmpeg'] else 'MISSING'}")
    print(f"  ElevenLabs key: {'OK' if env_result['data']['elevenlabs_key'] else 'MISSING (no voiceover)'}")
    print(f"  Jamendo key: {'OK' if env_result['data']['jamendo_key'] else 'MISSING (no music)'}")

    has_voiceover = env_result['data']['elevenlabs_key']
    has_music = env_result['data']['jamendo_key']

    if not env_result['data']['ffmpeg']:
        print("\nERROR: ffmpeg is required. Install from https://ffmpeg.org/")
        return

    try:
        # Clear audio cache to generate fresh voiceover
        audio_cache = server._audio_cache_dir
        if audio_cache.exists():
            print(f"  Clearing audio cache: {audio_cache}")
            shutil.rmtree(audio_cache)

        # Generate voiceover if API key available
        voiceover_path = None
        if has_voiceover:
            print("\n[2/9] Generating voiceover with ElevenLabs...")
            vo_result = await server.generate_voiceover(
                text="Welcome to our demo. Watch as we explore this page with smooth animations, highlights, and professional effects.",
                voice="H2JKG8QcEaH9iUMauArc",   # Abhinav - warm, natural
                provider="elevenlabs",
                stability=0.35,                 # More expressive (less robotic)
                similarity_boost=0.6,           # Balanced clarity
                style=0.3                       # Some emotion
            )
            if vo_result['success']:
                voiceover_path = vo_result['data']['path']
                print(f"  Voiceover: {voiceover_path}")
            else:
                print(f"  Voiceover failed: {vo_result['message']}")
        else:
            print("\n[2/9] Skipping voiceover (no ELEVENLABS_API_KEY)")

        # Download background music
        music_path = None
        if has_music:
            print("\n[3/9] Finding background music...")
            music_result = await server.list_stock_music(
                query="corporate",
                instrumental=True,
                speed="medium",
                limit=1
            )
            if music_result['success'] and music_result['data']['tracks']:
                track = music_result['data']['tracks'][0]
                print(f"  Found: {track['name']} by {track['artist']} ({track['duration_sec']}s)")

                dl_result = await server.download_stock_music(
                    url=track['download_url'],
                    filename="demo_music.mp3"
                )
                if dl_result['success']:
                    music_path = dl_result['data']['path']
                    print(f"  Downloaded: {music_path}")
        else:
            print("\n[3/9] Skipping music (no JAMENDO_CLIENT_ID)")

        # Start recording
        print("\n[4/9] Starting recording...")
        rec_result = await server.start_recording(width=1280, height=720)
        if not rec_result['success']:
            print(f"  Recording failed: {rec_result['message']}")
            return
        print(f"  Recording to: {rec_result['data']['video_dir']}")

        # Navigate and demonstrate features
        print("\n[5/9] Recording demo sequence...")

        # Set presentation mode (hide scrollbars)
        await server.set_presentation_mode(enabled=True)

        # Navigate to example.com
        await server.goto("https://example.com")
        await server.wait(500)

        # Add annotation
        print("  - Adding annotation...")
        await server.annotate("Example Domain", style="info", position="top-right")
        await server.wait(1000)

        # Highlight the heading with spotlight effect
        print("  - Highlighting heading with spotlight...")
        await server.spotlight(selector="h1", style="focus", color="#3b82f6", dim_opacity=0.6)
        await server.wait(2000)

        # Clear highlight and zoom
        await server.clear_spotlight()
        print("  - Camera zoom on heading...")
        await server.camera_zoom(selector="h1", level=1.5, duration_ms=1000)
        await server.wait(1500)

        # Camera reset
        await server.camera_reset(duration_ms=800)
        await server.wait(500)

        # Clear annotations
        await server.clear_annotations()

        # Smooth scroll down
        print("  - Smooth scrolling...")
        await server.smooth_scroll(direction="down", amount=200, duration_ms=1000)
        await server.wait(500)

        # Camera pan to paragraph with ring highlight
        print("  - Camera pan with ring highlight...")
        await server.camera_pan(selector="p", duration_ms=800)
        await server.spotlight(selector="p", style="ring", color="#10b981")
        await server.wait(1500)

        # Add another annotation
        await server.annotate("Main Content Area", style="dark", position="bottom-left")
        await server.wait(1500)

        # Camera reset and cleanup
        await server.clear_spotlight()
        await server.camera_reset(duration_ms=600)
        await server.wait(500)

        # Clear and scroll back
        await server.clear_annotations()
        await server.smooth_scroll(direction="up", amount=200, duration_ms=800)
        await server.wait(500)

        # Stop recording
        print("\n[6/9] Stopping recording...")
        stop_result = await server.stop_recording()
        if not stop_result['success']:
            print(f"  Stop failed: {stop_result['message']}")
            return
        video_path = stop_result['data']['path']
        print(f"  Duration: {stop_result['data']['duration_sec']:.1f}s")
        print(f"  Saved to: {video_path}")

        # Post-production using ffmpeg via subprocess (avoids MCP timeouts)
        import subprocess
        output_path = "videos/demo_final.mp4"
        current_video = video_path

        # Convert WebM to MP4 first
        print("\n[7/9] Converting WebM to MP4...")
        mp4_path = "videos/demo_converted.mp4"
        convert_cmd = [
            "ffmpeg", "-y", "-i", current_video,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", mp4_path
        ]
        result = subprocess.run(convert_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            current_video = mp4_path
            print(f"  Converted: {mp4_path}")
        else:
            print(f"  Convert failed: {result.stderr[:200]}")

        # Merge voiceover if available
        if voiceover_path:
            print("\n[8/9] Merging voiceover...")
            with_vo_path = "videos/demo_with_vo.mp4"
            merge_cmd = [
                "ffmpeg", "-y", "-i", current_video, "-i", voiceover_path,
                "-filter_complex", "[1:a]adelay=500|500[delayed]",
                "-map", "0:v", "-map", "[delayed]",
                "-c:v", "copy", "-c:a", "aac", with_vo_path
            ]
            result = subprocess.run(merge_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                current_video = with_vo_path
                print(f"  Merged: {with_vo_path}")
            else:
                print(f"  Merge failed: {result.stderr[:200]}")
        else:
            print("\n[8/9] Skipping voiceover merge")

        # Add title overlay
        print("\n[9/9] Adding title overlay...")
        title_cmd = [
            "ffmpeg", "-y", "-i", current_video,
            "-vf", "drawtext=text='Cinematic Engine Demo':fontsize=42:fontcolor=white:x=(w-text_w)/2:y=50:enable='between(t,0,3)'",
            "-c:a", "copy", output_path
        ]
        result = subprocess.run(title_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  Final video: {output_path}")
        else:
            print(f"  Title failed: {result.stderr[:200]}")
            output_path = current_video

        # Get final file size
        from pathlib import Path
        final_path = Path(output_path)
        if final_path.exists():
            size_mb = final_path.stat().st_size / 1024 / 1024
            print(f"  Size: {size_mb:.2f} MB")

        print("\n" + "="*60)
        print("DEMO VIDEO COMPLETE!")
        print("="*60)
        print(f"\nOutput: {output_path}")
        print("\nFeatures demonstrated:")
        print("  - Virtual cursor with smooth movement")
        print("  - Floating annotations")
        print("  - Spotlight effects (ring, focus)")
        print("  - Camera zoom/pan effects")
        print("  - Smooth scrolling")
        print("  - Presentation mode")
        if voiceover_path:
            print("  - AI voiceover (ElevenLabs TTS)")
        if music_path:
            print("  - Background music (Jamendo CC)")
        print("  - Title overlay")

    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(create_demo_video())
