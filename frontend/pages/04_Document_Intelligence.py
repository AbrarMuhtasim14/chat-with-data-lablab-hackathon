# frontend/pages/04_Document_Intelligence.py
"""
Document Intelligence Page — Track 4 Hackathon Feature
RAG over proprietary documents + Knowledge Graph Extraction using Gemini.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import networkx as nx
import json

# Legacy SDK (already used elsewhere in repo)
import google.generativeai as genai

# New unified SDK (recommended for Google Search grounding)
from google import genai as genai_new
from google.genai import types

from utils.config import GEMINI_API_KEY
from utils.document_processor import (
    extract_text_from_pdf,
    extract_knowledge_graph,
    build_networkx_graph,
    compare_with_database
)
from utils.metrics_engine import get_core_metrics

# Configure legacy Gemini SDK (kept for your existing helper funcs if they use it)
genai.configure(api_key=GEMINI_API_KEY)


def answer_with_grounding(prompt: str, api_key: str) -> str:
    """
    Gemini answers using prompt and can ground responses with Google Search when needed.
    Official: Grounding with Google Search (Gemini API docs). :contentReference[oaicite:4]{index=4}
    """
    client = genai_new.Client(api_key=api_key)

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
        ),
    )
    return resp.text or ""


# ════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════


st.title("📄 Document Intelligence")
st.caption(
    "Upload hotel industry reports, competitor analysis, or market benchmarks. "
    "Gemini extracts entities and relationships, then answers questions spanning "
    "both the document AND your live database."
)

# ════════════════════════════════════════════════
# SESSION STATE
# ════════════════════════════════════════════════
if "doc_text" not in st.session_state:
    st.session_state.doc_text = None
if "knowledge_graph" not in st.session_state:
    st.session_state.knowledge_graph = None
if "doc_chat_history" not in st.session_state:
    st.session_state.doc_chat_history = []
if "doc_name" not in st.session_state:
    st.session_state.doc_name = None

# ════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════
with st.sidebar:
    st.title("📋 How It Works")
    st.markdown("""
    **Step 1:** Upload a PDF document
    (hotel report, market analysis, competitor data)
    
    **Step 2:** Gemini reads and extracts:
    - 🏨 Hotels & cities mentioned
    - 📊 KPIs & benchmarks
    - 🔗 Entity relationships
    - 💡 Key insights
    
    **Step 3:** Explore the knowledge graph
    
    **Step 4:** Ask questions that combine
    document data + your live database
    
    ---
    
    **Example questions:**
    - "How does our RevPAR compare to the industry benchmark?"
    - "Which cities in the report show high growth potential?"
    - "What does the report say about cancellation rates?"
    """)

    st.markdown("---")

    if st.button("🗑️ Clear Document", use_container_width=True):
        st.session_state.doc_text = None
        st.session_state.knowledge_graph = None
        st.session_state.doc_chat_history = []
        st.session_state.doc_name = None
        st.rerun()

# ════════════════════════════════════════════════
# SECTION 1: PDF UPLOAD
# ════════════════════════════════════════════════
st.markdown("## 📤 Upload Document")

uploaded_file = st.file_uploader(
    "Upload a hospitality industry PDF",
    type=["pdf"],
    help="Upload any hotel industry report, market analysis, or competitor benchmark document"
)

# ── Process Upload ──
if uploaded_file and uploaded_file.name != st.session_state.doc_name:
    with st.spinner("📖 Reading document with Gemini..."):
        try:
            # Extract text
            doc_text = extract_text_from_pdf(uploaded_file)

            if len(doc_text.strip()) < 100:
                st.error("Could not extract meaningful text from this PDF. Please try another file.")
            else:
                st.session_state.doc_text = doc_text
                st.session_state.doc_name = uploaded_file.name
                st.session_state.doc_chat_history = []

                # Extract knowledge graph
                with st.spinner("🧠 Gemini is extracting entities and relationships..."):
                    knowledge_graph = extract_knowledge_graph(doc_text)
                    st.session_state.knowledge_graph = knowledge_graph

                st.success(f"✅ Document processed: **{uploaded_file.name}**")

        except Exception as e:
            st.error(f"Error processing document: {str(e)}")

# ════════════════════════════════════════════════
# SECTION 2: KNOWLEDGE GRAPH + INSIGHTS
# ════════════════════════════════════════════════
if st.session_state.knowledge_graph:
    kg = st.session_state.knowledge_graph

    if "error" in kg and not kg.get("entities"):
        st.warning(f"Knowledge graph extraction had issues: {kg['error']}")
    else:
        st.markdown("---")
        st.markdown("## 🔗 Knowledge Graph")

        # ── Tabs for different views ──
        tab1, tab2, tab3, tab4 = st.tabs([
            "🕸️ Graph Visualization",
            "📊 Extracted KPIs",
            "🏆 Benchmarks vs Your Data",
            "💡 Key Insights"
        ])

        # ── Tab 1: Graph Visualization ──
        with tab1:
            entities = kg.get('entities', [])
            relationships = kg.get('relationships', [])

            if entities:
                G = build_networkx_graph(kg)

                if len(G.nodes) > 0:
                    # Use spring layout
                    pos = nx.spring_layout(G, seed=42, k=2)

                    # Build plotly graph
                    edge_x, edge_y, edge_labels = [], [], []
                    for edge in G.edges(data=True):
                        x0, y0 = pos[edge[0]]
                        x1, y1 = pos[edge[1]]
                        edge_x.extend([x0, x1, None])
                        edge_y.extend([y0, y1, None])

                    node_x = [pos[node][0] for node in G.nodes()]
                    node_y = [pos[node][1] for node in G.nodes()]
                    node_labels = list(G.nodes())

                    # Color nodes by type
                    node_colors = []
                    for node in G.nodes(data=True):
                        node_type = node[1].get('node_type', 'hotel')
                        color_map = {
                            'hotel': '#5D5FEF',
                            'city': '#7EC8E3',
                            'brand': '#FF6B6B'
                        }
                        node_colors.append(color_map.get(node_type, '#5D5FEF'))

                    fig_graph = go.Figure()

                    # Add edges
                    fig_graph.add_trace(go.Scatter(
                        x=edge_x, y=edge_y,
                        mode='lines',
                        line=dict(width=1, color='#888'),
                        hoverinfo='none',
                        showlegend=False
                    ))

                    # Add nodes
                    fig_graph.add_trace(go.Scatter(
                        x=node_x, y=node_y,
                        mode='markers+text',
                        hoverinfo='text',
                        text=node_labels,
                        textposition="top center",
                        marker=dict(
                            size=20,
                            color=node_colors,
                            line=dict(width=2, color='white')
                        ),
                        name='Entities'
                    ))

                    fig_graph.update_layout(
                        title="Entity Relationship Graph",
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        height=500,
                        paper_bgcolor='white',
                        plot_bgcolor='white'
                    )

                    st.plotly_chart(fig_graph, use_container_width=True)

                    # Entity list
                    st.markdown("### 🏨 Entities Detected")
                    entity_df = pd.DataFrame(entities)
                    if not entity_df.empty:
                        st.dataframe(entity_df, hide_index=True, use_container_width=True)

                else:
                    st.info("No relationships found to visualize. The document may not contain enough entity relationships.")
            else:
                st.info("No entities extracted from this document.")

        # ── Tab 2: Extracted KPIs ──
        with tab2:
            kpis = kg.get('kpis', [])
            if kpis:
                kpi_df = pd.DataFrame(kpis)
                st.markdown("### 📊 KPIs Mentioned in Document")
                st.dataframe(kpi_df, hide_index=True, use_container_width=True)

                # Visualize numeric KPIs
                numeric_kpis = [k for k in kpis if isinstance(k.get('value'), (int, float))]
                if numeric_kpis:
                    fig_kpi = go.Figure(go.Bar(
                        x=[k['metric'] for k in numeric_kpis],
                        y=[k['value'] for k in numeric_kpis],
                        marker_color='#5D5FEF',
                        text=[f"{k['value']}{k.get('unit', '')}" for k in numeric_kpis],
                        textposition='outside'
                    ))
                    fig_kpi.update_layout(
                        title="Document KPIs",
                        xaxis_title="Metric",
                        yaxis_title="Value",
                        height=350,
                        margin=dict(t=40, b=40)
                    )
                    st.plotly_chart(fig_kpi, use_container_width=True)
            else:
                st.info("No specific KPIs extracted from this document.")

        # ── Tab 3: Benchmarks vs Your Data ──
        with tab3:
            st.markdown("### 🏆 Industry Benchmarks vs Your Database")
            benchmarks = kg.get('benchmarks', [])

            if benchmarks:
                # Load current DB metrics
                with st.spinner("Loading your current metrics..."):
                    db_metrics = get_core_metrics()

                comparisons = compare_with_database(benchmarks, db_metrics)

                if comparisons:
                    for comp in comparisons:
                        metric_label = comp['metric'].replace('_', ' ').title()
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric(
                                label=f"Your {metric_label}",
                                value=f"{comp['your_value']:,.2f}",
                            )
                        with col2:
                            st.metric(
                                label=f"Benchmark ({comp['context']})",
                                value=f"{comp['benchmark']:,.2f}",
                            )
                        with col3:
                            sign = "+" if comp['difference'] > 0 else ""
                            status_emoji = "✅" if comp['status'] == 'above' else "⚠️"
                            st.metric(
                                label="Difference",
                                value=f"{sign}{comp['difference']:,.2f}",
                                delta=f"{sign}{comp['difference_pct']:.1f}% vs benchmark"
                            )

                        st.markdown("---")
                else:
                    # Show raw benchmarks if comparison fails
                    bench_df = pd.DataFrame(benchmarks)
                    st.dataframe(bench_df, hide_index=True, use_container_width=True)
                    st.info("Could not automatically match benchmarks to your database metrics.")
            else:
                st.info("No benchmarks extracted from this document.")

        # ── Tab 4: Key Insights ──
        with tab4:
            insights = kg.get('insights', [])
            if insights:
                st.markdown("### 💡 Key Insights from Document")
                for i, insight in enumerate(insights, 1):
                    impact = insight.get('impact', 'medium')
                    icon = "🔴" if impact == 'high' else ("🟡" if impact == 'medium' else "🟢")
                    st.markdown(f"{icon} **{i}.** {insight.get('finding', '')}")
            else:
                st.info("No insights extracted from this document.")

# ════════════════════════════════════════════════
# SECTION 3: CROSS-SOURCE CHAT
# ════════════════════════════════════════════════
if st.session_state.doc_text:
    st.markdown("---")
    st.markdown("## 💬 Ask Questions Across Document + Database")
    st.caption(
        "Gemini will answer using both the uploaded document AND your live database metrics."
    )

    # Display chat history
    for message in st.session_state.doc_chat_history:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant", avatar="🏨"):
                st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about the document or compare with your data..."):

        # Add user message
        st.session_state.doc_chat_history.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🏨"):
            with st.spinner("🔍 Gemini is analyzing document + database..."):
                try:
                    # Load current DB metrics for context
                    db_metrics = get_core_metrics()

                    # Build context for Gemini
                    doc_context = f"""
DOCUMENT: {st.session_state.doc_name}

DOCUMENT CONTENT (excerpt):
{st.session_state.doc_text[:5000]}

EXTRACTED KNOWLEDGE GRAPH:
{json.dumps(st.session_state.knowledge_graph, indent=2)[:2000]}

LIVE DATABASE METRICS (AtliQ Hospitality):
- Total Revenue: ₹{db_metrics.get('revenue', 0)/1e6:.1f}M
- Occupancy Rate: {db_metrics.get('occupancy_pct', 0):.1f}%
- ADR: ₹{db_metrics.get('adr', 0):,.0f}
- RevPAR: ₹{db_metrics.get('revpar', 0):,.0f}
- Realisation %: {db_metrics.get('realisation_pct', 0):.1f}%
- Cancellation %: {db_metrics.get('cancellation_pct', 0):.1f}%
- Average Rating: {db_metrics.get('average_rating', 0):.2f}
"""

                    cross_source_prompt = f"""You are a hospitality intelligence analyst.
You have access to:
1. An uploaded industry document
2. Live database metrics from AtliQ Hospitality
3. Live web search grounding (when needed)

{doc_context}

USER QUESTION: {prompt}

Provide a comprehensive answer that:
- Cites specific numbers from the document when relevant
- Compares with the live database metrics when applicable
- Uses web search only if the document does not contain the needed benchmark/context
- Gives actionable business insights
- Keeps the response under 300 words

Answer:"""

                    # ✅ Grounded answer (PDF + DB + live web)
                    answer = answer_with_grounding(cross_source_prompt, GEMINI_API_KEY)

                    st.markdown(answer)
                    st.session_state.doc_chat_history.append({
                        "role": "assistant",
                        "content": answer
                    })

                except Exception as e:
                    error_msg = f"Error generating response: {str(e)}"
                    st.error(error_msg)
                    st.session_state.doc_chat_history.append({
                        "role": "assistant",
                        "content": error_msg
                    })

# ════════════════════════════════════════════════
# EMPTY STATE
# ════════════════════════════════════════════════
if not st.session_state.doc_text:
    st.markdown("---")
    st.info(
        "👆 Upload a PDF document above to get started. "
        "Try uploading a hotel industry report, market analysis, or any hospitality benchmark document."
    )

    # Show example of what the output looks like
    st.markdown("### 📋 What you'll get:")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        **🕸️ Knowledge Graph**
        - Entity visualization
        - Hotel & city relationships
        - Competitor connections
        """)

    with col2:
        st.markdown("""
        **📊 Benchmark Comparison**
        - Industry KPIs vs your data
        - Performance gap analysis
        - Automatic metric matching
        """)

    with col3:
        st.markdown("""
        **💬 Cross-Source Chat**
        - Ask questions across both sources
        - Document + database combined
        - Gemini-powered insights
        """)

# ════════════════════════════════════════════════
# FOOTER
# ════════════════════════════════════════════════
st.markdown("---")
st.caption(
    "📄 Document Intelligence powered by Gemini | "
    "Knowledge graph extraction + cross-source RAG | "
    "Track 4: Data & Intelligence"
)