"""Minimal diagnostic — run: .venv/Scripts/python.exe test_ai.py"""
import asyncio, os, sys, traceback
from dotenv import load_dotenv; load_dotenv()

os.environ["PYTHONUNBUFFERED"] = "1"

async def main():
    from app.config import get_settings
    s = get_settings()
    key = s.openai_api_key
    print(f"[1] openai_api_key set: {bool(key)}, first 12: {key[:12]}")
    print(f"[2] openai_model: {s.openai_model}")
    print(f"[3] use_openai: {s.use_openai}")

    # Direct OpenAI test
    print("\n[4] Testing OpenAI directly...")
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=key)
        resp = await client.chat.completions.create(
            model=s.openai_model,
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": 'Return exactly: {"ok": true}'}
            ],
            max_tokens=30,
            timeout=20,
            response_format={"type": "json_object"},
        )
        print(f"[4] SUCCESS: {resp.choices[0].message.content}")
    except Exception as e:
        print(f"[4] FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()

    # analyze_code test with patched logging
    print("\n[5] Testing analyze_code...")
    import logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, force=True)
    try:
        from app.services.llm_service import analyze_code
        result = await analyze_code(
            code="def bad():\n    for i in range(len(lst)+1): print(lst[i])",
            language="python",
            context="Python loops: use range(len(arr)) not range(len(arr)+1)",
            code_features={"suspected_concepts": ["loops"], "has_loops": True,
                           "has_recursion": False, "complexity_estimate": "low", "line_count": 2},
        )
        print(f"\n[5] confidence_score = {result.get('confidence_score')}")
        print(f"[5] errors = {len(result.get('errors', []))}")
        print(f"[5] feedback = {result.get('overall_feedback', '')[:100]}")
    except Exception as e:
        print(f"[5] EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()

asyncio.run(main())
