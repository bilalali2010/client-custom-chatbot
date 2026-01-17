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
CHAT_HISTORY_FILE = "chat_history.json"
MAX_CONTEXT = 4500

FALLBACK_MESSAGES = [
    "I'm not completely sure, but I'll try to help you.",
    "Let me guide you with the available information.",
    "That's a good question. Here's what I can tell you."
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
/* Main container with chat width */
.main .block-container {
    max-width: 420px !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

.chat-container {
    max-width: 420px;
    margin: auto;
    background: white;
    border-radius: 18px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.15);
    overflow: hidden;
    margin-bottom: 20px;
}
.chat-header {
    background: linear-gradient(135deg, #2563eb, #1e40af);
    padding: 16px;
    color: white;
    text-align: center;
}
.chat-header h4 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
}
.chat-header small {
    font-size: 13px;
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
.stChatInput {
    max-width: 420px !important;
    margin: auto !important;
}
.stChatInput textarea {
    border-radius: 999px !important;
    padding: 12px 16px !important;
}

/* Simple doctor schedule styling */
.doctor-schedule {
    background: white;
    padding: 12px;
    border-radius: 10px;
    margin: 10px 0;
    border-left: 4px solid #2563eb;
}
.doctor-item {
    padding: 10px;
    margin: 8px 0;
    background: #f8fafc;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
}
.doctor-name {
    font-weight: 600;
    color: #1e40af;
    margin-bottom: 5px;
}
.doctor-details {
    font-size: 14px;
    color: #4b5563;
    line-height: 1.4;
}

/* Admin section styling */
.admin-section {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 10px;
    margin: 10px 0;
    border-left: 4px solid #2563eb;
}
.admin-history-item {
    padding: 8px 12px;
    margin: 5px 0;
    background: white;
    border-radius: 8px;
    border: 1px solid #e9ecef;
    font-size: 14px;
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

# Initial greeting (only once when empty)
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

# Load chat history from file if exists
def load_chat_history():
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            import json
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_chat_history():
    import json
    # Keep only last 50 messages to prevent file from getting too large
    recent_history = st.session_state.chat_history[-50:] if len(st.session_state.chat_history) > 50 else st.session_state.chat_history
    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(recent_history, f, default=str)

# Load existing chat history
if "loaded_history" not in st.session_state:
    st.session_state.chat_history = load_chat_history()
    st.session_state.loaded_history = True

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
                st.rerun()
            else:
                st.sidebar.error("Wrong password")
    else:
        st.sidebar.success("✅ Admin Access Granted")
        
        # Knowledge Management Section
        st.sidebar.markdown("---")
        st.sidebar.subheader("📚 Knowledge Management")
        
        # Delete trained data option
        st.sidebar.markdown('<div class="admin-section">', unsafe_allow_html=True)
        
        if st.sidebar.button("🗑️ Delete All Trained Data", type="secondary"):
            if os.path.exists(KNOWLEDGE_FILE):
                os.remove(KNOWLEDGE_FILE)
                knowledge = ""
                st.sidebar.success("All trained data deleted!")
                st.rerun()
        
        if st.sidebar.button("🗑️ Delete Chat History", type="secondary"):
            if os.path.exists(CHAT_HISTORY_FILE):
                os.remove(CHAT_HISTORY_FILE)
                st.session_state.chat_history = []
                st.sidebar.success("Chat history deleted!")
                st.rerun()
        
        st.sidebar.markdown('</div>', unsafe_allow_html=True)
        
        # Upload PDFs and add text
        st.sidebar.markdown("---")
        st.sidebar.subheader("➕ Add New Knowledge")
        
        pdfs = st.sidebar.file_uploader("Upload Hospital PDFs", type="pdf", accept_multiple_files=True)
        text_data = st.sidebar.text_area("Add/Update Hospital Knowledge", height=150, value=knowledge)
        
        if st.sidebar.button("💾 Save Knowledge", type="primary"):
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
                combined = text_data.strip() if not pdfs else combined + "\n" + text_data.strip()
            
            combined = combined[:MAX_CONTEXT]
            if combined.strip():
                with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
                    f.write(combined)
                knowledge = combined
                st.sidebar.success("Knowledge saved successfully!")
                st.rerun()
        
        # View Recent Questions Section
        st.sidebar.markdown("---")
        st.sidebar.subheader("📋 Recent Questions (Last 10)")
        
        recent_questions = st.session_state.chat_history[-10:] if len(st.session_state.chat_history) > 10 else st.session_state.chat_history
        
        if recent_questions:
            st.sidebar.markdown('<div class="admin-section">', unsafe_allow_html=True)
            for i, (question, answer, timestamp) in enumerate(reversed(recent_questions)):
                try:
                    dt = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp
                    time_str = dt.strftime("%I:%M %p, %b %d")
                except:
                    time_str = str(timestamp)[:19]
                
                st.sidebar.markdown(f"""
                <div class="admin-history-item">
                <strong>Q{i+1}:</strong> {question[:60]}...
                <br><small>📅 {time_str}</small>
                </div>
                """, unsafe_allow_html=True)
            st.sidebar.markdown('</div>', unsafe_allow_html=True)
        else:
            st.sidebar.info("No recent questions yet.")
        
        # Current Knowledge Preview
        st.sidebar.markdown("---")
        st.sidebar.subheader("📖 Current Knowledge Preview")
        
        if knowledge:
            st.sidebar.markdown(f"""
            <div style="font-size: 12px; color: #666; padding: 10px; background: #f0f0f0; border-radius: 5px; max-height: 200px; overflow-y: auto;">
            {knowledge[:500]}...
            </div>
            """, unsafe_allow_html=True)
            st.sidebar.caption(f"Characters: {len(knowledge)}")
        else:
            st.sidebar.warning("No knowledge data loaded.")

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

# Function to format doctor schedules simply
def format_simple_doctor_info(text):
    """Convert markdown tables to simple doctor information"""
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        # Check if line looks like a table header separator
        if line.strip().startswith('|---'):
            continue
        # Check if line looks like a table header with "Doctor | Available Time Slot | Fees"
        elif '| Doctor |' in line or '| Doctor ' in line or '|--------|' in line:
            continue
        # Check if it's a table row with doctor info
        elif '|' in line and ('Dr.' in line or 'PM' in line or 'AM' in line):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 3:
                # Format as simple text
                doctor_info = f"**{parts[0]}**\n⏰ {parts[1]}\n💰 {parts[2]} PKR\n"
                formatted_lines.append(f'<div class="doctor-item"><div class="doctor-name">{parts[0]}</div><div class="doctor-details">Available: {parts[1]}<br>Consultation Fee: {parts[2]} PKR</div></div>')
            else:
                formatted_lines.append(line)
        else:
            formatted_lines.append(line)
    
    # Join lines and check if we have doctor items
    result = '\n'.join(formatted_lines)
    
    # If we found doctor items, wrap them in a container
    if 'doctor-item' in result:
        result = result.replace('<div class="doctor-item">', '<div class="doctor-schedule"><h4>👨‍⚕️ Available Doctors:</h4>') + '</div>'
    
    return result

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

# Display all messages (both user and assistant)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # Format the content if it's from assistant and contains doctor info
        if msg["role"] == "assistant" and ('Doctor' in msg["content"] or 'Dr.' in msg["content"]):
            formatted_content = format_simple_doctor_info(msg["content"])
            if '<div class="doctor-schedule">' in formatted_content:
                st.markdown(formatted_content, unsafe_allow_html=True)
            else:
                st.markdown(msg["content"])
        else:
            st.markdown(msg["content"])

# Quick replies (static demo)
st.markdown("""
<div style="max-width:420px;margin:auto;padding:8px">
    <span class="quick-reply" onclick="this.style.backgroundColor='#2563eb';this.style.color='white';">🏥 Book Appointment</span>
    <span class="quick-reply" onclick="this.style.backgroundColor='#2563eb';this.style.color='white';">👨‍⚕️ Doctors Schedule</span>
    <span class="quick-reply" onclick="this.style.backgroundColor='#2563eb';this.style.color='white';">🧪 Lab Reports</span>
    <span class="quick-reply" onclick="this.style.backgroundColor='#2563eb';this.style.color='white';">📞 Contact Hospital</span>
</div>
""", unsafe_allow_html=True)

# Add some JavaScript for quick reply clicks
st.markdown("""
<script>
document.addEventListener('DOMContentLoaded', function() {
    const quickReplies = document.querySelectorAll('.quick-reply');
    quickReplies.forEach(reply => {
        reply.addEventListener('click', function() {
            const text = this.textContent.replace(/[🏥👨‍⚕️🧪📞]/g, '').trim();
            const chatInput = document.querySelector('.stChatInput textarea');
            if (chatInput) {
                chatInput.value = text;
                chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                
                // Trigger send (simulate Enter key)
                setTimeout(() => {
                    const sendButton = document.querySelector('.stChatInput button');
                    if (sendButton) sendButton.click();
                }, 100);
            }
        });
    });
});
</script>
""", unsafe_allow_html=True)

# -----------------------------
# CHAT INPUT
# -----------------------------
user_input = st.chat_input("Enter your message...")

if user_input:
    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Add to messages
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Prepare knowledge prompt with instruction for simple doctor info
    prompt = ""
    if knowledge.strip():
        prompt += f"Hospital Knowledge:\n{knowledge}\n\n"
    
    # Add instruction for simple formatting
    prompt += f"Question: {user_input}\n\n"
    prompt += "Important: When listing doctors and their schedules, use simple format like:\n"
    prompt += "Dr. Usman Tariq - Available: 5:00 PM – 9:00 PM, Fee: 2,200 PKR\n"
    prompt += "Dr. Farah Khan - Available: 10:00 AM – 1:00 PM, Fee: 2,400 PKR\n"
    prompt += "Do NOT use markdown tables or table headers. Just list doctors with their details simply."
    
    # Generate assistant response
    payload = {
        "model": "nvidia/nemotron-3-nano-30b-a3b:free",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a hospital customer support chatbot. "
                    "Respond politely, clearly, and professionally. "
                    "When listing doctors and their schedules, use simple plain text format. "
                    "DO NOT use markdown tables or table headers. "
                    "Just list each doctor with their timing and fee in a simple readable format."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "max_output_tokens": 350,
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
    except Exception as e:
        print(f"Error: {e}")
        bot_reply = random.choice(FALLBACK_MESSAGES)
    
    # Format the response to ensure simple doctor info
    bot_reply = format_simple_doctor_info(bot_reply)
    
    # Display assistant message with typing effect
    with st.chat_message("assistant"):
        if '<div class="doctor-schedule">' in bot_reply:
            # For HTML formatted content, don't use typing effect
            st.markdown(bot_reply, unsafe_allow_html=True)
            animated = bot_reply
        else:
            animated = typing_effect(bot_reply)
    
    # Add assistant message to history
    st.session_state.messages.append({"role": "assistant", "content": animated})
    
    # Add to chat history and save
    st.session_state.chat_history.append((user_input, animated, datetime.now()))
    save_chat_history()
    
    # Force rerun to update UI
    st.rerun()

# Display admin link at bottom
st.markdown("""
<div style="text-align: center; margin-top: 20px; max-width: 420px; margin-left: auto; margin-right: auto;">
<small>
<a href="/?admin=true" style="color: #666; text-decoration: none;">🔐 Admin Panel</a>
</small>
</div>
""", unsafe_allow_html=True)
