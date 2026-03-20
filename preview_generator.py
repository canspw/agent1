from __future__ import annotations

import pandas as pd

from policy_engine import PolicyDecision, PolicyEngine


def generate_preview(
    customer_data_path: str,
    engine: PolicyEngine,
    role: str,
    purpose: str,
    sample_size: int = 5,
) -> tuple[PolicyDecision, pd.DataFrame]:
    decision = engine.evaluate(role=role, purpose=purpose)
    df = pd.read_csv(customer_data_path)

    preview_df = engine.apply_masking(df, decision).head(sample_size)

    return decision, preview_df
