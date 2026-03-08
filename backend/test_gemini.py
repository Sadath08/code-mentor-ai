import asyncio
import os
from dotenv import load_dotenv
load_dotenv(override=True)

async def test():
    key = os.getenv('GEMINI_API_KEY', '')
    model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
    print('Key prefix:', key[:15] if key else 'MISSING')
    print('Model:', model_name)
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        m = genai.GenerativeModel(model_name)
        resp = await asyncio.to_thread(
            m.generate_content,
            'Return this exact JSON: {"status": "ok"}',
            generation_config={'temperature': 0.1, 'max_output_tokens': 50}
        )
        print('Response:', resp.text)
        print('SUCCESS: Gemini is working!')
    except Exception as e:
        print('FAILED:', type(e).__name__, '-', str(e))

asyncio.run(test())
