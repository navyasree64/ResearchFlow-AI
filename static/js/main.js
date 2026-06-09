document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('analyze-form');
    if (!form) return;

    const analyzeBtn = document.getElementById('analyze-btn');
    const loadingState = document.getElementById('loading-state');
    const resultsArea = document.getElementById('results-area');
    const urlWarning = document.getElementById('url-warning');

    // Known research domains for client-side hint
    const RESEARCH_DOMAINS = [
        'arxiv.org', 'pubmed.ncbi.nlm.nih.gov', 'ncbi.nlm.nih.gov',
        'doi.org', 'dx.doi.org', 'ieee.org', 'ieeexplore.ieee.org',
        'acm.org', 'dl.acm.org', 'springer.com', 'nature.com',
        'sciencedirect.com', 'researchgate.net', 'biorxiv.org',
        'medrxiv.org', 'plos.org', 'wiley.com', 'frontiersin.org',
        'tandfonline.com', 'oup.com', 'semanticscholar.org', 'jstor.org',
        'ssrn.com', 'pmc.ncbi.nlm.nih.gov', 'cell.com', 'science.org',
        'jamanetwork.com', 'bmj.com', 'thelancet.com', 'nejm.org',
        'mdpi.com', 'hindawi.com', 'scholar.google.com', 'hal.science',
        'openreview.net', 'paperswithcode.com'
    ];

    function isResearchUrl(url) {
        try {
            const host = new URL(url).hostname.replace(/^www\./, '');
            return RESEARCH_DOMAINS.some(d => host === d || host.endsWith('.' + d));
        } catch { return false; }
    }

    // Real-time URL hint as user types
    document.getElementById('urls').addEventListener('input', function() {
        const urls = this.value.split('\n').map(u => u.trim()).filter(Boolean);
        const nonResearch = urls.filter(u => u && !isResearchUrl(u));
        if (nonResearch.length > 0) {
            urlWarning.textContent = `⚠️ Possibly not a research source: ${nonResearch[0]}`;
            urlWarning.style.display = 'block';
        } else {
            urlWarning.style.display = 'none';
        }
    });

    const STAGE_LABELS = {
        checking: '🔍 Checking URL…',
        scraping: '📄 Scraping content…',
        extracting: '🧠 Extracting with AI…',
        synthesizing: '📊 Synthesizing research summary…',
    };
    const STATUS_ICONS = { success: '✅', failed: '❌', skipped: '⏭️' };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const topic = document.getElementById('topic').value.trim();
        const urlsRaw = document.getElementById('urls').value;
        const urls = urlsRaw.split('\n').filter(u => u.trim() !== '');

        if (urls.length === 0) {
            alert("Please enter at least one research paper URL.");
            return;
        }

        // Reset & show progress UI
        analyzeBtn.disabled = true;
        form.style.opacity = '0.5';
        loadingState.classList.remove('hidden');
        resultsArea.classList.add('hidden');
        const banner = document.getElementById('error-banner');
        if (banner) banner.innerHTML = '';

        const progressStage = document.getElementById('progress-stage');
        const progressCounter = document.getElementById('progress-counter');
        const progressBar = document.getElementById('progress-bar');
        const progressLog = document.getElementById('progress-log');
        progressStage.textContent = 'Starting analysis…';
        progressCounter.textContent = '';
        progressBar.style.width = '0%';
        progressLog.innerHTML = '';

        try {
            const response = await fetch('/api/analyze_stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic, urls })
            });

            if (!response.ok) {
                const errData = await response.json();
                alert('Error: ' + (errData.error || 'Failed to start analysis.'));
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    let event;
                    try { event = JSON.parse(line.slice(6)); } catch { continue; }

                    if (event.type === 'progress') {
                        const pct = Math.round((event.current / event.total) * (event.stage === 'synthesizing' ? 100 : 90));
                        progressBar.style.width = pct + '%';
                        progressCounter.textContent = `${event.current} of ${event.total}`;
                        const shortUrl = event.url ? new URL(event.url).pathname.slice(0, 40) : '';
                        progressStage.textContent = (STAGE_LABELS[event.stage] || event.stage) + (shortUrl ? ` ${shortUrl}` : '');

                    } else if (event.type === 'url_status') {
                        const icon = STATUS_ICONS[event.status] || '•';
                        const shortUrl = event.url.length > 60 ? event.url.slice(0, 57) + '…' : event.url;
                        progressLog.innerHTML += `<div>${icon} <span style="opacity:0.6">${shortUrl}</span> — ${event.message}</div>`;
                        progressLog.scrollTop = progressLog.scrollHeight;

                    } else if (event.type === 'complete') {
                        progressBar.style.width = '100%';
                        progressStage.textContent = 'Done!';

                        if (event.summary) {
                            renderResults(event.topic || topic || 'Analyzed Papers', event.summary, event.new_papers);
                            // Show partial failures
                            if (event.failed && event.failed.length > 0) {
                                const names = event.failed.map(f => `• ${f.reason}`).join('<br>');
                                let fbanner = document.getElementById('error-banner');
                                if (!fbanner) {
                                    fbanner = document.createElement('div');
                                    fbanner.id = 'error-banner';
                                    document.querySelector('.analyze-section').after(fbanner);
                                }
                                fbanner.innerHTML = `<div style="background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.35);border-radius:10px;padding:14px 18px;margin-top:12px;font-size:0.85em;color:#fcd34d;">⚠️ Some URLs were skipped:<br>${names}</div>`;
                            }
                        } else if (event.failed?.length || event.rejected?.length) {
                            // All failed — show error banner
                            const allFailed = [...(event.failed || []), ...(event.rejected || [])];
                            let html = `<div style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.4);border-radius:10px;padding:18px 22px;margin-top:20px;font-size:0.9em;line-height:1.7;">`;
                            html += `<strong style="color:#f87171;">❌ No papers could be analyzed.</strong><br><br>`;
                            allFailed.forEach(f => {
                                html += `<div style="margin-bottom:10px;"><span style="opacity:0.6;word-break:break-all;">${f.url}</span><br><span style="color:#fca5a5;">${f.reason}</span></div>`;
                            });
                            html += `<div style="margin-top:12px;padding-top:12px;border-top:1px solid rgba(239,68,68,0.25);color:#fcd34d;">💡 Use open-access sources like arXiv, PubMed PMC, bioRxiv, or medRxiv for best results.</div></div>`;
                            let ebanner = document.getElementById('error-banner');
                            if (!ebanner) {
                                ebanner = document.createElement('div');
                                ebanner.id = 'error-banner';
                                document.querySelector('.analyze-section').after(ebanner);
                            }
                            ebanner.innerHTML = html;
                            ebanner.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        } else {
                            alert('Papers may already be in Memento memory. Check the Memento Database tab.');
                        }
                    }
                }
            }

        } catch (error) {
            console.error(error);
            alert("Network error occurred.");
        } finally {
            analyzeBtn.disabled = false;
            form.style.opacity = '1';
            loadingState.classList.add('hidden');
        }
    });

    function renderResults(topic, summary, newPapers) {
        document.getElementById('result-topic').textContent = topic;
        
        // Main Summary
        document.getElementById('res-summary').innerHTML = `<p>${summary.summary}</p>`;
        
        // Novel Contributions
        const novelHtml = summary.novel_contributions.map(c => 
            `<div class="finding-pill"><span class="pill-icon">&rarr;</span><div>${c}</div></div>`
        ).join('');
        document.getElementById('res-novel').innerHTML = novelHtml;
        
        // Open Questions
        const qHtml = summary.open_questions.map(q => 
            `<div class="finding-pill"><span class="pill-icon question">?</span><div>${q}</div></div>`
        ).join('');
        document.getElementById('res-questions').innerHTML = qHtml;
        
        // Comparison
        document.getElementById('res-comparison').innerHTML = `<p>${summary.conflicts_or_agreements}</p>`;
        
        // Trajectory
        document.getElementById('res-trajectory').innerHTML = `<p>${summary.field_trajectory}</p>`;
        
        // Key Insights from individual papers (combining core findings)
        let insightsHtml = '';
        newPapers.forEach(paper => {
            if (paper.insights && paper.insights.core_findings) {
                paper.insights.core_findings.forEach(finding => {
                    insightsHtml += `<div class="finding-pill"><span class="pill-icon">&rarr;</span><div>${finding} <br><small class="card-meta" style="margin-bottom:0;opacity:0.7;">— ${paper.title}</small></div></div>`;
                });
            }
        });
        document.getElementById('res-insights').innerHTML = insightsHtml;
        
        // Show results
        resultsArea.classList.remove('hidden');
        resultsArea.scrollIntoView({ behavior: 'smooth' });
        
        // Update metric counter if present
        const metricEl = document.querySelector('.metric-value');
        if (metricEl) {
            // A bit of a hack: just increment by the number of new papers for immediate visual feedback
            const current = parseInt(metricEl.textContent);
            metricEl.textContent = current + newPapers.length;
        }
    }
});
