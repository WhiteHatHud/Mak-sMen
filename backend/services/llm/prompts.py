# services/llm/prompts.py
from __future__ import annotations
from typing import Dict, Any
from dataclasses import dataclass
import time


PROMPT_VERSION = "v1.0.0"


@dataclass
class PromptMeta:
    version: str
    section: str
    locale: str
    persona: str




def system_prompt(locale: str = "en", persona: str = "executive") -> str:
    base = {
    "en": (
    "You are an expert data analyst and technical writer. "
    "Explain anomaly detection results in clear, concise language. "
    "Avoid jargon unless persona=technical. Be truthful and calibrated."
    ),
    "zh": (
    "你是一名资深数据分析师和技术写作者。用清晰简洁的语言解释异常检测结果。"
    "除非 persona=technical，否则尽量避免术语，保持真实与校准。"
    ),
    "es": (
    "Eres un analista de datos experto y redactor técnico. Explica los resultados de detección de anomalías"
    " con lenguaje claro y conciso. Evita jerga salvo persona=technical."
    ),
    }
    return base.get(locale, base["en"]) + f"\nPrompt-Version: {PROMPT_VERSION}\nPersona: {persona}"




def few_shots(locale: str = "en", persona: str = "executive") -> str:
    if locale == "en" and persona == "executive":
        return (
        "\nExamples:\n"
        "Input: anomaly_score=0.97, key_signals=['sudden spike in amount', 'rare category']\n"
        "Output: We detected an unusual spike in the amount combined with a rarely seen category."
        " This pattern occurs in fewer than 3% of historical cases, so we recommend a quick review.\n"


        "Input: anomaly_score=0.65, key_signals=['missing values', 'seasonality deviation']\n"
        "Output: The data departs from its typical seasonal behavior and has missing values. "
        "This is likely data quality related; monitor but no immediate action required.\n"
        )
    # Minimal non-English examples (fallback to English examples translated lightly)
    if locale == "zh":
        return (
        "\n示例:\n"
        "输入: anomaly_score=0.97, 关键信号=['金额突增', '罕见类别']\n"
        "输出: 出现了金额的异常突增并伴随罕见类别。该模式在历史中少于3%，建议尽快复核。\n"
        )
    return ""

def section_instructions(section: str, persona: str = "executive") -> str:
    sections = {
        "executive_summary": "Write 3–5 bullet points. Focus on business impact, risk, and next steps.",
        "technical_details": "Summarize data, features, models (IF, LOF, ensemble), thresholds, and metrics.",
        "recommendations": "Give prioritized actions (Must/Should/Could). Keep items concise and testable.",
        "risk_assessment": "Describe likelihood, impact, and detection confidence. Include caveats.",
        "action_items": "Produce a checklist with owners and due dates placeholders.",
        "viz_descriptions": "Describe charts in plain language: what changed, when, and how much.",
    }
    tone = "Use plain business language." if persona != "technical" else "Use precise technical wording."
    return sections.get(section, "") + " " + tone




def template_vars(meta: PromptMeta, **kwargs: Any) -> Dict[str, Any]:
    base = {
    "_meta": meta.__dict__,
    "_ts": int(time.time()),
    }
    base.update(kwargs)
    return base