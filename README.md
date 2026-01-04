# Rock–Paper–Scissors–Plus (RPS+) Referee — Google ADK + Offline Mode
🔗 **Live Demo:**  
👉 [https://your-live-url-here](https://agenticairpsgameadk-yxjzftazwewxbaxgejmpdn.streamlit.app/)

A 3-round Rock–Paper–Scissors game with an extra move: **bomb** (usable **once** per player).
This project uses **Google ADK** (Agent Development Kit) to run an LLM “referee” agent that calls a tool (`process_turn`) to enforce rules and track state.

It also supports an **OFFLINE_MODE** that runs the same game logic without any LLM or API key.

---

## Rules

- **3 rounds total** — game ends automatically after round 3.
- Moves: `rock`, `paper`, `scissors`, `bomb`
- **Bomb can be used once per player**
- `bomb` beats any non-bomb; `bomb` vs `bomb` is a draw
- **Invalid input wastes the round**

---

## Project Structure (suggested)


## Requirements

- Python **3.10+** 
- Dependencies:
  - `google-adk`
  - `streamlit`
  - `python-dotenv`
 
## UI and Working of the Agent 

<img width="1749" height="817" alt="image" src="https://github.com/user-attachments/assets/a7b6e36e-640f-48e4-945f-d909a844500a" />
<img width="986" height="769" alt="image" src="https://github.com/user-attachments/assets/c317a3cf-2b4b-44d0-bf1e-bad03a19cd18" />
<img width="1163" height="668" alt="image" src="https://github.com/user-attachments/assets/0d8a5475-0a43-4b9b-b394-828c4268b56c" />







