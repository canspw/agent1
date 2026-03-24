import os
import json
import re
from typing import Any, Dict
from google import genai
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "models/gemini-2.0-flash-lite"

# client = genai.Client(
#     api_key=os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
# )
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PROMPT_TEMPLATE = """
You extract structured information from enterprise customer-data access requests.

Return ONLY valid JSON.

Allowed values:
- business_purpose: "Marketing Campaign", "Customer Issue Resolution", or "Unknown"
- requested_action: "Download Data", "Access Data", "View Data", or "Unknown"

Return JSON with:
{
  "business_purpose": "...",
  "requested_action": "...",
  "mentioned_data_categories": ["..."],
  "urgency": "low|normal|high",
  "missing_information": ["..."],
  "contains_sensitive_data_request": true,
  "confidence": 0.0
}

Email subject: {subject}
Email body:
{body}
"""

def _parse_json(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)

def extract_request(subject: str, body: str) -> Dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(subject=subject, body=body)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )

    return _parse_json(response.text)