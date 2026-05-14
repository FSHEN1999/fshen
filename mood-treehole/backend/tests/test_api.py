import os
from pathlib import Path

os.environ["DATABASE_URL"] = f"sqlite:///{(Path(__file__).parent / 'test_treehole.db').as_posix()}"
os.environ["QWEN_API_KEY"] = ""
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "adminpass123"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_anonymous_entry_and_history():
    response = client.post(
        "/api/entries",
        json={
            "visitor_id": "visitor-1",
            "mood": "低落",
            "content": "今天心情很低落，但我想慢慢变好。",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["visitor_id"] == "visitor-1"
    assert data["conversation_id"]
    assert data["conversation_status"] == "active"
    assert data["ai_reply"]
    assert data["analysis_source"] == "fallback"
    assert data["status"] == "visible"

    history = client.get("/api/me/entries", params={"visitor_id": "visitor-1"})
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_conversation_can_continue_until_farewell():
    first = client.post(
        "/api/entries",
        json={"visitor_id": "visitor-talk", "mood": "焦虑", "content": "我今天想多说一会儿。"},
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/api/entries",
        json={
            "conversation_id": conversation_id,
            "visitor_id": "visitor-talk",
            "mood": "疲惫",
            "content": "继续说一下，感觉身体也很累。",
        },
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    assert second.json()["conversation_status"] == "active"

    farewell = client.post(
        "/api/entries",
        json={
            "conversation_id": conversation_id,
            "visitor_id": "visitor-talk",
            "mood": "还好",
            "content": "今天先到这里，再见。",
        },
    )
    assert farewell.status_code == 200
    assert farewell.json()["conversation_id"] == conversation_id
    assert farewell.json()["conversation_status"] == "closed"
    assert farewell.json()["is_farewell"] is True

    detail = client.get(f"/api/conversations/{conversation_id}", params={"visitor_id": "visitor-talk"})
    assert detail.status_code == 200
    assert detail.json()["status"] == "closed"
    assert len(detail.json()["messages"]) == 3


def test_register_login_and_user_entries():
    register = client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "password123", "display_name": "Alice"},
    )
    assert register.status_code == 200
    token = register.json()["token"]

    entry = client.post(
        "/api/entries",
        headers={"Authorization": f"Bearer {token}"},
        json={"visitor_id": "visitor-2", "mood": "焦虑", "content": "工作很多，我有点焦虑。"},
    )
    assert entry.status_code == 200

    login = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert login.status_code == 200

    mine = client.get("/api/me/entries", headers={"Authorization": f"Bearer {token}"})
    assert mine.status_code == 200
    assert mine.json()[0]["mood"] == "焦虑"


def test_admin_can_list_and_moderate_entries():
    entry = client.post(
        "/api/entries",
        json={"visitor_id": "visitor-3", "mood": "崩溃", "content": "我已经崩溃到睡不着。"},
    )
    assert entry.status_code == 200
    entry_id = entry.json()["id"]

    ordinary = client.get("/api/admin/entries")
    assert ordinary.status_code == 401

    login = client.post("/api/admin/login", json={"username": "admin", "password": "adminpass123"})
    assert login.status_code == 200
    admin_token = login.json()["token"]

    entries = client.get("/api/admin/entries", headers={"Authorization": f"Bearer {admin_token}"})
    assert entries.status_code == 200
    assert len(entries.json()) == 1
    assert entries.json()[0]["conversation_id"]

    patched = client.patch(
        f"/api/admin/entries/{entry_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "hidden", "manual_reply": "我看到了，会先把这条记录收起来。"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "hidden"
    assert patched.json()["manual_reply"]


def test_admin_manual_reply_pushes_websocket_event():
    entry = client.post(
        "/api/entries",
        json={"visitor_id": "visitor-ws", "mood": "委屈", "content": "我想听到有人回应我。"},
    )
    assert entry.status_code == 200
    entry_data = entry.json()
    conversation_id = entry_data["conversation_id"]

    login = client.post("/api/admin/login", json={"username": "admin", "password": "adminpass123"})
    assert login.status_code == 200
    admin_token = login.json()["token"]

    with client.websocket_connect(f"/api/ws/conversations/{conversation_id}?visitor_id=visitor-ws") as websocket:
        patched = client.patch(
            f"/api/admin/entries/{entry_data['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"manual_reply": "管理员在这里，已经看到你的留言。"},
        )
        assert patched.status_code == 200
        event = websocket.receive_json()

    assert event["type"] == "admin_reply"
    assert event["conversation_id"] == conversation_id
    assert event["entry_id"] == entry_data["id"]
    assert event["manual_reply"] == "管理员在这里，已经看到你的留言。"


def test_close_conversation_button_endpoint():
    entry = client.post(
        "/api/entries",
        json={"visitor_id": "visitor-close", "mood": "还好", "content": "我先测试一下关闭按钮。"},
    )
    conversation_id = entry.json()["conversation_id"]

    closed = client.post(
        f"/api/conversations/{conversation_id}/close",
        json={"visitor_id": "visitor-close"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_reason"] == "user_button"


def test_high_risk_goes_to_review_even_without_model():
    response = client.post(
        "/api/entries",
        json={"visitor_id": "visitor-4", "mood": "绝望", "content": "我不想活了，想结束生命。"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "high"
    assert data["status"] == "pending_review"
