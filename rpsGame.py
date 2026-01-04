import os
import random
import re
from typing import Any,Dict,Literal, Optional,TypedDict
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Content, Part
import asyncio

### importing load_dotenv form env file
from dotenv import load_dotenv
load_dotenv()

try:
    from google.adk.models.google_llm import _ResourceExhaustedError
except Exception:
    _ResourceExhaustedError = Exception

Move = Literal["rock", "paper", "scissors", "bomb"]


class TurnResult(TypedDict, total=False):
    ok:bool
    round_number:int
    user_move:Optional[str]
    bot_move:Optional[str]
    round_winner:Literal["user","bot","draw","none"]
    reason:str
    user_score:int
    bot_score:int
    rounds_played:int
    rounds_left:int
    game_over:bool
    final_result:Optional[Literal["User wins", "Bot wins", "Draw"]]

VALID_MOVES : set[str] = {"rock","paper","scissors","bomb"}


### Offline tool context

class SimpleToolContext:
    def __init__(self,state:Dict[str,Any]):
        self.state = state


### Initilization of the state

def ensure_state_initialized(state: Dict[str,Any])->None:

    if state.get("rps_plus_initialized"):
        return 
    
    state["rps_plus_initialized"]=True
    state["rounds_played"] = 0
    state["user_score"] = 0
    state["bot_score"] = 0
    state["user_bomb_used"] = False
    state["bot_bomb_used"] = False
    state["game_over"] = False
    state["final_result"] = None
    state["history"] = []

### Normalizing the user move logic

def normalize_user_move(user_text:str)->Optional[str]:
    text = user_text.strip().lower()
    synonyms = {
        "r":"rock",
        "p":"paper",
        "s":"scissors",
        "scissor":"scissors",
        "bomb":"bomb",
        "nuke":"bomb",
    }
    tokens = [t for t in re.split(r"[^a-z]+",text) if t]
    for t in tokens:
        t = synonyms.get(t,t)
        if t in VALID_MOVES:
            return t
    return None

### Chossing the bot move

def choose_bot_move(state:Dict[str,Any])->Move:
    bomb_avaliable = not state.get("bot_bomb_used",False)
    if bomb_avaliable and random.random() < 0.15:
        return "bomb"
    return random.choice(["rock", "paper", "scissors"])

### Logics behind the rounds and situations

def resolve_round(user_move: Move , bot_move: Move)->tuple[str,str]:
    if user_move=="bomb" and bot_move=="bomb":
        return "draw" , "bomb vs bomb -> draw"
    if user_move=="bomb" and bot_move!="bomb":
        return "user" , "bomb beats all other moves"
    if bot_move=="bomb" and user_move!="bomb":
        return "bot" , "bomb beats all the other moves"
    
    if user_move==bot_move:
        return "draw", "same_move->draw"
    
    beats = {"rock":"scissors","paper":"rock","scissors":"paper"}
    if beats[user_move]==bot_move:
        return "user", f"{user_move} beats {bot_move}"
    return "bot" , f"{bot_move} beats {user_move}"

def finalize_if_needed(state:Dict[str,Any],base:TurnResult)->TurnResult:
    rounds_played = int(state.get("rounds_played",0))
    user_score = int(state.get("user_score",0))
    bot_score = int(state.get("bot_score",0))

    base["rounds_played"] = rounds_played
    base["rounds_left"] = max(0, 3 - rounds_played)
    base["user_score"] = user_score
    base["bot_score"] = bot_score

    if rounds_played>=3:
        state["game_over"] = True
        if user_score > bot_score:
            state["final_result"] = "User wins"
        elif bot_score > user_score:
            state["final_result"] = "Bot wins"
        else:
            state["final_result"] = "Draw"

        base["game_over"] = True
        base["final_result"] = None
    else:
        base["game_over"] = False
        base["final_result"]=None

    return base

#=================
#ADK TOOL
#=================

def process_turn(user_input:str , tool_context : ToolContext)->TurnResult:

    state = tool_context.state
    ensure_state_initialized(state)

    ### logic for number of rounds game played

    if state.get("game_over"):
        return {
            "ok": True,
            "game_over": True,
            "final_result": state.get("final_result"),
            "rounds_played": state.get("rounds_played", 3),
            "rounds_left": 0,
            "user_score": state.get("user_score", 0),
            "bot_score": state.get("bot_score", 0),
            "round_winner": "none",
            "user_move": None,
            "bot_move": None,
            "round_number": 3,
            "reason": "Game is already over. Start a new session to play again.",
        }
    
    rounds_played = int(state.get("rounds_played",0))
    round_number = rounds_played+1

    ### Stricting the number of rounds_played upto 3

    if round_number>3:
        state["game_over"] = True
        state["final_result"] = state.get("final_result") or "Draw"

        return {
            "ok": True,
            "game_over": True,
            "final_result": state["final_result"],
            "rounds_played": rounds_played,
            "rounds_left": 0,
            "user_score": state.get("user_score", 0),
            "bot_score": state.get("bot_score", 0),
            "round_winner": "none",
            "user_move": None,
            "bot_move": None,
            "round_number": 3,
            "reason": "Reached the 3-round limit.",
        }
    
    ### Checking for the invalid input

    normalized = normalize_user_move(user_input)

    if normalized is None:
        state["rounds_played"] = rounds_played+1
        state["history"].append(
            {"round":round_number,"user_move":None,"bot_move":None,"winner":"none","reason":"Invalid input"}
        )
        return finalize_if_needed(
            state,
            {
                "ok": True,
                "round_number": round_number,
                "user_move": None,
                "bot_move": None,
                "round_winner": "none",
                "reason": "Invalid input → round wasted",
            },

        )
    ### Bomb only once for user
    if normalized == "bomb" and state.get("user_bomb_used", False):
        state["rounds_played"] = rounds_played + 1
        state["history"].append(
            {"round": round_number, "user_move": "bomb", "bot_move": None, "winner": "none", "reason": "Bomb already used"}
        )
        return finalize_if_needed(
            state,
            {
                "ok": True,
                "round_number": round_number,
                "user_move": "bomb",
                "bot_move": None,
                "round_winner": "none",
                "reason": "You already used bomb once → invalid → round wasted",
            },
        )
    
    user_move: Move = normalized  
    bot_move = choose_bot_move(state)

    if user_move == "bomb":
        state["user_bomb_used"] = True
    if bot_move == "bomb":
        state["bot_bomb_used"] = True

    winner, reason = resolve_round(user_move, bot_move)

    if winner == "user":
        state["user_score"] = int(state.get("user_score", 0)) + 1
    elif winner == "bot":
        state["bot_score"] = int(state.get("bot_score", 0)) + 1

    state["rounds_played"] = rounds_played + 1
    state["history"].append(
        {"round": round_number, "user_move": user_move, "bot_move": bot_move, "winner": winner, "reason": reason}
    )

    return finalize_if_needed(
        state,
        {
            "ok": True,
            "round_number": round_number,
            "user_move": user_move,
            "bot_move": bot_move,
            "round_winner": winner, 
            "reason": reason,
        },
    )

### LLM Response Formating -> Agent Response

SYSTEM_INSTRUCTION = """You are an AI Game Referee for Rock–Paper–Scissors–Plus.
Rules (<=5 lines, only once):
- 3 rounds total, game ends automatically after round 3.
- Moves: rock, paper, scissors, bomb (bomb only once per player).
- bomb beats any non-bomb; bomb vs bomb is a draw.
- Invalid input wastes the round.

Always call the tool process_turn(user_input) each turn.
After tool result, print exactly:
Round <n>/3
Moves: User=<...>, Bot=<...>
Winner: <user/bot/draw/none>
Score: User <u> - <b> Bot

If game_over=true, end with:
Final result: <User wins/Bot wins/Draw>
and DO NOT ask for another move.

If game_over=false, prompt: "Your move?"
"""

root_agent = LlmAgent(
    name="rps_plus_referee",
    model=os.environ.get("ADK_MODEL", "gemini-2.0-flash"),
    description="Referees a 3-round Rock–Paper–Scissors–Plus game and tracks state.",
    instruction=SYSTEM_INSTRUCTION,
    tools=[process_turn],
)

### logic for offline rendering

def fmt_move(x: Optional[str]) -> str:
        return x if x is not None else "—"

def _render_offline(tr: TurnResult) -> str:
    rn = tr.get("round_number", 0)

    um = fmt_move(tr.get("user_move"))
    bm = fmt_move(tr.get("bot_move"))
    winner = tr.get("round_winner", "none")
    if winner == "none":
        winner_text = "none (invalid/wasted)"
    else:
        winner_text = winner

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


### logic for calling the main function

APP_NAME = "rps_plus_app"
USER_ID = "local_user"
SESSION_ID = "local_session"


async def main() -> None:
    api_key_present = bool(os.getenv("GOOGLE_API_KEY"))
    model_name = os.getenv("ADK_MODEL", "gemini-2.0-flash")
    offline_mode = os.getenv("OFFLINE_MODE", "0") == "1"

    print(f"Diagnostics: GOOGLE_API_KEY present={api_key_present}, ADK_MODEL={model_name}, OFFLINE_MODE={offline_mode}")

   
    if not api_key_present and not offline_mode:
        print("Missing GOOGLE_API_KEY. Set it (or set OFFLINE_MODE=1 to demo without LLM).")
        return

    session_service = InMemorySessionService()
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

    print("\nRPS+ Referee is ready.\nMoves: rock | paper | scissors | bomb (once)\n")

    offline_state: Dict[str, Any] = {}

    while True:
        user_text = input("You: ").strip()
        if not user_text:
            continue

        if offline_mode:
            tool_ctx = SimpleToolContext(offline_state)
            tr = process_turn(user_text, tool_ctx)  
            print(f"\nReferee:\n{_render_offline(tr)}\n")
            if tr.get("game_over"):
                break
            continue

        user_message = Content(parts=[Part(text=user_text)])
        final_text = None

        try:
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=SESSION_ID,
                new_message=user_message,
            ):
                if event.is_final_response():
                    try:
                        final_text = "".join([p.text or "" for p in (event.content.parts or [])])
                    except Exception:
                        final_text = str(event.content)

        except _ResourceExhaustedError as e:
            print(
                "\nReferee:\nERROR: Gemini API quota/rate-limit (429 RESOURCE_EXHAUSTED).\n"
                "Your key is loaded, but your project has 0 available quota.\n"
                "Fix: enable billing/quota for the project OR set OFFLINE_MODE=1 in .env.\n"
            )
            msg = str(e).splitlines()
            if msg:
                print("Details:", msg[0])
            break

        except Exception as e:
            print("\nReferee:\nUnexpected error:", repr(e))
            break

        if final_text:
            print(f"\nReferee:\n{final_text}\n")

        sess = await session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
        if sess and sess.state.get("game_over"):
            break


if __name__ == "__main__":
    asyncio.run(main())


