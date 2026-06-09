import os
from dotenv import load_dotenv

load_dotenv()

class WebCrawler:
    def __init__(self):
        api_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.ready = bool(api_key and api_key.strip() not in ("", "your_firecrawl_api_key_here"))
        self.api_key = api_key
        self.app = None
        self._init_error = None

        if self.ready:
            try:
                # firecrawl-py v4.x uses `Firecrawl` class (not `FirecrawlApp`)
                from firecrawl import Firecrawl
                self.app = Firecrawl(api_key=api_key)
                self._client_type = "v4"
            except ImportError:
                try:
                    # Fallback for older firecrawl-py v1.x
                    from firecrawl import FirecrawlApp
                    self.app = FirecrawlApp(api_key=api_key)
                    self._client_type = "v1"
                except Exception as e:
                    self.ready = False
                    self._init_error = str(e)
            except Exception as e:
                self.ready = False
                self._init_error = str(e)

    def scrape_article(self, url: str) -> str:
        """Scrapes the URL using Firecrawl and returns the markdown text."""
        if not self.ready:
            return f"ERROR:FIRECRAWL_KEY_MISSING:{self._init_error or ''}"

        try:
            if self._client_type == "v4":
                # firecrawl-py v4.x API: scrape(url, formats=[...])
                result = self.app.scrape(url, formats=["markdown"])
            else:
                # firecrawl-py v1.x API: scrape_url(url, params={...})
                # Using getattr to bypass static type checking for Pylint
                scrape_method = getattr(self.app, "scrape_url")
                result = scrape_method(url, params={"formats": ["markdown"]})

            # Handle object-style response (v4 returns ScrapeResponse with attributes)
            if hasattr(result, "markdown") and result.markdown:
                return result.markdown
            if hasattr(result, "content") and result.content:
                return result.content

            # Handle dict-style response (v1)
            if isinstance(result, dict):
                return (
                    result.get("markdown")
                    or result.get("content")
                    or result.get("text")
                    or str(result)
                )

            return str(result)

        except Exception as e:
            return f"ERROR:SCRAPE_FAILED:{e}"
