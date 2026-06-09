import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from .schemas import ResearchPaper, ExtractedInsights

load_dotenv()

EXTRACTION_PROMPT = """
You are an expert biomedical and academic research analyst. Carefully read the following scraped markdown content.

CRITICAL INSTRUCTIONS (follow strictly in this order):
1. RESEARCH PAPER CHECK: First, determine if this content is a genuine academic or scientific research paper. A valid research paper must have ALL of the following: an identifiable title, at least one author, an abstract or introduction, and a methodology or results section. It can come from sources like arXiv, PubMed, IEEE, ACM, Springer, Nature, ScienceDirect, bioRxiv, medRxiv, ResearchGate, or any university/academic journal.
2. REJECT non-research content: If the page is a blog post, news article, product page, homepage, Wikipedia article, social media post, "404 Page Not Found", reCAPTCHA challenge, login wall, or any other non-research-paper content, you MUST set the "title" field to exactly "[NOT A RESEARCH PAPER]" and set "abstract" to a one-sentence explanation of what the page actually is. Leave all other fields empty.
3. EXTRACT only if it passes check #1: Extract ALL fields below and return them as a single valid JSON object ONLY. No markdown, no code fences, no explanation — just the raw JSON.

JSON Schema:
{{
    "title": "Full title of the paper",
    "authors": ["Author Full Name 1", "Author Full Name 2"],
    "publication_date": "YYYY-MM-DD or approximate year or 'Unknown'",
    "journal": "Journal or publisher name, or 'Unknown'",
    "doi": "DOI string if available else ''",
    "abstract": "2-3 sentence overview of the paper goal and context",
    "full_summary": "A detailed 3-4 paragraph narrative summary in plain English covering the background, methods, results, and conclusions of the paper",
    "insights": {{
        "core_findings": ["Specific finding 1", "Specific finding 2", "Specific finding 3"],
        "methodology": "Clear description of research design, data used, sample size, statistical tests, model types, etc.",
        "limitations": ["Limitation 1", "Limitation 2"],
        "keywords": ["keyword1", "keyword2", "keyword3"],
        "future_work": ["Future direction 1", "Future direction 2"]
    }}
}}

MARKDOWN CONTENT (truncated to 25000 chars):
{content}
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
    """Pick the best available Gemini model from GEMINI_MODEL_CANDIDATES."""
    try:
        available_models = {m.name.replace("models/", "") for m in genai.list_models()}
        for candidate in GEMINI_MODEL_CANDIDATES:
            if candidate in available_models:
                return candidate
    except Exception:
        pass
    return GEMINI_MODEL_CANDIDATES[0]  # fallback to top priority

# Allowed research paper domains (expanded as needed)
RESEARCH_DOMAINS = {
    "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov",
    "doi.org", "dx.doi.org",
    "ieee.org", "ieeexplore.ieee.org",
    "acm.org", "dl.acm.org",
    "springer.com", "link.springer.com",
    "nature.com", "www.nature.com",
    "sciencedirect.com", "www.sciencedirect.com",
    "researchgate.net", "www.researchgate.net",
    "biorxiv.org", "www.biorxiv.org",
    "medrxiv.org", "www.medrxiv.org",
    "plos.org", "journals.plos.org",
    "wiley.com", "onlinelibrary.wiley.com",
    "frontiersin.org", "www.frontiersin.org",
    "tandfonline.com", "www.tandfonline.com",
    "oup.com", "academic.oup.com",
    "semanticscholar.org", "api.semanticscholar.org",
    "jstor.org", "www.jstor.org",
    "ssrn.com", "papers.ssrn.com",
    "pmc.ncbi.nlm.nih.gov",
    "cell.com", "www.cell.com",
    "science.org", "www.science.org",
    "jamanetwork.com",
    "bmj.com", "www.bmj.com",
    "thelancet.com", "www.thelancet.com",
    "nejm.org", "www.nejm.org",
    "mdpi.com", "www.mdpi.com",
    "hindawi.com", "www.hindawi.com",
    "scholar.google.com",
    "hal.science", "hal.archives-ouvertes.fr",
    "openreview.net",
    "paperswithcode.com",
}

def is_research_url(url: str) -> bool:
    """Returns True if the URL belongs to a known academic/research domain."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        # Direct match or subdomain match
        return any(
            host == domain or host.endswith("." + domain)
            for domain in RESEARCH_DOMAINS
        )
    except Exception:
        return False

class InsightExtractor:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.ready = bool(api_key and api_key != "your_gemini_api_key_here")
        if self.ready:
            genai.configure(api_key=api_key)
            model_name = find_working_gemini_model()
            self.model = genai.GenerativeModel(model_name)
        else:
            self.model = None

    def extract_paper_details(self, url: str, markdown_content: str) -> ResearchPaper:
        """Parses raw scraped content into a structured ResearchPaper object."""

        if not self.ready:
            return self._error_paper(url, "Gemini API key is missing or invalid.")

        # ── Domain whitelist check ─────────────────────────────────────────────
        if not is_research_url(url):
            return self._error_paper(
                url,
                "[NOT A RESEARCH PAPER] This URL is not from a recognised academic/research publisher. "
                "Please provide a link from sources like arXiv, PubMed, IEEE, Springer, Nature, etc."
            )

        if markdown_content.startswith("ERROR:"):
            return self._error_paper(url, markdown_content)

        # Quick heuristic filter for common junk pages
        lower_content = markdown_content.lower()
        if "recaptcha" in lower_content and "verify you are human" in lower_content:
            return self._error_paper(url, "Blocked by reCAPTCHA")
        if "404 page not found" in lower_content or "the requested page is unavailable" in lower_content:
            return self._error_paper(url, "Page Not Found (404)")

        prompt = EXTRACTION_PROMPT.format(content=markdown_content[:25000])

        try:
            response = self.model.generate_content(prompt)
            raw_text = response.text.strip()
            # Strip markdown code fences if model ignored instruction
            if "```" in raw_text:
                # Extract content between first and last code fence
                parts = raw_text.split("```")
                raw_text = parts[1] if len(parts) >= 2 else raw_text
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()
            data = json.loads(raw_text)

            # Extra safeguard: if the LLM flagged it as an error or non-research
            title = data.get("title", "")
            if title.startswith("[ERROR]") or title.startswith("[NOT A RESEARCH PAPER]"):
                return self._error_paper(url, data.get("abstract", "Not a research paper — rejected by AI."))

            insights_data = data.get("insights", {})
            insights = ExtractedInsights(
                core_findings=insights_data.get("core_findings", []),
                methodology=insights_data.get("methodology", ""),
                limitations=insights_data.get("limitations", []),
                keywords=insights_data.get("keywords", []),
                future_work=insights_data.get("future_work", [])
            )

            return ResearchPaper(
                title=data.get("title", "Unknown Title"),
                authors=data.get("authors", []),
                publication_date=data.get("publication_date", ""),
                journal=data.get("journal", ""),
                doi=data.get("doi", ""),
                url=url,
                abstract=data.get("abstract", ""),
                full_summary=data.get("full_summary", ""),
                insights=insights
            )

        except json.JSONDecodeError as e:
            return self._error_paper(url, f"JSON parse failed: {e}")
        except Exception as e:
            return self._error_paper(url, f"LLM call failed: {e}")

    def _error_paper(self, url: str, reason: str) -> ResearchPaper:
        return ResearchPaper(
            title=f"[ERROR] {url[:60]}",
            url=url,
            abstract=reason,
            full_summary=reason,
            insights=ExtractedInsights(
                core_findings=["Extraction failed"],
                methodology="N/A",
                limitations=["N/A"],
                keywords=[],
                future_work=[]
            )
        )
