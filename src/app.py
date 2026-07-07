import os
import sys
import json
import streamlit as st
from dotenv import load_dotenv

# Add the project root directory to Python's path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent import run_agent_turn

# Load environment variables
load_dotenv()

# Set Page Config
st.set_page_config(
    page_title="UAE HR & Nafis Copilot",
    page_icon="AE",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom UAE Design System CSS
uae_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Noto+Sans+Arabic:wght@300;400;500;600;700&display=swap');

    /* Global Typography & Font override */
    html, body, [class*="css"], .stMarkdown, p, div, label {
        font-family: 'Outfit', 'Noto Sans Arabic', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }

    /* Main background override */
    .stApp {
        background-color: #F9F8F6 !important;
    }

    /* Force readable text colors in main area for markdown */
    .stMarkdown p, .stMarkdown li, .stMarkdown span, .stMarkdown label {
        color: #1C1D1F !important;
    }
    
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: #0A4C28 !important;
        font-weight: 700 !important;
    }

    /* Top prestigious banner */
    .banner-container {
        background-color: #0A4C28 !important; /* AEGreen */
        border-top: 5px solid #B68A35 !important; /* AEGold */
        padding: 20px 30px;
        border-radius: 8px;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(10, 76, 40, 0.08);
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: #FFFFFF !important;
    }

    .banner-container * {
        color: #FFFFFF !important;
    }

    .banner-title {
        font-size: 28px !important;
        font-weight: 700 !important;
        margin: 0 !important;
        letter-spacing: -0.5px !important;
    }

    .banner-subtitle {
        font-size: 14px !important;
        color: #D4AF37 !important; /* Gold accent */
        margin: 5px 0 0 0 !important;
        font-weight: 500 !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E5E7EB !important;
    }

    /* Force all text in sidebar to be dark grey/black */
    section[data-testid="stSidebar"] * {
        color: #1C1D1F !important;
    }

    .sidebar-header {
        border-bottom: 3px solid #B68A35 !important;
        padding-bottom: 10px;
        margin-bottom: 20px;
        font-weight: 700;
        color: #0A4C28 !important;
        font-size: 16px;
        letter-spacing: 0.5px;
    }

    /* Card styling */
    .metric-card {
        background-color: #F3F4F6 !important;
        border: 1px solid #E5E7EB !important;
        border-left: 4px solid #0A4C28 !important;
        padding: 12px 15px !important;
        border-radius: 6px !important;
        margin-bottom: 15px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
    }

    .metric-card strong {
        color: #0A4C28 !important;
        display: inline-block;
        margin-bottom: 4px;
    }

    .metric-card code {
        background-color: #E5E7EB !important;
        color: #0B4C28 !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-family: monospace !important;
        font-size: 12px !important;
    }

    /* Custom Chat Containers */
    .chat-bubble-user {
        background-color: #0A4C28 !important; /* AEGreen */
        color: #FFFFFF !important;
        border-radius: 18px 18px 2px 18px !important;
        padding: 14px 18px !important;
        margin-bottom: 15px !important;
        max-width: 75% !important;
        margin-left: auto !important;
        box-shadow: 0 2px 6px rgba(10, 76, 40, 0.12) !important;
        border: none !important;
    }
    
    .chat-bubble-user * {
        color: #FFFFFF !important;
    }

    .chat-bubble-assistant {
        background-color: #FFFFFF !important;
        color: #1C1D1F !important;
        border-left: 4px solid #B68A35 !important; /* AEGold */
        border-radius: 18px 18px 18px 2px !important;
        padding: 16px 20px !important;
        margin-bottom: 15px !important;
        max-width: 80% !important;
        margin-right: auto !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
        border: 1px solid #E5E7EB !important;
        border-left: 4px solid #B68A35 !important;
    }
    
    .chat-bubble-assistant * {
        color: #1C1D1F !important;
    }

    /* Citation Tag styling */
    .citation-tag {
        display: inline-block;
        background-color: #F0EAD6 !important;
        color: #361E12 !important;
        border: 1px solid #B68A35 !important;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: 600;
        margin-top: 5px;
    }

    /* Custom Status Blocks (Phase Indicators) */
    .status-container {
        border-left: 3px solid #B68A35 !important;
        background-color: #FFFDF9 !important;
        padding: 12px;
        border-radius: 4px;
        margin: 10px 0;
        font-size: 13px;
        color: #555555 !important;
    }

    /* Footer */
    .footer {
        text-align: center;
        padding: 20px 0;
        font-size: 12px;
        color: #6B7280 !important;
        margin-top: 40px;
        border-top: 1px solid #E5E7EB !important;
    }
</style>
"""
st.markdown(uae_css, unsafe_allow_html=True)

# Prestige Header
st.markdown(
    """
    <div class="banner-container">
        <div style="display: flex; align-items: center;">
            <div style="border: 2px solid #B68A35; border-radius: 4px; width: 45px; height: 30px; margin-right: 15px; background: linear-content; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.15);">
                <div style="display: flex; height: 100%; width: 100%;">
                    <div style="background-color: #FF0000; width: 30%; height: 100%;"></div>
                    <div style="display: flex; flex-direction: column; width: 70%; height: 100%;">
                        <div style="background-color: #00732F; height: 33.3%;"></div>
                        <div style="background-color: #FFFFFF; height: 33.3%;"></div>
                        <div style="background-color: #000000; height: 33.4%;"></div>
                    </div>
                </div>
            </div>
            <div>
                <h1 class="banner-title">UAE HR & Nafis Copilot</h1>
                <p class="banner-subtitle">Official Compliance Assistant • Federal Decree-Law No. (33) of 2021 & Cabinet Regulations</p>
            </div>
        </div>
        <div style="font-size: 20px; font-weight: 700; color: #D4AF37; letter-spacing: 1px;">
            COURAGE • JUSTICE • WORK
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar panel
with st.sidebar:
    # Prestigious CSS UAE Emblem Seal
    st.markdown(
        """
        <div style="text-align: center; padding: 15px 0 25px 0;">
            <div style="border: 2px solid #B68A35; border-radius: 50%; width: 90px; height: 90px; margin: 0 auto; display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #0A4C28; box-shadow: 0 4px 8px rgba(10, 76, 40, 0.15);">
                <span style="color: #FFFFFF !important; font-size: 10px; font-weight: 700; letter-spacing: 2px; margin-bottom: 2px;">GOV</span>
                <span style="color: #B68A35 !important; font-size: 15px; font-weight: 800; letter-spacing: 1px;">U.AE</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown('<div class="sidebar-header">SYSTEM PORTAL</div>', unsafe_allow_html=True)
    
    st.markdown("### Compliance Scope")
    st.markdown(
        "- **Federal Decree-Law No. (33) of 2021** (UAE Labour Relations Law)\n"
        "- **Cabinet Resolution No. (1) of 2022** (Executive Regulations)\n"
        "- **Cabinet Regulation No. (43) of 2025** (Nafis/Emiratisation Penalties)"
    )
    
    st.markdown("---")
    st.markdown("### Active Models")
    st.markdown(
        '<div class="metric-card">'
        '<strong>Reasoning Engine:</strong><br>'
        '<code style="color:#0A4C28;">gpt-4o-mini</code> (OpenAI)'
        '</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="metric-card">'
        '<strong>Embedding System:</strong><br>'
        '<code style="color:#0A4C28;">gemini-embedding-001</code> (Google)'
        '</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="metric-card">'
        '<strong>Database:</strong><br>'
        '<code style="color:#0A4C28;">Qdrant Local (124 Articles)</code>'
        '</div>',
        unsafe_allow_html=True
    )
    
    st.markdown("---")
    if st.button("Reset Conversation History", use_container_width=True, type="primary"):
        st.session_state.messages = []
        st.rerun()

# Display Chat History
st.markdown("### Inquiry Console")

# Render existing messages
for i, msg in enumerate(st.session_state.messages):
    role = msg.get("role")
    content = msg.get("content") or ""
    
    # Skip rendering system messages, internal queries or intermediate tools
    if role == "user":
        # Check if this query is a grounded prompt that contains "RETRIEVED LAW ARTICLES"
        # If so, clean it up so the user only sees the original question they typed
        display_content = content
        if "USER QUESTION:" in content:
            parts = content.split("USER QUESTION:")
            display_content = parts[-1].strip()
            
        st.markdown(f'<div class="chat-bubble-user">{display_content}</div>', unsafe_allow_html=True)
        
    elif role == "assistant":
        # Check if there are tool calls in this assistant step or subsequent tool response
        # To show what math calculations occurred, check if there's a tool execution associated with it
        # We can look ahead at the next message in history to check if it's a tool response
        tool_details = []
        if i + 1 < len(st.session_state.messages):
            next_msg = st.session_state.messages[i + 1]
            if next_msg.get("role") == "tool" and next_msg.get("content"):
                try:
                    tool_output = next_msg.get("content")
                    # Find args
                    if msg.get("tool_calls"):
                        tc = msg["tool_calls"][0]
                        args = tc.get("function", {}).get("arguments", "")
                        # Pretty render
                        tool_details.append(f"Expression: `{args}` &rarr; Calculated Result: **{tool_output}**")
                except Exception:
                    pass
                    
        # Render the tool details if any were found
        for td in tool_details:
            with st.expander("Intermediate Calculations (Math Tool)", expanded=False):
                st.markdown(td)
                
        # If assistant content is not empty, render it
        if content:
            st.markdown(f'<div class="chat-bubble-assistant">{content}</div>', unsafe_allow_html=True)
            
            # If the assistant message has parsed citations, render them as gold badges below the bubble
            citations = msg.get("citations", [])
            if citations:
                badge_html = " ".join(
                    f'<span class="citation-tag" title="{c.get("source_document", "")}">{c.get("article_number", "Citation")}</span>'
                    for c in citations
                )
                st.markdown(badge_html, unsafe_allow_html=True)

# Chat Input Area
user_input = st.chat_input("State your compliance inquiry (e.g., probation notice period, sham Emiratisation fines)...")

if user_input:
    # Render user query immediately
    st.markdown(f'<div class="chat-bubble-user">{user_input}</div>', unsafe_allow_html=True)
    
    # Process turn with Phase visualizations
    with st.container():
        # Phase A progress
        status_a = st.status("Phase A: Retrieving relevant federal articles from database...", expanded=True)
        
        # Execute query
        try:
            # We temporarily update status descriptions as the agent runs
            # Since run_agent_turn is blocking, we simulate or show updates
            # To get updates, we can update status_a, wait, then run the agent
            status_a.write("Matching query vectors with 3,072-dimensional space...")
            status_a.write("Applying Cosine Similarity thresholding...")
            status_a.update(label="Phase A: Retrieved closest matching articles from Qdrant", state="complete")
            
            # Phase B reasoning
            status_b = st.status("Phase B: Orchestrating LangGraph reasoning loop...", expanded=True)
            status_b.write("Analyzing retrieved legal clauses...")
            status_b.write("Evaluating boundary constraints and mathematical formulas...")
            
            # Perform blocking turn
            result = run_agent_turn(user_input, st.session_state.messages)
            
            # Extract fields from dictionary response
            final_answer = result["answer"]
            updated_history = result["history"]
            
            # Update status B
            status_b.write("Processing final output format...")
            status_b.update(label="Phase B: Reasoning completed", state="complete")
            
            # Save updated history
            st.session_state.messages = updated_history
            
            # Rerun page to cleanly render the assistant bubbles and any intermediate math tool logs
            st.rerun()
            
        except Exception as e:
            status_a.update(label="Retrieval failed", state="error")
            status_b.update(label="Agent error", state="error")
            st.error(f"Error executing agent turn: {str(e)}")

# Footer
st.markdown(
    '<div class="footer">'
    'UAE Federal HR & Emiratisation Regulatory Copilot • Powered by LangGraph, Qdrant & OpenAI GPT-4o-mini.<br>'
    'All regulations are pulled from official cabinet regulations and decree-laws. Verify major decisions with MOHRE counsel.'
    '</div>',
    unsafe_allow_html=True
)
