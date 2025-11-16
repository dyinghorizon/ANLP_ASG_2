# 🎭 Julius Caesar RAG System

An Expert Shakespearean Scholar powered by Retrieval-Augmented Generation (RAG) for Shakespeare's "The Tragedy of Julius Caesar."

## 🎯 Features

- **Expert Analysis**: Provides scholarly, cited answers about Julius Caesar
- **Full Play Coverage**: All 18 scenes indexed and searchable
- **Smart Retrieval**: Uses semantic search with BGE embeddings
- **Interactive UI**: Clean Streamlit interface
- **RESTful API**: FastAPI backend with auto-documentation
- **Containerized**: Fully Dockerized application

## 🏗️ Architecture
```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Streamlit  │─────▶│   FastAPI   │─────▶│  ChromaDB   │
│  Frontend   │      │   Backend   │      │ Vector DB   │
│  (Port 8501)│      │  (Port 8000)│      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                            │
                            ▼
                     ┌─────────────┐
                     │   Gemini    │
                     │  2.0 Flash  │
                     └─────────────┘
```

### Components

- **Embedding Model**: BAAI/bge-base-en-v1.5
- **LLM**: Google Gemini 2.0 Flash Exp
- **Vector Database**: ChromaDB (Persistent)
- **Backend Framework**: FastAPI
- **Frontend**: Streamlit

### Data Statistics

- **Total Chunks**: 89 unique chunks
- **Scene Chunks**: 18 (one per scene)
- **Soliloquy Chunks**: 71 (important speeches)
- **Coverage**: All 5 Acts, 18 Scenes

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Google API Key (for Gemini)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ANLP_ASG_2
```

2. **Create `.env` file**
```bash
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

3. **Build and run with Docker**
```bash
docker-compose up --build
```

4. **Access the application**
- **Frontend UI**: http://localhost:8501
- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health

## 📚 API Endpoints

### POST `/query`
Query the RAG system

**Request:**
```json
{
  "query": "How does Caesar first enter the play?",
  "top_k": 5,
  "include_sources": true
}
```

**Response:**
```json
{
  "answer": "Caesar first enters the play in Act 1, Scene 2...",
  "sources": [
    {
      "chunk_id": "1",
      "text": "...",
      "act": 1,
      "scene": 2,
      "chunk_type": "scene",
      "similarity": 0.85
    }
  ],
  "metadata": {
    "num_sources_used": 5,
    "query_length": 35
  }
}
```

### GET `/health`
Check API health status

### GET `/stats`
Get collection statistics

## 🛠️ Development

### Run locally (without Docker)
```bash
# Install dependencies
pip install -r requirements.txt

# Start backend
uvicorn main:app --reload

# Start frontend (in another terminal)
streamlit run frontend.py
```

### Docker Commands
```bash
# Build and start
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild
docker-compose build --no-cache
```

## 📁 Project Structure
```
ANLP_ASG_2/
├── Data/                           # Processed data files
│   ├── julius_caesar_chunks.jsonl
│   ├── julius_caesar_structured.jsonl
│   └── julius_caesar_clean.txt
├── db/                             # ChromaDB database
├── main.py                         # FastAPI backend
├── frontend.py                     # Streamlit UI
├── A2_cleaning.py                  # ETL pipeline
├── A2_indexing.py                  # Vector indexing
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker image definition
├── docker-compose.yml              # Multi-container setup
├── .env                            # Environment variables
├── .dockerignore                   # Docker ignore rules
└── README.md                       # This file
```

## 🧪 Testing

### Test the API
```bash
# Health check
curl http://localhost:8000/health

# Sample query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Who killed Caesar?",
    "top_k": 3,
    "include_sources": true
  }'
```

### Example Questions

- How does Caesar first enter the play?
- What does the Soothsayer warn Caesar about?
- Why did Brutus join the conspiracy?
- What is the context of "Et tu, Brute?"
- How does Antony's funeral speech manipulate the crowd?
- What are Brutus's internal conflicts?

## 🔧 Configuration

### Environment Variables

- `GOOGLE_API_KEY`: Your Google Gemini API key (required)
- `API_URL`: Backend URL for frontend (default: http://localhost:8000)

### Customization

Edit `main.py` to:
- Change the system prompt
- Adjust temperature
- Modify retrieval parameters
- Add metadata filters

## 📊 Performance

- **Average Query Time**: 2-5 seconds
- **Embedding Dimension**: 768
- **Max Tokens**: 2048
- **Temperature**: 0.2 (for consistent answers)

## 🐛 Troubleshooting

### API won't start
- Check `.env` file exists with valid `GOOGLE_API_KEY`
- Ensure `Data/` and `db/` folders exist
- Check port 8000 is not in use

### Frontend can't connect
- Verify API is running: `curl http://localhost:8000/health`
- Check `API_URL` environment variable
- Ensure both containers are on same network

### Docker build fails
- Clear cache: `docker-compose build --no-cache`
- Check disk space
- Verify all files are present

## 📝 Assignment Details

**Course**: Advanced NLP  
**Assignment**: 2 - RAG System  
**Institution**: [Your Institution]  
**Date**: November 2025

## 📄 License

This project is for educational purposes.

## 🙏 Acknowledgments

- Shakespeare's text from Folger Shakespeare Library
- Embeddings: BAAI/bge-base-en-v1.5
- LLM: Google Gemini 2.0 Flash
- Vector DB: ChromaDB
