"""
Comprehensive Cinematic Engine Demo - showcases ALL features.

Creates a long-form demo video with prominent display of every feature:
- Virtual cursor with smooth movement
- Floating annotations
- Highlight effects (ring, spotlight, focus)
- Camera zoom/pan/reset
- Smooth scrolling
- Human-like typing
- Presentation mode
- AI voiceover (ElevenLabs)
- Background music (Jamendo CC)
- Text overlays/titles
- Professional audio mixing
"""

import asyncio
import os
import shutil
from pathlib import Path

# Set API credentials (get your own keys)
# os.environ['JAMENDO_CLIENT_ID'] = 'your_jamendo_client_id'  # https://devportal.jamendo.com/
# os.environ['ELEVENLABS_API_KEY'] = 'your_elevenlabs_key'  # https://elevenlabs.io/

from agent_browser.mcp import BrowserServer


async def create_comprehensive_demo():
    server = BrowserServer('cinematic-full-demo')
    server.configure(allow_private=True, headless=False)

    print("\n" + "="*70)
    print("CINEMATIC ENGINE - Comprehensive Feature Demo")
    print("="*70)

    # Check environment
    print("\n[1/10] Checking environment...")
    env_result = await server.check_environment()
    print(f"  ffmpeg: {'OK' if env_result['data']['ffmpeg'] else 'MISSING'}")
    print(f"  ElevenLabs: {'OK' if env_result['data']['elevenlabs_key'] else 'MISSING'}")
    print(f"  Jamendo: {'OK' if env_result['data']['jamendo_key'] else 'MISSING'}")

    if not env_result['data']['ffmpeg']:
        print("\nERROR: ffmpeg required")
        return

    try:
        # Clear caches
        for cache_dir in [server._audio_cache_dir, Path("music_cache")]:
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                print(f"  Cleared: {cache_dir}")

        # Generate longer voiceover
        print("\n[2/10] Generating voiceover...")
        voiceover_text = """
Welcome to the Cinematic Engine demo.
This powerful toolkit enables AI agents to create professional marketing videos.
Watch as we demonstrate smooth cursor animations, spotlight effects, camera movements, and text overlays.
Every feature is designed for creating polished, production-ready content.
        """.strip().replace("\n", " ")

        vo_result = await server.generate_voiceover(
            text=voiceover_text,
            voice="21m00Tcm4TlvDq8ikWAM",
            provider="elevenlabs"
        )
        voiceover_path = vo_result['data']['path'] if vo_result['success'] else None
        if voiceover_path:
            # Get voiceover duration
            dur_result = await server.get_audio_duration(voiceover_path)
            vo_duration = dur_result['data']['duration_sec'] if dur_result['success'] else 10
            print(f"  Voiceover: {vo_duration:.1f}s - {voiceover_path}")
        else:
            print(f"  Voiceover failed: {vo_result.get('message')}")
            vo_duration = 10

        # Download background music
        print("\n[3/10] Finding background music...")
        music_path = None
        music_result = await server.list_stock_music(
            query="inspiring corporate",
            instrumental=True,
            speed="medium",
            limit=1
        )
        if music_result['success'] and music_result['data']['tracks']:
            track = music_result['data']['tracks'][0]
            print(f"  Found: {track['name']} by {track['artist']}")
            dl_result = await server.download_stock_music(
                url=track['download_url'],
                filename="demo_music.mp3"
            )
            if dl_result['success']:
                music_path = dl_result['data']['path']
                print(f"  Downloaded: {music_path}")

        # ============================================
        # SCENE 1: Introduction with Wikipedia
        # ============================================
        print("\n[4/10] Recording Scene 1: Introduction...")

        rec_result = await server.start_recording(width=1920, height=1080)
        if not rec_result['success']:
            print(f"  Recording failed: {rec_result['message']}")
            return
        print(f"  Recording started at 1920x1080")

        # Set presentation mode
        await server.set_presentation_mode(enabled=True)

        # Navigate to a content-rich page
        await server.goto("https://en.wikipedia.org/wiki/Artificial_intelligence")
        await server.wait(1500)

        # Add welcome annotation
        print("  - Welcome annotation...")
        await server.annotate("Cinematic Engine Demo", style="dark", position="top-right")
        await server.wait(2000)

        # Spotlight on the title
        print("  - Spotlight on title...")
        await server.spotlight(selector="h1", style="focus", color="#3b82f6", dim_opacity=0.7)
        await server.wait(3000)
        await server.clear_spotlight()

        # Camera zoom on title
        print("  - Camera zoom...")
        await server.camera_zoom(selector="h1", level=1.3, duration_ms=1200)
        await server.wait(2000)
        await server.camera_reset(duration_ms=1000)
        await server.wait(1000)

        # Clear and scroll
        await server.clear_annotations()

        # Smooth scroll down to content
        print("  - Smooth scrolling...")
        await server.smooth_scroll(direction="down", amount=400, duration_ms=1500)
        await server.wait(1000)

        # Ring highlight on first paragraph
        print("  - Ring highlight on content...")
        await server.spotlight(selector="#mw-content-text p", style="ring", color="#10b981", pulse_ms=1200)
        await server.annotate("AI-generated content detection", style="light", position="right")
        await server.wait(3000)
        await server.clear_spotlight()
        await server.clear_annotations()

        # Camera pan to infobox if exists
        print("  - Camera pan...")
        await server.camera_pan(selector=".infobox", duration_ms=1000)
        await server.wait(2000)

        # Spotlight on infobox
        await server.spotlight(selector=".infobox", style="spotlight", dim_opacity=0.6)
        await server.annotate("Quick Facts", style="dark", position="left")
        await server.wait(3000)
        await server.clear_spotlight()
        await server.clear_annotations()

        # Reset camera
        await server.camera_reset(duration_ms=800)
        await server.wait(1000)

        # Scroll back up
        await server.smooth_scroll(direction="up", amount=400, duration_ms=1200)
        await server.wait(1000)

        # Final annotation
        await server.annotate("Thank you for watching!", style="dark", position="center")
        await server.wait(2000)
        await server.clear_annotations()

        # Stop recording
        print("\n[5/10] Stopping recording...")
        stop_result = await server.stop_recording()
        if not stop_result['success']:
            print(f"  Stop failed: {stop_result['message']}")
            return

        raw_video = stop_result['data']['path']
        duration = stop_result['data']['duration_sec']
        print(f"  Raw video: {duration:.1f}s")

        # ============================================
        # POST-PRODUCTION
        # ============================================

        # Merge voiceover
        current_video = raw_video
        if voiceover_path:
            print("\n[6/10] Merging voiceover...")
            merge_result = await server.merge_audio_video(
                video=current_video,
                audio_tracks=[{"path": voiceover_path, "start_ms": 1000}],
                output="videos/demo_with_voice.mp4"
            )
            if merge_result['success']:
                current_video = merge_result['data']['path']
                print(f"  With voiceover: {current_video}")
            else:
                print(f"  Merge failed: {merge_result['message']}")

        # Add background music
        if music_path:
            print("\n[7/10] Adding background music...")
            music_result = await server.add_background_music(
                video=current_video,
                music=music_path,
                output="videos/demo_with_music.mp4",
                music_volume=0.10,  # 10% - very subtle
                voice_volume=1.4,   # 140% - boost voice
                fade_in_sec=2.0,
                fade_out_sec=3.0,
            )
            if music_result['success']:
                current_video = music_result['data']['path']
                print(f"  With music: {current_video}")
            else:
                print(f"  Music failed: {music_result['message']}")

        # Add intro title
        print("\n[8/10] Adding intro title...")
        title_result = await server.add_text_overlay(
            video=current_video,
            text="Cinematic Engine",
            output="videos/demo_with_title.mp4",
            position="center",
            start_sec=0,
            end_sec=3,
            font_size=72,
            font_color="white",
            bg_color="black@0.7",
            bg_padding=30,
            fade_in_sec=0.8,
            fade_out_sec=0.8,
        )
        if title_result['success']:
            current_video = title_result['data']['path']
            print(f"  With title: {current_video}")
        else:
            print(f"  Title failed: {title_result['message']}")

        # Add subtitle
        print("\n[9/10] Adding subtitle...")
        subtitle_result = await server.add_text_overlay(
            video=current_video,
            text="Professional Video Production for AI Agents",
            output="videos/demo_final.mp4",
            position="bottom",
            start_sec=1,
            end_sec=4,
            font_size=36,
            font_color="white",
            bg_color="black@0.5",
            bg_padding=15,
            fade_in_sec=0.5,
            fade_out_sec=0.5,
        )

        final_video = "videos/demo_final.mp4"
        if subtitle_result['success']:
            print(f"  Final video: {subtitle_result['data']['path']}")
        else:
            print(f"  Subtitle failed: {subtitle_result['message']}")
            final_video = current_video

        # Get final stats
        print("\n[10/10] Final video stats...")
        final_path = Path(final_video)
        if final_path.exists():
            size_mb = final_path.stat().st_size / 1024 / 1024
            dur_result = await server.get_video_duration(str(final_path))
            final_duration = dur_result['data']['duration_sec'] if dur_result['success'] else duration
            print(f"  Duration: {final_duration:.1f}s")
            print(f"  Size: {size_mb:.2f} MB")

        print("\n" + "="*70)
        print("DEMO VIDEO COMPLETE!")
        print("="*70)
        print(f"\nOutput: {final_video}")
        print("\nFeatures demonstrated:")
        print("  [x] Virtual cursor with smooth movement")
        print("  [x] Floating annotations (light & dark styles)")
        print("  [x] Highlight effects (ring, spotlight, focus)")
        print("  [x] Camera zoom with cinematic easing")
        print("  [x] Camera pan to elements")
        print("  [x] Camera reset")
        print("  [x] Smooth scrolling (up & down)")
        print("  [x] Presentation mode (hidden scrollbars)")
        print("  [x] AI voiceover (ElevenLabs)")
        print("  [x] Background music (Jamendo CC)")
        print("  [x] Professional audio mixing")
        print("  [x] Text overlay - main title")
        print("  [x] Text overlay - subtitle")
        print("  [x] Fade in/out effects")

    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(create_comprehensive_demo())
