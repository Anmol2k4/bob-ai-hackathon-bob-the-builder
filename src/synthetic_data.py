"""
TrialGuard AI — Deterministic Synthetic Clinical-Trial Data Generator

IMPORTANT DISCLAIMER:
All data in this module is entirely synthetic. No real patient information, real
clinical trial data, or real site information is used. The data is designed solely
for software demonstration purposes.

The deterministic random seed ensures the same dataset is always produced.
"""
from __future__ import annotations
from datetime import date, timedelta
import random

from models import RepositoryState
from security import hash_password

DEMO_PASSWORD = "TrialGuard2026!"
SEED = 37037


def build_demo_state() -> RepositoryState:
    rng = random.Random(SEED)
    state = RepositoryState()

    state.users = _build_users()
    state.sites = _build_sites(rng)
    state.patients = _build_patients(state.sites, rng)
    state.protocols = _build_protocol()
    state.visits = _build_visits(state.patients, rng)
    state.medications = _build_medications(state.patients, rng)
    state.deviations = _build_deviations(state.sites, state.patients, state.visits, state.medications, rng)
    state.risk_scores = _build_risk_scores(state.sites, state.deviations)
    state.capa_records = _build_capa_records(state.sites, state.deviations)
    state.audit_events = _build_audit_events(state.users)
    return state


# ─── users ────────────────────────────────────────────────────────────────────

def _build_users() -> list[dict]:
    return [
        {
            "user_id": "U-MANAGER",
            "name": "Maya Chen",
            "email": "manager@trialguard.demo",
            "password_hash": hash_password(DEMO_PASSWORD, "manager-salt"),
            "role": "STUDY_MANAGER",
            "site_id": None,
            "created_at": "2026-01-01",
        },
        {
            "user_id": "U-S037",
            "name": "Jordan Lee",
            "email": "site037@trialguard.demo",
            "password_hash": hash_password(DEMO_PASSWORD, "site-salt"),
            "role": "SITE_COORDINATOR",
            "site_id": "S037",
            "created_at": "2026-01-05",
        },
        {
            "user_id": "U-AUDITOR",
            "name": "Riley Singh",
            "email": "auditor@trialguard.demo",
            "password_hash": hash_password(DEMO_PASSWORD, "auditor-salt"),
            "role": "AUDITOR",
            "site_id": None,
            "created_at": "2026-01-03",
        },
        {
            "user_id": "U-ADMIN",
            "name": "Alex Morgan",
            "email": "admin@trialguard.demo",
            "password_hash": hash_password(DEMO_PASSWORD, "admin-salt"),
            "role": "SYSTEM_ADMIN",
            "site_id": None,
            "created_at": "2025-12-15",
        },
    ]


# ─── sites ────────────────────────────────────────────────────────────────────

LOCATIONS = ["Boston, MA", "Austin, TX", "Toronto, ON", "Dublin, IE", "Chicago, IL",
             "London, UK", "Sydney, AU", "Singapore", "Amsterdam, NL", "Zurich, CH"]
INVESTIGATORS = ["Dr. A. Patel", "Dr. M. Rivera", "Dr. S. Okafor", "Dr. L. Wong",
                 "Dr. J. Kim", "Dr. P. Fischer", "Dr. N. Gupta", "Dr. C. Roberts"]
SITE_PROFILES = {
    "S037": "high_dosing",
    "S008": "high_missed",    # S008 = second high-risk site (missed visits)
    "S021": "high_frequency", # S021 = third high-risk site (high frequency)
}

# Map human-readable demo names to actual site IDs
HIGH_RISK_DEMO_SITES = ["S037", "S008", "S021"]


def _build_sites(rng: random.Random) -> list[dict]:
    sites = []
    for index in range(1, 43):
        site_id = f"S{index:03d}"
        profile = SITE_PROFILES.get(site_id, "medium" if index % 3 == 0 else "low")
        sites.append({
            "site_id": site_id,
            "name": f"Site {site_id} – {LOCATIONS[index % len(LOCATIONS)].split(',')[0]} Clinical Research Unit",
            "location": LOCATIONS[index % len(LOCATIONS)],
            "investigator": INVESTIGATORS[index % len(INVESTIGATORS)],
            "patient_count": 20 + (index % 15),
            "status": "ACTIVE" if index % 12 != 0 else "SUSPENDED",
            "created_at": "2026-01-10",
            "profile": profile,
            "synthetic": True,
        })
    return sites


# ─── patients ─────────────────────────────────────────────────────────────────

def _build_patients(sites: list[dict], rng: random.Random) -> list[dict]:
    patients = []
    genders = ["F", "M", "X"]
    for site in sites:
        count = site["patient_count"]
        site_id = site["site_id"]
        for i in range(1, count + 1):
            # Eligibility violators: ~5% are outside 18-65
            age = rng.randint(19, 63)
            if site_id in ("S008", "S021") and i <= 2:
                age = rng.choice([16, 17, 67, 70])  # deliberate eligibility violations
            patients.append({
                "patient_id": f"P-{site_id[1:]}-{i:03d}",
                "site_id": site_id,
                "age": age,
                "gender": genders[rng.randint(0, 2)],
                "enrollment_date": "2026-01-15",
                "status": "ACTIVE" if i % 9 != 0 else "WITHDRAWN",
                "synthetic": True,
            })
    return patients


# ─── protocol ─────────────────────────────────────────────────────────────────

def _build_protocol() -> list[dict]:
    return [{
        "protocol_id": "TG-101",
        "version": "2.0",
        "name": "TrialGuard Demonstration Protocol — Phase II Safety Study",
        "description": (
            "Synthetic protocol for demonstration of TrialGuard AI clinical trial monitoring. "
            "All rules, thresholds, and requirements are fictional and for demonstration only."
        ),
        "study_phase": "Phase II",
        "therapeutic_area": "Synthetic",
        "sponsor": "TrialGuard Demo Sponsor",
        "created_at": "2025-12-01",
        "synthetic": True,
        "rules": [
            {
                "rule_id": "R-001",
                "domain": "Eligibility",
                "name": "Patient age eligibility",
                "expected": "18–65 years inclusive",
                "description": "All enrolled patients must be between 18 and 65 years of age at time of enrollment.",
                "severity_if_violated": "MAJOR",
            },
            {
                "rule_id": "R-002",
                "domain": "Visit Schedule",
                "name": "Visit 2 window (Day 7)",
                "expected": "Day 7 ± 2 days from Day 0",
                "description": "Visit 2 must occur between Day 5 and Day 9 relative to the enrollment date (Day 0).",
                "severity_if_violated": "MINOR",
            },
            {
                "rule_id": "R-003",
                "domain": "Dosing",
                "name": "Study drug dose",
                "expected": "100 mg once daily",
                "description": "The protocol-defined dose is 100 mg once daily. No dose modifications without medical monitor approval.",
                "severity_if_violated": "MAJOR",
            },
            {
                "rule_id": "R-004",
                "domain": "Concomitant Medications",
                "name": "Prohibited medications",
                "expected": "Drug X and Drug Y are prohibited throughout the study period",
                "description": "Drug X (strong CYP3A4 inhibitor) and Drug Y (QT-prolonging agent) are prohibited due to drug-drug interaction risk.",
                "severity_if_violated": "MAJOR",
            },
            {
                "rule_id": "R-005",
                "domain": "Assessments",
                "name": "Required safety assessment",
                "expected": "Safety assessment (vital signs + ECG + labs) completed at every scheduled visit",
                "description": "A complete safety assessment including vital signs, 12-lead ECG, and laboratory panel must be recorded at each visit.",
                "severity_if_violated": "MAJOR",
            },
            {
                "rule_id": "R-006",
                "domain": "Data Integrity",
                "name": "Data entry timeliness",
                "expected": "All visit data entered into EDC within 48 hours of visit",
                "description": "Source data must be transcribed into the electronic data capture system within 48 hours of the visit.",
                "severity_if_violated": "ADMINISTRATIVE",
            },
            {
                "rule_id": "R-007",
                "domain": "Visit Schedule",
                "name": "Visit 3 window (Day 14)",
                "expected": "Day 14 ± 2 days from Day 0",
                "description": "Visit 3 must occur between Day 12 and Day 16 relative to enrollment.",
                "severity_if_violated": "MINOR",
            },
            {
                "rule_id": "R-008",
                "domain": "Visit Schedule",
                "name": "No missed visits",
                "expected": "All scheduled visits must be attended or rescheduled within window",
                "description": "A visit is classified as missed if it cannot be rescheduled within the protocol-defined window.",
                "severity_if_violated": "MINOR",
            },
        ],
        "visit_schedule": [
            {"visit_number": 1, "label": "Day 0 – Baseline", "window_days": 0, "window_tolerance": 0},
            {"visit_number": 2, "label": "Day 7", "window_days": 7, "window_tolerance": 2},
            {"visit_number": 3, "label": "Day 14", "window_days": 14, "window_tolerance": 2},
            {"visit_number": 4, "label": "Day 28", "window_days": 28, "window_tolerance": 3},
            {"visit_number": 5, "label": "Day 56 – End of Treatment", "window_days": 56, "window_tolerance": 3},
        ],
    }]


# ─── visits ───────────────────────────────────────────────────────────────────

ENROLL_DATE = date(2026, 1, 15)


def _build_visits(patients: list[dict], rng: random.Random) -> list[dict]:
    visits = []
    visit_schedule = [1, 7, 14, 28, 56]
    for patient in patients:
        pid = patient["patient_id"]
        site_id = patient["site_id"]
        if patient["status"] == "WITHDRAWN":
            continue
        for visit_num, day in enumerate(visit_schedule, start=1):
            scheduled = ENROLL_DATE + timedelta(days=day)
            # Introduce realistic deviations based on site profile
            profile = _site_profile(site_id)
            if profile == "high_dosing":
                # More dosing errors and data delays
                dose = 150 if rng.random() < 0.35 else 100  # 35% dosing error
                delay = rng.randint(3, 8) if rng.random() < 0.4 else 0
                offset = rng.randint(-1, 1)
            elif profile == "high_missed":
                # More missed visits
                if rng.random() < 0.2:
                    continue  # missed visit
                dose = 100
                delay = rng.randint(2, 5) if rng.random() < 0.25 else 0
                offset = rng.randint(-5, 8) if rng.random() < 0.3 else rng.randint(-1, 1)
            elif profile in ("high_frequency", "medium"):
                dose = 80 if rng.random() < 0.1 else 100
                delay = rng.randint(3, 6) if rng.random() < 0.15 else 0
                offset = rng.randint(-3, 5) if rng.random() < 0.2 else rng.randint(-1, 1)
            else:
                dose = 100
                delay = rng.randint(3, 5) if rng.random() < 0.05 else 0
                offset = rng.randint(-1, 1)

            actual = scheduled + timedelta(days=offset)
            assessment = "MISSING" if rng.random() < _missing_rate(site_id) else "COMPLETE"
            entry_date = actual + timedelta(days=delay)

            visits.append({
                "visit_id": f"V-{pid}-{visit_num}",
                "patient_id": pid,
                "site_id": site_id,
                "visit_number": visit_num,
                "scheduled_date": scheduled.isoformat(),
                "actual_date": actual.isoformat(),
                "dose_expected": 100,
                "dose_actual": dose,
                "assessment_status": assessment,
                "data_entry_date": entry_date.isoformat(),
                "synthetic": True,
            })
    return visits


def _site_profile(site_id: str) -> str:
    return SITE_PROFILES.get(site_id, "medium" if int(site_id[1:]) % 3 == 0 else "low")


def _missing_rate(site_id: str) -> float:
    p = _site_profile(site_id)
    return {"high_dosing": 0.08, "high_missed": 0.12, "high_frequency": 0.10, "medium": 0.04, "low": 0.01}.get(p, 0.02)


# ─── medications ──────────────────────────────────────────────────────────────

def _build_medications(patients: list[dict], rng: random.Random) -> list[dict]:
    meds = []
    benign = ["Aspirin", "Vitamin D", "Lisinopril", "Metformin", "Atorvastatin"]
    prohibited = ["Drug X", "Drug Y"]
    for patient in patients:
        pid = patient["patient_id"]
        site_id = patient["site_id"]
        profile = _site_profile(site_id)
        # Most patients have 1-3 benign meds
        for _ in range(rng.randint(0, 2)):
            meds.append({
                "medication_id": f"MED-{pid}-{len(meds):04d}",
                "patient_id": pid,
                "medication_name": rng.choice(benign),
                "start_date": "2026-01-01",
                "end_date": None,
                "prohibited": False,
                "synthetic": True,
            })
        # Prohibited meds: higher rate at high-risk sites
        prob = {"high_dosing": 0.18, "high_missed": 0.10, "high_frequency": 0.15}.get(profile, 0.04)
        if rng.random() < prob:
            meds.append({
                "medication_id": f"MED-{pid}-PRO-{len(meds):04d}",
                "patient_id": pid,
                "medication_name": rng.choice(prohibited),
                "start_date": "2026-02-01",
                "end_date": None,
                "prohibited": True,
                "synthetic": True,
            })
    return meds


# ─── deviations ───────────────────────────────────────────────────────────────

def _build_deviations(
    sites: list[dict],
    patients: list[dict],
    visits: list[dict],
    medications: list[dict],
    rng: random.Random,
) -> list[dict]:
    """Build deviations by running the deterministic deviation engine over synthetic data."""
    from engines import run_deviation_engine
    from models import RepositoryState
    protocols = _build_protocol()
    deviations = run_deviation_engine(protocols, patients, visits, medications)

    # Ensure S037 has a strong set of deviations for demo narrative
    s037_devs = [d for d in deviations if d["site_id"] == "S037"]
    if len(s037_devs) < 12:
        _inject_s037_deviations(deviations, patients, rng)

    # Assign sequential IDs for readability
    for i, dev in enumerate(deviations, 1):
        if dev["deviation_id"].startswith("DYN-"):
            dev["deviation_id"] = f"DEV-{i:04d}"

    # Add some pre-seeded recurrence data for demo
    _add_recurrence_flags(deviations)

    return deviations


def _inject_s037_deviations(deviations: list[dict], patients: list[dict], rng: random.Random) -> None:
    """Inject additional S037 deviations to ensure demo narrative has enough data."""
    s037_patients = [p for p in patients if p["site_id"] == "S037"][:5]
    dates = ["2026-04-10", "2026-04-15", "2026-04-22", "2026-05-01", "2026-05-08",
             "2026-05-12", "2026-05-15", "2026-05-18"]
    for i, (patient, d) in enumerate(zip(s037_patients * 3, dates)):
        dtype = ["INCORRECT_DOSE", "MISSED_VISIT", "LATE_DATA_ENTRY", "MISSING_ASSESSMENT", "INCORRECT_DOSE"][i % 5]
        deviations.append({
            "deviation_id": f"S037-INJ-{i+1:03d}",
            "patient_id": patient["patient_id"],
            "site_id": "S037",
            "type": dtype,
            "description": f"{dtype.replace('_', ' ').title()} — injected for demo narrative",
            "expected": "100 mg" if dtype == "INCORRECT_DOSE" else "Per protocol",
            "actual": "150 mg" if dtype == "INCORRECT_DOSE" else "Not completed",
            "detected_at": d,
            "severity": "MAJOR" if dtype in ("INCORRECT_DOSE", "MISSING_ASSESSMENT") else "MINOR",
            "severity_score": 14 if dtype == "INCORRECT_DOSE" else 7,
            "severity_reason": "Prototype score from multi-factor severity engine.",
            "risk_factors": ["recurrence", "trending"],
            "status": "OPEN",
            "evidence": {"protocol_id": "TG-101", "rule_id": "R-003" if dtype == "INCORRECT_DOSE" else "R-008",
                         "comparison": "deterministic deviation engine"},
            "created_at": d,
            "synthetic": True,
        })


def _add_recurrence_flags(deviations: list[dict]) -> None:
    from collections import Counter
    site_type = Counter((d["site_id"], d["type"]) for d in deviations)
    for dev in deviations:
        key = (dev["site_id"], dev["type"])
        if site_type[key] > 2 and "recurrence" not in dev.get("risk_factors", []):
            dev.setdefault("risk_factors", []).append("recurrence")


# ─── risk scores ─────────────────────────────────────────────────────────────

def _build_risk_scores(sites: list[dict], deviations: list[dict]) -> list[dict]:
    from engines import calculate_site_risk
    scores = []
    for site in sites:
        risk = calculate_site_risk(site["site_id"], deviations, previous_score=0)
        risk["calculated_at"] = "2026-05-18"
        scores.append(risk)
    return scores


# ─── capa records ─────────────────────────────────────────────────────────────

def _build_capa_records(sites: list[dict], deviations: list[dict]) -> list[dict]:
    from services import generate_capa_record
    records = []
    high_risk_sites = ["S037", "S008", "S021"]
    overrides = {
        "S037": {"capa_id": "CAPA-0001", "status": "OPEN",        "created_at": "2026-05-18", "updated_at": "2026-05-18"},
        "S008": {"capa_id": "CAPA-0002", "status": "IN_PROGRESS", "created_at": "2026-05-10", "updated_at": "2026-05-15"},
        "S021": {"capa_id": "CAPA-0003", "status": "IN_PROGRESS", "created_at": "2026-05-12", "updated_at": "2026-05-16"},
    }
    for site_id in high_risk_sites:
        devs = [d for d in deviations if d["site_id"] == site_id and d["severity"] == "MAJOR"][:5]
        if not devs:
            devs = [d for d in deviations if d["site_id"] == site_id][:3]
        if not devs:
            continue
        record = generate_capa_record(site_id, devs, "U-MANAGER")
        record.update(overrides.get(site_id, {}))
        records.append(record)
    return records


# ─── audit events ─────────────────────────────────────────────────────────────

def _build_audit_events(users: list[dict]) -> list[dict]:
    import uuid
    events = []
    actions = [
        ("U-MANAGER", "LOGIN", "session"),
        ("U-MANAGER", "VIEW_DASHBOARD", "dashboard"),
        ("U-MANAGER", "VIEW_SITES", "sites"),
        ("U-MANAGER", "VIEW_SITE", "site", "S037"),
        ("U-MANAGER", "VIEW_SITE_RISK", "risk_score", "S037"),
        ("U-MANAGER", "VIEW_DEVIATIONS", "deviations"),
        ("U-MANAGER", "BOB_QUESTION", "bob"),
        ("U-MANAGER", "GENERATE_CAPA", "capa_records", "CAPA-0001"),
        ("U-MANAGER", "GENERATE_REPORT", "report"),
        ("U-S037", "LOGIN", "session"),
        ("U-S037", "VIEW_SITE", "site", "S037"),
        ("U-S037", "VIEW_SITE_DEVIATIONS", "deviations", "S037"),
        ("U-AUDITOR", "LOGIN", "session"),
        ("U-AUDITOR", "VIEW_DEVIATIONS", "deviations"),
        ("U-AUDITOR", "VIEW_CAPA", "capa_records"),
        ("U-ADMIN", "LOGIN", "session"),
        ("U-ADMIN", "RISK_RECALCULATED", "risk_scores"),
    ]
    timestamps = [
        "2026-05-18T08:00:00Z", "2026-05-18T08:01:00Z", "2026-05-18T08:02:00Z",
        "2026-05-18T08:03:00Z", "2026-05-18T08:04:00Z", "2026-05-18T08:05:00Z",
        "2026-05-18T08:10:00Z", "2026-05-18T08:15:00Z", "2026-05-18T08:20:00Z",
        "2026-05-18T09:00:00Z", "2026-05-18T09:02:00Z", "2026-05-18T09:05:00Z",
        "2026-05-18T10:00:00Z", "2026-05-18T10:02:00Z", "2026-05-18T10:05:00Z",
        "2026-05-17T14:00:00Z", "2026-05-17T14:30:00Z",
    ]
    for i, action_tuple in enumerate(actions):
        uid = action_tuple[0]
        action = action_tuple[1]
        resource_type = action_tuple[2]
        resource_id = action_tuple[3] if len(action_tuple) > 3 else ""
        events.append({
            "event_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"seed-{i}")),
            "user_id": uid,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "timestamp": timestamps[i] if i < len(timestamps) else "2026-05-18T12:00:00Z",
            "metadata": {},
        })
    return events
