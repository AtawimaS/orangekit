---
name: web-asset-generator
description: Creates web assets from a logo, text, or emoji — favicon set (16–512px, ICO), Apple Touch Icon, Android Chrome icons, OG/social card images, Next.js Metadata API code. Use when the user asks for a "favicon", "OG image", "social card", or "apple-touch-icon". Manual invocation only.
disable-model-invocation: true
---

# Web Asset Generator

Logo/text/emoji → favicon + OG image → Next.js integration code.
There is exactly one rendering engine, **Pillow** — it draws shapes and text locally and rasterizes them. It uses no key and no network.

## Workflow

### Step 1: Determine the task type

| Keyword | Type | Runs |
|--------|------|------|
| "favicons only" | favicon-only | generate_favicons.py |
| "OG image only" | og-only | generate_og_images.py |
| "all assets" | full | run both |
| not specified | full | default: generate everything |

### Step 2: Interview the user

Collect the source image, brand colors, and source type (logo/emoji). OG images are made with Pillow (if an AI background is needed, see the note in Step 5).

### Step 3: Check dependencies

`${CLAUDE_SKILL_DIR}` is substituted by Claude Code — it resolves wherever the skill is installed: personal, project, or plugin:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/check_dependencies.py
```

If Pillow is missing (exit 2), run the install command it prints after confirming with the user.

### Step 4: Generate favicons

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_favicons.py <logo_path> public/ all --validate
```

### Step 5: Generate OG/social images

**Pillow mode** (the offline default):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_og_images.py --title "<title>" --out public/ \
  [--subtitle "<subtitle>"] [--logo <path>] [--bg "#0F172A"] [--fg "#FFFFFF"]
```

**When you want AI to make a background or an illustration**, this skill does not do it — `/image-generator`
does that job (it is a skill on the dev harness side). Pass the image you get there in as `--logo` or as the background and composite it.
If that skill is not visible, the Pillow mode above is still the answer (solid background + text).

### Step 6: Check the validation result

The `--validate` flag verifies file size, image size, format compatibility, and WCAG contrast ratio.

### Step 7: Provide Next.js Metadata API integration code

See the "Next.js 15 Metadata API Integration" section of `references/specifications.md`.

### Step 8: Completion summary

Report the list of generated files, the validation result, and the next steps.

## Reference documents

Run the three scripts without reading them.

| File | When to read it |
| --- | --- |
| [references/specifications.md](references/specifications.md) | When giving the Next.js integration code in Step 7, or when size/format specs are needed |
