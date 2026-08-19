---
name: score-viral-script
description: Score Chinese talking-head scripts on prediction disruption, reward expectation, loss aversion, precise naming, replicability, concision, AI adaptability, emotional intensity, memorability, and shareability. Use when an agent must produce a 100-point evidence-backed viral-potential scorecard, validate scoring arithmetic, identify weak dimensions, or gate a script before production.
---

# Score Viral Script

## Purpose

Evaluate a supplied spoken script with a stable 100-point rubric. Separate semantic judgment from deterministic validation: let the executing Agent assess meaning, then use the bundled validator to verify dimensions, evidence, totals, and conclusion.

## When to Use

Use for “口播文案打分”, viral-potential assessment, evidence-backed script review, pre-production quality gates, or before-and-after score comparison.

## When NOT to Use

Do not generate a new script unless explicitly handed off to `viral-script`. Do not claim that a high score guarantees actual views, likes, comments, sales, or platform distribution.

## Inputs

- `action`: `score` or `validate`.
- `input.script`: the complete script to score.
- `input.assessment`: required only for deterministic validation of an existing scorecard.

## Optional Inputs

- `title`, `platform`, `audience`, `goal`, and portable pipeline `context`.
- `strict_evidence`: default `true`; require each quotation to occur in the source script.

## Workflow

1. Recover the script from `input.script` or `context.project.script.content`. Ask once only when both are missing.
2. Read `references/scoring_rubric.yaml` in full before assigning scores.
3. Score all ten dimensions independently. Do not raise one score merely because another dimension is strong.
4. For every dimension, provide at least one evidence item with an exact quotation and an explanation tied to the scoring band.
5. When a feature is absent, quote the closest relevant sentence and explain what is missing. Never invent a quotation or use only generic commentary such as “整体不错”.
6. Add one concise improvement for every dimension scoring below 8. Make the improvement actionable and preserve factual integrity.
7. Build a structured assessment conforming to `../../schemas/score.schema.json`.
8. Run `scripts/score_script.py` when Python and filesystem access are available. Let the script calculate subtotals, total, conclusion, strongest dimensions, and priority improvements.
9. In text-only mode, calculate with the same formulas and explicitly mark deterministic validation as skipped.
10. Store the validated scorecard in `context.project.script_score` without overwriting the script.

## Scoring Rules

- Core dimensions: four items, each `1–10`, subtotal `/40`.
- Practicality dimensions: three items, each `1–10`, subtotal `/30`.
- Bonus dimensions: three items, each `0–10`, subtotal `/30`.
- Total: core + practicality + bonus, maximum `100`.
- `80–100`: very high viral potential; directly reusable from the rubric perspective.
- `60–79`: viral potential exists; optimize one or two priority dimensions.
- `<60`: insufficient viral potential; recommend substantial rewriting.

Treat these levels as rubric conclusions, not performance guarantees. Penalize fabricated facts, manipulative promises, or fake urgency instead of rewarding them as strong loss aversion or reward expectation.

## Interaction Rules

- Do not ask for platform, audience, or title when the script can be scored without them.
- Do not ask the user to pre-score any dimension.
- Do not save or modify the source script during scoring.
- Preserve state in the universal response and pipeline context rather than relying on conversation memory.
- In the final user-facing reply, always tell the user whether to optimize weak dimensions, generate a question hook, or review the scorecard.

## Outputs

Return the universal envelope. Put the validated object under `data.scorecard` with:

```yaml
next_step: 下一步：根据分数优化最低分维度，或进入问题钩子生成。
dimensions:
  interrupt_prediction:
    score: 8
    evidence:
      - quote: "原文中的具体句子"
        reason: "这句话如何满足评分标准"
    improvement: null
subtotals:
  core: 0
  practicality: 0
  bonus: 0
total: 0
conclusion:
  level: very_high | potential | insufficient
  label: 中文结论
strongest_dimensions: []
priority_improvements: []
```

Optionally render a human-readable table after the structured scorecard. Keep the structured object authoritative.

## Tools

- `scripts/score_script.py`: validate exact evidence, score ranges, required dimensions, totals, and conclusion.
- No tool is required for semantic scoring; an LLM-capable Agent can run in text-only mode.

## Files

- Read `references/scoring_rubric.yaml` whenever scoring or reviewing a score.
- Validate scorecards against `../../schemas/score.schema.json` when schema validation is available.
- Use `../../schemas/context.schema.json` for cross-Agent handoff.

## Error Handling

- Return `awaiting_user` when no script is available.
- Return `partial` when semantic scoring is complete but deterministic validation cannot run.
- Return `error` with all validation issues when a dimension is missing, a score is out of range, evidence is not found in the source, or arithmetic is inconsistent.
- Never silently repair fabricated evidence. Ask the executing Agent to rescore or replace it with an exact quotation.

## Validation

- Require exactly ten named dimensions.
- Require at least one exact source quotation and reason per dimension.
- Enforce `1–10` for core and practicality; enforce `0–10` for bonus.
- Recalculate every subtotal and the total; ignore model-supplied arithmetic when it conflicts.
- Apply conclusion thresholds deterministically.
- Rank strongest dimensions by score and priority improvements by low score, then category importance.

## Examples

Input:

```yaml
skill: score-viral-script
action: score
input:
  script: "看完这条视频，你会知道为什么工具用得越多，反而越容易做不出内容……"
```

Return all ten evidence-backed scores, three subtotals, `/100` total, conclusion, and a portable next-action handoff to `optimize-viral-script` or `question-hook`.
