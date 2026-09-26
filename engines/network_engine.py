"""
Network/infrastructure KPI engine — the "bandwidth and other things"
piece. Pure calculation over normalized network samples: no AI, no
I/O, testable in isolation. Turns raw per-site daily samples into the
signals an IT Manager actually cares about: are we getting the
bandwidth we pay for, is latency creeping up, which sites are flaky.
"""

from collections import defaultdict


def calculate_network_kpis(samples: list[dict]) -> dict:
    if not samples:
        return {"insufficient_data": True}

    by_site = defaultdict(list)
    for s in samples:
        by_site[s["site"]].append(s)

    site_summaries = {}
    for site, site_samples in by_site.items():
        avg_committed = sum(s["bandwidth_mbps_committed"] for s in site_samples) / len(site_samples)
        avg_measured = sum(s["bandwidth_mbps_measured"] for s in site_samples) / len(site_samples)
        avg_latency = sum(s["latency_ms"] for s in site_samples) / len(site_samples)
        avg_loss = sum(s["packet_loss_pct"] for s in site_samples) / len(site_samples)
        avg_uptime = sum(s["uptime_pct"] for s in site_samples) / len(site_samples)

        # Under-delivery: measured bandwidth materially below what's paid for.
        underdelivery_pct = (
            round(100 * (avg_committed - avg_measured) / avg_committed, 1) if avg_committed else None
        )

        site_summaries[site] = {
            "avg_bandwidth_committed_mbps": round(avg_committed, 1),
            "avg_bandwidth_measured_mbps": round(avg_measured, 1),
            "bandwidth_underdelivery_pct": underdelivery_pct,
            "avg_latency_ms": round(avg_latency, 1),
            "avg_packet_loss_pct": round(avg_loss, 2),
            "avg_uptime_pct": round(avg_uptime, 2),
            "circuit_provider": site_samples[0].get("circuit_provider"),
            "sample_count": len(site_samples),
        }

    flagged_sites = [
        site
        for site, summary in site_summaries.items()
        if (summary["bandwidth_underdelivery_pct"] or 0) > 15
        or summary["avg_uptime_pct"] < 99.0
        or summary["avg_packet_loss_pct"] > 1.0
    ]

    return {
        "insufficient_data": False,
        "site_count": len(site_summaries),
        "site_summaries": site_summaries,
        "flagged_sites": flagged_sites,
    }
