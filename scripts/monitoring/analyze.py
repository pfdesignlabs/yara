"""Tester activity analysis CLI — a manual tool to inspect the operational data.

Two modes:

    python scripts/monitoring/analyze.py                     # snapshot
    python scripts/monitoring/analyze.py --user +316XXXXXXXX  # per-user drill-down

Connects to the same Postgres the app uses. When invoked from the host, the
docker-compose hostname `db` is rewritten to `localhost` so the script works
without being run inside a container.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models import Action, Conversation, Message, Reminder, User  # noqa: E402
from app.prompts import get_node_config  # noqa: E402

NL_TZ = ZoneInfo("Europe/Amsterdam")
ERROR_MARKERS = ("ERROR", "Traceback", "Exception")

EVAL_SYSTEM_PROMPT = """Je bent een kritische beoordelaar van WhatsApp-conversaties tussen Yara
(een prototype-hulpverlener voor nieuwkomers in Den Haag) en een gebruiker.

Beoordeel op zeven dimensies:
1. Taalkeuze — heeft Yara duidelijk om een taal gevraagd en die aangehouden?
2. Document-uitleg — als er een brief is gedeeld: helder, empathisch, met de kern in eigen woorden?
3. Acties — zijn concrete, uitvoerbare acties geformuleerd of opgeslagen?
4. Reminders — aangeboden waar relevant, op realistische tijden (binnen 24u in deze sandbox-fase)?
5. E-mail / mailto — als een mail nodig was: eerst samen waardes afstemmen, dan link aanbieden?
6. Toon — warm, menselijk, niet robotic of overweldigend; korte beurten?
7. Scope — bleef Yara bij brieven/documenten, zonder hard af te kappen als iets buiten scope kwam?

Antwoord in Nederlands, in exact dit format:

**Overall**: <1-zin oordeel>

**Per dimensie**:
- Taalkeuze: ✓/✗ — <korte toelichting>
- Document-uitleg: ✓/✗ — <korte toelichting>
- Acties: ✓/✗ — <korte toelichting>
- Reminders: ✓/✗ — <korte toelichting>
- E-mail: ✓/✗ — <korte toelichting of n.v.t.>
- Toon: ✓/✗ — <korte toelichting>
- Scope: ✓/✗ — <korte toelichting>

**Verbeterpunten** (max 3, concreet):
- ...
"""


def _build_engine_url() -> str:
    """Resolve a DB URL that works from the host.

    Docker compose uses `db` as the hostname; from the host that resolves to
    nothing. Rewrite to localhost so the script can be run from the venv.
    """
    url = get_settings().database_url
    return url.replace("@db:", "@localhost:")


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(NL_TZ).strftime("%Y-%m-%d %H:%M")


def _section(title: str) -> None:
    print(f"\n=== {title} ===")


def _recent_docker_errors(tail: int = 200, limit: int = 50) -> list[str]:
    try:
        result = subprocess.run(
            ["docker", "compose", "logs", "--no-color", f"--tail={tail}", "app"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return [f"(docker compose logs unavailable: {exc})"]

    lines = result.stdout.splitlines() + result.stderr.splitlines()
    matches = [line for line in lines if any(marker in line for marker in ERROR_MARKERS)]
    return matches[-limit:]


def snapshot(session: Session) -> None:
    now = datetime.now(UTC)
    last_hour = now - timedelta(hours=1)
    last_day = now - timedelta(hours=24)

    total_users = session.scalar(select(func.count()).select_from(User)) or 0
    new_users_24h = (
        session.scalar(select(func.count()).select_from(User).where(User.created_at >= last_day))
        or 0
    )

    convs_last_hour = (
        session.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.last_message_at >= last_hour)
        )
        or 0
    )
    convs_last_day = (
        session.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.last_message_at >= last_day)
        )
        or 0
    )

    def _msg_count(direction: str, since: datetime) -> int:
        return (
            session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.direction == direction, Message.created_at >= since)
            )
            or 0
        )

    inbound_hour = _msg_count("inbound", last_hour)
    outbound_hour = _msg_count("outbound", last_hour)
    inbound_day = _msg_count("inbound", last_day)
    outbound_day = _msg_count("outbound", last_day)

    _section("Users")
    print(f"  total: {total_users}")
    print(f"  new (last 24h): {new_users_24h}")

    _section("Conversations (by last_message_at)")
    print(f"  active in last hour: {convs_last_hour}")
    print(f"  active in last 24h:  {convs_last_day}")

    _section("Messages")
    print(f"  last hour:  inbound {inbound_hour} / outbound {outbound_hour}")
    print(f"  last 24h:   inbound {inbound_day} / outbound {outbound_day}")

    pending_reminders = session.scalars(
        select(Reminder)
        .where(Reminder.status == "scheduled")
        .order_by(Reminder.scheduled_for.asc())
    ).all()
    _section(f"Pending reminders ({len(pending_reminders)})")
    if not pending_reminders:
        print("  (none)")
    for rem in pending_reminders:
        user = session.get(User, rem.user_id)
        phone = user.phone_number if user else "?"
        preview = (rem.body_template or "").replace("\n", " ")[:80]
        print(f"  {_fmt(rem.scheduled_for)}  {phone}  {preview!r}")

    _section("Recent errors (docker compose logs app)")
    errors = _recent_docker_errors()
    if not errors:
        print("  (none)")
    for line in errors:
        print(f"  {line}")


def _find_user(session: Session, phone_number: str) -> User | None:
    normalized = phone_number if phone_number.startswith("+") else f"+{phone_number}"
    return session.scalars(select(User).where(User.phone_number == normalized)).first()


def _build_transcript(
    messages: list[Message], actions: list[Action], reminders: list[Reminder]
) -> str:
    lines: list[str] = []
    for msg in messages:
        role = "user" if msg.direction == "inbound" else f"yara[{msg.source_node or '—'}]"
        body = (msg.content_text or "").strip()
        lines.append(f"{_fmt(msg.created_at)}  {role}: {body}")

    if actions:
        lines.append("")
        lines.append("Acties (uit DB):")
        for act in actions:
            lines.append(
                f"  - status={act.status} urgency={act.urgency or '—'} "
                f"deadline={_fmt(act.deadline_date)} :: {act.description}"
            )

    if reminders:
        lines.append("")
        lines.append("Reminders (uit DB):")
        for rem in reminders:
            lines.append(
                f"  - scheduled_for={_fmt(rem.scheduled_for)} status={rem.status} "
                f"sent_at={_fmt(rem.sent_at)} :: {(rem.body_template or '').strip()[:200]}"
            )

    return "\n".join(lines)


def _evaluate_conversation(transcript: str) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        return "(evaluation skipped: OPENAI_API_KEY not set)"

    cfg = get_node_config("state_extractor_node")
    llm = ChatOpenAI(
        model=cfg["model"],
        temperature=cfg["temperature"],
        api_key=settings.openai_api_key,
    )
    response = llm.invoke(
        [
            SystemMessage(content=EVAL_SYSTEM_PROMPT),
            HumanMessage(content=f"Transcript:\n\n{transcript}"),
        ]
    )
    return response.content if isinstance(response.content, str) else str(response.content)


def drilldown(session: Session, phone_number: str, evaluate: bool = True) -> None:
    user = _find_user(session, phone_number)
    if user is None:
        print(f"No user found for phone_number={phone_number}", file=sys.stderr)
        sys.exit(1)

    _section("User")
    print(f"  id:           {user.id}")
    print(f"  phone:        {user.phone_number}")
    print(f"  display_name: {user.display_name}")
    print(f"  language:     {user.preferred_language}")
    print(f"  municipality: {user.municipality}")
    print(f"  status:       {user.status}")
    print(f"  created_at:   {_fmt(user.created_at)}")

    messages = session.scalars(
        select(Message).where(Message.user_id == user.id).order_by(Message.created_at.asc())
    ).all()
    _section(f"Messages ({len(messages)})")
    for msg in messages:
        body = (msg.content_text or "").replace("\n", " ")
        node = msg.source_node or "—"
        marker = "▶" if msg.direction == "inbound" else "◀"
        print(f"  {_fmt(msg.created_at)}  {marker} [{node}]  {body[:200]}")

    actions = session.scalars(
        select(Action).where(Action.user_id == user.id).order_by(Action.created_at.asc())
    ).all()
    _section(f"Actions ({len(actions)})")
    for act in actions:
        print(
            f"  {_fmt(act.created_at)}  status={act.status}  "
            f"urgency={act.urgency or '—'}  deadline={_fmt(act.deadline_date)}"
        )
        print(f"      {act.description[:200]}")

    reminders = session.scalars(
        select(Reminder).where(Reminder.user_id == user.id).order_by(Reminder.scheduled_for.asc())
    ).all()
    _section(f"Reminders ({len(reminders)})")
    for rem in reminders:
        print(
            f"  scheduled_for={_fmt(rem.scheduled_for)}  status={rem.status}  "
            f"sent_at={_fmt(rem.sent_at)}"
        )
        print(f"      {(rem.body_template or '')[:200]}")

    if evaluate and messages:
        _section("Evaluatie (LLM)")
        transcript = _build_transcript(messages, actions, reminders)
        print(_evaluate_conversation(transcript))


def main() -> None:
    parser = argparse.ArgumentParser(description="Yara tester activity analysis")
    parser.add_argument(
        "--user",
        metavar="PHONE",
        help="Phone number (E.164 or with leading +) to drill into.",
    )
    parser.add_argument(
        "--no-eval",
        action="store_true",
        help="Skip the LLM conversation evaluation in --user drill-down mode.",
    )
    args = parser.parse_args()

    engine = create_engine(_build_engine_url(), future=True)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionFactory() as session:
        if args.user:
            drilldown(session, args.user, evaluate=not args.no_eval)
        else:
            snapshot(session)


if __name__ == "__main__":
    main()
