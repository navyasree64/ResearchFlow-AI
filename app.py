import os
from flask import Flask, render_template, request, jsonify, Response
import json as json_module

# Load environment
from dotenv import load_dotenv
load_dotenv()

from modules.crawler import WebCrawler
from modules.extractor import InsightExtractor
from modules.memento import MementoDB
from modules.synthesizer import KnowledgeSynthesizer
import google.generativeai as genai

app = Flask(__name__)

# Initialize singletons (for simplicity in this example)
# In production, you might want to handle this differently.
crawler = WebCrawler()
extractor = InsightExtractor()
memento = MementoDB()
synthesizer = KnowledgeSynthesizer()

# Initialize Gemini AI for chatbot using same model selection as extractor
gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    
    # Use the same model selection logic as the extractor
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
        return GEMINI_MODEL_CANDIDATES[0]
    
    model_name = find_working_gemini_model()
    chat_model = genai.GenerativeModel(model_name)
    print(f"Chatbot using model: {model_name}")
else:
    chat_model = None
    print("Warning: GEMINI_API_KEY not found. Chatbot functionality will be disabled.")

@app.context_processor
def inject_memento_count():
    # Makes memento_count available to all templates
    return dict(memento_count=memento.count())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/memento')
def memento_view():
    page = request.args.get('page', 1, type=int)
    paginated = memento.get_papers_paginated(page=page, per_page=10)
    return render_template('memento.html', **paginated)

@app.route('/paper/<paper_id>')
def view_paper(paper_id):
    paper = memento.get_paper_by_id(paper_id)
    if not paper:
        return "Paper not found", 404
    return render_template('paper.html', paper=paper)

@app.route('/chat')
def chat_page():
    return render_template('chat.html')

@app.route('/summaries')
def summaries_view():
    summaries = memento.get_all_summaries()
    return render_template('summaries.html', summaries=summaries)

@app.route('/summary/<summary_id>')
def view_summary(summary_id):
    summary = memento.get_summary_by_id(summary_id)
    if not summary:
        return "Summary not found", 404
    return render_template('summary_detail.html', summary=summary)

@app.route('/api/chat', methods=['POST'])
def chat():
    if not chat_model:
        return jsonify({"error": "Chatbot not available - GEMINI_API_KEY not configured"}), 503
    
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({"error": "Message is required"}), 400
    
    try:
        # Get relevant context from Memento database based on the user's query
        context = memento.retrieve_context_for_topic(user_message, n_results=3)
        
        # Strict research-only system prompt
        system_prompt = f"""You are ResearchFlow AI Assistant — a specialist AI for academic and scientific research ONLY.

Your STRICT rules:
1. ONLY answer questions about: research papers, scientific studies, academic topics, methodology, data analysis, literature reviews, citations, and the specific papers stored in this database.
2. If the user asks about ANYTHING unrelated to academic research (e.g. cooking, sports, entertainment, general knowledge, coding unrelated to research, personal advice), you MUST respond ONLY with:
   "I'm specialised for academic research only. Please ask me about research papers, scientific topics, or the papers in this database."
3. Never break character. Never pretend to be a general assistant.
4. Be concise, precise, and cite paper titles from context when relevant.

Context from Memento research database (use this to answer paper-specific questions):
{context}
"""

        full_prompt = f"{system_prompt}\n\nUser: {user_message}\n\nAssistant:"
        response = chat_model.generate_content(full_prompt)
        
        return jsonify({
            "success": True,
            "response": response.text,
            "context_used": bool(context and context != "No prior knowledge exists in the Memento database yet.")
        })
        
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/api/analyze_stream', methods=['POST'])
def analyze_stream():
    """SSE endpoint that streams per-URL progress updates to the frontend."""
    data = request.json
    topic = (data.get('topic') or '').strip()
    urls = data.get('urls', [])

    if not urls:
        return jsonify({"error": "At least one URL is required"}), 400

    def generate():
        new_papers = []
        rejected_urls = []
        failed_urls = []
        skipped_urls = []
        valid_urls = [u.strip() for u in urls if u.strip()]
        total = len(valid_urls)

        for idx, url in enumerate(valid_urls):
            # Send progress event
            yield f"data: {json_module.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'url': url, 'stage': 'checking'})}\n\n"

            if memento.paper_exists(url):
                skipped_urls.append(url)
                yield f"data: {json_module.dumps({'type': 'url_status', 'url': url, 'status': 'skipped', 'message': 'Already in Memento'})}\n\n"
                continue

            # Stage: scraping
            yield f"data: {json_module.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'url': url, 'stage': 'scraping'})}\n\n"
            markdown_content = crawler.scrape_article(url)

            if markdown_content.startswith("ERROR:FIRECRAWL_KEY_MISSING"):
                failed_urls.append({"url": url, "reason": "Firecrawl API key is missing."})
                yield f"data: {json_module.dumps({'type': 'url_status', 'url': url, 'status': 'failed', 'message': 'Firecrawl API key missing'})}\n\n"
                continue
            if markdown_content.startswith("ERROR:SCRAPE_FAILED"):
                reason = markdown_content.replace("ERROR:SCRAPE_FAILED:", "", 1)
                if any(kw in reason.lower() for kw in ["403", "401", "paywall", "access denied", "login", "subscribe"]):
                    msg = "Paywall / login wall detected"
                else:
                    msg = f"Scrape failed: {reason[:120]}"
                failed_urls.append({"url": url, "reason": msg})
                yield f"data: {json_module.dumps({'type': 'url_status', 'url': url, 'status': 'failed', 'message': msg})}\n\n"
                continue

            # Stage: extracting with AI
            yield f"data: {json_module.dumps({'type': 'progress', 'current': idx + 1, 'total': total, 'url': url, 'stage': 'extracting'})}\n\n"
            paper = extractor.extract_paper_details(url, markdown_content)

            if paper.title.startswith("[ERROR]"):
                abstract_lower = paper.abstract.lower()
                if "not a research paper" in paper.abstract:
                    rejected_urls.append({"url": url, "reason": paper.abstract})
                    msg = "Not a research paper"
                elif "recaptcha" in abstract_lower or "login" in abstract_lower:
                    msg = "Access blocked (login wall / CAPTCHA)"
                    failed_urls.append({"url": url, "reason": msg})
                elif "404" in abstract_lower or "not found" in abstract_lower:
                    msg = "Page not found (404)"
                    failed_urls.append({"url": url, "reason": msg})
                else:
                    msg = f"Extraction failed: {paper.abstract[:120]}"
                    failed_urls.append({"url": url, "reason": msg})
                yield f"data: {json_module.dumps({'type': 'url_status', 'url': url, 'status': 'failed', 'message': msg})}\n\n"
            else:
                memento.save_paper(paper)
                new_papers.append(paper)
                yield f"data: {json_module.dumps({'type': 'url_status', 'url': url, 'status': 'success', 'message': paper.title})}\n\n"

        # Stage: synthesis
        nonlocal_topic = topic
        if not nonlocal_topic and new_papers:
            nonlocal_topic = ", ".join(p.title[:50] for p in new_papers[:2])

        summary_dict = None
        if new_papers:
            yield f"data: {json_module.dumps({'type': 'progress', 'current': total, 'total': total, 'url': '', 'stage': 'synthesizing'})}\n\n"
            past_context = memento.retrieve_context_for_topic(nonlocal_topic)
            evolving_summary = synthesizer.generate_evolving_summary(
                nonlocal_topic, past_context, new_papers
            )
            memento.save_summary(nonlocal_topic, evolving_summary, len(new_papers))
            summary_dict = {
                "summary": evolving_summary.summary,
                "novel_contributions": evolving_summary.novel_contributions,
                "conflicts_or_agreements": evolving_summary.conflicts_or_agreements,
                "open_questions": evolving_summary.open_questions,
                "field_trajectory": evolving_summary.field_trajectory,
            }

        # Final result event
        result = {
            "type": "complete",
            "success": True,
            "new_papers": [p.dict() for p in new_papers],
            "skipped": skipped_urls,
            "failed": failed_urls,
            "rejected": rejected_urls,
            "summary": summary_dict,
            "topic": nonlocal_topic,
        }
        yield f"data: {json_module.dumps(result)}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    topic = (data.get('topic') or '').strip()
    urls = data.get('urls', [])

    if not urls:
        return jsonify({"error": "At least one URL is required"}), 400

    new_papers = []
    rejected_urls = []   # non-research URLs
    failed_urls   = []   # scrape/paywall/other failures
    skipped_urls  = []   # already in Memento

    # Early check: no Firecrawl key means scraping will fail for every URL
    firecrawl_missing = not crawler.ready

    for url in urls:
        url = url.strip()
        if not url:
            continue

        if memento.paper_exists(url):
            skipped_urls.append(url)
            continue

        # 1. Scrape
        markdown_content = crawler.scrape_article(url)

        # Detect scrape-level failures before calling Gemini
        if markdown_content.startswith("ERROR:FIRECRAWL_KEY_MISSING"):
            failed_urls.append({
                "url": url,
                "reason": "❌ Firecrawl API key is missing. Add FIRECRAWL_API_KEY to your .env file to enable scraping."
            })
            continue
        if markdown_content.startswith("ERROR:SCRAPE_FAILED"):
            reason = markdown_content.replace("ERROR:SCRAPE_FAILED:", "", 1)
            # Common paywall / login-wall detection
            if any(kw in reason.lower() for kw in ["403", "401", "paywall", "access denied", "login", "subscribe"]):
                failed_urls.append({
                    "url": url,
                    "reason": f"🔒 Paywall or login wall detected — this paper requires a subscription. Try an open-access version (e.g. arXiv, PubMed PMC, or ResearchGate)."
                })
            else:
                failed_urls.append({"url": url, "reason": f"⚠️ Scrape failed: {reason[:200]}"})
            continue

        # 2. Extract
        paper = extractor.extract_paper_details(url, markdown_content)

        # 3. Store or categorise
        if paper.title.startswith("[ERROR]"):
            abstract_lower = paper.abstract.lower()
            if "not a research paper" in paper.abstract:
                rejected_urls.append({"url": url, "reason": paper.abstract})
            elif "recaptcha" in abstract_lower or "login" in abstract_lower:
                failed_urls.append({
                    "url": url,
                    "reason": "🔒 Access blocked (login wall / CAPTCHA). The page requires authentication. Try an open-access mirror."
                })
            elif "404" in abstract_lower or "not found" in abstract_lower:
                failed_urls.append({"url": url, "reason": "❌ Page not found (404). Check the URL and try again."})
            else:
                failed_urls.append({"url": url, "reason": f"⚠️ Could not extract paper details: {paper.abstract[:200]}"})
        else:
            memento.save_paper(paper)
            new_papers.append(paper)

    # If all URLs were rejected as non-research, return a clear error immediately
    if rejected_urls and not new_papers and not failed_urls:
        return jsonify({
            "error": "None of the provided URLs are research papers.",
            "rejected": rejected_urls
        }), 422

    # If nothing succeeded at all — return detailed failure report
    if not new_papers and not skipped_urls:
        reasons_html = ""
        for f in (failed_urls + rejected_urls):
            reasons_html += f"• {f['url']}\n  → {f['reason']}\n"
        return jsonify({
            "error": "No papers could be analyzed.",
            "details": reasons_html or "Unknown error.",
            "failed": failed_urls,
            "rejected": rejected_urls,
            "tip": "IEEE and many journals are paywalled. Use open-access sources like arXiv (arxiv.org), PubMed PMC, bioRxiv, or medRxiv for best results."
        }), 422

    # Auto-derive topic from paper titles if not provided
    if not topic and new_papers:
        topic = ", ".join(p.title[:50] for p in new_papers[:2])

    # 4. Context Retrieval & Synthesis
    if new_papers:
        past_context = memento.retrieve_context_for_topic(topic)
        evolving_summary = synthesizer.generate_evolving_summary(
            topic, past_context, new_papers
        )

        # Save it to the database automatically
        memento.save_summary(topic, evolving_summary, len(new_papers))

        # Convert to dictionary for JSON response
        summary_dict = {
            "summary": evolving_summary.summary,
            "novel_contributions": evolving_summary.novel_contributions,
            "conflicts_or_agreements": evolving_summary.conflicts_or_agreements,
            "open_questions": evolving_summary.open_questions,
            "field_trajectory": evolving_summary.field_trajectory,
        }
    else:
        summary_dict = None

    # Return results (include any partial failures alongside successes)
    return jsonify({
        "success": True,
        "new_papers": [p.dict() for p in new_papers],
        "skipped": skipped_urls,
        "failed": failed_urls,
        "rejected": rejected_urls,
        "summary": summary_dict
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
