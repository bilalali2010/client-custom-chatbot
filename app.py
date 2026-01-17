import streamlit as st
import os
import requests
import PyPDF2
from datetime import datetime
import random
import time

# -----------------------------
# CONFIG
# -----------------------------
ADMIN_PASSWORD = "@supersecret"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    st.error("⚠️ OPENROUTER_API_KEY missing")
    st.stop()

KNOWLEDGE_FILE = "knowledge.txt"
MAX_CONTEXT = 4500

FALLBACK_MESSAGES = [
    "I’m not completely sure, but I’ll try to help you.",
    "Let me guide you with the available information.",
    "That’s a good question. Here’s what I can tell you."
]

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Hospital Chatbot Demo",
    page_icon="🏥",
    layout="centered"
)

# -----------------------------
# TIDIO-STYLE HOSPITAL UI
# -----------------------------
st.markdown("""
<style>
.chat-container {
    max-width: 420px;
    margin: auto;
    background: white;
    border-radius: 18px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.15);
    overflow: hidden;
}
.chat-header {
    background: linear-gradient(135deg, #2563eb, #1e40af);
    padding: 16px;
    color: white;
}
.chat-header h4 {
    margin: 0;
    font-size: 16px;
}
.chat-header small {
    font-size: 12px;
    color: #dbeafe;
}
div[data-testid="stChatMessage"][data-role="assistant"] > div {
    background: #f1f5f9;
    border-radius: 16px;
    padding: 10px 14px;
    max-width: 80%;
    margin: 6px 0;
}
div[data-testid="stChatMessage"][data-role="user"] > div {
    background: #2563eb;
    color: white;
    border-radius: 16px;
    padding: 10px 14px;
    max-width: 80%;
    margin-left: auto;
    margin: 6px 0;
}
.quick-reply {
    display: inline-block;
    border: 1px solid #2563eb;
    color: #2563eb;
    padding: 7px 14px;
    border-radius: 999px;
    font-size: 13px;
    margin: 4px;
    cursor: pointer;
}
.quick-reply:hover {
    background: #2563eb;
    color: white;
}
.stChatInput textarea {
    border-radius: 999px !important;
    padding: 12px 16px !important;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# SESSION STATE
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = False

# Greeting (once)
if len(st.session_state.messages) == 0:
    st.session_state.messages.append({
        "role": "assistant",
        "content": "Hi 👋 How can I help you today?"
    })

# -----------------------------
# LOAD KNOWLEDGE
# -----------------------------
knowledge = ""
if os.path.exists(KNOWLEDGE_FILE):
    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        knowledge = f.read()

# -----------------------------
# ADMIN PANEL
# -----------------------------
IS_ADMIN_PAGE = "admin" in st.query_params

if IS_ADMIN_PAGE:
    st.sidebar.header("🔐 Admin Panel")
    if not st.session_state.admin_unlocked:
        pwd = st.sidebar.text_input("Enter admin password", type="password")
        if st.sidebar.button("Unlock Admin"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_unlocked = True
                st.sidebar.success("Admin unlocked")
                st.experimental_rerun()
            else:
                st.sidebar.error("Wrong password")
    else:
        st.sidebar.success("Admin Access Granted")
        pdfs = st.sidebar.file_uploader("Upload Hospital PDFs", type="pdf", accept_multiple_files=True)
        text_data = st.sidebar.text_area("Add Hospital Knowledge", height=150)

        if st.sidebar.button("💾 Save Knowledge"):
            combined = ""
            if pdfs:
                for file in pdfs:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        try:
                            combined += page.extract_text() or ""
                        except:
                            pass
            if text_data.strip():
                combined += "\n" + text_data.strip()

            combined = combined[:MAX_CONTEXT]
            if combined.strip():
                with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
                    f.write(combined)
                st.sidebar.success("Knowledge saved")

# -----------------------------
# TYPING EFFECT
# -----------------------------
def typing_effect(text, speed=0.03):
    placeholder = st.empty()
    typed = ""
    for word in text.split():
        typed += word + " "
        placeholder.markdown(typed)
        time.sleep(speed)
    return typed

# -----------------------------
# CHAT RENDER
# -----------------------------
st.markdown("""
<div class="chat-container">
    <div class="chat-header">
        <h4>Chat with Hospital Assistant</h4>
        <small>🟢 We are online!</small>
    </div>
</div>
""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Quick replies (static demo)
st.markdown("""
<div style="max-width:420px;margin:auto;padding:8px">
    <span class="quick-reply">🏥 Book Appointment</span>
    <span class="quick-reply">👨‍⚕️ Doctors Schedule</span>
    <span class="quick-reply">🧪 Lab Reports</span>
    <span class="quick-reply">📞 Contact Hospital</span>
</div>
""", unsafe_allow_html=True)

# -----------------------------
# CHAT INPUT
# -----------------------------
user_input = st.chat_input("Enter your message...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.chat_history.append((user_input, "", datetime.now()))

    prompt = ""
    if knowledge.strip():
        prompt += f"Hospital Knowledge:\n{knowledge}\n\n"
    prompt += f"Question:\n{user_input}"

    payload = {
        "model": "nvidia/nemotron-3-nano-30b-a3b:free",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a hospital customer support chatbot. "
                    "Respond politely, clearly, and professionally."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "max_output_tokens": 180,
        "temperature": 0.4
    }

    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        data = res.json()
        bot_reply = data["choices"][0]["message"]["content"].strip()
        if not bot_reply:
            bot_reply = random.choice(FALLBACK_MESSAGES)
    except:
        bot_reply = random.choice(FALLBACK_MESSAGES)

    with st.chat_message("assistant"):
        animated = typing_effect(bot_reply)

    st.session_state.messages.append({"role": "assistant", "content": animated})
    st.session_state.chat_history[-1] = (user_input, animated, datetime.now())
