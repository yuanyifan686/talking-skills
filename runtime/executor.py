from __future__ import annotations

import importlib.util
import json
import re
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

from shared.utils.protocol import response
from shared.utils.validation import validate

from .providers import LLMProvider, ProviderError, ProviderUnavailable, VolcengineProvider
from .registry import ROOT, SkillDefinition, SkillRegistry


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


viral_workflow = _load_module(
    "talking_runtime_viral_workflow",
    ROOT / "skills" / "viral-script" / "scripts" / "workflow.py",
)
template_store = _load_module(
    "talking_runtime_template_store",
    ROOT / "skills" / "viral-script" / "scripts" / "template_store.py",
)
scorer = _load_module(
    "talking_runtime_scorer",
    ROOT / "skills" / "score-viral-script" / "scripts" / "score_script.py",
)
optimizer = _load_module(
    "talking_runtime_optimizer",
    ROOT / "skills" / "optimize-viral-script" / "scripts" / "validate_optimization.py",
)
hook_generator = _load_module(
    "talking_runtime_hook_generator",
    ROOT / "skills" / "question-hook" / "scripts" / "generate_hook.py",
)
person_renderer = _load_module(
    "talking_runtime_person_renderer",
    ROOT / "skills" / "person-intro" / "scripts" / "render_intro.py",
)


def _json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型未返回 JSON 对象")
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("模型返回值必须是 JSON 对象")
    return value


def _characters(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def _duration_seconds(value: Any) -> float:
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(match.group()) if match else 60.0


def _duration_range(seconds: float) -> tuple[int, int]:
    presets = {
        15: (70, 110),
        30: (160, 240),
        45: (250, 340),
        60: (350, 480),
        90: (520, 700),
    }
    rounded = int(round(seconds))
    return presets.get(rounded, (max(1, int(seconds * 4.5)), max(2, int(seconds * 6))))


def _context(invocation: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(invocation.get("context") or {"project": {}})
    value.setdefault("protocol_version", "1.0.0")
    value.setdefault("project", {})
    return value


def _script_from(invocation: dict[str, Any]) -> str:
    input_data = invocation.get("input") or {}
    direct = input_data.get("script")
    if isinstance(direct, str):
        return direct.strip()
    context_script = (invocation.get("context") or {}).get("project", {}).get("script")
    if isinstance(context_script, str):
        return context_script.strip()
    if isinstance(context_script, dict):
        return str(context_script.get("content") or "").strip()
    return ""


class SkillExecutor:
    """Execute universal invocations against the single canonical Skill library."""

    def __init__(
        self,
        registry: SkillRegistry | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self.registry = registry or SkillRegistry()
        self.provider = provider or VolcengineProvider()

    def invoke(self, invocation: dict[str, Any]) -> dict[str, Any]:
        errors = self.registry.validate_invocation(invocation)
        if errors:
            return response(
                status="error",
                state="validation",
                message="Skill 调用校验失败。",
                errors=[{"code": "invalid_invocation", "message": item, "recoverable": True} for item in errors],
                request_id=invocation.get("request_id"),
            )

        skill_id = str(invocation["skill"])
        try:
            if skill_id == "viral-script":
                result = self._viral_script(invocation)
            elif skill_id == "score-viral-script":
                result = self._score_script(invocation)
            elif skill_id == "optimize-viral-script":
                result = self._optimize_script(invocation)
            elif skill_id == "question-hook":
                result = self._question_hook(invocation)
            elif skill_id == "person-intro":
                result = self._person_intro(invocation)
            else:
                raise KeyError(f"No runtime handler for {skill_id}")
        except ProviderUnavailable as exc:
            result = response(
                status="error",
                state="provider_configuration",
                message=str(exc),
                errors=[{"code": "provider_unavailable", "message": str(exc), "recoverable": True}],
                request_id=invocation.get("request_id"),
            )
        except (ProviderError, ValueError, KeyError, RuntimeError) as exc:
            result = response(
                status="error",
                state="execution",
                message="Skill 执行失败。",
                errors=[{"code": "execution_failed", "message": str(exc), "recoverable": True}],
                request_id=invocation.get("request_id"),
            )

        response_errors = validate(result, ROOT / "schemas" / "response.schema.json")
        if response_errors:
            return response(
                status="error",
                state="response_validation",
                message="Skill 返回值不符合统一协议。",
                errors=[{"code": "invalid_response", "message": item, "recoverable": False} for item in response_errors],
                request_id=invocation.get("request_id"),
            )
        return result

    def _skill_system(self, skill: SkillDefinition) -> str:
        references = json.dumps(skill.references, ensure_ascii=False, indent=2)
        return (
            "你正在通过一个 Agent-Agnostic Skill Runtime 执行能力。"
            "严格遵守下面的 Skill 行为规范和引用资料，不要依赖网页提示词。\n\n"
            f"{skill.instructions}\n\n## Loaded references\n{references}"
        )

    def _complete_json(
        self,
        skill: SkillDefinition,
        user: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        return _json_object(
            self.provider.complete(
                system=self._skill_system(skill),
                user=user,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        )

    def _viral_script(self, invocation: dict[str, Any]) -> dict[str, Any]:
        action = invocation["action"]
        if action == "generate":
            return viral_workflow.title_response(invocation)
        if action == "continue":
            if invocation.get("state") == "style_selection" and (
                (invocation.get("input") or {}).get("selected_style")
                or (invocation.get("input") or {}).get("agent_select")
            ):
                promoted = deepcopy(invocation)
                promoted["action"] = "run_pipeline"
                promoted["input"] = {
                    **(promoted.get("input") or {}),
                    "variant_count": 1,
                    "auto_select": True,
                }
                return self._viral_run_pipeline(promoted)
            return viral_workflow.continue_response(invocation)
        if action == "run_pipeline":
            return self._viral_run_pipeline(invocation)
        if action in {"analyze", "create_template"}:
            return self._viral_analysis(invocation, create_template=action == "create_template")
        if action == "add_template":
            candidate = (invocation.get("input") or {}).get("template")
            if not isinstance(candidate, dict):
                raise ValueError("input.template must be an object")
            outcome = template_store.add_template(
                ROOT / "skills" / "viral-script" / "references" / "copy_templates.yaml",
                candidate,
                confirm=True,
            )
            if outcome["status"] != "success":
                return response(
                    status=outcome["status"],
                    state="template_validation",
                    message="模板未保存。",
                    data={"template": candidate},
                    errors=[{"code": "invalid_template", "message": item, "recoverable": True} for item in outcome.get("errors", [])],
                    request_id=invocation.get("request_id"),
                )
            return response(
                status="success",
                state="completed",
                message="模板已加入模板库。",
                data=outcome,
                request_id=invocation.get("request_id"),
            )
        raise ValueError(f"Unsupported viral-script action: {action}")

    def _viral_run_pipeline(self, invocation: dict[str, Any]) -> dict[str, Any]:
        skill = self.registry.get("viral-script")
        input_data = invocation.get("input") or {}
        context = _context(invocation)
        topic = viral_workflow.clean_topic(input_data.get("topic") or context["project"].get("topic"))
        if not topic:
            return response(
                status="awaiting_user",
                state="topic",
                message="请提供一个口播主题。",
                errors=[{"code": "missing_topic", "message": "Topic is required", "recoverable": True}],
                context=context,
                request_id=invocation.get("request_id"),
            )

        duration = _duration_seconds(input_data.get("duration") or 60)
        target_characters = _duration_range(duration)
        variant_count = int(input_data.get("variant_count") or 1)
        variant_count = max(1, min(4, variant_count))
        templates = skill.references["templates"].get("templates", [])
        template_ids = [item.get("id") for item in templates if isinstance(item, dict)]
        requested_template = input_data.get("template_id") or input_data.get("structure_id")
        if requested_template == "auto":
            requested_template = None
        deliveries = skill.references.get("deliveries", {}).get("presets", [])
        selected_deliveries = [item for item in deliveries if isinstance(item, dict)][:variant_count]
        if len(selected_deliveries) < variant_count:
            selected_deliveries.extend(
                {"id": f"version_{index + 1}", "label": f"版本 {index + 1}", "tag": "口播", "fit": "通用表达", "style": "natural_chat"}
                for index in range(len(selected_deliveries), variant_count)
            )

        question_hook = input_data.get("question_hook", input_data.get("questionHook", True)) is not False
        payload = {
            "topic": topic,
            "platform": input_data.get("platform") or context["project"].get("platform") or "douyin",
            "audience": input_data.get("audience") or "泛人群",
            "goal": input_data.get("goal") or "评论",
            "duration_seconds": duration,
            "target_characters_per_version": f"{target_characters[0]}-{target_characters[1]}",
            "question_hook": question_hook,
            "requested_template_id": requested_template,
            "allowed_template_ids": template_ids,
            "delivery_presets": selected_deliveries,
            "selected_title": input_data.get("selected_title"),
            "selected_style": input_data.get("selected_style") or input_data.get("style"),
        }
        contract = {
            "structure": {
                "id": "必须来自 allowed_template_ids",
                "reason": "一句话说明匹配原因",
                "match_score": "0-100整数",
            },
            "versions": [
                {
                    "id": "对应 delivery_presets.id",
                    "title": "标题",
                    "hook": "自然开头",
                    "body": ["正文段落"],
                    "ending": "自然结尾",
                    "style": "风格ID",
                }
            ],
        }
        user = (
            "执行 action=run_pipeline。自动完成标题、结构和风格选择，并生成可直接念的完整口播稿。\n"
            "只返回合法 JSON，不要 Markdown。versions 数量必须与 delivery_presets 相同，且顺序一致。"
            "不要编造数据、案例、身份或收益；每段都要推进信息。\n"
            f"调用输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
            f"返回协议：\n{json.dumps(contract, ensure_ascii=False, indent=2)}"
        )
        last_error = "模型输出无效"
        for attempt in range(2):
            retry = "" if attempt == 0 else f"\n上次校验失败：{last_error}。请完整重写并只返回 JSON。"
            raw = self._complete_json(skill, user + retry, max_tokens=5600, temperature=0.8)
            try:
                structure, versions = self._normalize_viral(raw, selected_deliveries, templates, duration, question_hook)
                break
            except ValueError as exc:
                last_error = str(exc)
        else:
            raise ValueError(last_error)

        first = versions[0]
        script = {
            "title": first["title"],
            "content": first["content"],
            "platform": payload["platform"],
            "audience": payload["audience"],
            "style": first["style"],
            "template_id": structure["id"],
            "question_hook": question_hook,
            "estimated_duration": first["estimated_duration"],
            "estimated_characters": first["estimated_characters"],
            "metadata": {"selection_source": "agent", "goal": payload["goal"]},
        }
        context["project"].update({"topic": topic, "platform": payload["platform"], "script": script})
        return response(
            status="success",
            state="completed",
            message=f"已通过 viral-script 生成 {len(versions)} 个口播版本。",
            data={"structure": structure, "versions": versions, "script": script},
            next_actions=[{"skill": "score-viral-script", "action": "score", "reason": "生成后进行统一质量评分"}],
            context=context,
            request_id=invocation.get("request_id"),
        )

    def _normalize_viral(
        self,
        raw: dict[str, Any],
        deliveries: list[dict[str, Any]],
        templates: list[dict[str, Any]],
        duration: float,
        question_hook: bool,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        source_structure = raw.get("structure")
        if not isinstance(source_structure, dict):
            raise ValueError("缺少 structure")
        template_map = {item.get("id"): item for item in templates if isinstance(item, dict)}
        template_id = source_structure.get("id")
        if template_id not in template_map:
            raise ValueError("structure.id 不在 Skill 模板库中")
        template = template_map[template_id]
        score = source_structure.get("match_score", 80)
        if not isinstance(score, int):
            score = 80
        structure = {
            "id": template_id,
            "name": template.get("name") or template_id,
            "kicker": template.get("kicker") or "推荐结构",
            "description": source_structure.get("reason") or template.get("description") or "适合当前主题",
            "chain": template.get("display_chain") or template.get("structure") or [],
            "color": template.get("color") or "blue",
            "match_score": max(0, min(100, score)),
        }
        source_versions = raw.get("versions")
        if not isinstance(source_versions, list) or len(source_versions) != len(deliveries):
            raise ValueError(f"versions 必须正好包含 {len(deliveries)} 个版本")
        versions = []
        for index, preset in enumerate(deliveries):
            item = source_versions[index]
            if not isinstance(item, dict):
                raise ValueError(f"versions[{index}] 不是对象")
            hook = str(item.get("hook") or "").strip()
            ending = str(item.get("ending") or "").strip()
            body_value = item.get("body")
            body = [str(part).strip() for part in body_value if str(part).strip()] if isinstance(body_value, list) else []
            title = str(item.get("title") or "").strip()
            if not title or not hook or not body or not ending:
                raise ValueError(f"versions[{index}] 的 title、hook、body、ending 必须完整")
            if question_hook and not re.search(r"[？?]", hook[:100]):
                hook = f"你有没有想过，{hook.rstrip('。！!?？')}？"
            if not question_hook and re.search(r"[？?]", hook[:100]):
                hook = hook.replace("？", "。").replace("?", "。")
            content = "\n\n".join([hook, *body, ending])
            character_count = _characters(content)
            minimum, maximum = _duration_range(duration)
            if character_count < int(minimum * 0.85):
                raise ValueError(f"versions[{index}] 过短：{character_count} 字，目标至少约 {minimum} 字")
            if character_count > int(maximum * 1.15):
                raise ValueError(f"versions[{index}] 过长：{character_count} 字，目标至多约 {maximum} 字")
            versions.append(
                {
                    "id": preset.get("id") or f"version_{index + 1}",
                    "label": preset.get("label") or f"版本 {index + 1}",
                    "tag": preset.get("tag") or "口播",
                    "fit": preset.get("fit") or "通用表达",
                    "title": title,
                    "hook": hook,
                    "body": body,
                    "ending": ending,
                    "content": content,
                    "style": item.get("style") or preset.get("style") or "natural_chat",
                    "template_id": structure["id"],
                    "estimated_characters": character_count,
                    "estimated_duration": round(character_count / 5.2, 1),
                    "requested_duration": duration,
                }
            )
        return structure, versions

    def _viral_analysis(self, invocation: dict[str, Any], *, create_template: bool) -> dict[str, Any]:
        script = _script_from(invocation)
        if not script:
            return response(status="awaiting_user", state="analysis_mode", message="请提供需要分析的文案。")
        skill = self.registry.get("viral-script")
        if create_template:
            contract = {
                "template": {
                    "id": "lowercase_snake_case_v1",
                    "name": "模板名",
                    "suitable_topics": [],
                    "platforms": [],
                    "title_formula": [],
                    "hook_formula": [],
                    "structure": [],
                    "rhythm": {},
                    "ending_style": [],
                    "avoid": [],
                }
            }
            purpose = "提炼一个可保存但暂不写入模板库的模板"
        else:
            contract = {"analysis": {name: "具体分析和原文证据" for name in ("title", "hook", "conflict", "emotion", "information_gap", "rhythm", "sentence_structure", "turning_point", "conclusion", "cta")}}
            purpose = "拆解文案"
        data = self._complete_json(
            skill,
            f"{purpose}。只返回合法 JSON。\n原文：\n{script}\n返回协议：\n{json.dumps(contract, ensure_ascii=False, indent=2)}",
        )
        return response(
            status="success",
            state="completed",
            message="文案结构已提炼。" if create_template else "文案分析已完成。",
            data=data,
            request_id=invocation.get("request_id"),
        )

    def _score_script(self, invocation: dict[str, Any]) -> dict[str, Any]:
        input_data = invocation.get("input") or {}
        if invocation["action"] == "validate":
            assessment = input_data.get("assessment")
            if not isinstance(assessment, dict):
                raise ValueError("input.assessment must be an object")
            normalized, errors, corrections = scorer.normalize(
                assessment,
                strict_evidence=input_data.get("strict_evidence", True) is not False,
            )
            if errors:
                raise ValueError("; ".join(errors))
            return response(
                status="success",
                state="completed",
                message="评分卡校验通过。",
                data={"scorecard": normalized, "corrections": corrections},
                next_actions=["review_scorecard", "optimize_weak_dimensions"],
            )

        script = _script_from(invocation)
        if not script:
            return response(status="awaiting_user", state="scoring", message="请提供需要评分的完整文案。")
        skill = self.registry.get("score-viral-script")
        dimension_ids = list(scorer.ALL_DIMENSIONS)
        contract = {
            "source_script": "必须逐字等于原文",
            "title": input_data.get("title"),
            "dimensions": {
                name: {
                    "score": "整数",
                    "evidence": [{"quote": "原文中的精确短句", "reason": "对应评分档位的原因"}],
                    "improvement": "低于8分时必填，否则可为null",
                }
                for name in dimension_ids
            },
        }
        base_user = (
            "执行 action=score。严格按十个维度独立评分。证据 quote 必须逐字出现在原文中。"
            "只返回合法 JSON，不计算总分，Runtime 会确定性计算。\n"
            f"原文：\n{script}\n返回协议：\n{json.dumps(contract, ensure_ascii=False, indent=2)}"
        )
        last_error = "评分结果无效"
        for attempt in range(2):
            retry = "" if attempt == 0 else f"\n上次校验失败：{last_error}。修正所有问题后完整返回。"
            assessment = self._complete_json(skill, base_user + retry, max_tokens=5000, temperature=0.2)
            assessment["source_script"] = script
            normalized, errors, corrections = scorer.normalize(
                assessment,
                strict_evidence=input_data.get("strict_evidence", True) is not False,
            )
            if not errors and normalized is not None:
                break
            last_error = "; ".join(errors)
        else:
            raise ValueError(last_error)

        context = _context(invocation)
        context["project"]["script_score"] = normalized
        next_action = (
            {"skill": "question-hook", "action": "generate", "reason": "评分达到 80 分质量门槛"}
            if normalized["total"] >= 80
            else {"skill": "optimize-viral-script", "action": "optimize", "reason": "优化最低分维度"}
        )
        return response(
            status="success",
            state="completed",
            message=f"评分完成：{normalized['total']}/100。",
            data={"scorecard": normalized, "corrections": corrections},
            next_actions=[next_action],
            context=context,
            request_id=invocation.get("request_id"),
        )

    def _optimize_script(self, invocation: dict[str, Any]) -> dict[str, Any]:
        input_data = invocation.get("input") or {}
        if invocation["action"] == "validate":
            candidate = input_data.get("optimization")
            if not isinstance(candidate, dict):
                raise ValueError("input.optimization must be an object")
            normalized, errors, warnings = optimizer.validate_revision(
                candidate,
                max_change_ratio=float(input_data.get("max_change_ratio") or 0.65),
            )
            if errors:
                raise ValueError("; ".join(errors))
            return response(
                status="success",
                state="completed",
                message="优化记录校验通过。",
                data={"optimization": normalized, "warnings": warnings},
                next_actions=[{"skill": "score-viral-script", "action": "score", "reason": "复评优化后的文案"}],
            )

        script = _script_from(invocation)
        context = _context(invocation)
        scorecard = input_data.get("scorecard") or context["project"].get("script_score")
        if not script:
            return response(status="awaiting_user", state="rewriting", message="请提供需要优化的文案。", context=context)
        if not isinstance(scorecard, dict):
            return response(
                status="partial",
                state="awaiting_score",
                message="需要先用 score-viral-script 生成评分卡。",
                next_actions=[{"skill": "score-viral-script", "action": "score", "reason": "优化必须基于统一评分卡"}],
                context=context,
            )
        force_rewrite = invocation["action"] == "rewrite"
        plan, plan_errors = optimizer.build_plan(
            scorecard,
            requested=input_data.get("target_dimensions"),
            max_targets=input_data.get("max_target_dimensions"),
            force_rewrite=force_rewrite,
        )
        if plan_errors or plan is None:
            raise ValueError("; ".join(plan_errors))
        skill = self.registry.get("optimize-viral-script")
        duration = _duration_seconds(input_data.get("duration") or 0) if input_data.get("duration") else None
        contract = {
            "optimized_title": "可选",
            "optimized_script": "不带Hook/正文等标签的完整自然口播稿",
            "changes": [
                {
                    "dimension": "必须来自 target_dimensions",
                    "before_quote": "原文精确短句",
                    "after_quote": "优化稿精确短句",
                    "reason": "修改如何修复该维度",
                    "technique": "使用的技巧",
                }
            ],
        }
        base_user = (
            "执行评分驱动优化。只返回合法 JSON。每个目标维度至少一条 change；before_quote 和 "
            "after_quote 必须分别逐字存在于原文和优化稿。不得编造事实。\n"
            f"目标时长：{duration or '保持原时长'} 秒\n"
            f"优化计划：\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n"
            f"评分卡：\n{json.dumps(scorecard, ensure_ascii=False, indent=2)}\n"
            f"原文：\n{script}\n返回协议：\n{json.dumps(contract, ensure_ascii=False, indent=2)}"
        )
        last_error = "优化结果无效"
        for attempt in range(2):
            retry = "" if attempt == 0 else f"\n上次校验失败：{last_error}。请修正并完整返回 JSON。"
            generated = self._complete_json(skill, base_user + retry, max_tokens=5600, temperature=0.55)
            candidate = {
                "source_title": input_data.get("title"),
                "optimized_title": generated.get("optimized_title"),
                "source_script": script,
                "scorecard": scorecard,
                "optimized_script": generated.get("optimized_script"),
                "mode": plan["mode"],
                "target_dimensions": plan["target_dimensions"],
                "changes": generated.get("changes"),
                "preserved_constraints": input_data.get("preserve") or ["事实", "核心观点", "目标人群"],
            }
            normalized, errors, warnings = optimizer.validate_revision(
                candidate,
                max_change_ratio=float(input_data.get("max_change_ratio") or 0.65),
            )
            if not errors and normalized is not None:
                break
            last_error = "; ".join(errors)
        else:
            raise ValueError(last_error)

        previous_script = context["project"].get("script")
        if isinstance(previous_script, dict):
            updated_script = {**previous_script, "content": normalized["optimized_script"]}
            if normalized.get("optimized_title"):
                updated_script["title"] = normalized["optimized_title"]
            updated_script["estimated_characters"] = normalized["metrics"]["optimized_characters"]
            updated_script["estimated_duration"] = normalized["metrics"]["estimated_duration"]
        else:
            updated_script = {
                "title": normalized.get("optimized_title") or input_data.get("title") or "优化口播稿",
                "content": normalized["optimized_script"],
                "estimated_characters": normalized["metrics"]["optimized_characters"],
                "estimated_duration": normalized["metrics"]["estimated_duration"],
            }
        context["project"]["script_score_previous"] = scorecard
        context["project"]["script_optimization"] = normalized
        context["project"]["script"] = updated_script
        return response(
            status="success",
            state="completed",
            message="文案已按最低分维度完成优化。",
            data={"optimization": normalized, "optimized_script": normalized["optimized_script"], "warnings": warnings},
            next_actions=[{"skill": "score-viral-script", "action": "score", "reason": "用同一量表复评分"}],
            context=context,
            request_id=invocation.get("request_id"),
        )

    def _question_hook(self, invocation: dict[str, Any]) -> dict[str, Any]:
        action = invocation["action"]
        if action not in {"generate", "run_pipeline"}:
            return response(
                status="partial",
                state="completed",
                message="Runtime 已识别该媒体动作；请使用 Skill 自带脚本执行 TTS 或 FFmpeg。",
                data={"skipped": [action], "reason": "媒体动作需要明确文件路径和本机能力"},
                request_id=invocation.get("request_id"),
            )
        script = _script_from(invocation)
        if not script:
            return response(status="awaiting_user", state="hook_generation", message="请提供口播正文。")
        input_data = invocation.get("input") or {}
        context = _context(invocation)
        hook = hook_generator.build_hook(script, input_data.get("hook_type") or "auto", input_data.get("topic") or context["project"].get("topic"))
        context["project"]["hook"] = hook
        skipped = []
        status = "success"
        if action == "run_pipeline" and not (context["project"].get("video") or {}).get("source"):
            status = "partial"
            skipped = ["tts", "intro_render", "video_composition"]
        return response(
            status=status,
            state="completed",
            message="问题钩子已生成。" if not skipped else "问题钩子已生成；没有源视频，媒体步骤已跳过。",
            data={"hook": hook, "skipped": skipped},
            next_actions=[
                {"skill": "question-hook", "action": "synthesize", "reason": "需要问题音频时执行"},
                {"skill": "question-hook", "action": "compose", "reason": "提供源视频后合成"},
            ],
            context=context,
            request_id=invocation.get("request_id"),
        )

    def _person_intro(self, invocation: dict[str, Any]) -> dict[str, Any]:
        input_data = invocation.get("input") or {}
        context = _context(invocation)
        person = input_data.get("person") or context["project"].get("person")
        if not isinstance(person, dict):
            return response(status="awaiting_user", state="content_selection", message="请提供人物信息。", context=context)
        lines = person_renderer.select_lines(person)
        position, fallback = person_renderer.resolve_position(
            str(input_data.get("position") or "auto"),
            input_data.get("person_position"),
        )
        person_assets = person.get("assets") if isinstance(person.get("assets"), dict) else {}
        input_assets = input_data.get("assets") if isinstance(input_data.get("assets"), dict) else {}
        assets = {
            "avatar": input_data.get("avatar") or input_assets.get("avatar") or person_assets.get("avatar"),
            "logo": input_data.get("logo_file") or input_assets.get("logo") or (person_assets.get("logos") or [None])[0],
            "background": input_data.get("background_image") or input_assets.get("background") or person_assets.get("background"),
            "font": input_data.get("font") or input_assets.get("font") or person_assets.get("font"),
        }
        assets = {key: value for key, value in assets.items() if value}
        spec = {
            "lines": lines,
            "duration": float(input_data.get("duration") or 4),
            "position": position,
            "position_fallback": fallback,
            "animation": input_data.get("animation") or "fade_slide",
            "style": input_data.get("style") or "professional",
            "logo": bool(input_data.get("logo", True) or assets.get("logo")),
            "assets": assets,
        }
        context["project"].setdefault("output", {})["person_intro"] = spec
        render_requested = invocation["action"] in {"render", "run_pipeline"}
        status = "partial" if render_requested else "success"
        return response(
            status=status,
            state="completed",
            message="人物介绍内容已生成。" if not render_requested else "人物介绍内容已生成；渲染请交给 Skill 自带 FFmpeg 脚本。",
            data={"person_intro": spec, "skipped": ["video_render"] if render_requested else []},
            next_actions=["render_person_intro", "review_person_intro"],
            context=context,
            request_id=invocation.get("request_id"),
        )
