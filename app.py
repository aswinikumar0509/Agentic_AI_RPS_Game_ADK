import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from rpsGame import process_turn, SimpleToolContext  


st.set_page_config(page_title="RPS+ Referee", page_icon="🎮")

st.title("🎮 Rock–Paper–Scissors–Plus Referee")
st.caption("Best of 3 rounds. Moves: rock, paper, scissors, bomb (once). Invalid input wastes the round.")

# ---- initialize Streamlit session state ----
if "offline_state" not in st.session_state:
    st.session_state.offline_state = {}  # persists across reruns

if "chat" not in st.session_state:
    st.session_state.chat = []  # list of {"role": "user"/"assistant", "content": str}

if "game_over" not in st.session_state:
    st.session_state.game_over = False


def render_offline_result(tr: dict) -> str:
    def fmt(x):
        return x if x is not None else "—"

    rn = tr.get("round_number", 0)
    um = fmt(tr.get("user_move"))
    bm = fmt(tr.get("bot_move"))
    winner = tr.get("round_winner", "none")
    winner_text = "none (invalid/wasted)" if winner == "none" else winner
    u = tr.get("user_score", 0)
    b = tr.get("bot_score", 0)

    lines = [
        f"Round {rn}/3",
        f"Moves: User={um}, Bot={bm}",
        f"Winner: {winner_text}",
        f"Score: User {u} - {b} Bot",
    ]
    if tr.get("game_over"):
        lines.append(f"Final result: {tr.get('final_result')}")
    else:
        lines.append("Your move?")
    return "\n".join(lines)


# ---- sidebar controls ----
with st.sidebar:
    st.header("Controls")
    if st.button("🔁 Reset Game"):
        st.session_state.offline_state = {}
        st.session_state.chat = []
        st.session_state.game_over = False
        st.rerun()

    st.write("**Mode**: Offline (no Gemini calls)")
    st.write("If you want Online (Gemini) mode later, I can give you a Runner-based version too.")


# ---- show chat history ----
for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ---- input box ----
if st.session_state.game_over:
    st.info("Game ended. Click **Reset Game** to play again.")
else:
    user_text = st.chat_input("Type your move (rock/paper/scissors/bomb)...")

    if user_text:
        # user message
        st.session_state.chat.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.markdown(user_text)

        # tool call (offline): process_turn updates st.session_state.offline_state
        tool_ctx = SimpleToolContext(st.session_state.offline_state)
        tr = process_turn(user_text, tool_ctx)

        assistant_text = "```\n" + render_offline_result(tr) + "\n```"
        st.session_state.chat.append({"role": "assistant", "content": assistant_text})

        with st.chat_message("assistant"):
            st.markdown(assistant_text)

        if tr.get("game_over"):
            st.session_state.game_over = True
