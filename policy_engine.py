from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd


@dataclass
class PolicyDecision:
    role: str
    purpose: str
    download_allowed: bool
    approval_required: bool
    allowed_fields: List[str]
    masked_fields: List[str]
    denied_fields: List[str]
    reason_by_field: Dict[str, str]


class PolicyEngine:
    def __init__(self, field_catalog_path: str, access_rules_path: str):
        self.field_catalog = pd.read_csv(field_catalog_path)
        self.access_rules = pd.read_csv(access_rules_path)

    def get_rule(self, role: str, purpose: str) -> pd.Series:
        match = self.access_rules[
            (self.access_rules["role"] == role)
            & (self.access_rules["purpose"] == purpose)
        ]
        if match.empty:
            raise ValueError(f"No access rule found for role='{role}', purpose='{purpose}'")
        return match.iloc[0]

    def evaluate(self, role: str, purpose: str) -> PolicyDecision:
        rule = self.get_rule(role, purpose)
        allowed_flag_column = rule["allowed_flag_column"]

        allowed_fields: List[str] = []
        masked_fields: List[str] = []
        denied_fields: List[str] = []
        reason_by_field: Dict[str, str] = {}

        for _, row in self.field_catalog.iterrows():
            field_name = row["field_name"]
            allowed_for_purpose = str(row[allowed_flag_column]).strip().lower() == "yes"
            masking_rule = str(row["masking_rule"]).strip().lower()

            if not allowed_for_purpose:
                denied_fields.append(field_name)
                reason_by_field[field_name] = f"Not permitted for purpose '{purpose}'"
                continue

            if masking_rule in {"surrogate", "mask_last4"}:
                allowed_fields.append(field_name)
                masked_fields.append(field_name)
                reason_by_field[field_name] = f"Allowed with masking rule '{masking_rule}'"
            elif masking_rule == "allow":
                allowed_fields.append(field_name)
                reason_by_field[field_name] = "Allowed"
            else:
                denied_fields.append(field_name)
                reason_by_field[field_name] = f"Denied due to masking rule '{masking_rule}'"

        return PolicyDecision(
            role=role,
            purpose=purpose,
            download_allowed=str(rule["download_allowed"]).strip().lower() == "yes",
            approval_required=str(rule["approval_required"]).strip().lower() == "yes",
            allowed_fields=allowed_fields,
            masked_fields=masked_fields,
            denied_fields=denied_fields,
            reason_by_field=reason_by_field,
        )

    def apply_masking(self, df: pd.DataFrame, decision: PolicyDecision) -> pd.DataFrame:
        output = df[decision.allowed_fields].copy()

        field_catalog_indexed = self.field_catalog.set_index("field_name")

        for field in decision.masked_fields:
            masking_rule = str(field_catalog_indexed.loc[field, "masking_rule"]).strip().lower()

            if masking_rule == "surrogate":
                output[field] = output[field].apply(self._surrogate_value)
            elif masking_rule == "mask_last4":
                output[field] = output[field].apply(self._mask_last4)

        return output

    @staticmethod
    def _surrogate_value(value: object) -> str:
        if pd.isna(value):
            return "UNKNOWN"
        return f"SURR_{abs(hash(str(value))) % 100000:05d}"

    @staticmethod
    def _mask_last4(value: object) -> str:
        if pd.isna(value):
            return "****"
        text = str(value)
        if len(text) >= 4:
            return f"****{text[-4:]}"
        return "****"