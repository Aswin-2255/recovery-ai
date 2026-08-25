# Machine Learning Subsystem — RecoverAI

## Scope & Philosophy
The ML subsystem powers honest, interpretable probability estimation for payment recovery:
$$P(\text{successful recovery} \mid \text{transaction features})$$

### Guiding Principles:
1. **Honest Metrics**: Evaluated strictly on held-out test datasets. Metrics include Precision, Recall, F1-Score, ROC-AUC, and full confusion matrix.
2. **Interpretability First**: Baseline models prioritize Logistic Regression and transparent feature importances before considering complex ensembles.
3. **No Fabricated Labels**: Ground truth labels derive deterministically from synthetic simulations and historical transaction logs.

### Key Features (Planned for Milestone 4):
- `amount`: Monetary value in INR.
- `payment_method`: UPI, Card, Netbanking, Wallet, EMI.
- `failure_code`: Standardized gateway failure codes (e.g. `BAD_REQUEST_GATEWAY_TIMEOUT`, `INSUFFICIENT_FUNDS`).
- `customer_success_ratio`: Historical merchant-customer relationship score.
- `retry_count`: Prior retry attempts on this transaction.
- `hour_of_day` & `day_of_week`: Temporal factors in bank settlement degradation.
