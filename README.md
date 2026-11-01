# Toronto Travel RAG Assistant — Free LLM Edition

This version keeps the original Toronto travel-guide RAG use case but removes the required OpenAI and Pinecone dependencies. Retrieval embeddings run locally using Sentence Transformers; choose one of three answer-generation providers in the Streamlit sidebar.

## Supported LLM providers

1. **OpenRouter free models** — hosted API; requires an OpenRouter key and is subject to free-model rate limits and availability.
2. **Google Gemini API free tier** — hosted API; requires a Gemini API key and is subject to Google's current model availability and quotas.
3. **Ollama local** — runs a model on your own computer; no hosted LLM API key is required, but you must install Ollama and download a model.

## Setup

Use Python 3.10 or newer.

```bash
python -m venv .venv
```

Activate the environment:

- Windows: `.venv\\Scripts\\activate`
- macOS/Linux: `source .venv/bin/activate`

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your local environment file by copying `.env.example` to `.env`, then add the API key for your selected hosted provider. Do not upload `.env` or commit it to Git.

- OpenRouter key: https://openrouter.ai/settings/keys
- Gemini key: https://aistudio.google.com/apikey
- Ollama: https://ollama.com

For Ollama, install and start Ollama, then download a small model, for example:

```bash
ollama pull qwen2.5:3b
```

Run the app from the project root:

```bash
streamlit run src/streamlitMain.py
```

The first run downloads `sentence-transformers/all-MiniLM-L6-v2` for local retrieval embeddings. Internet access is needed for this initial download. The downloaded model is separate from the selected LLM provider.

## Project structure

```text
free_llm_rag_project/
├── .env.example
├── README.md
├── requirements.txt
└── src/
    ├── RAG_ChatBot.py
    ├── streamlitMain.py
    └── materials/
        ├── torontoTravelAssistant.txt
        └── torontoTravelAssistant.docx
```

## Notes

- The app retrieves relevant text chunks from the Toronto guide, then supplies those chunks to the chosen LLM.
- Model IDs and free-tier quotas can change. If a model is no longer available, update its ID in the sidebar using the provider's current model list.
- The local Ollama option requires enough RAM/CPU/GPU resources for the model you choose.
- API keys are secrets. Keep them in `.env`, not in source code, screenshots, or shared ZIP files.
