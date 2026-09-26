"""
Persistence helpers — the only place main.py needs to touch the
database. Keeps SQLAlchemy session/commit mechanics out of the
pipeline logic itself.
"""

from datetime import datetime

from models.schema import Contract, Customer, KPISnapshot, NetworkSample, Report, Ticket, get_session

SYNTHETIC_CUSTOMER_NAME = "Synthetic Demo Tenant"


def get_or_create_synthetic_customer(engine) -> int:
    with get_session(engine) as session:
        customer = session.query(Customer).filter_by(name=SYNTHETIC_CUSTOMER_NAME).first()
        if customer:
            return customer.id
        customer = Customer(name=SYNTHETIC_CUSTOMER_NAME)
        session.add(customer)
        session.commit()
        return customer.id


def persist_tickets(engine, customer_id: int, tickets: list[dict]) -> None:
    with get_session(engine) as session:
        for t in tickets:
            session.add(
                Ticket(
                    customer_id=customer_id,
                    external_id=t["external_id"],
                    source_system=t["source_system"],
                    title=t["title"],
                    category=t["category"],
                    priority=t["priority"],
                    status=t["status"],
                    opened_at=t["opened_at"],
                    closed_at=t["closed_at"],
                    sla_target_hours=t["sla_target_hours"],
                    assigned_to=t["assigned_to"],
                    vendor=t["vendor"],
                )
            )
        session.commit()


def persist_network_samples(engine, customer_id: int, samples: list[dict]) -> None:
    with get_session(engine) as session:
        for s in samples:
            session.add(
                NetworkSample(
                    customer_id=customer_id,
                    site=s["site"],
                    sample_date=s["sample_date"],
                    bandwidth_mbps_committed=s["bandwidth_mbps_committed"],
                    bandwidth_mbps_measured=s["bandwidth_mbps_measured"],
                    latency_ms=s["latency_ms"],
                    packet_loss_pct=s["packet_loss_pct"],
                    uptime_pct=s["uptime_pct"],
                    circuit_provider=s["circuit_provider"],
                )
            )
        session.commit()


def persist_contracts(engine, customer_id: int, contracts: list[dict]) -> None:
    with get_session(engine) as session:
        for c in contracts:
            session.add(
                Contract(
                    customer_id=customer_id,
                    vendor_name=c["vendor_name"],
                    service_name=c["service_name"],
                    annual_cost=c["annual_cost"],
                    renewal_date=datetime.fromisoformat(c["renewal_date"]) if c["renewal_date"] else None,
                    license_count=c["license_count"],
                    licenses_in_use=c["licenses_in_use"],
                )
            )
        session.commit()


def persist_kpi_snapshot(
    engine,
    customer_id: int,
    period_label: str,
    ticket_kpis: dict,
    network_kpis: dict,
    recurring: list[dict],
    cost_kpis: dict | None = None,
    technician_performance: dict | None = None,
) -> int:
    with get_session(engine) as session:
        snapshot = KPISnapshot(
            customer_id=customer_id,
            period_label=period_label,
            ticket_kpis=ticket_kpis,
            network_kpis=network_kpis,
            cost_kpis=cost_kpis,
            technician_performance=technician_performance,
            recurring_categories=recurring,
        )
        session.add(snapshot)
        session.commit()
        return snapshot.id


def persist_report(
    engine, customer_id: int, period_label: str, ai_report: dict, pdf_path: str, excel_path: str, kpi_snapshot_id: int
) -> int:
    with get_session(engine) as session:
        report = Report(
            customer_id=customer_id,
            period_label=period_label,
            ai_report_json=ai_report,
            pdf_path=pdf_path,
            excel_path=excel_path,
            kpi_snapshot_id=kpi_snapshot_id,
            generated_at=datetime.utcnow(),
        )
        session.add(report)
        session.commit()
        return report.id


def get_latest_report(engine, customer_id: int) -> Report | None:
    with get_session(engine) as session:
        return (
            session.query(Report)
            .filter_by(customer_id=customer_id)
            .order_by(Report.generated_at.desc())
            .first()
        )


def get_latest_kpi_snapshot(engine, customer_id: int) -> KPISnapshot | None:
    with get_session(engine) as session:
        return (
            session.query(KPISnapshot)
            .filter_by(customer_id=customer_id)
            .order_by(KPISnapshot.computed_at.desc())
            .first()
        )
