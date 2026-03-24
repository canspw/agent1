from __future__ import annotations

from typing import List, Dict, Optional
from uuid import uuid4
import re

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from policy_engine import PolicyEngine
from preview_generator import generate_preview

from llm_extractor import extract_request

app = FastAPI(title="Customer Data Access Agent POC")

engine = PolicyEngine(
    field_catalog_path="data/field_catalog.csv",
    access_rules_path="data/access_rules.csv",
)


class EmailRequest(BaseModel):
    sender: str
    subject: str
    body: str
    role_override: Optional[str] = None


class ParsedRequest(BaseModel):
    request_id: str
    sender: str
    subject: str
    request_type: str
    business_purpose: str
    requested_action: str
    mentioned_data: List[str]
    possible_sensitive_data_requested: List[str]
    confidence: float
    missing_information: List[str]
    routed_team: str
    status: str


class AccessEvaluationRequest(BaseModel):
    role: str
    purpose: str


class AccessEvaluationResponse(BaseModel):
    role: str
    purpose: str
    download_allowed: bool
    approval_required: bool
    allowed_fields: List[str]
    masked_fields: List[str]
    denied_fields: List[str]
    reason_by_field: Dict[str, str]
    preview_rows: List[Dict[str, object]]


class SubmitRequestResponse(BaseModel):
    request_id: str
    sender: str
    resolved_role: str
    subject: str
    request_type: str
    business_purpose: str
    requested_action: str
    mentioned_data: List[str]
    possible_sensitive_data_requested: List[str]
    confidence: float
    missing_information: List[str]
    routed_team: str
    status: str
    download_allowed: bool
    approval_required: bool
    allowed_fields: List[str]
    masked_fields: List[str]
    denied_fields: List[str]
    reason_by_field: Dict[str, str]
    preview_rows: List[Dict[str, object]]
    user_message: str


PURPOSE_KEYWORDS = {
    "marketing": "Marketing Campaign",
    "campaign": "Marketing Campaign",
    "analytics": "Marketing Campaign",
    "analysis": "Marketing Campaign",
    "customer issue": "Customer Issue Resolution",
    "complaint": "Customer Issue Resolution",
    "billing issue": "Customer Issue Resolution",
    "service issue": "Customer Issue Resolution",
}

ACTION_KEYWORDS = {
    "download": "Download Data",
    "access": "Access Data",
    "extract": "Extract Data",
    "sample": "Request Sample",
    "view": "View Data",
}

DATA_FIELDS = {
    "credit card": "credit_card_number",
    "card number": "credit_card_number",
    "email": "email_address",
    "phone": "phone_number",
    "address": "home_address",
    "dob": "date_of_birth",
    "date of birth": "date_of_birth",
    "customer": "customer_profile",
    "campaign": "campaign_history",
    "response": "response_history",
    "balance": "account_balance_band",
    "segment": "customer_segment",
}

SENSITIVE_FIELDS = {
    "credit_card_number",
    "email_address",
    "phone_number",
    "home_address",
    "date_of_birth",
}

ROUTING_RULES = {
    "Marketing Campaign": "Marketing Data Governance",
    "Customer Issue Resolution": "Customer Operations Data Support",
    "Unknown": "Manual Review Queue",
}

# Simple POC sender-to-role mapping.
# In a real system this would come from HR/IAM/directory services.
SENDER_ROLE_MAP = {
    "alex@company.com": "Marketing Analyst",
    "maya@company.com": "Customer Service Rep",
    "olivia@company.com": "Operations Manager",
}


def detect_business_purpose(text: str) -> str:
    lowered = text.lower()
    for keyword, purpose in PURPOSE_KEYWORDS.items():
        if keyword in lowered:
            return purpose
    return "Unknown"


def detect_requested_action(text: str) -> str:
    lowered = text.lower()
    for keyword, action in ACTION_KEYWORDS.items():
        if keyword in lowered:
            return action
    return "Unknown"


def detect_data_mentions(text: str) -> List[str]:
    lowered = text.lower()
    found = []
    for keyword, field_name in DATA_FIELDS.items():
        if keyword in lowered and field_name not in found:
            found.append(field_name)
    return found


def infer_missing_information(body: str, business_purpose: str, requested_action: str) -> List[str]:
    missing = []

    if business_purpose == "Unknown":
        missing.append("business purpose is unclear")

    if requested_action == "Unknown":
        missing.append("requested action is unclear")

    if not re.search(r"\bapproval\b|\bmanager\b|\bdirector\b", body.lower()):
        missing.append("manager or business approval not mentioned")

    if not re.search(r"\burgent\b|\bby\b|\bbefore\b|\bdeadline\b", body.lower()):
        missing.append("timeline or urgency not provided")

    return missing


def score_confidence(
    business_purpose: str,
    requested_action: str,
    mentioned_data: List[str],
    missing_information: List[str],
) -> float:
    score = 0.4

    if business_purpose != "Unknown":
        score += 0.2
    if requested_action != "Unknown":
        score += 0.2
    if mentioned_data:
        score += 0.1

    score -= min(len(missing_information) * 0.05, 0.2)

    return max(0.0, min(round(score, 2), 1.0))


def route_request(business_purpose: str) -> str:
    return ROUTING_RULES.get(business_purpose, "Manual Review Queue")


def resolve_role(sender: str, role_override: Optional[str]) -> str:
    if role_override and role_override.strip():
        return role_override.strip()

    if sender.lower() in SENDER_ROLE_MAP:
        return SENDER_ROLE_MAP[sender.lower()]

    return "Customer Service Rep"


def build_user_message(
    parsed: ParsedRequest,
    resolved_role: str,
    download_allowed: bool,
    approval_required: bool,
) -> str:
    parts = []

    parts.append(
        f"I've submitted your request to {parsed.routed_team}. "
        f"Based on the sender profile, your role was resolved as {resolved_role}."
    )

    if approval_required:
        parts.append(
            "Approval is required before any governed extract can be provided."
        )

    if download_allowed:
        parts.append(
            "A download is permitted for this role and purpose, subject to governance rules."
        )
    else:
        parts.append(
            "Direct download is not permitted for this role and purpose."
        )

    parts.append(
        "Below is a policy-compliant synthetic preview showing the fields you are eligible to access. "
        "Restricted fields have been excluded or masked."
    )

    if parsed.missing_information:
        parts.append(
            "The request is missing some information that may be needed for fulfillment: "
            + "; ".join(parsed.missing_information)
            + "."
        )

    return " ".join(parts)


@app.get("/")
def root() -> dict:
    return {"message": "Customer Data Access Agent API is running"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest-email", response_model=ParsedRequest)
def ingest_email(email: EmailRequest) -> ParsedRequest:
    combined_text = f"{email.subject}\n{email.body}"
    print(f"combined text: {combined_text}")

    # from llm_extractor_v1 import extract_request

    try:
        llm_output = extract_request(email.subject, email.body)

        print("DEBUG: LLM extraction succeeded")
        print(f"DEBUG: LLM output = {llm_output}")

        business_purpose = llm_output.get("business_purpose", "Unknown")
        requested_action = llm_output.get("requested_action", "Unknown")
        mentioned_data = llm_output.get("mentioned_data_categories", [])
        confidence = llm_output.get("confidence", 0.5)

        sensitive_flag = llm_output.get("contains_sensitive_data_request", False)
        possible_sensitive_data_requested = mentioned_data if sensitive_flag else []

        missing_information = llm_output.get("missing_information", [])

    except Exception:
        print("DEBUG: LLM extraction FAIL")
        print(f"DEBUG: LLM output FAIL =")
        # fallback to keyword logic
        business_purpose = detect_business_purpose(combined_text)
        requested_action = detect_requested_action(combined_text)
        mentioned_data = detect_data_mentions(combined_text)
        possible_sensitive_data_requested = [
            f for f in mentioned_data if f in SENSITIVE_FIELDS
        ]
        missing_information = infer_missing_information(
            body=email.body,
            business_purpose=business_purpose,
            requested_action=requested_action,
        )
        confidence = 0.4




    sensitive_mentions = [f for f in mentioned_data if f in SENSITIVE_FIELDS]

    missing_information = infer_missing_information(
        body=email.body,
        business_purpose=business_purpose,
        requested_action=requested_action,
    )

    confidence = score_confidence(
        business_purpose=business_purpose,
        requested_action=requested_action,
        mentioned_data=mentioned_data,
        missing_information=missing_information,
    )

    status = "Needs Review" if missing_information else "Ready for Policy Evaluation"

    return ParsedRequest(
        request_id=str(uuid4()),
        sender=email.sender,
        subject=email.subject,
        request_type="Customer Data Access Request",
        business_purpose=business_purpose,
        requested_action=requested_action,
        mentioned_data=mentioned_data,
        possible_sensitive_data_requested=sensitive_mentions,
        confidence=confidence,
        missing_information=missing_information,
        routed_team=route_request(business_purpose),
        status=status,
    )


@app.post("/evaluate-access", response_model=AccessEvaluationResponse)
def evaluate_access(req: AccessEvaluationRequest) -> AccessEvaluationResponse:
    try:
        decision, preview_df = generate_preview(
            customer_data_path="data/synthetic_customer_data.csv",
            engine=engine,
            role=req.role,
            purpose=req.purpose,
            sample_size=5,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return AccessEvaluationResponse(
        role=decision.role,
        purpose=decision.purpose,
        download_allowed=decision.download_allowed,
        approval_required=decision.approval_required,
        allowed_fields=decision.allowed_fields,
        masked_fields=decision.masked_fields,
        denied_fields=decision.denied_fields,
        reason_by_field=decision.reason_by_field,
        preview_rows=preview_df.to_dict(orient="records"),
    )


@app.post("/submit-request", response_model=SubmitRequestResponse)
def submit_request(email: EmailRequest) -> SubmitRequestResponse:
    parsed = ingest_email(email)

    resolved_role = resolve_role(
        sender=email.sender,
        role_override=email.role_override,
    )

    if parsed.business_purpose == "Unknown":
        raise HTTPException(
            status_code=400,
            detail="Could not determine business purpose from the request."
        )

    try:
        decision, preview_df = generate_preview(
            customer_data_path="data/synthetic_customer_data.csv",
            engine=engine,
            role=resolved_role,
            purpose=parsed.business_purpose,
            sample_size=5,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_message = build_user_message(
        parsed=parsed,
        resolved_role=resolved_role,
        download_allowed=decision.download_allowed,
        approval_required=decision.approval_required,
    )

    return SubmitRequestResponse(
        request_id=parsed.request_id,
        sender=parsed.sender,
        resolved_role=resolved_role,
        subject=parsed.subject,
        request_type=parsed.request_type,
        business_purpose=parsed.business_purpose,
        requested_action=parsed.requested_action,
        mentioned_data=parsed.mentioned_data,
        possible_sensitive_data_requested=parsed.possible_sensitive_data_requested,
        confidence=parsed.confidence,
        missing_information=parsed.missing_information,
        routed_team=parsed.routed_team,
        status=parsed.status,
        download_allowed=decision.download_allowed,
        approval_required=decision.approval_required,
        allowed_fields=decision.allowed_fields,
        masked_fields=decision.masked_fields,
        denied_fields=decision.denied_fields,
        reason_by_field=decision.reason_by_field,
        preview_rows=preview_df.to_dict(orient="records"),
        user_message=user_message,
    )