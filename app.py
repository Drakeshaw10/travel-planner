"""Moody Trip Planner: Phase 1 streaming chat page."""

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from planner.llm import MAX_HISTORY, get_llm

SYSTEM_PROMPT = (
    "You are a warm, curious travel companion for people in India who don't know "
    "where they want to go. Ask one short, friendly question at a time about their "
    "mood and preferences. Do not suggest destinations yet."
)
GREETING = (
    "Hi! Let's find you a trip without you having to pick a place first. "
    "To start: right now, would you rather hear waves or birdsong?"
)

st.set_page_config(page_title="Moody Trip Planner", page_icon="🧭")
st.title("Moody Trip Planner")
st.caption("Not sure where to go? Let's figure it out together.")

if "messages" not in st.session_state:
    st.session_state.messages = [AIMessage(GREETING)]

with st.sidebar:
    if st.button("New trip"):
        st.session_state.messages = [AIMessage(GREETING)]
        st.rerun()

for msg in st.session_state.messages:
    role = "user" if isinstance(msg, HumanMessage) else "assistant"
    with st.chat_message(role):
        st.markdown(msg.content)

if prompt := st.chat_input("Type your answer..."):
    st.session_state.messages.append(HumanMessage(prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            recent = st.session_state.messages[-MAX_HISTORY:]
            history = [SystemMessage(SYSTEM_PROMPT), *recent]
            reply = st.write_stream(chunk.content for chunk in get_llm().stream(history))
        except Exception as exc:
            # Drop the unanswered message so the user can simply try again.
            st.session_state.messages.pop()
            st.error(f"The model call failed: {exc}")
            st.stop()

    st.session_state.messages.append(AIMessage(reply))
