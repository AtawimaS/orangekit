---
name: figma-asset-extractor
description: Reads a Figma design file, breaks its screens down into components, and extracts tokens, component specs, screen layouts, flow diagrams, images and icons into a design bundle under dev/docs/design/figma/. Use when the user gives a Figma URL and asks to "extract the design", "turn the Figma into assets", "pull out the components", or before building a product from a finished plan and design. Implementing a single screen straight into code goes to figma-design-to-code; setting a visual direction when no design exists goes to /ui-ux-design.
---

# /figma-asset-extractor — Figma → design bundle

Goal: turn a finished design into a machine-readable bundle so an implementing agent can reproduce it at the
same quality **without Figma**. The bundle is the primary source for implementation; Figma is only for
re-checking an ambiguous node.

## Boundary

| Request | Not here, but |
| --- | --- |
| Implement one node as code right now | `figma:figma-design-to-code` (pass it the node id from the bundle if one exists) |
| No design yet — choose style, color, fonts | `/ui-ux-design` |
| Draw or edit in Figma | `figma:figma-use` — **this skill never writes to the Figma file** |

## Checklist — copy into your response and mark progress

```
- [ ] 0. Pick the path (probe)
- [ ] 1. Settle scope and output location
- [ ] 2. Collect raw data (REST fetch or MCP fallback)
- [ ] 3. build
- [ ] 4. Naming (aliases.json)
- [ ] 5. build → check loop
- [ ] 6. Report
```

## 0. Pick the path

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/figma_bundle.py probe --url "<Figma URL>"
```

| Output | exit | Next |
| --- | --- | --- |
| `ready` + page list | 0 | REST path (2-A) |
| `no-token` | 2 | **Do not block.** Show the user the token instructions as printed; if they will not wait, take the MCP fallback (2-B) |
| `API 403/404` | 1 | The token's account cannot see the file — have the user request sharing |

The user puts the token in the `FIGMA_TOKEN` environment variable or `~/.config/figma/token` themselves.
**Never take the token in chat, and never write it into a command-line argument or a project file.** If the user
has copied it to the clipboard, `pbpaste | tr -d '[:space:]' > ~/.config/figma/token && chmod 600 ~/.config/figma/token`
stores it without the value entering the conversation — clear the clipboard afterwards. The fallback needs the Figma
MCP (`plugin:figma:figma`) connected — if MCP `whoami` fails, have the user authenticate in `/mcp` and stop.

## 1. Scope and output location

- **Output**: `dev/docs/design/figma/<file-slug>/` in the consumer project (e.g. `dev/docs/design/figma/orangetopia-2026/`),
  or wherever the user says. `dev/docs/design/` is the same design-doc root as `/ui-ux-design`'s `MASTER.md` — never overwrite a directory of the same slug.
- **Page scope**: from probe's page list, propose excluding presentation, draft, cover and archive pages, and ask **once**.
  If the user already named the pages, do not ask. Include the component page even though it has no screens — the instances' originals live there.

## 2-A. Collect — REST (default)

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/figma_bundle.py fetch --url "<URL>" --out <bundle> --pages <id,id,…>
```

Downloads the raw JSON (`raw/file.json`), original images, screen and component-variant PNGs (2x) and icon SVGs
straight to disk — nothing passes through the conversation. Large files take minutes; run it in the background.
If it stops or reports failures, rerun the same command with `--resume`: it reuses `raw/file.json` and skips assets already on disk.

## 2-B. Collect — MCP fallback (no token)

Everything passes through the conversation, so it is expensive (about 15KB per screen). Before starting, tell the user the
bundle will have **summary fidelity** (an instance's inner structure survives only through its component definition).

1. `create_session` (fileKey, "Design bundle extraction — read only")
2. For each page, Read `${CLAUDE_SKILL_DIR}/scripts/extract-page.js`, change only `pageId` and `offset` in `ARGS`, and send it as
   `use_figma`'s code. Write the return value **as is** to `<bundle>/raw/mcp-<pageId>-<offset>.json`. Repeat with `part.next` while it is not null.
   With three or more pages, hand each page to a subagent (the steps above plus saving; it reports only the saved path and screen count)
3. Assets: for each screen and component set, call `download_assets`, collect the `export` (render) and `rawImages` (original) URLs in
   `<bundle>/raw/urls.json` as `{"kind": "screens|components|images|icons", "node": "<id>", "url": "…"}`, and download right away (the URLs expire within minutes):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/figma_bundle.py fetch-urls --list <bundle>/raw/urls.json --out <bundle>
```

An original image's SHA-1 equals its Figma `imageHash`, so the script names it automatically.

## 3. build

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/figma_bundle.py build --out <bundle>
```

| Output | Contents |
| --- | --- |
| `README.md` | The index an implementing agent reads first — reading order, token tables, component and screen lists |
| `tokens.json` | Colors, text colors, borders, type, radii, spacing, shadows. Near-identical colors are merged; each kind is capped; the rest is `offToken` with its `nearest` token |
| `components/*.md` | Per definition: property table, variants, per-variant structure, usage, renders. Copies of one component on several pages fold into one |
| `components/candidates/*.md` | **Structures that repeat in three or more distinct screens but were never made a Figma component** — they become components in code |
| `screens/<page>/*.md` | Per screen: preview, sibling states, prototype flow, node tree (positions, layout, tokens, instance links) |
| `flows/<page>.md` | Flow diagrams drawn on the page (shapes and connectors) — Mermaid with branch labels, plus planning notes that point at screen elements |
| `manifest.json` | Machine index of all of the above |
| `assets/{screens,components,images,icons}/` | PNG and SVG |

## 4. Naming — the only judgment the model makes in this skill

Figma names are often unusable as code names: `Component 11`, `Property 1=…`, two sets with the same name.
`check` lists what needs a name. **Read the preview PNGs** when the structure and copy are not enough, and write `<bundle>/aliases.json`:

```json
{
  "components": { "4:941": { "name": "MissionCard", "purpose": "Today's mission card on Home — done/not done" } },
  "candidates": { "3k9x2a1b": { "name": "SocialLoginButton", "purpose": "Social sign-in button on the login screen" },
                  "7fq0c2dd": { "reject": "Just a title + subtitle arrangement — compose it in layout" } },
  "tokens": { "color": { "#F27321": "brand/primary" }, "font": { "Poppins|700|30": "display/lg" }, "radius": { "5": "sm" } },
  "images": { "81f18cc0…": "hani-meadow-background" },
  "pages": { "8:880": "auth" }
}
```

- Name components as code components (PascalCase) by **role**, not looks (`OrangeButton` ✗ `PrimaryButton` ○). The key is the id `check` printed
- Adopt a candidate when it is one role; reject it with a reason when the shapes merely coincide, when it is another width of an adopted candidate,
  or when it is a mock of something the platform draws (OS status bar, a third-party sign-in sheet)
- Name tokens by role too (`text/muted`, `surface/base`). Never give one name to two values

## 5. build → check loop

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/figma_bundle.py build --out <bundle> && python3 ${CLAUDE_SKILL_DIR}/scripts/figma_bundle.py check --out <bundle>
```

Repeat 4→5 until exit 0. Fix naming defects only through aliases; fix render and image defects by collecting again.
**Stop when the defect count does not drop from the previous round** and report what remains (the same input gives the same result).

| Defect code | Fix in |
| --- | --- |
| `COMP-NAME` · `COMP-DUP` · `CAND-UNDECIDED` · `TOKEN-NAME` · `TOKEN-DUP` | `aliases.json` |
| `SCREEN-PREVIEW` · `COMP-PREVIEW` · `IMG-MISSING` | Collect again with `--resume` (see `raw/fetch-report.json`) |

## 6. Report

Give the bundle path, size (pages, screens, components, adopted candidates, images, Iconify icons, flow diagrams), fidelity (full/summary),
token coverage per kind (low coverage means the file was drawn without tokens — say so), remaining warnings, and **one line telling the
implementer to start from `<bundle>/README.md`**. If `dev/docs/design/*/MASTER.md` already exists, say its values may differ from Figma —
`tokens.json` from Figma wins, and which side to change is the user's call. The bundle is large (original images); if it will be committed, say so.

## Self-check

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/figma_bundle.py --self-test
```
