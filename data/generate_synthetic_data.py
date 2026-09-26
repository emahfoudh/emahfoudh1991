"""
Generates realistic synthetic ticket and network CSVs for the MVP
demo. Deterministic (seeded) so test runs are reproducible. This is
the ONLY data source for now — no real company's data is used or
referenced anywhere in this repo.
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

CATEGORIES = ["network", "access", "hardware", "software", "email"]
PRIORITIES = ["P1", "P2", "P3", "P4"]
ENGINEERS = ["engineer_a", "engineer_b", "engineer_c"]
VENDORS = ["vendor_x", "vendor_y", None]
SLA_BY_PRIORITY = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}

SITES = ["site_a", "site_b", "site_c", "site_d"]
PROVIDERS = {"site_a": "isp_alpha", "site_b": "isp_beta", "site_c": "isp_alpha", "site_d": "isp_gamma"}
COMMITTED_MBPS = {"site_a": 100, "site_b": 200, "site_c": 50, "site_d": 100}


def generate_tickets(path: str, count: int = 220, days: int = 90) -> None:
    start = datetime(2026, 6, 1)
    rows = []
    for i in range(count):
        opened_offset = random.randint(0, days * 24)
        opened_at = start + timedelta(hours=opened_offset)
        priority = random.choices(PRIORITIES, weights=[5, 15, 50, 30])[0]
        # Bias network/access categories to spike in the last 2 weeks, to
        # give the recurring-problem detector and AI layer something real
        # to flag, mirroring how a genuine incident cluster looks.
        if opened_offset > (days - 14) * 24 and random.random() < 0.4:
            category = random.choice(["network", "access"])
        else:
            category = random.choice(CATEGORIES)

        sla_target = SLA_BY_PRIORITY[priority]
        # ~80% resolved within SLA, rest late or still open
        resolved = random.random() < 0.85
        closed_at = ""
        status = "open"
        if resolved:
            within_sla = random.random() < 0.8
            resolve_hours = random.uniform(0.5, sla_target * (0.9 if within_sla else 2.0))
            closed_at = (opened_at + timedelta(hours=resolve_hours)).isoformat()
            status = "closed"

        rows.append(
            {
                "ticket_id": f"TCK-{1000 + i}",
                "title": f"{category} issue #{i}",
                "category": category,
                "priority": priority,
                "status": status,
                "opened_at": opened_at.isoformat(),
                "closed_at": closed_at,
                "sla_target_hours": sla_target,
                "assigned_to": random.choice(ENGINEERS),
                "vendor": random.choice(VENDORS) or "",
            }
        )

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def generate_network_samples(path: str, days: int = 30) -> None:
    start = datetime(2026, 8, 27)
    rows = []
    for day in range(days):
        sample_date = start + timedelta(days=day)
        for site in SITES:
            committed = COMMITTED_MBPS[site]
            # site_c deliberately under-delivers and flakes, to prove the
            # flagging logic works end to end
            if site == "site_c":
                measured = committed * random.uniform(0.55, 0.75)
                latency = random.uniform(40, 90)
                loss = random.uniform(0.5, 2.5)
                uptime = random.uniform(96.5, 99.2)
            else:
                measured = committed * random.uniform(0.9, 1.02)
                latency = random.uniform(5, 25)
                loss = random.uniform(0.0, 0.4)
                uptime = random.uniform(99.5, 100.0)

            rows.append(
                {
                    "site": site,
                    "sample_date": sample_date.date().isoformat(),
                    "bandwidth_mbps_committed": committed,
                    "bandwidth_mbps_measured": round(measured, 1),
                    "latency_ms": round(latency, 1),
                    "packet_loss_pct": round(loss, 2),
                    "uptime_pct": round(uptime, 2),
                    "circuit_provider": PROVIDERS[site],
                }
            )

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    generate_tickets("data/sample_tickets.csv")
    generate_network_samples("data/sample_network.csv")
    print("Synthetic data written to data/sample_tickets.csv and data/sample_network.csv")
