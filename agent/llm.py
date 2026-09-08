"""Small provider switch for optional LLM-written wording."""
import os
from dotenv import load_dotenv
load_dotenv()

def get_llm():
    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    openai_key, anthropic_key = os.getenv("OPENAI_API_KEY", ""), os.getenv("ANTHROPIC_API_KEY", "")
    def usable(key):
        return bool(key) and not key.lower().startswith(("dummy", "test", "your_", "replace"))
    if provider in ("auto", "openai") and usable(openai_key):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini", temperature=0, api_key=openai_key)
    if provider in ("auto", "anthropic") and usable(anthropic_key):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL") or "claude-3-5-haiku-latest", temperature=0, api_key=anthropic_key)
    return None
