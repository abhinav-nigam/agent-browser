# Cinematic Engine - Implementation Guide

> Transform agent-browser from "functional testing" to "marketing video production"

## Value Proposition

**The Problem:** Creating marketing videos for web apps requires:
- Screen recording software
- Video editing skills
- Voiceover recording/TTS setup
- Manual timing synchronization
- Custom cursor overlays
- Multiple tool coordination

**Our Solution:** An AI agent says:
```
"Create a 30-second demo of the checkout flow with narration"
```
And gets a polished marketing video with cursor animation, smooth movement, camera focus, and synchronized voiceover.

**Key Differentiator:** Integration. One coherent API that handles the entire pipeline, designed for AI agents.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agent                                  │
│  "Demo the login flow, zoom into the dashboard, narrate steps"  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Cinematic Engine                              │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│   Voice     │   Video     │   Virtual   │   Camera    │  Post   │
│  Generator  │  Recorder   │   Actor     │  Control    │ Process │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────┤
│ OpenAI TTS  │ Playwright  │ Cursor SVG  │ CSS Trans-  │ ffmpeg  │
│ ElevenLabs  │ CDP Screen- │ Mouse Ease  │ form Zoom   │ mixing  │
│             │ cast API    │ Smooth Scroll│ Pan/Focus  │         │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────┘
```

---

## Architecture Decision: Same Server, Optional Activation

**Decision:** Cinematic features will be part of the existing `agent-browser` MCP server, not a separate server.

**Rationale:**
- Recording needs the **same browser context** as interactions
- Separate server would require either two browser instances (wasteful) or complex IPC (fragile)
- Single server = cursor, annotations, and recording work seamlessly with existing tools

**Dependency Strategy:**
```bash
# Core testing - no video dependencies
pip install ai-agent-browser

# Video production - adds TTS clients
pip install ai-agent-browser[video]
```

| Dependency | Type | When Loaded |
|------------|------|-------------|
| `openai` | Optional pip extra | First `generate_voiceover()` call |
| `elevenlabs` | Optional pip extra | First `generate_voiceover(provider="elevenlabs")` call |
| `ffmpeg` | External CLI tool | Used via shell commands for post-production (avoids MCP timeouts) |

**Lazy Loading:**
```python
# Testing users - no change, no video deps loaded
await goto("https://myapp.com")
await click("#login")

# Video users - deps loaded on first use
await start_recording()      # Injects cursor, starts capture
await generate_voiceover()   # Lazy-loads TTS client
# Post-production: use ffmpeg via shell (see check_environment() for commands)
```

---

## Implementation Phases

### Phase 1: Voice & Timing (P0)
**Goal:** Generate voiceovers FIRST so we know timing for video pacing

> **Key Insight:** We must know audio duration BEFORE recording video.
> The voiceover drives the pacing of all visual actions.

#### 1.1 TTS Integration
- [ ] `generate_voiceover(text, options?)` - Generate audio file
  - Options: `provider` (openai/elevenlabs), `voice`, `speed`
- [ ] `get_audio_duration(file_path)` - Get length in ms
- [ ] Voice caching to avoid redundant API calls

**Technical Notes:**
- OpenAI TTS: `tts-1` or `tts-1-hd` model
- ElevenLabs: Higher quality, more voices
- Cache by hash of (text + voice + provider)
- Store in `audio_cache/` directory

#### 1.2 Audio Utilities
- [ ] `get_audio_duration(path)` - Returns duration in ms
- [ ] `concatenate_audio(paths[], output)` - Join multiple clips
- [ ] `add_silence(path, before_ms?, after_ms?)` - Add padding

**Deliverable:** Can generate voiceovers and know exact timing for pacing.

---

### Phase 2: Recording & Virtual Actor (P1)
**Goal:** Record video with visible cursor, paced to audio timing

#### 2.1 Video Recording
- [ ] `start_recording(filename?, width?, height?, mode?)` - Begin capture
  - `mode="draft"` - 30fps, fast iteration during script development
  - `mode="render"` - 60fps, final production quality (CPU intensive)
- [ ] `stop_recording()` - End capture, return video path
- [ ] `recording_status()` - Check if recording, get duration

**Technical Notes:**
- Draft mode: Playwright's `recordVideo` (~30fps) - fast, good for iteration
- Render mode: CDP `Page.startScreencast` API (60fps) - slower, final output
- Default to "draft" to save resources; switch to "render" for final export
- Store recordings in `videos/` directory

#### 2.2 Virtual Cursor
- [ ] Inject SVG cursor overlay on recording start
- [ ] Cursor follows mouse coordinates
- [ ] Click animation (ripple effect)
- [ ] Cursor styles: default, pointer, text, custom

**Technical Notes:**
- Fixed position div with `z-index: 2147483647`
- `pointer-events: none` so it doesn't interfere
- Animate position with CSS transitions or JS

#### 2.3 Audio-Paced Actions
- [ ] `smooth_click(selector, duration_ms)` - Move cursor then click
- [ ] `smooth_scroll(direction, amount?, duration_ms)` - Animated scroll
- [ ] All actions accept `duration_ms` to match voiceover timing

#### 2.4 Annotations & Highlights (CORE - not polish!)
> **Key Insight:** A cursor moving to a button is too subtle for mobile viewers.
> Visual cues are essential for marketing videos, not optional polish.

- [ ] `highlight(selector, style?, duration_ms?)` - Draw attention to element
  - Styles: `"ring"` (animated border), `"spotlight"` (dim background, focus element)
- [ ] `annotate(text, target_selector?, position?, duration_ms?)` - Floating text label
  - Positions: `"top"`, `"bottom"`, `"left"`, `"right"`, `"center"`
- [ ] `clear_annotations()` - Remove all overlays

**Technical Notes:**
- Annotations are fixed-position overlays with high z-index
- Spotlight effect: Semi-transparent overlay with CSS clip-path cutout
- Ring effect: Animated border using CSS box-shadow or SVG
- Auto-remove after `duration_ms` or on `clear_annotations()`

**Example Workflow:**
```python
# 1. Generate voiceover FIRST
audio = await generate_voiceover("Click the login button")
duration = await get_audio_duration(audio)  # 2000ms

# 2. Record video paced to audio duration
await start_recording()
await smooth_click("#login", duration_ms=duration)
await stop_recording()

# 3. Mix in post-production (use ffmpeg via shell)
# ffmpeg -i video.webm -i audio.mp3 -c:v libx264 -c:a aac output.mp4
```

**Deliverable:** Can record video with visible cursor, actions paced to voiceover.

---

### Phase 3: Camera Control (P2)
**Goal:** Direct viewer attention with zoom and pan (happens DURING recording)

#### 3.1 CSS Transform Camera
- [ ] `camera_zoom(selector, level?, duration_ms?)` - Zoom into element
- [ ] `camera_pan(selector, duration_ms?)` - Center element without zoom
- [ ] `camera_reset(duration_ms?)` - Return to full view

**Technical Notes:**
- Apply CSS `transform: scale() translate()` to document root
- Calculate translate to center target element
- Use CSS transitions for smooth animation
- **Critical:** Do NOT resize viewport (breaks responsive layouts)

**Example:**
```python
await camera_zoom("#price-total", level=2.0, duration_ms=1000)
await wait(2000)  # Hold the zoom
await camera_reset(duration_ms=800)
```

#### 3.2 Ken Burns Effect
- [ ] `camera_pan_zoom(from_selector, to_selector, duration_ms)` - Animated transition

**Deliverable:** Can create videos with professional zoom/pan camera movements.

---

### Phase 4: Post-Production (P3)
**Goal:** Combine audio and video into final output (happens AFTER recording)

> **Important:** Post-production uses ffmpeg via shell commands (not MCP tools) to avoid MCP timeout issues with long-running video operations. Call `check_environment()` to get copy-paste ffmpeg command examples!

#### 4.1 Environment Validation
- [x] `check_environment()` - Verify ffmpeg, API keys, get workflow guide
  - Returns: `{ffmpeg: bool, ffmpeg_examples: {...}, workflow: {...}, best_practices: [...]}`
  - Provides 8 ready-to-use ffmpeg command examples
- [x] `get_video_duration(path)` - Get video length in seconds/milliseconds

**Technical Notes:**
- ffmpeg required for: MP4 conversion, audio mixing, text overlays
- Without ffmpeg: Can still record WebM, generate TTS
- Auto-detect ffmpeg: `which ffmpeg` (Unix) or `where ffmpeg` (Windows)

#### 4.2 Audio-Video Merge (use ffmpeg via shell)
```bash
# Add voiceover to video
ffmpeg -i video.webm -i voiceover.mp3 -c:v libx264 -c:a aac output.mp4

# Multiple audio tracks with timing
ffmpeg -i video.mp4 -i audio1.mp3 -i audio2.mp3 \
  -filter_complex "[1:a]adelay=0|0[a1];[2:a]adelay=5000|5000[a2];[a1][a2]amix=inputs=2[aout]" \
  -map 0:v -map "[aout]" -c:v copy output.mp4
```

#### 4.3 Background Music (use ffmpeg via shell)
```bash
# Add background music at 15% volume
ffmpeg -i video_with_voice.mp4 -i music.mp3 \
  -filter_complex "[1:a]volume=0.15[music];[0:a][music]amix=inputs=2:duration=first[aout]" \
  -map 0:v -map "[aout]" -c:v copy output.mp4
```

**Deliverable:** Can produce final MP4 with synchronized voiceover AND background music using ffmpeg shell commands.

---

### Phase 5: Polish (P4)
**Goal:** Human-like movement and clean environment

#### 5.1 Advanced Mouse Movement
- [ ] Bezier curve paths (not straight lines)
- [ ] Easing functions (ease-in-out, cubic-bezier)
- [ ] Optional overshoot (human-like targeting)
- [ ] Variable speed based on distance

#### 5.2 Human-Like Typing
- [ ] `type_human(selector, text, wpm?, variance?)` - Realistic typing
- [ ] Variable inter-key delays
- [ ] Optional typos and corrections

#### 5.3 Director Mode
- [ ] `set_presentation_mode(enabled)` - Clean recording environment
  - Hide scrollbars (`::-webkit-scrollbar { display: none }`)
  - Force smooth scrolling (`scroll-behavior: smooth` on html/body)
  - Hide tooltips, debug overlays
  - Standardize fonts if needed
- [ ] `freeze_time(timestamp?)` - Mock Date.now() for consistent clocks

**Deliverable:** Professional-quality videos indistinguishable from manual production.

---

## API Reference (Target State)

### Recording
```python
start_recording(filename?: str, width?: int, height?: int, mode?: str) -> {path: str}
# mode: "draft" (30fps, fast) or "render" (60fps, production quality)
stop_recording() -> {path: str, duration_ms: int}
recording_status() -> {recording: bool, duration_ms?: int}
```

### Voice
```python
generate_voiceover(text: str, provider?: str, voice?: str, speed?: float) -> {path: str}
get_audio_duration(path: str) -> {duration_ms: int}
play_audio(path: str) -> {success: bool}  # For preview, not captured in recording
```

### Movement
```python
smooth_click(selector: str, duration_ms?: int, easing?: str) -> {success: bool}
smooth_scroll(direction: str, amount?: int, duration_ms?: int) -> {success: bool}
mouse_move_to(selector: str, duration_ms?: int, path?: str) -> {success: bool}
type_human(selector: str, text: str, wpm?: int, variance?: float) -> {success: bool}
```

### Camera
```python
camera_zoom(selector: str, level?: float, duration_ms?: int) -> {success: bool}
camera_pan(selector: str, duration_ms?: int) -> {success: bool}
camera_reset(duration_ms?: int) -> {success: bool}
```

### Environment
```python
set_presentation_mode(enabled: bool, cursor_style?: str) -> {success: bool}
freeze_time(timestamp?: int) -> {success: bool}
annotate(text: str, position?: str, style?: str, duration_ms?: int) -> {id: str}
clear_annotations() -> {success: bool}
```

### Post-Production
```python
check_environment() -> {ffmpeg: bool, ffmpeg_examples: {...}, workflow: {...}, best_practices: [...]}
get_video_duration(path: str) -> {duration_sec: float, duration_ms: int}

# For video processing, use ffmpeg via shell (avoids MCP timeouts):
# ffmpeg -i video.webm -c:v libx264 -preset fast output.mp4
# ffmpeg -i video.mp4 -i audio.mp3 -c:v copy -c:a aac output.mp4
# See check_environment()["data"]["ffmpeg_examples"] for full command reference
```

### Music Library
```python
search_music(mood?: str, genre?: str, duration_max?: int) -> {tracks: [{id, title, duration, preview_url}]}
download_music(track_id: str) -> {path: str}
# Moods: upbeat, calm, dramatic, inspiring, playful
# Genres: corporate, electronic, acoustic, cinematic, ambient
```

---

## Technical Considerations

### Video Quality
| Setting | Value | Notes |
|---------|-------|-------|
| Resolution | 1920x1080 (default) | 4K optional but CPU intensive |
| FPS | 30 (Playwright default) | 60fps requires CDP screencast |
| Codec | WebM (native) → MP4 (converted) | H.264 for compatibility |
| Bitrate | 4-8 Mbps | Balance quality vs file size |

### Cursor Implementation
```javascript
// Injected into page
const cursor = document.createElement('div');
cursor.id = '__agent_browser_cursor__';
cursor.style.cssText = `
  position: fixed;
  width: 24px;
  height: 24px;
  background: url(cursor.svg);
  pointer-events: none;
  z-index: 2147483647;
  transition: left 0.1s, top 0.1s;
`;
document.body.appendChild(cursor);

// Update position before each action
function moveCursor(x, y, duration) {
  cursor.style.transition = `left ${duration}ms, top ${duration}ms`;
  cursor.style.left = x + 'px';
  cursor.style.top = y + 'px';
}
```

### Camera Zoom Implementation
```javascript
// Apply to html element
function zoomTo(element, level, duration) {
  const rect = element.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;

  const viewportCenterX = window.innerWidth / 2;
  const viewportCenterY = window.innerHeight / 2;

  const translateX = viewportCenterX - centerX;
  const translateY = viewportCenterY - centerY;

  document.documentElement.style.transition = `transform ${duration}ms ease-in-out`;
  document.documentElement.style.transformOrigin = `${centerX}px ${centerY}px`;
  document.documentElement.style.transform = `scale(${level}) translate(${translateX/level}px, ${translateY/level}px)`;
}
```

### TTS Providers

#### OpenAI TTS
```python
from openai import OpenAI
client = OpenAI()
response = client.audio.speech.create(
    model="tts-1-hd",
    voice="alloy",  # alloy, echo, fable, onyx, nova, shimmer
    input="Your text here"
)
response.stream_to_file("output.mp3")
```

#### ElevenLabs
```python
from elevenlabs import generate, save
audio = generate(
    text="Your text here",
    voice="Rachel",
    model="eleven_monolingual_v1"
)
save(audio, "output.mp3")
```

---

## Example: Complete Marketing Video

```python
# Agent receives: "Create a demo of the login flow for our landing page"

# ============================================
# STEP 0: Verify environment
# ============================================
env = await check_environment()
if not env["ffmpeg"]:
    print("Warning: ffmpeg not found. Will output WebM without music.")
if not env["openai_key"]:
    raise Error("OPENAI_API_KEY required for voiceover generation")

# ============================================
# STEP 1: Generate all voiceovers FIRST
# (We need durations before recording video)
# ============================================
voiceovers = [
    await generate_voiceover("Welcome to MyApp. Let me show you how easy it is to get started."),
    await generate_voiceover("Simply enter your email and password."),
    await generate_voiceover("Click login, and you're in! Notice the personalized dashboard."),
]
durations = [await get_audio_duration(v) for v in voiceovers]
# durations = [3200, 2800, 4100]  # Example: ms for each clip

# ============================================
# STEP 2: Record video, pacing actions to audio
# (No audio captured - just visual recording)
# ============================================
await set_presentation_mode(True)
await viewport(1920, 1080)
await goto("https://myapp.com")

await start_recording("login_demo", mode="render")  # 60fps for final output

# Scene 1: Introduction (3200ms to match voiceover[0])
await wait(durations[0])

# Scene 2: Fill form (2800ms to match voiceover[1])
await camera_zoom("#login-form", level=1.5, duration_ms=600)
await highlight("#email", style="ring", duration_ms=1500)  # Draw attention!
await annotate("Enter your email", target="#email", position="right")
await smooth_click("#email", duration_ms=400)
await type_human("#email", "demo@example.com", wpm=80)
await clear_annotations()
await smooth_click("#password", duration_ms=300)
await type_human("#password", "********", wpm=80)
await camera_reset(duration_ms=500)

# Scene 3: Submit and result (4100ms to match voiceover[2])
await smooth_click("#login-btn", duration_ms=500)
await wait_for_url("/dashboard")
await camera_zoom(".welcome-message", level=1.3, duration_ms=800)
await wait(2000)
await camera_reset(duration_ms=800)

video_path = await stop_recording()

# ============================================
# STEP 3: Post-production - use ffmpeg via shell (avoids MCP timeouts)
# ============================================
# Run these commands in your shell/terminal:

# Convert WebM to MP4
# ffmpeg -i {video_path} -c:v libx264 -preset fast -crf 23 login_demo.mp4

# Merge multiple voiceovers with timing offsets
# ffmpeg -i login_demo.mp4 -i {voiceovers[0]} -i {voiceovers[1]} -i {voiceovers[2]} \
#   -filter_complex "[1:a]adelay=0|0[a1];[2:a]adelay={durations[0]}|{durations[0]}[a2];[3:a]adelay={durations[0]+durations[1]}|{durations[0]+durations[1]}[a3];[a1][a2][a3]amix=inputs=3[aout]" \
#   -map 0:v -map "[aout]" -c:v copy login_demo_with_voice.mp4

# ============================================
# STEP 4: Find and add background music
# ============================================
tracks = await list_stock_music(query="upbeat corporate", instrumental=True)
music_result = await download_stock_music(url=tracks["data"]["tracks"][0]["download_url"])
music_path = music_result["data"]["path"]

# Add background music (15% volume) - run in shell:
# ffmpeg -i login_demo_with_voice.mp4 -i {music_path} \
#   -filter_complex "[1:a]volume=0.15[music];[0:a][music]amix=inputs=2:duration=first[aout]" \
#   -map 0:v -map "[aout]" -c:v copy login_demo_final.mp4
```

---

## Success Metrics

- [ ] **Phase 1 Complete:** Can generate voiceovers and get duration for pacing
- [ ] **Phase 2 Complete:** Can record video with cursor + annotations, paced to audio
- [ ] **Phase 3 Complete:** Can zoom/pan camera smoothly during recording
- [ ] **Phase 4 Complete:** Can merge audio + video + music into final MP4
- [ ] **Phase 5 Complete:** Videos are indistinguishable from professional production

---

## Open Questions

1. **TTS API Keys:** How should users configure their OpenAI/ElevenLabs keys?
   - Recommendation: Environment variables (`OPENAI_API_KEY`, `ELEVENLABS_API_KEY`)

2. **Background Music Library:** Integrate with free music APIs
   - Pixabay Music API (free, no attribution required for most tracks)
   - Free Music Archive API
   - `search_music(mood?, genre?, duration?)` → returns track options
   - `download_music(track_id)` → downloads to local cache

3. **Video Hosting:** Should we integrate upload to YouTube/Vimeo/S3?
   - Nice to have but not core functionality

4. **Templates:** Should we provide pre-built "video templates" for common flows?
   - E.g., "product demo", "tutorial walkthrough", "feature highlight"
