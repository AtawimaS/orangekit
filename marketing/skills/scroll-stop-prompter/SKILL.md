---
name: scroll-stop-prompter
description: Writes 3 kinds of AI image/video prompts (assembled, deconstructed, transition) per target model for turning product photos or footage into scroll-stop content, and emits an HTML preview. Use when the source video does not exist yet, or when the user wants a generation model to produce a scene of the product assembling or coming apart. If a video already exists, use /scroll-stop-builder.
---

# Scroll-Stop Prompter

Generates 3 kinds of AI image/video prompts for producing a product's "scroll-stop" content and delivers them as an HTML preview page.

## Workflow

### Step 1: Determine the task type

| condition                                            | mode       | steps run         |
| ---------------------------------------------------- | ---------- | ----------------- |
| called from marketing-workflow (a campaign directory exists) | pipeline   | 2 → 3 → 4 → 5     |
| called on its own                                    | standalone | 2 → 3 → 4         |
| only one prompt type requested ("assembled only", "video only") | single     | 2 → 3 (that one only) → 4 |

### Step 2: User intake

Collect with AskUserQuestion: product name, product description, visual style, target AI model.

### Step 3: Generate the prompts

Generate 3 prompts: Prompt A (Assembled Shot), Prompt B (Deconstructed Shot), Prompt C (Video Transition).

For the detailed elements of each prompt and the per-model optimization mapping, see `references/prompt-guide.md`.

### Step 4: Generate the HTML preview page

Generate the HTML from the `assets/prompt-page-template.html` template.

### Step 5: Pipeline handoff (pipeline mode only)

Save `prompts.md` into the campaign directory.

## Prompt-writing principles

- **Concrete visual description**: "brushed aluminum with subtle anodized finish" instead of "sleek"
- **Lighting description required**: state the lighting setup in every prompt
- **Background consistency**: keep the background tone the same across all 3 prompts
- **Model-specific syntax**: follow each AI model's parameter format

## Reference documents

| File | When to read it |
| --- | --- |
| [references/prompt-guide.md](references/prompt-guide.md) | Just before writing the prompts in Step 3 |
| [assets/prompt-page-template.html](assets/prompt-page-template.html) | When generating the HTML in Step 4 (a reasonable default — adjust it to the prompt content) |

- Pipeline integration: the marketing-workflow skill (calls this as Stage 1)
