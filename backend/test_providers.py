"""Quick test to verify provider selection logic and imports."""
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv(override=True)

# Test 1: Provider detection
from app.services.llm_service import _has_openai, _has_groq, _has_gemini
print("Provider detection:")
print(f"  OpenAI available:  {_has_openai()}")
print(f"  Groq available:    {_has_groq()}")
print(f"  Gemini available:  {_has_gemini()}")

# Test 2: SDK imports
try:
    from groq import AsyncGroq
    print("\n✅ Groq SDK imported OK")
except ImportError as e:
    print(f"\n❌ Groq SDK import failed: {e}")

try:
    import google.generativeai as genai
    print("✅ Gemini SDK imported OK")
except ImportError as e:
    print(f"❌ Gemini SDK import failed: {e}")

try:
    from openai import OpenAI
    print("✅ OpenAI SDK imported OK")
except ImportError as e:
    print(f"❌ OpenAI SDK import failed: {e}")

# Test 3: Show selected provider
if _has_openai():
    selected = "openai"
elif _has_groq():
    selected = "groq"
elif _has_gemini():
    selected = "gemini"
else:
    selected = "NONE"

print(f"\n🤖 Active backend will be: {selected.upper()}")
print("\nTo switch providers, paste your Groq key (gsk_...) into .env as GROQ_API_KEY")
