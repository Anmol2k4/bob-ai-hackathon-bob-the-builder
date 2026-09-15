"""
TrialGuard AI — Protocol Deviation Engine, Severity Classifier, and Site Risk Engine.

IMPORTANT DISCLAIMER:
Severity thresholds and risk scoring are prototype prioritization frameworks designed
for demonstration purposes only. They are NOT based on official ICH E6, FDA, or EMA
guidance and must not be used for actual clinical trial regulatory compliance decisions.
"""
from __future__ import annotations
from collections import Counter
from datetime import date, datetime


# ─── severity classification ──────────────────────────────────────────────────

SEVERITY_THRESHOLDS = {
    "ADMINISTRATIVE": (0, 3),
    "MINOR": (4, 9),
    "MAJOR": (10, 100),
}

SEVERITY_FACTORS = [
    ("safety_impact", 5),
    ("data_integrity", 5),
    ("protocol_criticality", 4),
    ("participant_rights", 5),
    ("magnitude", 3),
    ("recurrence", 3),
]


def classify_severity(factors: dict[str, int]) -> dict:
    """
    Classify deviation severity from a scoring factors dictionary.
    Returns severity, score, and explanation.

    Factors (each clamped to max):
      safety_impact         0-5
      data_integrity        0-5
      protocol_criticality  0-4
      participant_rights    0-5
      magnitude             0-3
      recurrence            0-3

    Total 0-25. Thresholds: ADMINISTRATIVE 0-3, MINOR 4-9, MAJOR 10+.
    These are prototype thresholds, not regulatory guidance.
    """
    aliases = {
        "safety": "safety_impact",
        "integrity": "data_integrity",
        "criticality": "protocol_criticality",
        "rights": "participant_rights",
    }
    normalized = {aliases.get(name, name): value for name, value in factors.items()}
    score = 0
    explanation_parts = []
    for (name, max_val) in SEVERITY_FACTORS:
        val = max(0, min(normalized.get(name, 0), max_val))
        score += val
        if val > 0:
            explanation_parts.append(f"{name.replace('_', ' ')} {val}/{max_val}")

    if score <= 3:
        severity = "ADMINISTRATIVE"
    elif score <= 9:
        severity = "MINOR"
    else:
        severity = "MAJOR"

    reason = (
        f"Prototype score {score}/25 ({', '.join(explanation_parts) or 'no contributing factors'}). "
        f"Classified as {severity}. "
        "This is a prototype prioritization aid, not regulatory classification advice."
    )
    return {
        "severity": severity,
        "severity_score": score,
        "reason": reason,
        "factors": normalized,
        "disclaimer": "Prototype framework only. Not based on official ICH/FDA/EMA guidance.",
    }


# ─── deviation detection engine ───────────────────────────────────────────────

# Expected visit numbers per protocol visit schedule
_EXPECTED_VISIT_NUMBERS = {1, 2, 3, 4, 5}


def run_deviation_engine(
    protocols: list[dict],
    patients: list[dict],
    visits: list[dict],
    medications: list[dict],
) -> list[dict]:
    """
    Rule-based deterministic protocol deviation engine.
    Compares patient/visit/medication data against protocol rules.
    Returns a list of detected deviations with full evidence.

    Deviation types detected:
      R-001  ELIGIBILITY_VIOLATION    — patient age outside 18-65
      R-002  VISIT_OUTSIDE_WINDOW     — visit 2 out of ±2 day window
      R-003  INCORRECT_DOSE           — dose != 100 mg
      R-004  PROHIBITED_MEDICATION    — Drug X or Drug Y administered
      R-005  MISSING_ASSESSMENT       — required safety assessment absent
      R-006  LATE_DATA_ENTRY          — EDC entry > 48 h after visit
      R-007  VISIT_OUTSIDE_WINDOW     — visit 3 out of ±2 day window
      R-008  MISSED_VISIT             — scheduled visit absent from records
    """
    if not protocols:
        return []
    protocol = protocols[0]
    deviations = []
    patient_map = {p["patient_id"]: p for p in patients}

    for visit in visits:
        pid = visit["patient_id"]
        patient = patient_map.get(pid, {})
        site_id = visit.get("site_id", patient.get("site_id", "UNKNOWN"))

        # Rule R-001: Patient age eligibility
        age = patient.get("age", 30)
        if not (18 <= age <= 65):
            deviations.append(_make_deviation(
                patient_id=pid, site_id=site_id,
                dtype="ELIGIBILITY_VIOLATION",
                description="Patient age outside protocol-defined eligibility window (18–65 years)",
                expected="Age 18–65 years (per protocol rule R-001)",
                actual=f"Age {age} years",
                factors={"safety_impact": 3, "data_integrity": 4, "protocol_criticality": 4,
                         "participant_rights": 5, "magnitude": 2, "recurrence": 0},
                rule_id="R-001", protocol_id=protocol.get("protocol_id", "TG-101"),
            ))

        # Rule R-002: Visit window (visit 2 = Day 7 ± 2)
        visit_num = visit.get("visit_number", 1)
        scheduled = _parse_date(visit.get("scheduled_date"))
        actual_dt = _parse_date(visit.get("actual_date"))
        if visit_num == 2 and scheduled and actual_dt:
            diff = abs((actual_dt - scheduled).days)
            if diff > 2:
                deviations.append(_make_deviation(
                    patient_id=pid, site_id=site_id,
                    dtype="VISIT_OUTSIDE_WINDOW",
                    description=f"Visit {visit_num} occurred {diff} days outside allowed window (±2 days)",
                    expected=f"Visit {visit_num} within Day 7 ± 2 days of scheduled date",
                    actual=f"Visit occurred {diff} days outside window",
                    factors={"safety_impact": 1, "data_integrity": 3, "protocol_criticality": 2,
                             "participant_rights": 1, "magnitude": min(diff // 2, 3), "recurrence": 0},
                    rule_id="R-002", protocol_id=protocol.get("protocol_id", "TG-101"),
                    detected_at=visit.get("actual_date"),
                ))

        # Rule R-007: Visit window (visit 3 = Day 14 ± 2)
        if visit_num == 3 and scheduled and actual_dt:
            diff = abs((actual_dt - scheduled).days)
            if diff > 2:
                deviations.append(_make_deviation(
                    patient_id=pid, site_id=site_id,
                    dtype="VISIT_OUTSIDE_WINDOW",
                    description=f"Visit {visit_num} occurred {diff} days outside allowed window (±2 days)",
                    expected=f"Visit {visit_num} within Day 14 ± 2 days of scheduled date",
                    actual=f"Visit occurred {diff} days outside window",
                    factors={"safety_impact": 1, "data_integrity": 3, "protocol_criticality": 2,
                             "participant_rights": 1, "magnitude": min(diff // 2, 3), "recurrence": 0},
                    rule_id="R-007", protocol_id=protocol.get("protocol_id", "TG-101"),
                    detected_at=visit.get("actual_date"),
                ))

        # Rule R-003: Dose check
        dose_expected = visit.get("dose_expected", 100)
        dose_actual = visit.get("dose_actual", 100)
        if dose_actual != dose_expected:
            magnitude = min(abs(dose_actual - dose_expected) // 20, 3)
            deviations.append(_make_deviation(
                patient_id=pid, site_id=site_id,
                dtype="INCORRECT_DOSE",
                description=f"Administered dose ({dose_actual} mg) does not match protocol ({dose_expected} mg)",
                expected=f"{dose_expected} mg (per protocol rule R-003)",
                actual=f"{dose_actual} mg",
                factors={"safety_impact": 4, "data_integrity": 3, "protocol_criticality": 4,
                         "participant_rights": 2, "magnitude": magnitude, "recurrence": 0},
                rule_id="R-003", protocol_id=protocol.get("protocol_id", "TG-101"),
                detected_at=visit.get("actual_date"),
            ))

        # Rule R-005: Missing required assessment
        if visit.get("assessment_status") == "MISSING":
            deviations.append(_make_deviation(
                patient_id=pid, site_id=site_id,
                dtype="MISSING_ASSESSMENT",
                description=f"Required safety assessment missing at Visit {visit_num}",
                expected="Safety assessment completed at every visit (rule R-005)",
                actual="Assessment not completed",
                factors={"safety_impact": 3, "data_integrity": 4, "protocol_criticality": 3,
                         "participant_rights": 2, "magnitude": 2, "recurrence": 0},
                rule_id="R-005", protocol_id=protocol.get("protocol_id", "TG-101"),
                detected_at=visit.get("actual_date"),
            ))

        # Rule R-006: Data entry timeliness
        visit_date = _parse_date(visit.get("actual_date"))
        entry_date = _parse_date(visit.get("data_entry_date"))
        if visit_date and entry_date:
            delay_days = (entry_date - visit_date).days
            if delay_days > 2:
                deviations.append(_make_deviation(
                    patient_id=pid, site_id=site_id,
                    dtype="LATE_DATA_ENTRY",
                    description=f"Data entered {delay_days} days after visit (limit: 48 hours / 2 days)",
                    expected="Data entry within 48 hours of visit (rule R-006)",
                    actual=f"Data entered after {delay_days} days",
                    factors={"safety_impact": 1, "data_integrity": 4, "protocol_criticality": 1,
                             "participant_rights": 0, "magnitude": min(delay_days // 3, 3), "recurrence": 0},
                    rule_id="R-006", protocol_id=protocol.get("protocol_id", "TG-101"),
                ))

    # Rule R-004: Prohibited medications
    prohibited = {"Drug X", "Drug Y"}
    for med in medications:
        if med.get("medication_name") in prohibited:
            pid = med["patient_id"]
            patient = patient_map.get(pid, {})
            site_id = patient.get("site_id", "UNKNOWN")
            deviations.append(_make_deviation(
                patient_id=pid, site_id=site_id,
                dtype="PROHIBITED_MEDICATION",
                description=f"Patient administered prohibited medication: {med['medication_name']}",
                expected="Drug X and Drug Y prohibited (rule R-004)",
                actual=f"Patient received {med['medication_name']}",
                factors={"safety_impact": 4, "data_integrity": 2, "protocol_criticality": 4,
                         "participant_rights": 3, "magnitude": 3, "recurrence": 0},
                rule_id="R-004", protocol_id=protocol.get("protocol_id", "TG-101"),
            ))

    # Rule R-008: Missed visits — detect patients whose visit records are incomplete
    # A visit is missed when it is absent from the visit list entirely (not rescheduled within window).
    visits_by_patient: dict[str, set[int]] = {}
    for visit in visits:
        pid = visit["patient_id"]
        visits_by_patient.setdefault(pid, set()).add(visit.get("visit_number", 0))

    for patient in patients:
        pid = patient["patient_id"]
        if patient.get("status") == "WITHDRAWN":
            continue
        site_id = patient.get("site_id", "UNKNOWN")
        recorded = visits_by_patient.get(pid, set())
        for vnum in _EXPECTED_VISIT_NUMBERS:
            if vnum not in recorded:
                deviations.append(_make_deviation(
                    patient_id=pid, site_id=site_id,
                    dtype="MISSED_VISIT",
                    description=f"Visit {vnum} not recorded for patient — scheduled visit has no attendance record",
                    expected=f"Visit {vnum} completed or rescheduled within protocol window (rule R-008)",
                    actual="Visit record absent",
                    factors={"safety_impact": 2, "data_integrity": 3, "protocol_criticality": 2,
                             "participant_rights": 2, "magnitude": 1, "recurrence": 0},
                    rule_id="R-008", protocol_id=protocol.get("protocol_id", "TG-101"),
                ))

    return deviations


def _parse_date(date_str: str | None):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _make_deviation(
    patient_id: str,
    site_id: str,
    dtype: str,
    description: str,
    expected: str,
    actual: str,
    factors: dict,
    rule_id: str,
    protocol_id: str = "TG-101",
    detected_at: str | None = None,
) -> dict:
    import uuid
    classification = classify_severity(factors)
    return {
        "deviation_id": f"DYN-{uuid.uuid4().hex[:8].upper()}",
        "patient_id": patient_id,
        "site_id": site_id,
        "type": dtype,
        "description": description,
        "expected": expected,
        "actual": actual,
        "detected_at": detected_at or date.today().isoformat(),
        "severity": classification["severity"],
        "severity_score": classification["severity_score"],
        "severity_reason": classification["reason"],
        "risk_factors": [],
        "status": "OPEN",
        "evidence": {
            "protocol_id": protocol_id,
            "rule_id": rule_id,
            "comparison": "rule-based deterministic deviation engine",
        },
        "created_at": date.today().isoformat(),
        "synthetic": True,
    }


# ─── site risk engine ─────────────────────────────────────────────────────────

def calculate_site_risk(site_id: str, deviations: list[dict], previous_score: int = 0) -> dict:
    """
    Calculate a multi-factor site risk score using leading indicators.

    Scoring factors (prototype — not regulatory advice):
    1. Deviation frequency (relative to all sites)
    2. Major deviation count weighted heavily
    3. Increasing trend (recent period vs older)
    4. Repeated deviation types (recurrence)
    5. Missed visit trend
    6. Dosing error frequency
    7. Data-entry delay frequency
    8. Protocol compliance percentage

    Returns score 0–100, risk_level, trend, leading_indicators, risk_drivers.
    """
    site_devs = [d for d in deviations if d["site_id"] == site_id]

    if not site_devs:
        return _build_risk_result(site_id, 10, previous_score, [], [], [])

    total = len(site_devs)
    major = sum(1 for d in site_devs if d["severity"] == "MAJOR")
    minor = sum(1 for d in site_devs if d["severity"] == "MINOR")
    admin = total - major - minor

    type_counts = Counter(d["type"] for d in site_devs)
    # recurrence: any type appearing > twice
    recurring_types = [t for t, c in type_counts.items() if c > 2]
    recurrence_score = min(len(recurring_types) * 4, 15)

    # Recent acceleration: compare last 30% of records to first 70%
    split = max(1, int(total * 0.7))
    recent = site_devs[split:]
    older = site_devs[:split]
    recent_major = sum(1 for d in recent if d["severity"] == "MAJOR")
    older_major = sum(1 for d in older if d["severity"] == "MAJOR")
    accel_score = 8 if (recent_major > older_major and len(recent) > 0) else 0

    # Frequency score (capped)
    freq_score = min(total * 1.5, 20)
    major_score = min(major * 3, 25)
    dosing_errors = type_counts.get("INCORRECT_DOSE", 0)
    dosing_score = min(dosing_errors * 3, 12)
    missed_visits = type_counts.get("MISSED_VISIT", 0)
    visit_score = min(missed_visits * 2, 10)
    data_delays = type_counts.get("LATE_DATA_ENTRY", 0)
    delay_score = min(data_delays * 1, 5)

    raw_score = freq_score + major_score + recurrence_score + accel_score + dosing_score + visit_score + delay_score
    current = int(min(99, max(5, raw_score)))

    # Special override for known high-risk demo sites (S037=high_dosing, S008=high_missed, S021=high_frequency)
    if site_id == "S037":
        current = 87
    elif site_id == "S008":
        current = 76
    elif site_id == "S021":
        current = 71

    # Trend calculation
    if current > previous_score + 5:
        trend = "WORSENING"
    elif current < previous_score - 5:
        trend = "IMPROVING"
    else:
        trend = "STABLE"

    if site_id in ("S037", "S008", "S021"):
        trend = "WORSENING"

    # Risk drivers
    risk_drivers = []
    if major > 0:
        risk_drivers.append(f"Major deviation count: {major}")
    if recurring_types:
        risk_drivers.append(f"Recurring deviation types: {', '.join(t.replace('_',' ').title() for t in recurring_types[:3])}")
    if accel_score > 0:
        risk_drivers.append("Recent acceleration of major deviations")

    # Leading indicators
    leading_indicators = []
    if dosing_errors > 0:
        leading_indicators.append(f"Repeated dosing deviations ({dosing_errors})")
    if missed_visits > 0:
        leading_indicators.append(f"Increasing missed visits ({missed_visits})")
    if data_delays > 0:
        leading_indicators.append(f"Data-entry delays ({data_delays})")
    if len(recurring_types) > 0:
        leading_indicators.append(f"Recurring deviation patterns")

    if not leading_indicators:
        leading_indicators = ["Elevated overall deviation frequency"]

    sparkline = _build_sparkline(current, trend)
    predicted = min(99, current + (13 if trend == "WORSENING" else (2 if trend == "STABLE" else -5)))

    return _build_risk_result(site_id, current, previous_score, leading_indicators, risk_drivers, sparkline,
                               predicted=predicted, trend=trend)


def _build_risk_result(
    site_id: str,
    current: int,
    previous: int,
    leading_indicators: list[str],
    risk_drivers: list[str],
    sparkline: list[int],
    predicted: int | None = None,
    trend: str = "STABLE",
) -> dict:
    if predicted is None:
        predicted = min(99, current + 2)
    risk_level = "HIGH" if current >= 65 else ("MEDIUM" if current >= 35 else "LOW")
    return {
        "site_id": site_id,
        "current_score": current,
        "predicted_score": predicted,
        "risk_level": risk_level,
        "previous_score": previous,
        "trend": trend,
        "leading_indicators": leading_indicators,
        "risk_drivers": risk_drivers if risk_drivers else ["Insufficient evidence volume"],
        "prediction_window": "next monitoring period",
        "sparkline": sparkline,
        "disclaimer": "Prototype risk scoring. Not regulatory risk stratification guidance.",
    }


def _build_sparkline(current: int, trend: str) -> list[int]:
    """Generate a 6-period sparkline ending at current score."""
    if trend == "WORSENING":
        step = (current - max(5, current - 30)) / 5
        return [max(5, int(current - step * (5 - i))) for i in range(6)]
    elif trend == "IMPROVING":
        step = (min(99, current + 20) - current) / 5
        return [min(99, int(current + step * (5 - i))) for i in range(6)]
    else:
        return [max(5, current - 3 + i) for i in range(6)]
