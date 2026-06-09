import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from .schemas import ResearchPaper, EvolvingSummary

load_dotenv()

SYNTHESIS_PROMPT = """
You are a senior research analyst and scientific journalist. You will synthesize a cohesive, 
structured intelligence report on the evolution of research in the field: "{topic}".

You have access to:
1. PAST KNOWLEDGE: Summaries of previously analyzed papers in this field.
2. NEW RESEARCH: Structured insights extracted from newly ingested papers.

Your job is to explain how the field has changed, what has been confirmed, what is new, and where research is heading.

Return a single raw JSON object with NO markdown or code fences — exactly this schema:
{{
    "summary": "A rich 4-5 sentence narrative covering the field's evolution from past to new research",
    "novel_contributions": [
        "Specific contribution 1 from the new papers",
        "Specific contribution 2 from the new papers"
    ],
    "conflicts_or_agreements": "A paragraph explaining where the new research aligns with or contradicts prior findings, citing specific examples where possible.",
    "open_questions": [
        "Unanswered question implied by the research gap 1",
        "Unanswered question implied by the research gap 2"
    ],
    "field_trajectory": "A paragraph describing where the field appears to be heading based on all research reviewed."
}}

PAST KNOWLEDGE:
{past_context}

NEW RESEARCH:
{new_research}
"""

GEMINI_MODEL_CANDIDATES = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-1.0-pro",
    "gemini-pro",
]

def find_working_gemini_model() -> str:
    """Find the best available Gemini model by checking against GEMINI_MODEL_CANDIDATES priority list."""
    try:
        available_models = {m.name.replace("models/", "") for m in genai.list_models()}
        for candidate in GEMINI_MODEL_CANDIDATES:
            if candidate in available_models:
                return candidate
    except Exception:
        pass
    return GEMINI_MODEL_CANDIDATES[0]  # fallback to top priority

class KnowledgeSynthesizer:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.ready = bool(api_key and api_key != "your_gemini_api_key_here")
        if self.ready:
            genai.configure(api_key=api_key)
            model_name = find_working_gemini_model()
            self.model = genai.GenerativeModel(model_name)
        else:
            self.model = None

    def generate_evolving_summary(
        self,
        topic: str,
        past_context: str,
        new_papers: list,
    ) -> EvolvingSummary:

        if not self.ready:
            return EvolvingSummary(
                summary="Gemini API key not configured. Please add GEMINI_API_KEY to your .env file.",
                novel_contributions=[],
                conflicts_or_agreements="",
                open_questions=[],
                field_trajectory=""
            )

        # Format new papers into detailed text block
        new_research_blocks = []
        for p in new_papers:
            block = (
                f"Title: {p.title}\n"
                f"Authors: {', '.join(p.authors)}\n"
                f"Published: {p.publication_date} in {p.journal}\n"
                f"Abstract: {p.abstract}\n"
                f"Methodology: {p.insights.methodology}\n"
                f"Core Findings:\n" + "\n".join(f"  - {f}" for f in p.insights.core_findings) + "\n"
                f"Limitations:\n" + "\n".join(f"  - {l}" for l in p.insights.limitations) + "\n"
                f"Future Work:\n" + "\n".join(f"  - {f}" for f in p.insights.future_work)
            )
            new_research_blocks.append(block)

        prompt = SYNTHESIS_PROMPT.format(
            topic=topic,
            past_context=past_context,
            new_research="\n\n---\n\n".join(new_research_blocks)
        )

        try:
            response = self.model.generate_content(prompt)
            raw = response.text.strip()
            if "```" in raw:
                parts = raw.split("```")
                raw = parts[1] if len(parts) >= 2 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
            return EvolvingSummary(
                summary=data.get("summary", ""),
                novel_contributions=data.get("novel_contributions", []),
                conflicts_or_agreements=data.get("conflicts_or_agreements", ""),
                open_questions=data.get("open_questions", []),
                field_trajectory=data.get("field_trajectory", "")
            )
        except Exception as e:
            return EvolvingSummary(
                summary=f"Synthesis failed: {e}",
                novel_contributions=[],
                conflicts_or_agreements="",
                open_questions=[],
                field_trajectory=""
            )
