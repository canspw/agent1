
from google import genai
import json
from typing import Dict, Any

# Configure API
genai.configure(api_key="AQ.Ab8RN6IMe71HYO8OQkHmWOnHhUT_VMxWW__jB5jATGPCkFb65A")  # or use env var

MODEL_NAME = "gemini-2.5-flash-lite"  # cheap + fast


PROMPT_TEMPLATE = """
You are an AI system that extracts structured information from internal enterprise data access requests.

Given the following email, extract the information in JSON format.

ONLY return valid JSON. No explanations.

Fields:
- business_purpose (one of: "Marketing Campaign", "Customer Issue Resolution", "Unknown")
- requested_action (one of: "Download Data", "Access Data", "View Data", "Unknown")
- mentioned_data_categories (list of strings)
- urgency (one of: "low", "normal", "high")
- missing_information (list of strings)
- contains_sensitive_data_request (true/false)
- confidence (0 to 1)

Email:
Subject: {subject}
Body:
{body}
"""


def extract_request(subject: str, body: str) -> Dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(subject=subject, body=body)

    model = genai.GenerativeModel(MODEL_NAME)

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.1,
        },
    )

    text = response.text.strip()

    # Defensive parsing (LLMs can misbehave)
    try:
        # Remove code fences if present
        if text.startswith("```"):
            text = text.strip("```").strip()

        parsed = json.loads(text)
        return parsed

    except Exception as e:
        raise ValueError(f"Failed to parse LLM response: {text}") from e