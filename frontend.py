"""
Simple Streamlit Frontend for Julius Caesar RAG API
"""

import streamlit as st
import requests
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Julius Caesar Scholar",
    page_icon="🎭",
    layout="wide"
)

st.title("🎭 Julius Caesar Expert Scholar")
st.markdown("*Ask questions about Shakespeare's Julius Caesar*")

with st.sidebar:
    st.header("Settings")
    top_k = st.slider("Number of sources", 1, 10, 5)
    include_sources = st.checkbox("Show sources", value=True)

    st.divider()
    st.markdown("### About")
    st.info("""
    This RAG system uses:
    - **Embeddings**: BGE-base-en-v1.5
    - **LLM**: Gemini 2.0 Flash
    - **Vector DB**: ChromaDB
    """)

query = st.text_area(
    "Your question:",
    placeholder="e.g., What does the Soothsayer warn Caesar about?",
    height=100
)

if st.button("Ask Scholar", type="primary"):
    if not query:
        st.warning("Please enter a question")
    else:
        with st.spinner("Consulting the Scholar..."):
            try:
                response = requests.post(
                    f"{API_URL}/query",
                    json={
                        "query": query,
                        "top_k": top_k,
                        "include_sources": include_sources
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()

                    st.success("Answer")
                    st.markdown(data["answer"])

                    if include_sources and data.get("sources"):
                        st.divider()
                        st.subheader("📚 Sources")

                        for i, source in enumerate(data["sources"], 1):
                            with st.expander(
                                    f"Source {i}: Act {source['act']}, Scene {source['scene']} "
                                    f"(Similarity: {source['similarity']:.3f})"
                            ):
                                st.markdown(f"**Type:** {source['chunk_type']}")
                                if source.get('speaker'):
                                    st.markdown(f"**Speaker:** {source['speaker']}")
                                st.text_area(
                                    "Text",
                                    value=source['text'],
                                    height=200,
                                    disabled=True,
                                    key=f"source_{i}"
                                )
                else:
                    st.error(f"Error: {response.status_code} - {response.text}")

            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to API. Is the backend running?")
            except Exception as e:
                st.error(f"Error: {str(e)}")

with st.expander("📋 Example Questions"):
    st.markdown("""
    - What does the Soothsayer warn Caesar about?
    - Why did Brutus join the conspiracy?
    - What is the context of "Et tu, Brute?"
    - How does Antony's funeral speech turn the crowd against Brutus?
    - What are Brutus's internal conflicts in Act 2?
    """)