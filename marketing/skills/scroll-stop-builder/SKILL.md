---
name: scroll-stop-builder
description: Builds an Apple-style website from a product video where frames advance as the user scrolls — FFmpeg frame extraction and Canvas rendering, with 13 sections to combine. Use when a video file already exists and the user wants a scroll-animation landing or product-intro page implemented. If the AI prompts to make the video are needed first, use /scroll-stop-prompter.
---

# Scroll-Stop Builder

Video file → frame extraction → a Canvas scroll-animation website.

The same technique as Apple's product pages: frames of a sequence are drawn onto a Canvas and mapped to scroll position.

## Prerequisites

- FFmpeg must be installed (`brew install ffmpeg`)
- Video 3–10 seconds, first frame must be a white background
- A local server is required (frames cannot load from `file://`)

## Workflow

### Step 1: Determine the task type

| condition | mode | steps run |
|------|------|----------|
| called from marketing-workflow (prompts.md exists) | pipeline | 2 (partial) → 3 → 4 → 5 → 6 → 7 |
| called on its own + a URL supplied | standalone-url | 2 → 3 → 4 → 5 → 6 |
| called on its own + content supplied directly | standalone-manual | 2 → 3 → 4 → 5 → 6 |

### Step 2: User interview

Collect the brand/product name, logo, accent color, background color, and mood/vibe. Confirm the section toggles.

### Step 3: Analyze the video and extract frames

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/extract-frames.sh "<VIDEO_PATH>" "<OUTPUT_DIR>" [TARGET_FPS]
```

Run the script without reading it. A missing FFmpeg or video ends with exit 2 and a message; a length outside 3–10 seconds only prints a WARN (extraction continues).

### Step 4: Generate the HTML site

Generate it as a single HTML file. For each section's implementation, see `references/sections-guide.md`.

### Step 5: Apply the design system

Compose fonts, colors, card styles, buttons, and effects from the interview results.

### Step 6: Apply the content and serve

```bash
cd "<OUTPUT_DIR>" && python3 -m http.server 8080
```

### Step 7: Pipeline handoff (pipeline mode only)

Save `site.md` into the campaign directory.

## Reference documents

| File | When to read it |
| --- | --- |
| [references/sections-guide.md](references/sections-guide.md) (250 lines, HTML/CSS/JS for each of the 13 sections) | Step 4, only the sections you implement |
| [assets/html-template.html](assets/html-template.html) | Copy as the scaffold when starting Step 4 |
| [scripts/extract-frames.sh](scripts/extract-frames.sh) | Run in Step 3 |

- Pipeline integration: the marketing-workflow skill (calls this as Stage 2)
