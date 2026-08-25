# RecoverAI — System Architecture & Design Specification

## Overview
RecoverAI is a financial intelligence and autonomous revenue recovery system built for Razorpay Track 3. It addresses revenue leakage from payment failures, checkout drop-offs, and subscription declines without risking customer trust or violating merchant policies.

## The 6-Stage Recovery Lifecycle

```
[Detect] ➔ [Diagnose] ➔ [Decide] ➔ [Execute] ➔ [Verify] ➔ [Measure]
```

1. **Detect (Revenue-at-Risk Engine)**
   - Listens to payment failure events and webhooks.
   - Evaluates whether the failure is transient, systemic, or terminal.
   - Computes expected revenue at risk based on payment method and merchant historical baseline.

2. **Diagnose (Root Cause Analysis)**
   - Computes real-time degradation metrics (e.g. UPI bank gateway latency surge, OTP expiry, insufficient funds).
   - Generates deterministic, verifiable statistical summaries.

3. **Decide (ML Recovery Probability & Agent Strategy)**
   - Predicts $P(\text{recovery} \mid \text{features})$ using an interpretable model.
   - AI agent evaluates available interventions (smart retry, payment link dispatch, fallback payment method prompt, invoice reminder).

4. **Execute (Policy Guardrails & Bounded Actions)**
   - **Policy Engine has absolute veto authority.** AI agent proposes; Policy Engine validates.
   - Enforces stopping rules: max retry limit, customer opt-out, high-risk threshold, time elapsed.
   - Executes bounded action via Razorpay Test Mode or local deterministic simulator.

5. **Verify (Payment Status Validation)**
   - Validates payment confirmation via cryptographically signed webhooks and status queries.
   - Detects and drops duplicate webhooks via idempotency tracking.

6. **Measure & Audit (Financial Impact Accounting)**
   - Calculates exact currency recovered from verified ledger entries.
   - Records an immutable audit log linking detection, rationale, policy check, action, and verified outcome.

---

## Security & Safety Boundaries
- **No LLM Direct Database Access**: The AI agent only accesses controlled function tools with strict input schemas.
- **Independent Policy Engine**: Safety rules are hardcoded deterministic logic outside the LLM prompt.
- **Zero Live Credentials**: All integrations strictly use Razorpay Test Mode keys with sandbox accounts.
