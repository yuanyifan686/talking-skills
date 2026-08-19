# AI Short Video Skill Library

This repository is an Agent-Agnostic skill system. Core business behavior lives once under `skills/`; runtime-specific compatibility belongs under `adapters/`, and deterministic orchestration lives under `runtime/`.

```text
Agent → Adapter → Runtime → Skill → Tools / Scripts → Output
```

## Quick start

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m runtime.cli discover
python tests/run_all.py
```

Copy `config/env.example` to a local `.env` or export the values through your environment. Never commit real API keys.

## Core packages

- `skills/viral-script`: interactive title, style, script, analysis, and template workflow.
- `skills/score-viral-script`: evidence-backed 100-point script scoring and deterministic quality gate.
- `skills/optimize-viral-script`: score-driven surgical optimization or rewrite with exact before/after evidence and rescore handoff.
- `skills/question-hook`: question hook, provider-neutral TTS, and video composition.
- `skills/person-intro`: concise identity-card planning and rendering.
- `schemas/`: universal invocation, response, context, and media contracts.
- `shared/`: capability detection, protocol utilities, TTS providers, and media helpers.
- `adapters/`: thin runtime mappings with no business logic.
- `runtime/`: executable registry, provider ports, HTTP/CLI entrypoints, and declarative Pipeline runner.

## Universal invocation

```yaml
skill: viral-script
action: generate
input:
  topic: AI创业
  duration: 30
  platform: douyin
```

Every response contains `status`, `state`, `message`, `data`, `files`, `next_step`, `next_actions`, and `errors`. `next_step` is the human-readable handoff that must be shown in the final reply; `next_actions` remains the machine-readable continuation contract. Carry `context` between Agents so pipelines do not depend on conversation memory.

For every standalone Skill, the final reply should end with a clear next-step prompt:

```text
结果：已完成评分，当前总分 76/100。
下一步：调用 optimize-viral-script，针对最低分维度进行优化。
```

If a Skill is partial or blocked, the prompt must explain what to fix:

```text
结果：已生成问题钩子，但没有执行 TTS。
下一步：配置本地 CosyVoice 或云端 TTS Provider 后重试。
```

Use `action: run_pipeline` when a stateless client explicitly wants automatic title, structure, and style selection plus a completed script. The original `generate → continue` state machine remains available for interactive Agents.

## Executable Runtime

The default LLM adapter is Volcengine Ark, selected behind the provider-neutral `LLMProvider` interface. Configure `VOLCENGINE_API_KEY` and `VOLCENGINE_ENDPOINT_ID` (or their `ARK_*` aliases) through environment variables.

```text
python -m runtime.server --host 127.0.0.1 --port 8765
python -m runtime.cli discover
python -m runtime.cli invoke examples/generate-viral-script.yaml
python -m runtime.cli pipeline examples/pipeline-context.yaml --id short-video
```

HTTP endpoints:

- `GET /health`
- `GET /skills`
- `GET /catalog/viral-script`
- `POST /invoke`
- `POST /pipelines/short-video`

The default short-video Pipeline executes script generation, scoring, conditional optimization, rescoring, question-hook generation, and optional person-intro handoff. Missing media inputs degrade to structured text output instead of breaking the text pipeline.

## Generic adapter

```text
python adapters/generic/adapter.py discover
python adapters/generic/adapter.py prepare invocation.yaml
python adapters/generic/adapter.py validate-response response.json
```

Run all checks with `python tests/run_all.py`. Rendering tests skip automatically when FFmpeg or a suitable CJK font is unavailable.

TTS defaults to the provider-neutral `auto` route: local CosyVoice, ByteDance Seed Audio 1.0, then legacy Volcengine TTS. Local `.env` files at the project root or `talking-skills/.env` are loaded automatically by the Runtime and web launcher. Configure `BYTEDANCE_SEED_AUDIO_API_KEY` there using a newly generated key; never place API keys in Skill files, source code, or committed history.

Python helpers use the small dependency set in `requirements.txt`. Core text-only execution remains possible without installing or invoking these helpers.

## End-to-end workflow

The library supports both an interactive workflow and a stateless automatic workflow.

### Interactive mode

Use this mode when a human should select the title and delivery style:

```text
topic
  ↓
title_generation → title_selection
  ↓
style_selection
  ↓
script_generation
  ↓
completed
```

The `viral-script` Skill does not ask for a topic that is already present, does not generate a full script before title selection, and returns the current `state` plus portable `context` after every step. This allows one Agent to pause and another Agent to continue.

### Automatic mode

Use `action: run_pipeline` when the caller explicitly authorizes automatic choices:

```text
topic
  ↓
viral-script: choose title + template + style
  ↓
score-viral-script: score 10 dimensions
  ↓
optimize-viral-script: repair weak dimensions
  ↓
score-viral-script: rescore
  ↓
question-hook: create a question opening
  ↓
person-intro: optionally create a person card
  ↓
structured output / media handoff
```

The current default pipeline performs one bounded optimization and one rescore. A score below 80 is retained in the context as a quality signal; callers can run another bounded iteration without losing the previous version.

## Person card: user assets plus Agent design

`person-intro` accepts user-provided identity data and optional local media assets. The Agent selects no more than four useful lines, chooses a preset style, resolves the text position, and returns a render specification.

```yaml
skill: person-intro
action: render
input:
  person:
    name: 袁艺凡
    title: FDE 前沿部署工程师
    organization: 示例机构
    education:
      - 维多利亚大学计算机系
    assets:
      avatar: /absolute/path/avatar.png
      logos:
        - /absolute/path/logo.png
      background: /absolute/path/brand-background.jpg
      font: /absolute/path/brand-font.ttf
  source_video: /absolute/path/talking-head.mp4
  style: technology
  position: auto
  person_position: right
  duration: 4
```

Asset behavior is deliberately explicit:

- The user supplies the identity claims and local asset paths.
- The Agent designs the copy selection, visual preset, position, and animation parameters.
- The renderer verifies every asset path before invoking FFmpeg.
- A supplied avatar, logo, background, and font can be composited into the card.
- If FFmpeg or an asset is unavailable, the Skill degrades to a validated text/render plan instead of claiming a finished video.

## Iteration and learning roadmap

The current system already supports controlled iteration:

```text
original_script
  ↓ scorecard
weak_dimensions
  ↓ targeted optimization
optimized_script
  ↓ same scorecard
rescore
  ↓ keep the better version in context
```

The next level is a data-driven content loop, which should be added without putting business logic into any Agent adapter:

```text
generated variants
  ↓
published video/article metrics
  ↓
likes / comments / completion / saves / shares
  ↓
dimension and template analysis
  ↓
versioned template weights
  ↓
next generation
```

Recommended extension order:

1. Add `experiments/` records containing topic, template, style, scorecard, version, and platform.
2. Add a `feedback` schema for platform metrics and manually tagged comments.
3. Store immutable script versions instead of overwriting the previous draft.
4. Compare variants against the same scoring card before publishing.
5. Update template recommendations only after enough real-world samples; never let one viral result rewrite the library.
6. Add a platform publishing Skill that stops at draft review and keeps publication separate from content generation.

This separation keeps the architecture portable:

```text
Agent = intent and decision
Adapter = compatibility
Skill = reusable capability
Runtime = orchestration
Template = versioned knowledge
Metrics = feedback
```

## Quality gates

Before a script is handed to a media or publishing Skill, validate:

- duration and estimated character count;
- scorecard arithmetic and evidence quotes;
- factual claims and supplied identity information;
- optimized-script before/after evidence;
- asset paths and output file existence;
- execution mode: `full`, `partial`, or `text_only`.

Run the regression suite with:

```text
python tests/run_all.py
```
