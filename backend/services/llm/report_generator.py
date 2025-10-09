# services/llm/report_generator.py
from __future__ import annotations
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging
import os
import json


from .explainer import LLMClient
from .prompts import system_prompt, section_instructions, PromptMeta, template_vars


try:
    from jinja2 import Environment, BaseLoader # type: ignore
except Exception: # pragma: no cover
    Environment = None # type: ignore
    BaseLoader = object # type: ignore


logger = logging.getLogger(__name__)

@dataclass
class ReportSection:
	title: str
	content: str

@dataclass
class GeneratedReport:
	executive_summary: ReportSection
	technical_details: ReportSection
	recommendations: ReportSection
	risk_assessment: ReportSection
	action_items: ReportSection
	viz_descriptions: ReportSection
	usage_summary: Dict[str, Any]
	template_name: str



class ReportGenerator:
    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()
        self.persona_exec = os.getenv("LLM_PERSONA_EXEC", "executive")
        self.persona_tech = os.getenv("LLM_PERSONA_TECH", "technical")
        self.language = os.getenv("LLM_LANG", "en")


    def _gen(self, section: str, user_payload: str, persona: str) -> tuple[str, Dict[str, Any]]:
        sys = system_prompt(locale=self.language, persona=persona)
        ins = section_instructions(section, persona=persona)
        messages = [
        {"role": "system", "content": sys},
        {"role": "user", "content": f"{ins}\nInput:\n{user_payload}"},
        ]
        text, usage = self.client.chat(messages)
        return text, usage.__dict__

    def generate(
		self,
		analysis_summary: Dict[str, Any],
		anomalies: list[Dict[str, Any]],
		template: str = "default",
	) -> GeneratedReport:
        payload = json.dumps({"summary": analysis_summary, "anomalies": anomalies})[:4000]
        exec_text, u1 = self._gen("executive_summary", payload, persona=self.persona_exec)
        tech_text, u2 = self._gen("technical_details", payload, persona=self.persona_tech)
        rec_text, u3 = self._gen("recommendations", payload, persona=self.persona_exec)
        risk_text, u4 = self._gen("risk_assessment", payload, persona=self.persona_exec)
        act_text, u5 = self._gen("action_items", payload, persona=self.persona_exec)
        viz_text, u6 = self._gen("viz_descriptions", payload, persona=self.persona_exec)

        usage = {"sections": [u1, u2, u3, u4, u5, u6]}
        
        if template == "default":
            rendered = self.render_template_default(
                executive_summary=exec_text,
                technical_details=tech_text,
                recommendations=rec_text,
                risk_assessment=risk_text,
                action_items=act_text,
                viz_descriptions=viz_text,
			)
        else:
            rendered = self.render_template_default(
                executive_summary=exec_text,
                technical_details=tech_text,
                recommendations=rec_text,
                risk_assessment=risk_text,
                action_items=act_text,
                viz_descriptions=viz_text,
            )

        return GeneratedReport(
            executive_summary=ReportSection("Executive Summary", exec_text),
            technical_details=ReportSection("Technical Details", tech_text),
            recommendations=ReportSection("Recommendations", rec_text),
            risk_assessment=ReportSection("Risk Assessment", risk_text),
            action_items=ReportSection("Action Items", act_text),
            viz_descriptions=ReportSection("Visualizations", viz_text),
            usage_summary=usage,
            template_name=template,
        )

    # --------- Templates ---------
    def render_template_default(self, **sections: str) -> str:
        if Environment is None:
            # Fallback simple layout
            parts = [f"# {k.replace('_', ' ').title()}\n\n{v}" for k, v in sections.items()]
            return "\n\n".join(parts)
        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(
            """
            # Executive Summary
            {{ executive_summary }}


            ## Technical Details
            {{ technical_details }}


            ## Recommendations
            {{ recommendations }}


            ## Risk Assessment
            {{ risk_assessment }}


            ## Action Items
            {{ action_items }}


            ## Visualizations
            {{ viz_descriptions }}
            """
        )
        return tmpl.render(**sections)