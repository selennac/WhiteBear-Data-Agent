from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.connections import engine_for
from app.db.models import AnalysisRunRecord, Conversation, Message
from app.schemas.analysis import (
    AnalysisRun,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
)


class RecordNotFoundError(ValueError):
    pass


def summary(record: Conversation) -> ConversationSummary:
    return ConversationSummary(
        id=record.id, datasource_id="business", title=record.title, created_at=record.created_at
    )


def create_conversation(settings: Settings, body: ConversationCreate) -> ConversationSummary:
    engine = engine_for(settings.app_database_url, "APP_DATABASE_URL")
    try:
        with Session(engine) as session, session.begin():
            record = Conversation(
                id=uuid4(),
                datasource_id=body.datasource_id,
                title=body.title,
                created_at=datetime.now(UTC),
            )
            session.add(record)
            return summary(record)
    finally:
        engine.dispose()


def list_conversations(settings: Settings, offset: int = 0) -> list[ConversationSummary]:
    engine = engine_for(settings.app_database_url, "APP_DATABASE_URL")
    try:
        with Session(engine) as session:
            records = session.scalars(
                select(Conversation)
                .order_by(Conversation.created_at.desc(), Conversation.id)
                .offset(offset)
                .limit(50)
            )
            return [summary(record) for record in records]
    finally:
        engine.dispose()


def get_conversation(settings: Settings, conversation_id: UUID) -> ConversationDetail:
    engine = engine_for(settings.app_database_url, "APP_DATABASE_URL")
    try:
        with Session(engine) as session:
            record = session.get(Conversation, conversation_id)
            if record is None:
                raise RecordNotFoundError("会话不存在。")
            runs = session.scalars(
                select(AnalysisRunRecord)
                .where(AnalysisRunRecord.conversation_id == conversation_id)
                .order_by(AnalysisRunRecord.created_at.desc(), AnalysisRunRecord.id)
                .limit(50)
            )
            return ConversationDetail(
                **summary(record).model_dump(),
                runs=list(reversed([AnalysisRun.model_validate(run.payload) for run in runs])),
            )
    finally:
        engine.dispose()


def create_run(settings: Settings, run: AnalysisRun) -> None:
    engine = engine_for(settings.app_database_url, "APP_DATABASE_URL")
    try:
        with Session(engine) as session, session.begin():
            conversation = session.get(Conversation, run.conversation_id)
            if conversation is None:
                raise RecordNotFoundError("会话不存在。")
            message_id = uuid4()
            session.add(
                Message(
                    id=message_id,
                    conversation_id=run.conversation_id,
                    role="user",
                    content=run.question,
                    created_at=run.created_at,
                )
            )
            session.flush()
            session.add(
                AnalysisRunRecord(
                    id=run.id,
                    conversation_id=run.conversation_id,
                    message_id=message_id,
                    created_at=run.created_at,
                    payload=run.model_dump(mode="json"),
                )
            )
            if conversation.title == "新建分析":
                conversation.title = run.question[:100]
    finally:
        engine.dispose()


def save_run(settings: Settings, run: AnalysisRun) -> None:
    engine = engine_for(settings.app_database_url, "APP_DATABASE_URL")
    try:
        with Session(engine) as session, session.begin():
            record = session.get(AnalysisRunRecord, run.id)
            if record is None:
                raise RecordNotFoundError("运行记录不存在。")
            record.payload = run.model_dump(mode="json")
            content = run.error_message
            if run.draft and run.status == "clarification_required":
                content = run.draft.clarification
            elif run.result:
                content = f"查询返回 {run.result.row_count} 行。"
            session.add(
                Message(
                    id=uuid4(),
                    conversation_id=run.conversation_id,
                    role="assistant",
                    content=content,
                    created_at=run.completed_at or datetime.now(UTC),
                )
            )
    finally:
        engine.dispose()


def get_run(settings: Settings, run_id: UUID) -> AnalysisRun:
    engine = engine_for(settings.app_database_url, "APP_DATABASE_URL")
    try:
        with Session(engine) as session:
            record = session.get(AnalysisRunRecord, run_id)
            if record is None:
                raise RecordNotFoundError("运行记录不存在。")
            return AnalysisRun.model_validate(record.payload)
    finally:
        engine.dispose()
