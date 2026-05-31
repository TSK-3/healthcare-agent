import logging
import textwrap
import json
import os
import psycopg2

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
)
from livekit.plugins import deepgram, silero, groq
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env.local"))
load_dotenv(_ENV_PATH)


def load_ques(path: str | None = None):
    if path is None:
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "questions.json"))
    with open(path, "r") as f:
        data = json.load(f)
    return data['questions']


def get_db_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))


class SaveSession:
    def __init__(self, room_id: str, department: str = "general"):
        self.room_id      = room_id
        self.department   = department
        self.conversation = []

        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS answers (
                id           SERIAL PRIMARY KEY,
                room_id      TEXT,
                department   TEXT,
                conversation JSONB,
                created_at   TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        

    def add(self, role: str, text: str):
        self.conversation.append({
            "role": role,
            "text": text,
            "time": __import__('datetime').datetime.now().isoformat()
        })
  

    def save(self):
        try:
            conn = get_db_connection()
            cur  = conn.cursor()
            cur.execute(
                """INSERT INTO answers
                   (room_id, department, conversation)
                   VALUES (%s, %s, %s)""",
                (
                    self.room_id,
                    self.department,
                    json.dumps(self.conversation)
                )
            )
            conn.commit()
            cur.close()
            conn.close()
           
        except Exception as e:
            print(f" DB error: {e}")


def build_instructions(questions):
    questions_text = ""
    for i, q in enumerate(questions, 1):
        questions_text += f"{i}. {q['question']}\n"

    return textwrap.dedent(f"""
        You are a friendly healthcare voice assistant conducting
        a patient intake interview over a phone call.

        Your job is to ask the patient these questions ONE BY ONE in order:

        {questions_text}

        # Rules
        - Ask ONE question at a time
        - Wait for the patient to finish answering before moving on
        - If answer is unclear ask them to repeat once politely
        - Be warm, empathetic and professional
        - After ALL questions are done say exactly:
          "Thank you! Your responses have been recorded.
           A healthcare professional will follow up with you soon. Goodbye!"
        - Do NOT skip any questions
        - Keep responses short — this is a voice call
        - Never use lists, markdown or bullet points — speak naturally

        # Output rules
        - Respond in plain text only
        - Spell out numbers
        - Keep replies brief and conversational
    """)


class HealthcareAssistant(Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(
            llm=groq.LLM(model="llama-3.3-70b-versatile"),
            instructions=instructions,
        )


server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm


@server.rtc_session(agent_name="healthcare-agent")
async def healthcare_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    questions    = load_ques()
    instructions = build_instructions(questions)
    save_session = SaveSession(room_id=ctx.room.name)

    session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="en"),
        tts=deepgram.TTS(model="aura-asteria-en"),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    @session.on("user_input_transcribed")
    def on_user_speech(event):
        if event.is_final:
            
            save_session.add("patient", event.transcript)

    @session.on("agent_speech_committed")
    def on_agent_speech(event):
        
        save_session.add("agent", event.text) 

    @session.on("session_stopped")             
    def on_session_end():
        
        save_session.save()

    await session.start(
        agent=HealthcareAssistant(instructions=instructions),
        room=ctx.room,
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)