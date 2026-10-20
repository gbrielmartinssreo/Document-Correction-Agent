from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv

import os
import requests

load_dotenv()


def check_openrouter_key() -> bool:
    key = os.getenv("OPENROUTER_API_KEY")

    if not key:
        return False

    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=5,
        )
        return response.status_code == 200

    except requests.RequestException:
        return False


def create_dca_agent():
    key = os.getenv("OPENROUTER_API_KEY")

    if not key:
        raise ValueError("OPENROUTER_API_KEY não encontrada no .env")

    checkpointer = InMemorySaver()

    model = init_chat_model(
        "openrouter:deepseek/deepseek-v4-flash-0731",
        api_key=key,
        temperature=0.1,
        timeout=60000,
        max_tokens=10000,
    )

    agent = create_agent(
        model=model,
        tools=[],
        checkpointer=checkpointer,
    )

    return agent, checkpointer
