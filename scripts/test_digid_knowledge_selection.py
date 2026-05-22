from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.knowledge_service import KnowledgeService

SCENARIOS = [
    "Ik heb een activeringscode gekregen maar ik weet niet wat ik nu moet doen met DigiD",
    "Ik krijg geen sms-code van DigiD",
    "Ik heb nog geen BSN en ik wil DigiD aanvragen",
    "Ik heb geen vast adres, kan ik toch DigiD krijgen?",
    "Ik ben mijn DigiD wachtwoord vergeten",
]

service = KnowledgeService()
for scenario in SCENARIOS:
    print(f"\nSCENARIO: {scenario}")
    selected = service.select_for_digid_help(user_message=scenario)
    for chunk in selected["chunks"]:
        print(f"- {chunk['chunk_id']} | {chunk['section_heading']}")
