# b4video

Automated video production pipeline for b4arena. Write a Markdown script, run a command, get a YouTube-ready video.

## How it works

```
script.md -> Parse -> Voice (ElevenLabs) -> Visuals (HeyGen + Showboat) -> Compose (FFmpeg) -> final.mp4
```

Each `## Section` in your script becomes a scene. Scenes can be:
- **`presenter`** -- full-screen AI avatar speaking the narration
- **`demo`** -- screen recording with avatar picture-in-picture, narration as voiceover

## Quick start

```bash
# Install
pip install -e .

# Configure API keys
cp .env.example .env
# Edit .env with your ElevenLabs and HeyGen API keys

# Render a video
b4video render examples/beads-demo.md

# Preview cost first
b4video render examples/beads-demo.md --dry-run
```

## Script format

```markdown
---
title: "My Video Title"
voice: b4arena-default
avatar: presenter-01
resolution: 1920x1080
fps: 30
---

## Intro
<!-- type: presenter -->
Welcome! Today we'll look at...

## Feature Demo
<!-- type: demo -->
<!-- showboat: path/to/demo-script.sh -->
Here we see the feature in action...

## Outro
<!-- type: presenter -->
Thanks for watching!
```

## Commands

```bash
b4video render script.md                # Full pipeline
b4video render script.md --dry-run      # Validate + cost estimate
b4video render script.md --stage=voice  # Run one stage only
b4video render script.md --force        # Regenerate everything

b4video voices list                     # Show configured voices
b4video voices preview <alias>          # 10-second sample
b4video avatars list                    # Show configured avatars
b4video avatars preview <alias>         # 5-second test clip

b4video cost script.md                  # Quick cost estimate
```

## Cost

Typical 3-5 min video (~800 words, 4-5 scenes): **$11-20**

| Service | Cost |
|---------|------|
| ElevenLabs (voice) | $3-5 |
| HeyGen (avatar) | $8-15 |
| FFmpeg (composition) | $0 |

## Dependencies

- Python 3.12+
- `ffmpeg` and `ffprobe` (system packages)
- ElevenLabs API key
- HeyGen API key

## License

GPL-3.0-or-later
