# Demo Walkthrough — Agentic Toronto Travel Assistant

## Demo purpose
Show that the backend performs agent-like steps beyond calling an LLM: intent routing, semantic retrieval, evidence checking, optional LLM synthesis, and trace display.

## Demo A: offline tool demonstration (no provider API key)
1. Run `streamlit run src/streamlitMain.py`.
2. Enable **Offline demo mode (no LLM API call)** in the sidebar.
3. Click **Try: 3-day itinerary**.
4. Explain the trace in this order:
   - request received;
   - intent routed to `itinerary_planning`;
   - `retrieve_knowledge` searches the local travel guide;
   - `validate_context` checks evidence quality;
   - offline mode returns retrieved excerpts instead of generating an LLM answer.
5. Point out the retrieved chunk IDs and similarity scores.

Expected behavior: the app displays two relevant guide excerpts and the execution trace. Similarity scores vary by embedding-model version and should not be quoted as a benchmark.

## Demo B: full RAG answer with a free/provider model
1. Add a valid provider key to `.env`, or install Ollama and run `ollama pull qwen2.5:3b`.
2. Disable Offline demo mode.
3. Select the configured provider and model.
4. Ask: `Create a 3-day itinerary for Toronto.`
5. Show the generated answer and expand the agent trace.

## Suggested presentation narration
"This is not only an LLM wrapper. First, the agent classifies the request, then a retrieval tool searches our local Toronto guide. A context validator checks whether useful evidence was found. The selected LLM then writes an answer grounded in that evidence, and the response validator checks for an empty output. The UI exposes the trace so we can inspect how the answer was produced."

## Deployment/demo status
The offline and provider-backed demos are designed to run locally. A live public demo has **not** been published from this workspace. Once deployment is completed on Streamlit Community Cloud, replace this note with the real URL and actual deployment date.
