---
name: optimize-viral-script
description: Rewrite or surgically optimize Chinese talking-head scripts from a score-viral-script scorecard. Use when a script has weak scoring dimensions, needs evidence-linked revisions, must preserve facts and voice, or should enter a bounded score-revise-rescore loop before production.
---

# Optimize Viral Script

## Purpose

Convert a validated viral-script scorecard into a controlled rewrite. Improve selected weak dimensions while preserving the script's factual integrity, central thesis, audience, and natural spoken voice.

## When to Use

Use after `score-viral-script` returns a scorecard, when a user asks to optimize a scored script, or when a pipeline score gate returns `potential` or `insufficient`.

## When NOT to Use

Do not score an unscored script, generate an unrelated script from a topic, verify current facts, or promise views and engagement. Hand scoring to `score-viral-script`, new-script generation to `viral-script`, and fact verification to an available research capability.

## Inputs

- `action`: `optimize`, `rewrite`, or `validate`.
- `input.script`: complete source script, unless available at `context.project.script.content`.
- `input.scorecard`: validated scorecard, unless available at `context.project.script_score`.
- `input.optimization`: required for deterministic `validate`.

## Optional Inputs

- `target_dimensions`: one or more scoring dimension IDs.
- `target_score`: default `8`.
- `variant_count`: `1–3`, default `1`.
- `max_target_dimensions`: default `2` in surgical mode and `4` in rewrite mode.
- `duration`, `audience`, `platform`, `style`, `preserve`, `max_change_ratio`, and portable `context`.

## Workflow

1. Recover the script and scorecard from input or pipeline context. If the script exists but the scorecard does not, return `state: awaiting_score` and hand off to `score-viral-script`; do not guess scores.
2. Require the scorecard's `source_script` to match the source script. Validate the scorecard with the scorer when Python is available.
3. Read `references/optimization_rules.yaml` in full.
4. Select mode. Use `surgical` for totals `60–79`, `rewrite` below `60`, and `polish` at `80+` only when optimization was explicitly requested. Explicit `action: rewrite` always selects `rewrite`.
5. Select targets. Honor explicit `target_dimensions`; otherwise rank dimensions below the target score by lowest score, then core, practicality, and bonus order. Limit targets according to the selected mode.
6. Build a revision brief for every target with an exact source quotation, diagnosis, scorecard improvement, selected technique, and factual guardrail.
7. Rewrite the script. Preserve the thesis, supported facts, intended audience, and recognizable voice. Improve target dimensions without weakening strong dimensions.
8. Keep spoken sentences short and natural. Do not expose workflow labels such as `Hook`, `冲突`, `奖励期待`, or `CTA` inside the final spoken copy.
9. Produce an exact change log. Every target requires at least one `before_quote` found in the source and one `after_quote` found in the optimized script.
10. Run `scripts/validate_optimization.py validate` when Python and filesystem access are available.
11. Pass the optimized script to `score-viral-script`. Do not claim a score increase until the new scorecard exists.
12. Stop after two score-revise cycles by default. Return the best validated version and remaining weaknesses instead of looping indefinitely.

## Interaction Rules

- Do not ask the user to choose dimensions when a valid scorecard already identifies weak dimensions.
- Respect explicit target dimensions, length limits, tone, facts, and required phrases.
- Ask only when a requested revision would materially change the thesis, audience, or factual claim.
- Generate multiple versions only when `variant_count` requests them.
- In the final user-facing reply, always tell the user to rescore the optimized version or review the remaining weak dimensions.

## Optimization Rules

- Prefer one structural change that improves several related signals over keyword stuffing.
- Reward expectation must provide a real payoff in the current script, not only tease the next video.
- Loss aversion must use honest opportunity cost, not invented urgency or fear.
- Precise naming must reflect a plausible audience experience, not stereotype a group.
- Emotional intensity must come from stakes, contrast, or scenes, not attacks or fabricated facts.
- No-fluff optimization may shorten the script beyond normal duration tolerance when repetition is the diagnosed weakness.

## Outputs

Return the universal response envelope. Put each result under `data.optimization` or `data.variants`:

```yaml
status: success
state: completed
message: Script optimized and revision evidence validated.
next_step: 下一步：用 score-viral-script 复评优化后的文案。
data:
  optimization:
    mode: surgical
    source_script: "..."
    optimized_script: "..."
    target_dimensions: [reward_expectation, emotional_intensity]
    changes:
      - dimension: reward_expectation
        before_quote: "原文句子"
        after_quote: "优化后句子"
        reason: "如何修复该评分弱项"
files: []
next_actions:
  - skill: score-viral-script
    action: score
errors: []
```

Preserve the original under `context.project.script_optimization.source_script`. Update `context.project.script` only after validation, and preserve the previous scorecard under the optimization record for cross-Agent handoff.

## Tools

- `scripts/validate_optimization.py plan`: deterministically choose targets and mode from a scorecard.
- `scripts/validate_optimization.py validate`: validate source/optimized evidence, target coverage, and revision metrics.
- An LLM is required for semantic rewriting; Python is optional but recommended for validation.

## Files

- Read `references/optimization_rules.yaml` before planning or rewriting.
- Validate scorecards against `../../schemas/score.schema.json`.
- Validate revision records against `../../schemas/optimization.schema.json` when schema validation is available.
- Preserve portable state with `../../schemas/context.schema.json`.

## Error Handling

- Return `awaiting_user` when no source script exists.
- Return `partial` and `state: awaiting_score` when a script exists but no scorecard is available.
- Return `error` for a mismatched scorecard, fabricated change-log quotation, missing target coverage, unchanged output, or invalid dimension.
- Return `partial` when semantic rewriting succeeds but deterministic validation cannot run.

## Validation

- Require at least one target dimension and one change record per target.
- Require exact before/after quotations in their corresponding scripts.
- Reject an optimized script identical to the source.
- Reject placeholders, unsupported statistics, fabricated cases, and fake guarantees.
- Keep normal duration within 15% unless the user changes it or `no_fluff` is a target.
- Use rescoring as the authority for improvement; textual confidence is not evidence.

## Examples

```yaml
skill: optimize-viral-script
action: optimize
input:
  script: "完整原文"
  scorecard: "score-viral-script 返回的 data.scorecard"
  target_dimensions: [reward_expectation, emotional_intensity]
  variant_count: 1
```
