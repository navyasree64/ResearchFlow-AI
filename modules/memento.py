import chromadb
import json
import hashlib
from typing import List, Dict, Any, Optional
from .schemas import ResearchPaper

PERSIST_DIR = "./memento_data"

class MementoDB:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=PERSIST_DIR)
        self.collection = self.client.get_or_create_collection(
            name="research_papers",
            metadata={"hnsw:space": "cosine"}
        )
        self.summary_collection = self.client.get_or_create_collection(
            name="evolving_summaries"
        )

    def _url_id(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def paper_exists(self, url: str) -> bool:
        result = self.collection.get(ids=[self._url_id(url)])
        return bool(result and result.get("ids"))

    def count(self) -> int:
        return self.collection.count()

    def save_paper(self, paper: ResearchPaper):
        """Embed and store a paper's relevant text with full metadata."""
        pid = self._url_id(paper.url)
        document = (
            f"Title: {paper.title}\n"
            f"Abstract: {paper.abstract}\n"
            f"Findings: {' | '.join(paper.insights.core_findings)}\n"
            f"Keywords: {' '.join(paper.insights.keywords)}\n"
            f"Methodology: {paper.insights.methodology}"
        )
        metadata = {
            "title": paper.title,
            "url": paper.url,
            "authors": json.dumps(paper.authors),
            "publication_date": paper.publication_date or "",
            "journal": paper.journal or "",
            "doi": paper.doi or "",
            "abstract": paper.abstract,
            "full_summary": paper.full_summary or "",
            "methodology": paper.insights.methodology,
            "core_findings": json.dumps(paper.insights.core_findings),
            "limitations": json.dumps(paper.insights.limitations),
            "keywords": json.dumps(paper.insights.keywords),
            "future_work": json.dumps(paper.insights.future_work),
            "added_at": paper.added_at,
        }
        self.collection.upsert(ids=[pid], documents=[document], metadatas=[metadata])

    def get_papers_paginated(self, page: int = 1, per_page: int = 10) -> dict:
        """Return a paginated slice of stored papers plus pagination metadata."""
        all_papers = self.get_all_papers()
        total = len(all_papers)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = start + per_page
        return {
            "papers": all_papers[start:end],
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        }

    def get_all_papers(self) -> List[Dict[str, Any]]:
        """Return every stored paper as a rich dict for UI rendering."""
        results = self.collection.get(include=["metadatas", "documents"])
        papers = []
        if not results or not results.get("ids"):
            return papers
        for i, pid in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            papers.append({
                "id": pid,
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
                "authors": json.loads(meta.get("authors", "[]")),
                "publication_date": meta.get("publication_date", ""),
                "journal": meta.get("journal", ""),
                "doi": meta.get("doi", ""),
                "abstract": meta.get("abstract", ""),
                "full_summary": meta.get("full_summary", ""),
                "methodology": meta.get("methodology", ""),
                "core_findings": json.loads(meta.get("core_findings", "[]")),
                "limitations": json.loads(meta.get("limitations", "[]")),
                "keywords": json.loads(meta.get("keywords", "[]")),
                "future_work": json.loads(meta.get("future_work", "[]")),
                "added_at": meta.get("added_at", "Unknown"),
                "document": results["documents"][i] if results.get("documents") else "",
            })
        papers.sort(key=lambda x: x.get("added_at", "1970-01-01 00:00:00"), reverse=True)
        return papers

    def get_papers_paginated(self, page: int = 1, per_page: int = 10):
        """Return a page of papers for paginated display."""
        all_papers = self.get_all_papers()
        total = len(all_papers)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = start + per_page
        return {
            "papers": all_papers[start:end],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        }

    def get_paper_by_id(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single paper by its ID."""
        results = self.collection.get(ids=[paper_id], include=["metadatas", "documents"])
        if not results or not results.get("ids"):
            return None
        meta = results["metadatas"][0]
        return {
            "id": paper_id,
            "title": meta.get("title", ""),
            "url": meta.get("url", ""),
            "authors": json.loads(meta.get("authors", "[]")),
            "publication_date": meta.get("publication_date", ""),
            "journal": meta.get("journal", ""),
            "doi": meta.get("doi", ""),
            "abstract": meta.get("abstract", ""),
            "full_summary": meta.get("full_summary", ""),
            "methodology": meta.get("methodology", ""),
            "core_findings": json.loads(meta.get("core_findings", "[]")),
            "limitations": json.loads(meta.get("limitations", "[]")),
            "keywords": json.loads(meta.get("keywords", "[]")),
            "future_work": json.loads(meta.get("future_work", "[]")),
            "added_at": meta.get("added_at", "Unknown"),
            "document": results["documents"][0] if results.get("documents") else "",
        }

    def retrieve_context_for_topic(self, topic: str, n_results: int = 6) -> str:
        """Semantic vector search to pull relevant past papers as context."""
        total = self.collection.count()
        if total == 0:
            return "No prior knowledge exists in the Memento database yet."
        results = self.collection.query(
            query_texts=[topic],
            n_results=min(n_results, total),
            include=["documents", "metadatas"]
        )
        if not results or not results.get("documents") or not results["documents"][0]:
            return "No prior knowledge found matching this topic."
        blocks = []
        for i in range(len(results["documents"][0])):
            doc = results["documents"][0][i]
            meta = results["metadatas"][0][i]
            blocks.append(
                f"[Past Paper #{i+1}]\n"
                f"Title: {meta.get('title')}\n"
                f"Published: {meta.get('publication_date')} | {meta.get('journal')}\n"
                f"Content: {doc}\n"
            )
        return "\n---\n".join(blocks)

    def _summary_id(self, topic: str, timestamp: str) -> str:
        return hashlib.md5(f"{topic}_{timestamp}".encode()).hexdigest()

    def save_summary(self, topic: str, summary, new_papers_count: int):
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sid = self._summary_id(topic, timestamp)
        metadata = {
            "topic": topic,
            "created_at": timestamp,
            "summary": summary.summary,
            "novel_contributions": json.dumps(summary.novel_contributions),
            "conflicts_or_agreements": summary.conflicts_or_agreements,
            "open_questions": json.dumps(summary.open_questions),
            "field_trajectory": summary.field_trajectory,
            "new_papers_count": new_papers_count
        }
        self.summary_collection.upsert(ids=[sid], documents=[topic], metadatas=[metadata])

    def get_all_summaries(self) -> List[Dict[str, Any]]:
        results = self.summary_collection.get(include=["metadatas"])
        summaries = []
        if not results or not results.get("ids"):
            return summaries
        for i, sid in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            summaries.append({
                "id": sid,
                "topic": meta.get("topic", "Unknown Topic"),
                "created_at": meta.get("created_at", ""),
                "summary": meta.get("summary", ""),
                "novel_contributions": json.loads(meta.get("novel_contributions", "[]")),
                "conflicts_or_agreements": meta.get("conflicts_or_agreements", ""),
                "open_questions": json.loads(meta.get("open_questions", "[]")),
                "field_trajectory": meta.get("field_trajectory", ""),
                "new_papers_count": meta.get("new_papers_count", 0)
            })
        summaries.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return summaries

    def get_summary_by_id(self, summary_id: str) -> Optional[Dict[str, Any]]:
        results = self.summary_collection.get(ids=[summary_id], include=["metadatas"])
        if not results or not results.get("ids"):
            return None
        meta = results["metadatas"][0]
        return {
            "id": summary_id,
            "topic": meta.get("topic", "Unknown Topic"),
            "created_at": meta.get("created_at", ""),
            "summary": meta.get("summary", ""),
            "novel_contributions": json.loads(meta.get("novel_contributions", "[]")),
            "conflicts_or_agreements": meta.get("conflicts_or_agreements", ""),
            "open_questions": json.loads(meta.get("open_questions", "[]")),
            "field_trajectory": meta.get("field_trajectory", ""),
            "new_papers_count": meta.get("new_papers_count", 0)
        }
