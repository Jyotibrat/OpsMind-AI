"""
scripts/evaluate.py
───────────────────
Simple evaluation script for OpsMind AI.

For each test question, this script calls the /ask endpoint and reports:
  - Whether the answer contains citations
  - The confidence score
  - A keyword match check
  - Whether the answer is the fallback

Usage (with server running):
    python scripts/evaluate.py

Set BASE_URL to point to your running server.
"""

import sys
import json
import requests

BASE_URL = "http://localhost:8000"

# ── Test cases ────────────────────────────────────────────────────────────────
TEST_CASES = [
    {
        "question": "What is the annual leave entitlement for employees?",
        "expected_keywords": ["leave", "days", "annual"],
        "source_hint": "Leave Policy",
    },
    {
        "question": "What are the remote work guidelines?",
        "expected_keywords": ["remote", "work", "home"],
        "source_hint": "Remote Work Policy",
    },
    {
        "question": "How are travel expenses reimbursed?",
        "expected_keywords": ["travel", "reimburs", "expense"],
        "source_hint": "Travel Reimbursement Policy",
    },
    {
        "question": "What is the policy on data privacy?",
        "expected_keywords": ["data", "privacy", "personal"],
        "source_hint": "Data Privacy Policy",
    },
    {
        "question": "How can an employee raise a grievance?",
        "expected_keywords": ["grievance", "complaint", "redress"],
        "source_hint": "Grievance Redressal Policy",
    },
    {
        "question": "What is the recipe for chocolate cake?",  # Should return fallback
        "expected_keywords": [],
        "expects_fallback": True,
    },
]

FALLBACK_TEXT = "I don't know based on the available documents."


def evaluate() -> None:
    print("=" * 65)
    print("  OpsMind AI — Evaluation Report")
    print("=" * 65)

    passed = 0
    total = len(TEST_CASES)

    for i, case in enumerate(TEST_CASES, start=1):
        question = case["question"]
        print(f"\n[{i}/{total}] Q: {question}")

        try:
            resp = requests.post(
                f"{BASE_URL}/ask",
                json={"question": question},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"  ✗ Request failed: {exc}")
            continue

        answer = data.get("answer", "")
        confidence = data.get("confidence_score", 0.0)
        citations = data.get("citations", [])
        is_fallback = FALLBACK_TEXT in answer

        print(f"  Confidence : {confidence:.4f}")
        print(f"  Citations  : {len(citations)}")
        print(f"  Fallback   : {is_fallback}")
        print(f"  Answer     : {answer[:120]}…" if len(answer) > 120 else f"  Answer     : {answer}")

        checks = []

        # Fallback expectation check
        if case.get("expects_fallback"):
            ok = is_fallback
            checks.append(("Expects fallback", ok))
        else:
            # Keyword check
            kw_ok = any(
                kw.lower() in answer.lower() for kw in case.get("expected_keywords", [])
            )
            checks.append(("Keyword match", kw_ok))
            # Citation check
            checks.append(("Has citations", len(citations) > 0))
            # Confidence check
            checks.append(("Confidence ≥ 0.75", confidence >= 0.75))

        for check_name, ok in checks:
            icon = "✓" if ok else "✗"
            print(f"  {icon} {check_name}")

        if all(ok for _, ok in checks):
            passed += 1

    print("\n" + "=" * 65)
    print(f"  Results: {passed}/{total} test cases passed.")
    print("=" * 65)


if __name__ == "__main__":
    evaluate()
