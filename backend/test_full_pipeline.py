import asyncio
import sys
import os
import warnings
warnings.filterwarnings("ignore")

# Add app to path
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv(override=True)

from app.services.llm_service import analyze_code

async def test():
    print("Testing Gemini analysis pipeline...")
    result = await analyze_code(
        code='def find_max(nums):\n    max_val = 0\n    for i in range(len(nums) + 1):\n        if nums[i] > max_val:\n            max_val = nums[i]\n    return max_val',
        language='python',
        context='No specific KB context.',
        code_features={'suspected_concepts': ['loops', 'off-by-one']},
        is_recurring=False
    )
    print("Confidence:", result.get('confidence_score'))
    print("Errors:", len(result.get('errors', [])))
    print("Overall:", result.get('overall_feedback', '')[:100])
    print("Success:", result.get('confidence_score', 0) > 0.3)

asyncio.run(test())
