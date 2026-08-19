# AI 短视频 Skill 合集

这是一套与 Agent 无关、可迁移、可组合的 AI 短视频内容 Skill 系统。

它可以被 Codex、Claude、WorkBuddy、自研 Agent 或其他 Agent Runtime 调用，完成：

- 口播主题和标题生成
- 口播文案创作
- 爆款文案评分
- 根据评分结果定向优化
- 问题型开场生成
- TTS 音频生成
- 人物卡设计与渲染
- 文案、音频、视频之间的 Pipeline 编排

## 先看流程

### 最简单的使用流程

```text
输入一个主题
    ↓
viral-script：生成标题和口播文案
    ↓
score-viral-script：按照评分卡打分
    ↓
optimize-viral-script：针对低分项优化
    ↓
score-viral-script：重新评分
    ↓
得到可直接使用的口播文案
```

### 完整的短视频流程

```text
主题
  ↓
生成标题
  ↓
选择标题和口播风格
  ↓
生成口播文案
  ↓
评分
  ↓
根据最低分维度优化
  ↓
重新评分
  ↓
生成问题型开场
  ↓
生成 TTS 音频
  ↓
生成或上传人物卡
  ↓
交给视频剪辑或合成工具
  ↓
输出结构化内容或完整视频
```

### 三个核心 Skill 如何配合

```text
viral-script
    负责“写出来”
        ↓
score-viral-script
    负责“判断哪里不好”
        ↓
optimize-viral-script
    负责“针对问题改好”
        ↓
question-hook / person-intro
    负责“包装成视频内容”
```

如果只想生成文案，调用 `viral-script`。

如果已经有文案，想知道好不好，调用 `score-viral-script`。

如果已经评分，想按照评分卡优化，调用 `optimize-viral-script`。

## 目录结构

```text
talking-skills/
├── skills/                    # 核心能力，每个 Skill 可独立调用
│   ├── viral-script/           # 口播文案创作
│   ├── score-viral-script/     # 口播文案评分
│   ├── optimize-viral-script/ # 评分驱动的文案优化
│   ├── question-hook/          # 问题型开场、TTS 和视频合成
│   └── person-intro/           # 人物卡规划和渲染
├── adapters/                  # Agent 适配层，不包含业务逻辑
├── runtime/                   # Skill 注册、调用、HTTP 和 CLI 运行时
├── schemas/                   # 统一输入、输出和上下文协议
├── shared/                    # TTS、媒体、配置和通用工具
├── config/                    # 默认配置和环境变量示例
├── examples/                  # 可直接参考的调用示例
├── tests/                     # 全量测试
└── output/                    # 默认输出目录
```

核心原则是：

```text
Agent ≠ Skill

Agent       = 理解意图、做选择、调用能力
Adapter     = 适配不同 Agent 的调用方式
Skill       = 可复用的业务能力
Runtime     = 注册和编排 Skill
Template    = 可版本化的知识和经验
Script      = 确定性的执行逻辑
Tool        = FFmpeg、TTS、文件系统等工具
```

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

### 2. 检查 Skill 是否可用

```bash
python -m runtime.cli discover
```

### 3. 运行全部测试

```bash
python tests/run_all.py
```

### 4. 启动本地运行服务

```bash
python -m runtime.server --host 127.0.0.1 --port 8765
```

服务启动后提供：

```text
GET  /health
GET  /skills
GET  /catalog/viral-script
POST /invoke
POST /pipelines/short-video
```

## 统一调用方式

所有 Skill 都使用统一的调用结构：

```yaml
skill: viral-script
action: generate
input:
  topic: AI创业
  duration: 30
  platform: douyin
  audience: 普通职场人
  style: 自然聊天型
```

统一返回结构：

```yaml
status: awaiting_user
state: title_selection
message: 已生成 6 个标题，请选择一个。
data:
  titles: []
files: []
next_step: 请选择标题后继续生成正文。
next_actions:
  - continue_with_selected_title
errors: []
```

字段说明：

- `status`：执行状态，例如 `success`、`awaiting_user`、`partial`、`error`。
- `state`：当前流程状态，例如 `title_selection`、`script_generation`、`completed`。
- `data`：当前 Skill 生成的数据。
- `files`：生成的音频、视频或其他文件。
- `next_step`：给用户看的下一步提示。
- `next_actions`：给 Agent 或程序继续调用的动作。
- `errors`：错误和缺失能力说明。

每个 Skill 的最终回复都必须告诉用户下一步做什么：

```text
结果：评分完成，当前总分 76/100。
下一步：调用 optimize-viral-script，针对最低分维度进行优化。
```

如果只是部分完成，也要说明如何继续：

```text
结果：问题型开场已生成，但没有执行 TTS。
下一步：配置本地 CosyVoice 或云端 TTS Provider 后重试。
```

## Skill 说明

### 1. viral-script：口播文案创作

用于从主题生成标题、选择标题、选择风格、生成口播文案，也支持分析已有文案和提取模板。

默认工作流：

```text
topic
  ↓
title_generation
  ↓
title_selection
  ↓
style_selection
  ↓
script_generation
  ↓
completed
```

特点：

- 已经提供主题时不重复询问主题。
- 默认先生成 6 个标题，不直接生成长正文。
- 等待用户选择标题后，再生成完整文案。
- 支持反常识、认知冲突、利益冲突、身份冲突、趋势判断、强问题和结果悬念等标题方向。
- 支持犀利观点型、反常识型、故事冲突型、知识拆解型、情绪共鸣型、商业洞察型和自然聊天型等风格。
- 支持 15 秒、30 秒、45 秒、60 秒、90 秒和自定义时长。

调用示例：

```yaml
skill: viral-script
action: generate
input:
  topic: 普通人如何在 AI 时代立足
  duration: 60
  platform: douyin
```

### 2. score-viral-script：口播文案评分

用于判断一篇口播文案是否具备传播潜力和落地价值。

评分结构：

```text
核心维度：40 分
  打断预测、奖励期待、损失厌恶、精准命名

落地性：30 分
  可复制性、无废话程度、AI 适配性

加分项：30 分
  情绪强度、记忆点、传播性

总分：100 分
```

每个维度都必须包含：

- 分数
- 评分标准
- 原文证据链
- 具体问题
- 可执行建议

结论规则：

```text
80 分以上：爆款潜力较高，可直接复用
60-79 分：有潜力，需要优化 1-2 个维度
60 分以下：需要重新设计结构或重写
```

### 3. optimize-viral-script：评分驱动的文案优化

用于根据评分结果进行局部修复，而不是没有目标地整体重写。

优化逻辑：

```text
原始文案
  ↓
读取评分卡
  ↓
找到最低分维度
  ↓
定位对应原句
  ↓
局部优化或结构重写
  ↓
保留原意和事实边界
  ↓
输出优化前后证据
  ↓
交给 score-viral-script 重新评分
```

优化时重点检查：

- 开头是否有刺激和预测打断。
- 观众能否明确知道看完得到什么。
- 是否让观众意识到不看会错过什么。
- 抽象观点是否转换成具体案例。
- 是否有可以直接复制的公式、步骤或答案。
- 是否删除了重复、空泛和无法口播的句子。
- 是否提炼出可记忆、可转发的金句。

### 4. question-hook：问题型开场

用于从正文生成 8-25 个汉字的问题型开场，也支持 TTS 和视频合成。

支持的开场方向：

- 为什么型
- 反差型
- 利益型
- 趋势型
- 身份型
- 二选一
- 结果悬念型
- 认知挑战型

返回示例：

```yaml
hook:
  text: 为什么现在 AI 工具越来越多，却越来越没用？
  type: cognitive_conflict
  estimated_duration: 2.6
  relation_to_script: direct
```

如果有完整运行环境，可以继续执行：

```text
问题开场
  ↓
TTS 音频
  ↓
开场片段
  ↓
原始视频
  ↓
最终视频
```

如果没有 TTS Key 或 FFmpeg，Skill 至少返回问题文本、TTS 参数和视频合成方案。

### 5. person-intro：人物卡

用于在视频开头生成 4 秒左右的人物介绍卡。

支持两种方式：

1. 用户上传头像、Logo、背景和字体，Agent 负责排版和动画设计。
2. 用户只提供人物信息，Agent 生成文字布局和视觉方案。

示例：

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

人物卡不会展示完整简历，默认只选择：

```text
姓名
+
核心职位
+
1-2 个背景标签
```

如果没有 FFmpeg 或素材文件，Skill 会返回可执行的文字和视觉渲染方案，不会假装已经生成视频。

## TTS 和媒体能力

TTS 采用 Provider 接口，不把 Skill 绑定到某一个服务商：

```text
shared/tts/
├── base.py
├── cosyvoice.py
├── volcengine.py
├── seed_audio.py
├── openai.py
└── local.py
```

默认路由：

```text
本地 CosyVoice
    ↓ 不可用时
字节跳动 Seed Audio 1.0
    ↓ 不可用时
旧版火山引擎 TTS
```

把 `config/env.example` 复制为本地 `.env`，通过环境变量配置：

```text
VOLCENGINE_API_KEY=
VOLCENGINE_ENDPOINT_ID=
BYTEDANCE_SEED_AUDIO_API_KEY=
```

真实 Key 只能放在本地 `.env` 或系统环境变量中，不能写入 Skill、Python、YAML 或 Git 历史。

## Agent 适配层

适配层只做调用格式转换，不复制业务逻辑：

```text
Agent
  ↓
Adapter
  ↓
统一 Skill Invocation Protocol
  ↓
Skill
```

当前提供：

```text
adapters/codex/
adapters/claude/
adapters/workbuddy/
adapters/generic/
```

通用适配器示例：

```text
python adapters/generic/adapter.py discover
python adapters/generic/adapter.py prepare invocation.yaml
python adapters/generic/adapter.py validate-response response.json
```

## 执行模式和降级策略

运行前可以检测以下能力：

```text
LLM
Filesystem
Python
Shell
FFmpeg
Network
Secrets
Image Processing
Video Processing
```

根据能力选择三种模式：

### full

具备文件读写、Python、FFmpeg、网络和 API 能力，可以生成完整成品。

### partial

例如有 Python，但没有 TTS Key。可以完成文案、评分、问题钩子和视频处理方案，并明确 `TTS not executed`。

### text_only

没有执行环境时，仍然输出文案、评分、问题钩子、人物介绍和结构化配置，方便另一个 Agent 接手。

## 可控迭代和未来扩展

当前已经支持一轮“评分—优化—复评”：

```text
原始文案
  ↓ 评分卡
低分维度
  ↓ 定向优化
优化文案
  ↓ 同一评分卡
重新评分
  ↓
保留更好的版本
```

未来可以加入真实数据闭环：

```text
生成多个版本
  ↓
发布视频或文章
  ↓
记录点赞、评论、完播、收藏、转发
  ↓
分析评分维度和模板表现
  ↓
更新版本化模板权重
  ↓
生成下一轮内容
```

推荐扩展顺序：

1. 增加 `experiments/`，记录主题、模板、风格、评分、版本和平台。
2. 增加 `feedback` Schema，记录平台数据和人工标注评论。
3. 保存不可变的文案版本，不覆盖历史稿件。
4. 发布前使用同一评分卡比较多个版本。
5. 积累足够真实样本后再更新模板推荐，不能让单个爆款结果改写模板库。
6. 增加字幕、BGM、封面、自动剪辑、发布等独立 Skill。

## 质量门禁

把文案交给视频或发布 Skill 前，至少检查：

- 时长和预估字数是否匹配。
- 评分卡加分是否正确。
- 每个评分是否有原文证据。
- 事实性陈述是否有来源或明确标注。
- 优化前后是否保留对比证据。
- 人物信息是否来自用户提供的资料。
- 素材路径和输出文件是否存在。
- 当前执行模式是 `full`、`partial` 还是 `text_only`。

运行回归测试：

```bash
python tests/run_all.py
```

## 许可证

MIT 开源许可证，详见 [`LICENSE`](LICENSE)。
