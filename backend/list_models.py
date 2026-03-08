import os; from dotenv import load_dotenv; load_dotenv(override=True)
import google.generativeai as genai
import warnings; warnings.filterwarnings("ignore")
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
for m in models:
    print(m)
