"""
One-off debug script: fetches exactly ONE real ticket and prints ONLY
its top-level field names, plus the raw (not normalized) structure of
status/category/priority/time fields specifically. Deliberately does
NOT print subject, description, or requester fields, since those
contain real ticket content and personal details that shouldn't need
to appear in a terminal/chat just to fix field-name mapping.

Delete this file once the mapping is fixed - it's a diagnostic tool,
not part of the pipeline.
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()

from connectors.manageengine_sdp import ManageEngineSDPConnector

sdp = ManageEngineSDPConnector()
sdp.authenticate()

import requests

response = requests.get(
    f"{sdp.api_domain}/api/v3/requests",
    headers=sdp._headers(),
    params={"input_data": json.dumps({"list_info": {"row_count": 1, "start_index": 1}})},
    timeout=30,
)
response.raise_for_status()
tickets = response.json().get("requests", [])

if not tickets:
    print("No tickets returned.")
else:
    t = tickets[0]
    print("Top-level field names present on this ticket:")
    print(sorted(t.keys()))
    print()
    for field in ["status", "category", "subcategory", "priority", "created_time", "due_by_time", "completed_time", "resolved_time", "closed_time"]:
        if field in t:
            print(f"{field}: {json.dumps(t[field])}")
        else:
            print(f"{field}: <not present>")
