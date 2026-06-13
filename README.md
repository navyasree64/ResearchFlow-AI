# ResearchFlow AI 🧬

An intelligent research paper analysis and management system powered by AI. ResearchFlow AI helps researchers analyze, organize, and synthesize academic papers with advanced AI capabilities.

## ✨ Features

### 🔍 **Research Analysis**
- **Multi-paper Analysis**: Analyze multiple research papers simultaneously
- **AI-powered Extraction**: Automatically extract key insights, methodology, and findings
- **Intelligent Synthesis**: Generate evolving summaries across multiple papers
- **Semantic Search**: Find related papers using vector embeddings

### 🗂️ **Memento Database**
- **Vector Storage**: ChromaDB-powered semantic search and retrieval
- **Paper Organization**: Automatically categorize and store research papers
- **Deduplication**: Prevent re-analysis of previously processed papers
- **Context Retrieval**: Smart context-aware responses

### 🤖 **AI Assistant**
- **Interactive Chat**: Conversational AI assistant for research queries
- **Database Integration**: Chat with your research papers
- **Smart Responses**: Context-aware answers using your Memento database
- **Research Guidance**: Get help with methodology and analysis

### 🎨 **Modern UI**
- **Multiple Interfaces**: Streamlit, Flask web app, and FastAPI server
- **Clean Design**: Professional academic aesthetic
- **Light/Dark Themes**: Customizable interface themes
- **Responsive**: Mobile-friendly design

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- API Keys:
  - [Firecrawl API](https://www.firecrawl.dev/) (500 credits/month free)
  - [Google Gemini API](https://aistudio.google.com/) (free tier)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/sarvani10/ResearchFlow-AI.git
cd ResearchFlow-AI
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. **Run the application**

**Option 1: Flask Web App (Recommended)**
```bash
python app.py
```
Visit: http://127.0.0.1:5000

**Option 2: Streamlit App**
```bash
streamlit run main_app.py
```

**Option 3: FastAPI Server**
```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

## 📖 Usage Guide

### 1. **Analyze Research Papers**
- Navigate to "Analyze Research" in the sidebar
- Enter a research topic
- Add paper URLs (one per line)
- Click "Analyze Papers" to process

### 2. **Browse Memento Database**
- Access "Memento Database" in the sidebar
- View all analyzed papers
- Search and filter papers
- Click on papers for detailed view

### 3. **Chat with AI Assistant**
- Navigate to "💬 AI Assistant"
- Ask questions about your research papers
- Get methodology guidance
- Request paper recommendations

### 4. **View Past Analyses**
- Check "Past Analyses" for evolving summaries
- Review synthesis across multiple papers
- Track research trends over time

## 🏗️ Architecture

### **Backend Components**
- **WebCrawler**: Scrapes research papers from URLs
- **InsightExtractor**: Uses Gemini AI to extract structured insights
- **MementoDB**: Vector database for semantic search and storage
- **KnowledgeSynthesizer**: Generates evolving summaries

### **Frontend Options**
- **Flask App**: Full-featured web interface with chatbot
- **Streamlit App**: Interactive data science interface
- **FastAPI**: RESTful API for programmatic access

### **AI Models**
- **Primary**: Gemini 2.5 Flash Lite (auto-selected)
- **Fallback**: Multiple Gemini models with smart selection
- **Vector Embeddings**: ChromaDB for semantic similarity

## 🔧 Configuration

### Environment Variables (.env)
```env
FIRECRAWL_API_KEY=fc-your_firecrawl_api_key_here
GEMINI_API_KEY=AIzaSy-your_gemini_api_key_here
```

### Model Selection
The system automatically selects the best available Gemini model:
1. gemini-2.5-flash-lite
2. gemini-2.5-flash
3. gemini-2.0-flash
4. gemini-1.5-flash
5. gemini-flash-latest

## 📁 Project Structure

```
ResearchFlow-AI/
├── app.py                 # Flask web application
├── main_app.py            # Streamlit application
├── server.py              # FastAPI server
├── modules/               # Core functionality
│   ├── crawler.py         # Web scraping
│   ├── extractor.py       # AI extraction
│   ├── memento.py         # Vector database
│   ├── synthesizer.py     # Knowledge synthesis
│   └── schemas.py         # Data models
├── templates/             # Flask templates
├── static/                # CSS and JS assets
├── memento_data/          # ChromaDB storage
├── requirements.txt       # Python dependencies
└── .env.example          # Environment template
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 API Reference

### Flask Endpoints
- `GET /` - Main application interface
- `GET /chat` - AI assistant interface
- `GET /memento` - Paper database
- `POST /api/chat` - Chat with AI assistant
- `POST /api/analyze` - Analyze research papers

### FastAPI Endpoints
- `GET /docs` - Interactive API documentation
- `POST /api/analyze` - Research analysis API

## 🔍 Troubleshooting

### Common Issues

**"Chatbot not available" Error**
- Check your GEMINI_API_KEY in .env file
- Ensure the API key is valid and has quota

**"404 models/gemini-pro is not found"**
- The app automatically selects available models
- Restart the application if model selection fails

**Paper Analysis Fails**
- Verify Firecrawl API key is valid
- Check if URLs are accessible and not paywalled
- Ensure URLs point to research papers/articles

### Debug Mode
Flask app runs in debug mode by default. Check console output for detailed error messages.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Google Gemini](https://ai.google.dev/) for AI capabilities
- [Firecrawl](https://www.firecrawl.dev/) for web scraping
- [ChromaDB](https://www.trychroma.com/) for vector storage
- [Streamlit](https://streamlit.io/) for data science interface
- [Flask](https://flask.palletsprojects.com/) for web framework

## 📞 Support

- 📧 Email: [your-email@example.com]
- 🐛 Issues: [GitHub Issues](https://github.com/sarvani10/ResearchFlow-AI/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/sarvani10/ResearchFlow-AI/discussions)

---

**ResearchFlow AI** - Empowering researchers with intelligent paper analysis 🧬✨
