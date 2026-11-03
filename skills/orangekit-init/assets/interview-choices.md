<!-- An asset used only by orangekit-init. Called after the interview protocol in SKILL.md. Read it when building option lists. -->

# Rules shared by every option list — custom · not sure

**Every stack question has two exits** — for the person whose stack is not on the list, and for the person who cannot judge the list.
**The one exception is ⑩** — its 4 option slots are filled by real frameworks, so there is no "Not sure" slot. The parent ⑥
has "Not sure", and at ⑩ writing "recommend" in the custom field takes the same recommendation path.

**Custom** — present the free-input field the tool attaches as "Custom (type it in)".

- If the input matches a pack name or alias, **normalize it to that pack** — "Express" → `node-api`,
  "NestJS" → `node-nest`, "Hono" → `aws-container`, "vanilla JS" → `vanilla`,
  "Expo" → `react-native`, "SwiftUI" → `ios-swift`
- If it does not match, write **`custom`** to `presets.<axis>` and write the entered name as-is into that axis's `framework`
  (· `language`). **Never invent a preset name** — `presets` values are a schema
  enum. An invented name (`expo-universal` and the like) is not found by install-guide and drifts onto the generation path,
  and what the user actually picked disappears from the record
- A `custom` axis gets its empty dimensions (DB · ORM · commands) in the 4th call — the preset fills nothing in

**Not sure** — when this is picked, slot **just one more question into the next call**: "Get a recommendation" / "Decide later".

- **Get a recommendation** — ask at most 2 of the deciding questions below, then give one recommendation with a one-line reason. The
  recommendation is confirmed again in the Step 4.9 confirmation summary. Writing "recommend" in the custom field takes the same path
- **Decide later** — write **`undecided`** to `presets.<axis>`. No guide is built for that axis; it is
  decided later with `/stack-guide-generator`. If the product form itself is left undecided, do not write `deliveryModel` ·
  `clientKind`, and set the screen axes (`frontend` · `app`) to `undecided` — fill in the default `web`
  and browser guidance ships to an app project
- **If ① is "Mobile app", `clientKind` is settled as `app` even when what follows is undecided** — even with the approach, shell and
  framework left as "decide later", write `clientKind: "app"`. Leave it empty and the backend guide
  drifts into the `browser` slots (cookie session · CSRF). How undecided and custom values are recorded is set by the mapping table in Step 2

| Question | Deciding questions (at most 2) | Recommendation |
| --- | --- | --- |
| ① product form | Must it be installed from a store? · Does it lean heavily on camera · location · push? | no to both → web · install needed but web screens are enough → mobile app (hybrid) · device features are the core → mobile app (cross-platform) |
| ⑤ app approach | Do you also ship a web version? · Do you have dedicated developers per platform? | ships web too → hybrid · dedicated per-platform developers and platform-native UX matters → fully native · otherwise → cross-platform |
| ⑤ web framework | Does search visibility (SEO) matter? | yes → `nextjs` · no → `react-vite` |
| ⑨ app shell | Are there screens the web cannot build (high-performance maps · burst capture · background location)? | yes → RN shell + native screens · no → Capacitor |
| ⑨ cross-platform | Does the team use React · TypeScript? | yes → `react-native` · no → `flutter` |
| ② backend type | Is there someone to run servers and a DB? · Are the server rules complex, like payments · settlement · external integrations? | no one to run it → BaaS (`supabase`) · someone, and complex → self-hosted server · already on AWS with spiky traffic → serverless |
| ⑥ self-hosted server language | The team's main language? · Is AI · data processing the core? | the same TS as the web → TypeScript (`fastify`) · AI · data → Python (`fastapi`) · performance and memory come first and someone knows Rust → Rust |
