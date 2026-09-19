"""
TrialGuard AI — Seed Script

Seeds the database with deterministic synthetic demo data.
Run: python seed.py

This will:
  - Clear or recreate all demo collections
  - Create demo users
  - Create synthetic sites, patients, visits, medications
  - Run the deterministic protocol deviation engine
  - Calculate site risk scores
  - Create sample CAPA records
  - Create seed audit events

All data is entirely synthetic. No real patient data is used.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import create_repository
from synthetic_data import build_demo_state, DEMO_PASSWORD


if __name__ == "__main__":
    print("TrialGuard AI - Data Seeder")
    print("=" * 50)
    print("Building deterministic synthetic dataset...")

    repository = create_repository()
    state = build_demo_state()
    repository.replace_all(state)

    print(f"\n[OK] Backend:    {repository.backend}")
    print(f"[OK] Medicines:  {len(state.medicines)}")
    print(f"[OK] Trials:     {len(state.trials)}")
    print(f"[OK] Sites:      {len(state.sites)}")
    print(f"[OK] Patients:   {len(state.patients)} (synthetic only)")
    print(f"[OK] Visits:     {len(state.visits)}")
    print(f"[OK] Meds:       {len(state.medications)}")
    print(f"[OK] Deviations: {len(state.deviations)}")
    print(f"[OK] Risk scores:{len(state.risk_scores)}")
    print(f"[OK] Risk hist:  {len(state.risk_history)}")
    print(f"[OK] CAPAs:      {len(state.capa_records)}")
    print(f"[OK] Users:      {len(state.users)}")
    print(f"\nDemo accounts (password: {DEMO_PASSWORD})")
    print(f"  manager@trialguard.demo   (STUDY_MANAGER)")
    print(f"  site037@trialguard.demo   (SITE_COORDINATOR - S037 only)")
    print(f"  auditor@trialguard.demo   (AUDITOR - read-only)")
    print(f"  admin@trialguard.demo     (SYSTEM_ADMIN)")
    print(f"\nSeed complete. Run 'python server.py' to start.")
    print("=" * 50)
