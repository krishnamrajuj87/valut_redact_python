import os
from dotenv import load_dotenv
import google.generativeai as genai
from typing import List, Dict

# Load environment variables from .env file
load_dotenv()

# Initialize Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def find_text_to_redact(text: str, prompt: str) -> List[Dict[str, str]]:
    # Use Gemini to find text to redact based on prompt
    response = model.generate_content(f"""
    Given the following text and prompt, identify specific text segments that should be redacted.
    Return the results in a JSON format with the following structure:
    {{
        "matches": [
            {{
                "text": "exact text to redact",
                "type": "type of sensitive information",
                "reason": "why this should be redacted"
            }}
        ]
    }}

    Text to analyze:
    {text}

    Prompt for redaction:
    {prompt}
    """)
    
    try:
        # Parse the response to extract matches
        import json
        response_text = response.text
        # Find JSON in the response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        json_str = response_text[start_idx:end_idx]
        result = json.loads(json_str)
        print("result of find_text_to_redact", result)
        return result.get("matches", [])
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        return [] 