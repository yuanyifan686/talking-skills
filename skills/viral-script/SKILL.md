---
name: viral-script
description: Generate, continue, analyze, and templatize short-form talking-head scripts. Use when an agent needs title ideation, interactive title and style selection, structured spoken-copy generation, script analysis, or explicit template-library updates for short-video content.
---

# Viral Script

## Purpose

Turn a topic into selectable titles and a natural spoken script, or turn an existing script into a reusable template. Keep the workflow portable by exchanging only the universal invocation and response objects defined in `../../schemas/`.

## When to Use

Use for title generation, talking-head script generation, script analysis, structure extraction, template creation, or explicit template saving.

## When NOT to Use

Do not synthesize audio, edit video, render a person card, publish content, or permanently save a template without explicit authorization. Hand those tasks to composable skills through `next_actions`.

## Inputs

- `action`: `generate`, `continue`, `run_pipeline`, `analyze`, `create_template`, or `add_template`.
- `input.topic` for generation, unless recoverable from the current pipeline context.
- `state` and `input.selected_title` when continuing from title selection.
- `input.script` for analysis or template creation.

## Optional Inputs

- `platform`: default `douyin`.
- `duration`: `15`, `30`, `45`, `60`, `90`, or a positive custom number of seconds.
- `audience`, `category`, `style`, `template_id`, `goal`, `question_hook`.
- `context`: portable pipeline context conforming to `../../schemas/context.schema.json`.

## Workflow

1. Validate the invocation against `../../schemas/invocation.schema.json` when schema validation is available.
2. Detect capabilities and set execution mode to `full`, `partial`, or `text_only`. This skill requires only an LLM for full text generation.
3. Recover the topic from `input.topic` or `context.project.topic`. Ask once only when neither is usable.
4. For `generate`, classify the topic dynamically, read `references/copy_templates.yaml`, and generate exactly six distinct titles spanning at least five title types.
5. Return `status: awaiting_user` and `state: title_selection`. Do not generate the full script yet.
6. For `continue` at `title_selection`, resolve `selected_title`. If the user explicitly delegates selection, choose the strongest title and record `selection_source: agent`.
7. If no style is selected, read `references/style_presets.yaml`, present suitable styles, and return `state: style_selection`. If the invocation authorizes agent selection, select and record it.
8. Generate the script using the chosen template and style. Default sequence: hook, conflict, explanation, example or scene, viewpoint upgrade, conclusion, natural ending.
9. Return natural spoken copy without section labels in the script text. Include structured metadata separately.
10. For `analyze`, enter `analysis_mode` and extract title, hook, conflict, emotion, information gap, rhythm, sentence structure, turning point, conclusion, and CTA.
11. For `create_template`, return a candidate template but do not write it.
12. For `add_template`, require explicit save intent, validate the candidate, prevent duplicate IDs, then append it to `references/copy_templates.yaml` using a filesystem-capable adapter or deterministic utility.
13. For `run_pipeline`, treat the invocation as explicit authorization for automatic title, template, and style selection. Generate the requested `variant_count` in one completed response so a stateless Runtime or web client can use the Skill without pausing at interactive states. Keep `generate` and `continue` interactive.

## Interaction Rules

- Never ask for a topic already supplied.
- After generating titles, wait for selection unless the user explicitly says to choose.
- Do not depend on conversation memory. Echo the updated state and pipeline context in every response.
- In the final user-facing reply, always show `next_step` in plain language and keep `next_actions` available for machine execution.
- Read presets from references instead of inventing a fixed closed list.
- Let categories, templates, and styles expand without code changes.

## Writing Rules

- Write short, speakable sentences with rhythm and natural pauses.
- Prefer concrete scenes, tension, information gaps, contrast, and a clear point of view.
- Avoid essay labels, corporate-news language, fake facts, fabricated cases, and unsupported claims.
- Avoid mechanical transitions such as “首先、其次、再次、综上所述” unless logically necessary.
- Match approximate Chinese character targets: 15s `70–110`, 30s `160–240`, 45s `250–340`, 60s `350–480`, 90s `520–700`. For custom duration, estimate at 4.5–6 Chinese characters per second.

## Outputs

Always return these top-level keys:

```yaml
status: success | awaiting_user | partial | error
state: topic | title_generation | title_selection | style_selection | script_generation | analysis_mode | completed
message: concise human-readable status
next_step: concise user-facing handoff, for example "下一步：调用 score-viral-script 的 score。"
data: {}
files: []
next_actions: []
errors: []
```

Completed script data must include `title`, `content`, `style`, `template_id`, `estimated_duration`, `estimated_characters`, and `selection_source`. Preserve compatible fields under `context.project.script`.

## Tools

No tool is mandatory for text generation. Filesystem access is required only for `add_template`. Degrade to returning a validated template candidate when writing is unavailable.

## Files

- Read `references/copy_templates.yaml` when selecting or analyzing structure.
- Read `references/style_presets.yaml` when suggesting or applying style.
- Read `references/delivery_presets.yaml` when generating multiple distinct delivery versions.
- Validate common objects with schemas under `../../schemas/`.

## Error Handling

- Return `awaiting_user` for missing required user decisions.
- Return `partial` with the completed text artifact when persistence is unavailable.
- Never silently change templates, selected titles, factual claims, or user-provided context.

## Validation

- Produce exactly six titles in the title stage.
- Ensure title types are meaningfully varied.
- Ensure generated text is speakable and within the duration band, allowing 15% tolerance.
- Ensure script text contains no workflow labels.
- Ensure analysis cites concrete phrases or structural evidence from the supplied script.
- Validate saved template IDs as lowercase snake case and reject duplicates.

## Examples

Input:

```yaml
skill: viral-script
action: generate
input:
  topic: AI创业
  duration: 30
  platform: douyin
```

First response: `status: awaiting_user`, `state: title_selection`, and six titles. Continue only after a title choice or explicit delegation.
