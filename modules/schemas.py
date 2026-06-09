from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ExtractedInsights(BaseModel):
    core_findings: List[str] = Field(default=[], description="Main findings or results from the study.")
    methodology: str = Field(default="", description="Description of the study's methodology.")
    limitations: List[str] = Field(default=[], description="The study's stated limitations.")
    keywords: List[str] = Field(default=[], description="Key medical/academic terms from the paper.")
    future_work: List[str] = Field(default=[], description="Suggestions or directions for future research mentioned in the paper.")

class ResearchPaper(BaseModel):
    title: str
    authors: Optional[List[str]] = Field(default=[])
    publication_date: Optional[str] = Field(default="")
    journal: Optional[str] = Field(default="")
    doi: Optional[str] = Field(default="")
    url: str
    abstract: str
    full_summary: Optional[str] = Field(default="", description="A 2-3 paragraph full-length narrative summary of the paper.")
    added_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="Timestamp when this paper was added to Memento. Auto-set on creation."
    )
    insights: ExtractedInsights

class EvolvingSummary(BaseModel):
    summary: str = Field(description="Narrative summary analyzing past and new research combined.")
    novel_contributions: List[str] = Field(description="What the new research specifically adds over existing knowledge.")
    conflicts_or_agreements: str = Field(description="How the new research conflicts or agrees with past knowledge.")
    open_questions: List[str] = Field(default=[], description="Questions in the field still unanswered based on new and old research.")
    field_trajectory: str = Field(default="", description="Where the field appears to be heading based on the full body of research.")
