---
name: person-intro
description: Select concise on-screen identity information and optionally render a short person introduction card or video segment. Use when a talking-head video needs a 4-second name, role, organization, and one or two background labels with configurable position, animation, and style.
---

# Person Intro

## Purpose

Create a concise on-screen person introduction rather than a résumé dump, then optionally render it as a reusable video intro asset.

## When to Use

Use for person-card content selection, intro layout planning, render parameters, or FFmpeg rendering before a talking-head video.

## When NOT to Use

Do not invent credentials, verify a person’s claims, create a full biography, synthesize speech, or publish media. Use only supplied or previously verified identity data.

## Inputs

- `action`: `generate`, `render`, or `run_pipeline`.
- `input.person.name`.
- At least one of `title`, `organization`, `roles`, `education`, `experience`, or `tagline`.

## Optional Inputs

- `duration`: default `4` seconds.
- `position`: `left`, `right`, `bottom_left`, `bottom_right`, or `auto`.
- `person_position` when `position: auto` lacks visual detection.
- `animation`, `style`, `logo`, `avatar`, `logo_file`, `background_image`, dimensions, font, background, and output path.
- `input.person.assets.avatar`, `input.person.assets.logos`, `input.person.assets.background`, and `input.person.assets.font` for user-provided media assets.
- Portable `context` conforming to `../../schemas/context.schema.json`.

## Workflow

1. Validate person data against `../../schemas/person.schema.json` when possible.
2. Detect filesystem, Python, FFmpeg, image, and video capabilities; choose `full`, `partial`, or `text_only`.
3. Read `references/intro_styles.yaml` and resolve the selected style, including its visual palette.
4. Select only the name, core role, and one or two strongest supplied background labels. Do not display every field.
5. Resolve position. For `auto`, place text opposite the detected or supplied person position. If neither is available, default to `bottom_left` and mark the decision as a fallback.
6. Resolve user-provided avatar, logo, background, and font paths. Never invent or download identity assets without authorization.
7. Return the selected copy and render specification before rendering.
8. For rendering, call `scripts/render_intro.py`. Without a source video, store the standalone card at `context.project.video.person_intro`. With `source_video`, overlay the card during the first seconds of the question-hook output and store the result at `context.project.video.final`.

## Interaction Rules

- Never ask for optional credentials merely to fill space.
- Ask for `person_position` only when accurate auto placement materially matters and no visual capability exists.
- Keep the default intro to four seconds and four visible lines maximum.
- Treat logos as file references, not verified endorsements. A logo is rendered only when the user supplies a valid local path.
- Agent-designed means choosing from the style presets and generating a layout spec; it does not mean inventing a person’s credentials or brand identity.
- In the final user-facing reply, always tell the user to render, review, export, or fix the missing asset before continuing.

## Outputs

Return the universal envelope with:

```yaml
next_step: 下一步：渲染并检查人物卡，或将它叠加到最终视频。
data:
  person_intro:
    lines: [姓名, 核心职位, 背景标签1, 背景标签2]
    duration: 4
    position: bottom_left
    animation: fade_slide
    style: professional
    logo: true
    assets:
      avatar: /abs/path/avatar.png
      logo: /abs/path/logo.png
      background: /abs/path/background.jpg
  execution_mode: full | partial | text_only
```

Place rendered files in `files` and the portable pipeline context. Preserve `question_intro` and `hooked` when writing `final`.

## Tools

- `scripts/render_intro.py`: emit a render plan or render a video with FFmpeg, including optional avatar/logo/background layers.
- FFprobe: optional validation for rendered duration and streams.

## Files

- Read `references/intro_styles.yaml` for style and line limits.
- Use `assets/` only for user-approved reusable logos, fonts, or brand backgrounds.
- Validate video output with `../../schemas/video.schema.json`.

## Error Handling

- Return selected copy and render options in `text_only` mode when execution tools are absent.
- Return `partial` when content is valid but an asset, font, FFmpeg, or output permission is missing.
- Return a recoverable `missing_asset` error when a supplied avatar, logo, background, or font path does not exist.
- Never claim render success unless the output exists and is non-empty.

## Validation

- Require a non-empty name and at least one supporting identity field.
- Use no more than four visible lines.
- Include no more than two background labels by default.
- Keep default duration at four seconds and reject non-positive durations.
- Confirm every displayed claim came from input data.
- Confirm every rendered asset path exists before invoking FFmpeg.

## Examples

Given a person with several roles and credentials, select: “袁艺凡 / FDE 前沿部署工程师 / 维多利亚大学计算机系 / 加拿大海外6年工作经验”. Do not add unprovided awards or display the full résumé.
