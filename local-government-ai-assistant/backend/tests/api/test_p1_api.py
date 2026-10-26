"""API tests for P1 auth, conversations and document management."""

from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.dependencies import get_hybrid_pipeline, get_vector_store
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.data_models import ChunkReference, RAGResponse
from app.models.db_models import User
from app.repositories import users as user_repo


@pytest.fixture
async def client(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        http.session_factory = session_factory
        yield http

    app.dependency_overrides.clear()
    await engine.dispose()


async def register_and_login(client, email="user@example.com", password="Secret123"):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Người dùng"},
    )
    assert response.status_code == 201, response.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


class TestAuthAPI:
    async def test_register_login_and_me(self, client):
        token = await register_and_login(client)
        me = await client.get("/api/v1/auth/me", headers=auth_header(token))
        assert me.status_code == 200
        assert me.json()["email"] == "user@example.com"
        assert me.json()["role"] == "user"

    async def test_duplicate_email_returns_409(self, client):
        await register_and_login(client)
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "Secret123",
                "full_name": "Trùng",
            },
        )
        assert response.status_code == 409

    async def test_wrong_password_returns_401(self, client):
        await register_and_login(client)
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "wrong-pass"},
        )
        assert response.status_code == 401

    async def test_protected_route_requires_token(self, client):
        response = await client.get("/api/v1/conversations")
        assert response.status_code == 401

    async def test_non_admin_cannot_list_users(self, client):
        token = await register_and_login(client)
        response = await client.get(
            "/api/v1/users", headers=auth_header(token)
        )
        assert response.status_code == 403

    async def test_admin_can_list_users_and_change_role(self, client):
        user_token = await register_and_login(client)
        async with client.session_factory() as db:
            await user_repo.create_user(
                db,
                email="admin@example.com",
                hashed_password="unused",
                full_name="Admin",
                role="admin",
            )

        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "unused"},
        )
        # Password "unused" was stored as plaintext above; create a real hash.
        assert admin_login.status_code == 401

        async with client.session_factory() as db:
            admin = await user_repo.get_user_by_email(db, "admin@example.com")
            from app.core.security import hash_password

            admin.hashed_password = hash_password("AdminPass123")
            await db.commit()

        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "AdminPass123"},
        )
        admin_token = admin_login.json()["access_token"]

        users = await client.get(
            "/api/v1/users", headers=auth_header(admin_token)
        )
        assert users.status_code == 200
        assert len(users.json()) == 2

        target_id = users.json()[0]["id"]
        changed = await client.patch(
            f"/api/v1/users/{target_id}/role",
            json={"role": "admin"},
            headers=auth_header(admin_token),
        )
        assert changed.status_code == 200
        assert changed.json()["role"] == "admin"

        # The promoted user's old token still works for conversation routes.
        conversations = await client.get(
            "/api/v1/conversations", headers=auth_header(user_token)
        )
        assert conversations.status_code == 200


class TestConversationAPI:
    async def test_create_list_detail_delete(self, client):
        token = await register_and_login(client)
        headers = auth_header(token)

        created = await client.post(
            "/api/v1/conversations",
            json={"title": "Hỏi về Sở Nội vụ"},
            headers=headers,
        )
        assert created.status_code == 201, created.text
        conversation_id = created.json()["id"]

        listed = await client.get("/api/v1/conversations", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert listed.json()[0]["message_count"] == 0

        detail = await client.get(
            f"/api/v1/conversations/{conversation_id}", headers=headers
        )
        assert detail.status_code == 200
        assert detail.json()["messages"] == []

        deleted = await client.delete(
            f"/api/v1/conversations/{conversation_id}", headers=headers
        )
        assert deleted.status_code == 204

        missing = await client.get(
            f"/api/v1/conversations/{conversation_id}", headers=headers
        )
        assert missing.status_code == 404

    async def test_chat_persists_messages(self, client):
        token = await register_and_login(client)
        headers = auth_header(token)

        class FakePipeline:
            def query(self, query, k):
                return RAGResponse(
                    query_id="q-1",
                    answer="Câu trả lời có trích dẫn.",
                    source_chunks=[
                        ChunkReference(
                            document_id="150-2025-ND-CP",
                            text="Điều 1...",
                            similarity_score=0.9,
                            chunk_index=1,
                        )
                    ],
                    relevance_scores=[0.9],
                    processing_time=0.1,
                    model="fake",
                    timestamp=datetime.utcnow(),
                )

        app.dependency_overrides[get_hybrid_pipeline] = lambda: FakePipeline()

        response = await client.post(
            "/api/v1/chat/query",
            json={"query": "Sở Nội vụ quản lý lĩnh vực gì?", "k": 5},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        conversation_id = response.json()["conversation_id"]
        assert conversation_id

        detail = await client.get(
            f"/api/v1/conversations/{conversation_id}", headers=headers
        )
        assert detail.status_code == 200
        messages = detail.json()["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[1]["sources"][0]["document_id"] == "150-2025-ND-CP"

        app.dependency_overrides.pop(get_hybrid_pipeline, None)


class TestDocumentAdminAPI:
    async def test_upload_requires_admin(self, client):
        files = {"file": ("note.txt", b"Noi dung van ban.", "text/plain")}

        anonymous = await client.post("/api/v1/documents", files=files)
        assert anonymous.status_code == 401

        token = await register_and_login(client)
        user_upload = await client.post(
            "/api/v1/documents", files=files, headers=auth_header(token)
        )
        assert user_upload.status_code == 403

    async def test_list_and_delete_document(self, client, monkeypatch):
        token = await register_and_login(client)
        async with client.session_factory() as db:
            from app.core.security import hash_password

            admin = await user_repo.create_user(
                db,
                email="admin2@example.com",
                hashed_password=hash_password("AdminPass123"),
                full_name="Admin",
                role="admin",
            )
            assert isinstance(admin, User)

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin2@example.com", "password": "AdminPass123"},
        )
        headers = auth_header(login.json()["access_token"])

        class FakeVectorStore:
            def list_documents(self):
                return [
                    {
                        "document_id": "150-2025-ND-CP",
                        "filename": "150.pdf",
                        "chunk_count": 42,
                    }
                ]

            def delete_document(self, document_id):
                return 42 if document_id == "150-2025-ND-CP" else 0

        app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore()
        monkeypatch.setattr(
            "app.api.documents.rebuild_bm25_index", lambda *args, **kwargs: None
        )

        listed = await client.get("/api/v1/documents", headers=headers)
        assert listed.status_code == 200
        assert listed.json()[0]["chunk_count"] == 42

        deleted = await client.delete(
            "/api/v1/documents/150-2025-ND-CP", headers=headers
        )
        assert deleted.status_code == 200
        assert deleted.json()["deleted_chunks"] == 42

        missing = await client.delete(
            "/api/v1/documents/unknown", headers=headers
        )
        assert missing.status_code == 404

        app.dependency_overrides.pop(get_vector_store, None)


class TestCORS:
    async def test_allows_local_frontend(self, client):
        response = await client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    async def test_rejects_unknown_origin(self, client):
        response = await client.options(
            "/",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 400
