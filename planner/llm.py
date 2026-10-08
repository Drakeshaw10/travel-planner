"""LLM client for any OpenAI-compatible chat API (currently Google Gemini).

The provider is chosen entirely by secrets: LLM_BASE_URL, LLM_MODEL and
LLM_API_KEY. Switching provider (Hugging Face router, Gemini, a local
llama.cpp server) needs no code change, only different secret values.
"""

import streamlit as st
from langchain_openai import ChatOpenAI

# Only the most recent messages go to the model, to bound cost and latency.
MAX_HISTORY = 20


@st.cache_resource
def get_llm() -> ChatOpenAI:
    """Create the chat model once per server process and reuse it on every rerun."""
    return ChatOpenAI(
        base_url=st.secrets["LLM_BASE_URL"],
        api_key=st.secrets["LLM_API_KEY"],
        model=st.secrets["LLM_MODEL"],
        temperature=0.7,
        streaming=True,
        stream_usage=True,  # token counts arrive on the last chunk; logged to `usage` in Phase 2
        timeout=60,
        max_retries=2,
    )
