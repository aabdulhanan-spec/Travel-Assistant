import streamlit as st
from RAG_ChatBot import TravelAgent

st.set_page_config(page_title="Agentic Toronto Travel Assistant", page_icon="🧭", layout="wide")
st.title("🧭 Agentic Toronto Travel Assistant")
st.caption("A tool-using RAG agent: routes the request, retrieves guide evidence, checks context, then optionally calls an LLM.")

@st.cache_resource(show_spinner="Loading local embedding model and travel guide...")
def load_agent():
    return TravelAgent()

try:
    agent = load_agent()
except Exception as exc:
    st.error(f"Could not initialize the agent: {exc}")
    st.stop()

with st.sidebar:
    st.header("Agent controls")
    provider = st.selectbox("LLM provider", ["OpenRouter (free models)", "Google Gemini (free tier)", "Ollama (local)"])
    if provider == "OpenRouter (free models)":
        model = st.text_input("Model ID", value="openrouter/free", help="Use openrouter/free or a currently available model ending in :free.")
        st.markdown("[OpenRouter API keys](https://openrouter.ai/settings/keys)")
        st.caption("Free model availability and quotas can change.")
    elif provider == "Google Gemini (free tier)":
        model = st.text_input("Gemini model ID", value="gemini-2.5-flash")
        st.markdown("[Google AI Studio API key](https://aistudio.google.com/apikey)")
        st.caption("Free-tier limits depend on current Google terms.")
    else:
        model = st.text_input("Installed Ollama model", value="qwen2.5:3b")
        st.markdown("[Install Ollama](https://ollama.com)")
        st.code("ollama pull qwen2.5:3b", language="bash")
    top_k = st.slider("Knowledge chunks to retrieve", min_value=1, max_value=6, value=4)
    show_trace = st.toggle("Show agent execution trace", value=True)
    offline_demo = st.toggle("Offline demo mode (no LLM API call)", value=False, help="Runs routing, retrieval, and evidence checks, then displays excerpts instead of asking an LLM.")
    st.divider()
    st.caption("Knowledge source: src/materials/torontoTravelAssistant.txt")
    st.caption("Deployment status: local project; not yet published to a public URL.")

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "Hi! I'm an agentic Toronto travel assistant. Ask about attractions, food, transport, neighborhoods, or request an itinerary. I can show the backend tool trace too."
    }]

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("trace") and show_trace:
            with st.expander("Agent execution trace", expanded=False):
                for step in message["trace"]:
                    st.write(f"- {step}")
                if message.get("intent"):
                    st.caption(f"Intent: {message['intent']} · Provider: {message.get('provider', 'n/a')}")
                if message.get("sources"):
                    st.caption("Retrieved evidence")
                    for source in message["sources"][:3]:
                        st.write(f"Chunk {source['chunk_id']} · similarity {source['score']:.2f}")
                        st.code(source["text"][:450], language="text")

sample_col1, sample_col2, sample_col3 = st.columns(3)
with sample_col1:
    if st.button("Try: 3-day itinerary", use_container_width=True):
        st.session_state.pending_question = "Create a 3-day itinerary for Toronto."
with sample_col2:
    if st.button("Try: Toronto food areas", use_container_width=True):
        st.session_state.pending_question = "Compare food and dining areas in Toronto."
with sample_col3:
    if st.button("Try: transportation", use_container_width=True):
        st.session_state.pending_question = "How can I get around Toronto?"

pending = st.session_state.pop("pending_question", None)
question = st.chat_input("Ask about travelling to Toronto...") or pending
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Agent routing request → retrieving evidence → validating context → responding..."):
            try:
                history = st.session_state.messages[:-1]
                result = agent.run(
                    question,
                    provider=provider,
                    model=model.strip(),
                    top_k=top_k,
                    history=history,
                    offline_demo=offline_demo,
                )
                answer = result["answer"]
                st.markdown(answer)
                if show_trace:
                    with st.expander("Agent execution trace", expanded=True):
                        for step in result["trace"]:
                            st.write(f"- {step}")
                        st.caption(f"Intent: {result.get('intent', 'n/a')} · Provider: {result.get('provider', 'n/a')}")
                        for source in result.get("sources", [])[:3]:
                            st.write(f"Chunk {source['chunk_id']} · similarity {source['score']:.2f}")
            except Exception as exc:
                answer = f"**Could not complete the request.**\n\n{exc}"
                result = {"trace": ["Agent run failed; see error above."], "sources": [], "intent": "error", "provider": provider}
                st.error(answer)
    st.session_state.messages.append({
        "role": "assistant", "content": answer,
        "trace": result.get("trace", []), "sources": result.get("sources", []),
        "intent": result.get("intent"), "provider": result.get("provider", provider)
    })
