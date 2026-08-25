"""Database seeding CLI utility for RecoverAI.

Usage:
    python -m app.scripts.seed_db [--seed 42] [--count 500] [--no-reset]
"""
import argparse
import sys
from collections import Counter
from typing import Dict

from sqlalchemy import func
from app.core.database import Base, engine, SessionLocal
from app.models import Merchant, Customer, Transaction, RecoveryCase, RecoveryAction, AgentDecision, AuditLog
from app.services.synthetic_generator import SyntheticPaymentGenerator


def seed_database(seed: int = 42, count: int = 500, reset: bool = True) -> Dict[str, any]:
    """Populate database with reproducible synthetic transaction records."""
    print(f"\n========================================================")
    print(f"  RecoverAI Database Seeder [Seed: {seed}, Count: {count}]")
    print(f"========================================================")

    # 1. Prepare Schema
    if reset:
        print("Resetting database schema (dropping and recreating tables)...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    else:
        print("Ensuring database tables exist...")
        Base.metadata.create_all(bind=engine)

    # 2. Instantiate Generator
    generator = SyntheticPaymentGenerator(seed=seed)
    merchant = generator.generate_merchant()
    customers = generator.generate_customers(merchant_id=merchant.id, count=60)
    transactions, recovery_cases, audit_logs = generator.generate_dataset(
        merchant=merchant,
        customers=customers,
        total_transactions=count,
        include_incident=True,
    )

    # 3. Persist to Database in Transactional Batch
    db = SessionLocal()
    try:
        print(f"Persisting Merchant ({merchant.name})...")
        db.add(merchant)
        db.commit()

        print(f"Persisting {len(customers)} Customers...")
        db.add_all(customers)
        db.commit()

        print(f"Persisting {len(transactions)} Transactions...")
        db.add_all(transactions)
        db.commit()

        print(f"Persisting {len(recovery_cases)} Recovery Cases...")
        db.add_all(recovery_cases)
        db.commit()

        print(f"Persisting {len(audit_logs)} Audit Logs...")
        db.add_all(audit_logs)
        db.commit()

        # 4. Verify & Compute Analytics directly from Database
        db_mcht_count = db.query(Merchant).count()
        db_cust_count = db.query(Customer).count()
        db_txn_count = db.query(Transaction).count()
        db_case_count = db.query(RecoveryCase).count()
        db_audit_count = db.query(AuditLog).count()

        success_count = db.query(Transaction).filter(Transaction.status == "success").count()
        failed_count = db.query(Transaction).filter(Transaction.status == "failed").count()
        abandoned_count = db.query(Transaction).filter(Transaction.status == "abandoned").count()

        total_volume = db.query(func.sum(Transaction.amount)).scalar() or 0.0
        total_at_risk = db.query(func.sum(RecoveryCase.revenue_at_risk)).scalar() or 0.0

        # Method breakdown
        method_counts = Counter([t.payment_method for t in transactions])
        # Classification breakdown
        class_counts = Counter([c.classification for c in recovery_cases])
        # Incident transactions
        incident_txns = db.query(Transaction).filter(Transaction.is_degradation_incident == True).count()

        success_rate = (success_count / db_txn_count * 100) if db_txn_count > 0 else 0.0

        print("\n=== SEEDING SUMMARY REPORT ===")
        print(f"  Merchants:             {db_mcht_count}")
        print(f"  Customers:             {db_cust_count}")
        print(f"  Total Transactions:    {db_txn_count}")
        print(f"    - Success:           {success_count} ({success_rate:.1f}%)")
        print(f"    - Failed:            {failed_count}")
        print(f"    - Abandoned:         {abandoned_count}")
        print(f"  Total Revenue Volume:  INR {total_volume:,.2f}")
        print(f"  Total Revenue At Risk: INR {total_at_risk:,.2f}")
        print(f"  Recovery Cases:        {db_case_count}")
        print(f"    - Recoverable:       {class_counts.get('recoverable', 0)}")
        print(f"    - Uncertain:         {class_counts.get('uncertain', 0)}")
        print(f"    - Unlikely:          {class_counts.get('unlikely_to_recover', 0)}")
        print(f"  Audit Logs Recorded:   {db_audit_count}")
        print(f"  Incident Transcations: {incident_txns} (Degradation simulated)")
        print("========================================================\n")

        return {
            "merchants": db_mcht_count,
            "customers": db_cust_count,
            "transactions": db_txn_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "abandoned_count": abandoned_count,
            "success_rate": success_rate,
            "total_volume_inr": total_volume,
            "total_revenue_at_risk_inr": total_at_risk,
            "recovery_cases": db_case_count,
            "audit_logs": db_audit_count,
            "incident_transactions": incident_txns,
            "method_counts": dict(method_counts),
            "class_counts": dict(class_counts),
        }

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Seeding failed: {e}", file=sys.stderr)
        raise e
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed RecoverAI database with synthetic payment records.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation (default: 42)")
    parser.add_argument("--count", type=int, default=500, help="Total transactions to generate (default: 500)")
    parser.add_argument("--no-reset", action="store_true", help="Do not drop existing tables before inserting")

    args = parser.parse_args()
    seed_database(seed=args.seed, count=args.count, reset=not args.no_reset)


if __name__ == "__main__":
    main()
