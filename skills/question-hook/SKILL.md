---
name: question-hook
description: Create a concise Chinese question hook from a script and optionally synthesize its voice, render an intro segment, and prepend it to an original video. Use for question-led openings, TTS handoff, intro planning, or FFmpeg composition with graceful text-only fallback.
---

# Question Hook

## Purpose

Transform a script into a directly related 8–25-character question hook, then optionally produce audio, an intro segment, and a final video without binding the core behavior to one TTS provider.

## When to Use

Use when a script needs a question-led opening or when a pipeline needs hook text, TTS parameters, intro media, or `question intro + original content` composition.

## When NOT to Use

Do not generate a full script, biography card, unrelated clickbait question, or publish a result. Do not invent facts absent from the source script.

## Inputs

- `action`: `generate`, `synthesize`, `compose`, or `run_pipeline`.
- `input.script` for hook generation.
- `input.hook` for synthesis when already generated.
- `input.video.source` for composition.

## Optional Inputs

- `hook_type`, `voice`, `speed`, `tts_provider`, `output_dir`. The default TTS route is `auto`: local CosyVoice first, then ByteDance Seed Audio, then legacy Volcengine TTS.
- `intro.type`: `freeze_frame`, `solid_background`, or `provided_clip`.
- `intro.duration`, `intro.background`, `intro.provided_clip`, `font`, and render dimensions.
- Portable `context` conforming to `../../schemas/context.schema.json`.

## Workflow

1. Detect LLM, filesystem, Python, shell, FFmpeg, network, secrets, image, and video capabilities.
2. Choose `full`, `partial`, or `text_only` execution mode. Never fail solely because rendering is unavailable.
3. Read `references/hook_patterns.yaml` and choose a pattern that exposes the script’s real tension.
4. Generate a natural 8–25-Chinese-character question. Preserve the script’s topic and answer direction.
5. Return hook metadata before tool execution.
6. For synthesis, call `scripts/tts.py`, which delegates to the provider-neutral interface in `../../shared/tts/`. The default route is local CosyVoice, then ByteDance Seed Audio, then legacy Volcengine TTS. Seed Audio receives the complete request text as `text_prompt`, so it can handle plain narration or richer speaker/music/effect directions.
7. For composition, call `scripts/compose_video.py`. Before rendering, automatically normalize, compress, wrap, and fit hook text inside a safe area; reject any layout that still overflows. Normalize intro and source video before concatenation.
8. Update `context.project.hook`, `context.project.video.question_intro`, and `context.project.video.hooked` with generated text, audio, intro, and composed paths. Do not overwrite person-intro artifacts.

## Interaction Rules

- Use supplied script and context without asking for them again.
- Ask only for a missing source video when actual composition was requested.
- Never expose or persist API keys. Read secrets only through environment variables.
- If TTS is unavailable, return TTS parameters and continue with a plan or silent intro when requested.
- In the final user-facing reply, always tell the user whether to synthesize audio, compose the video, or fix the missing media capability.

## Outputs

Return the universal envelope. Hook data must follow:

```yaml
next_step: 下一步：生成问题音频，或将问题开场合成到源视频。
hook:
  text: AI工具用得越多，就真的越厉害吗？
  type: cognitive_conflict
  estimated_duration: 2.6
  relation_to_script: direct
```

Place generated paths in `files` and `context.project.video`. Use `question_intro` for the generated segment and `hooked` for the question-prepended source. List skipped operations in `data.skipped` and explain why.

## Tools

- `scripts/generate_hook.py`: deterministic hook candidate and metadata generator.
- `scripts/tts.py`: provider-neutral TTS command.
- `scripts/compose_video.py`: FFmpeg composition command with plan-only fallback.
- `scripts/hook_layout.py`: safe-area layout, automatic wrapping, font fitting, compression, and overflow validation.

## Files

- Read `references/hook_patterns.yaml` before choosing a hook pattern.
- Use `../../shared/tts/` for provider discovery and synthesis.
- Validate video data against `../../schemas/video.schema.json`.

## Error Handling

- Return `text_only` output when Python or filesystem access is absent.
- Return `partial` when hook text exists but TTS, FFmpeg, video, or credentials are missing.
- Preserve intermediate files and report their paths when a later stage fails.
- Never report a rendered file unless it exists and is non-empty.

## Validation

- Keep hook text between 8 and 25 Chinese characters, excluding punctuation.
- Require a question mark and a direct semantic relationship to the script.
- Reject hooks whose answer cannot be found or reasonably inferred from the source script.
- Keep rendered hook text within the configured maximum width, line count, and safe margins.
- Report any automatic compression and reject rendering when the fitted layout still overflows.
- Check output media existence and use FFprobe when available.

## Examples

For a script beginning “真正会使用AI的人，并不是每天研究几十种AI工具的人”, produce a hook such as “AI工具用得越多，就真的越厉害吗？” and return its type, estimated duration, and direct relation.
