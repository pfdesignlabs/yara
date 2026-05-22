from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_phone_number(session: Session, phone_number: str) -> User | None:
    statement = select(User).where(User.phone_number == phone_number)
    return session.scalar(statement)


def get_or_create_user_by_phone_number(
    session: Session,
    phone_number: str,
    display_name: str | None = None,
) -> User:
    user = get_user_by_phone_number(session, phone_number)
    if user is not None:
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    user = User(
        phone_number=phone_number,
        display_name=display_name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
