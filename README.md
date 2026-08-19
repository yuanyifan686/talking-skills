# AI Short Video Skill Library / AI 短视频 Skill 合集

This repository is an Agent-Agnostic skill system for creating, evaluating, optimizing, and packaging short-form talking-head content. Core business behavior lives once under `skills/`; runtime-specific compatibility belongs under `adapters/`; deterministic orchestration lives under `runtime/`.

这是一个与 Agent 无关的 AI 短视频 Skill 系统，用于创作、评分、优化和包装口播内容。核心业务逻辑只保留在 `skills/` 中；不同运行环境的兼容逻辑放在 `adapters/`；确定性的编排逻辑放在 `runtime/`。

```text
Agent → Adapter → Runtime → Skill → Tools / Scripts → Output
智能体 → 适配器 → 运行时 → Skill → 工具 / 脚本 → 输出
```

## What is included / 当前包含能力

- `skills/viral-script`: interactive title, style, script, analysis, and template workflow.
  `viral-script`：交互式标题、风格、文案、分析和模板工作流。
- `skills/score-viral-script`: evidence-backed 100-point script scoring and deterministic quality gate.
  `score-viral-script`：基于原文证据链的 100 分口播文案评分和质量门禁。
- `skills/optimize-viral-script`: score-driven targeted optimization or rewrite with before/after evidence and rescore handoff.
  `optimize-viral-script`：根据评分结果局部优化或重写，并保留前后对比证据和复评流程。
- `skills/question-hook`: question hook, provider-neutral TTS, and video composition.
  `question-hook`：问题型开场、与供应商无关的 TTS 接口和视频合成。
- `skills/person-intro`: concise identity-card planning and rendering.
  `person-intro`：人物卡内容规划和渲染，支持用户素材与 Agent 设计。
- `schemas/`: universal invocation, response, context, and media contracts.
  `schemas/`：统一调用、响应、上下文和媒体协议。
- `shared/`: capability detection, protocol utilities, TTS providers, and media helpers.
  `shared/`：能力检测、协议工具、TTS Provider 和媒体工具。
- `adapters/`: thin runtime mappings with no business logic.
  `adapters/`：不包含业务逻辑的轻量运行时适配层。
- `runtime/`: executable registry, provider ports, HTTP/CLI entrypoints, and declarative pipeline runner.
  `runtime/`：可执行注册表、Provider 接口、HTTP/CLI 入口和声明式 Pipeline 运行器。

## Quick start / 快速开始

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m runtime.cli discover
python tests/run_all.py
```

Copy `config/env.example` to a local `.env`, or export the values through your environment. Never commit real API keys.

将 `config/env.example` 复制为本地 `.env`，或者通过环境变量配置。不要提交真实 API Key。

## Universal invocation / 统一调用协议

```yaml
skill: viral-script
action: generate
input:
  topic: AI创业
  duration: 30
  platform: douyin
```

Every response contains `status`, `state`, `message`, `data`, `files`, `next_step`, `next_actions`, and `errors`. `next_step` is the human-readable handoff shown in the final reply; `next_actions` is the machine-readable continuation contract. Carry `context` between Agents so a pipeline does not depend on conversation memory.

每次响应都包含 `status`、`state`、`message`、`data`、`files`、`next_step`、`next_actions` 和 `errors`。其中 `next_step` 用于最终回复中的人类可读交接提示，`next_actions` 用于机器继续调用。通过传递 `context`，不同 Agent 可以接力执行，而不依赖某个对话窗口的记忆。

Every standalone Skill must end its user-facing reply with a clear next-step prompt:

每个独立 Skill 在最终回复时都必须给出明确的下一步提示：

```text
Result: scoring completed, current score 76/100.
Next step: call optimize-viral-script to repair the lowest-scoring dimensions.

结果：评分完成，当前总分 76/100。
下一步：调用 optimize-viral-script，针对最低分维度进行优化。
```

If execution is partial or blocked, explain what needs to be fixed:

如果执行结果是部分完成或被阻塞，必须说明需要修复的条件：

```text
Result: the question hook was generated, but TTS was not executed.
Next step: configure local CosyVoice or a cloud TTS Provider and retry.

结果：问题钩子已生成，但没有执行 TTS。
下一步：配置本地 CosyVoice 或云端 TTS Provider 后重试。
```

Use `action: run_pipeline` when a stateless client explicitly authorizes automatic title, structure, style selection, and completed script generation. The original `generate → continue` state machine remains available for interactive Agents.

当无状态客户端明确允许自动选择标题、结构和风格并直接生成完整文案时，使用 `action: run_pipeline`。交互式 Agent 仍然可以使用原有的 `generate → continue` 状态机。

## Executable runtime / 可执行运行时

The default LLM adapter is Volcengine Ark, selected behind the provider-neutral `LLMProvider` interface. Configure `VOLCENGINE_API_KEY` and `VOLCENGINE_ENDPOINT_ID` or their `ARK_*` aliases through environment variables.

默认 LLM 适配器是火山引擎 Ark，但它被封装在与供应商无关的 `LLMProvider` 接口之后。请通过环境变量配置 `VOLCENGINE_API_KEY`、`VOLCENGINE_ENDPOINT_ID` 或对应的 `ARK_*` 别名。

```text
python -m runtime.server --host 127.0.0.1 --port 8765
python -m runtime.cli discover
python -m runtime.cli invoke examples/generate-viral-script.yaml
python -m runtime.cli pipeline examples/pipeline-context.yaml --id short-video
```

HTTP endpoints / HTTP 接口：

- `GET /health`
- `GET /skills`
- `GET /catalog/viral-script`
- `POST /invoke`
- `POST /pipelines/short-video`

The default short-video Pipeline performs script generation, scoring, conditional optimization, rescoring, question-hook generation, and optional person-intro handoff. Missing media inputs degrade to structured text output instead of breaking the text pipeline.

默认短视频 Pipeline 会执行文案生成、评分、条件优化、复评、问题型开场生成和可选的人物卡交接。缺少媒体输入时，会降级为结构化文本输出，不会让文本流程整体失败。

## Generic adapter / 通用适配器

```text
python adapters/generic/adapter.py discover
python adapters/generic/adapter.py prepare invocation.yaml
python adapters/generic/adapter.py validate-response response.json
```

Run all checks with `python tests/run_all.py`. Rendering tests skip automatically when FFmpeg or a suitable CJK font is unavailable.

使用 `python tests/run_all.py` 运行全部检查。如果环境没有 FFmpeg 或合适的中文字体，渲染测试会自动跳过。

TTS defaults to the provider-neutral `auto` route: local CosyVoice, ByteDance Seed Audio 1.0, then legacy Volcengine TTS. Local `.env` files at the project root or `talking-skills/.env` are loaded automatically by the Runtime and web launcher. Configure `BYTEDANCE_SEED_AUDIO_API_KEY` with a newly generated key; never place API keys in Skill files, source code, or committed history.

TTS 默认使用与供应商无关的 `auto` 路由：本地 CosyVoice、字节跳动 Seed Audio 1.0，最后回退到旧版火山引擎 TTS。Runtime 和网页启动器会自动加载项目根目录或 `talking-skills/.env`。请使用新生成的 Key 配置 `BYTEDANCE_SEED_AUDIO_API_KEY`，绝不要把 API Key 写入 Skill 文件、源代码或 Git 历史。

## End-to-end workflow / 端到端流程

The library supports both an interactive workflow and a stateless automatic workflow.

本合集同时支持交互式工作流和无状态自动工作流。

### Interactive mode / 交互模式

Use this mode when a human should select the title and delivery style.

当需要用户选择标题和口播风格时，使用交互模式。

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

The `viral-script` Skill does not ask for a topic that is already present, does not generate a full script before title selection, and returns the current `state` plus portable `context` after every step. One Agent can pause and another Agent can continue.

`viral-script` 不会重复询问已经提供的主题，也不会在用户选择标题前提前生成完整正文。每一步都会返回当前 `state` 和可迁移的 `context`，因此可以由一个 Agent 暂停、另一个 Agent 继续。

### Automatic mode / 自动模式

Use `action: run_pipeline` when the caller explicitly authorizes automatic choices.

当调用方明确允许自动选择时，使用 `action: run_pipeline`。

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

The default Pipeline performs one bounded optimization and one rescore. A score below 80 remains in the context as a quality signal; callers can run another bounded iteration without losing the previous version.

默认 Pipeline 会执行一次有边界的优化和一次复评。低于 80 分的结果会作为质量信号保留在上下文中；调用方可以继续迭代，同时保留历史版本。

## Person card: user assets plus Agent design / 人物卡：用户素材与 Agent 设计

`person-intro` accepts user-provided identity data and optional local media assets. The Agent selects no more than four useful lines, chooses a preset style, resolves the text position, and returns a render specification.

`person-intro` 接收用户提供的人物信息和可选的本地素材。Agent 最多选择四行有效信息，选择预设风格，确定文字位置，并返回可执行的渲染规格。

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

Asset behavior is explicit / 素材行为保持明确：

- The user supplies identity claims and local asset paths. / 用户提供人物信息和本地素材路径。
- The Agent designs copy selection, visual preset, position, and animation parameters. / Agent 负责设计文字选择、视觉预设、位置和动画参数。
- The renderer verifies every asset path before invoking FFmpeg. / 渲染器调用 FFmpeg 前会验证所有素材路径。
- Avatar, logo, background, and font can be composited into the card. / 头像、Logo、背景和字体都可以合成到人物卡中。
- If FFmpeg or an asset is unavailable, the Skill returns a validated render plan instead of claiming a finished video. / 如果 FFmpeg 或素材不可用，Skill 会返回经过验证的渲染方案，而不会虚报已生成成片。

## Iteration and learning roadmap / 迭代与学习路线

The current system supports controlled iteration:

当前系统已经支持可控迭代：

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

The next level is a data-driven content loop. It should be added without putting business logic into any Agent adapter.

下一阶段是数据驱动的内容闭环，但不应把业务逻辑写进任何 Agent Adapter：

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

Recommended extension order / 推荐扩展顺序：

1. Add `experiments/` records containing topic, template, style, scorecard, version, and platform. / 增加 `experiments/`，记录主题、模板、风格、评分卡、版本和平台。
2. Add a `feedback` schema for platform metrics and manually tagged comments. / 增加 `feedback` Schema，记录平台数据和人工标注评论。
3. Store immutable script versions instead of overwriting previous drafts. / 保存不可变的文案版本，不覆盖旧稿。
4. Compare variants against the same scoring card before publishing. / 发布前使用同一评分卡比较多个版本。
5. Update template recommendations only after enough real-world samples; never let one viral result rewrite the library. / 积累足够真实样本后再更新模板推荐，不让单个爆款结果改写模板库。
6. Add a platform publishing Skill that stops at draft review and keeps publication separate from content generation. / 增加发布 Skill，但停在草稿审核阶段，让发布与内容生成保持解耦。

This separation keeps the architecture portable:

这种分层可以保持架构可迁移：

```text
Agent = intent and decision       / Agent = 意图理解与决策
Adapter = compatibility            / Adapter = 兼容层
Skill = reusable capability       / Skill = 可复用能力
Runtime = orchestration            / Runtime = 运行编排
Template = versioned knowledge     / Template = 版本化知识
Metrics = feedback                 / Metrics = 反馈数据
```

## Quality gates / 质量门禁

Before a script is handed to a media or publishing Skill, validate:

在把文案交给媒体或发布 Skill 之前，必须检查：

- duration and estimated character count; / 时长和预估字数；
- scorecard arithmetic and evidence quotes; / 评分卡计算和证据引用；
- factual claims and supplied identity information; / 事实性陈述和人物信息；
- optimized-script before/after evidence; / 优化前后的证据链；
- asset paths and output file existence; / 素材路径和输出文件是否存在；
- execution mode: `full`, `partial`, or `text_only`. / 执行模式：`full`、`partial` 或 `text_only`。

Run the regression suite / 运行回归测试：

```text
python tests/run_all.py
```

## License / 许可证

MIT. See [`LICENSE`](LICENSE).

MIT 开源许可证，详见 [`LICENSE`](LICENSE)。
