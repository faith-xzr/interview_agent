import asyncio

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import InterviewSession, VoiceSettingsResponse
from app.storage import RunStorage


def make_client(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "demo.sqlite3",
        vector_dir=tmp_path / "vectors",
        llm_api_key=None,
        llm_base_url=None,
        llm_model="demo-offline",
    )
    return TestClient(create_app(settings)), settings


def create_interview_session(client: TestClient) -> dict:
    run_response = client.post(
        "/api/runs",
        data={
            "jd_text": "AI Agent 开发工程师，负责智能体编排、工具调用、RAG 与多轮对话评估。",
            "resume_texts": (
                "小黄\n"
                "3年 AI Agent 开发经验。项目：智能客服 Agent，负责工具调用、RAG 检索和多轮追问。"
            ),
        },
    )
    assert run_response.status_code == 200
    report = run_response.json()

    session_response = client.post(
        f"/api/runs/{report['run_id']}/interviews",
        json={
            "candidate_id": report["candidates"][0]["candidate_id"],
            "mode": "voice:AI Agent 开发:中级:追问型",
            "skill_id": "ai-agent-dev",
        },
    )
    assert session_response.status_code == 200
    return session_response.json()


def test_voice_settings_reads_dashscope_key_state(tmp_path):
    client, settings = make_client(tmp_path)
    storage = RunStorage(settings.database_path)
    storage.set_setting("model_provider_api_key:dashscope", "sk-test-dashscope")

    response = client.get("/api/settings/voice")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_id"] == "dashscope"
    assert payload["api_key_configured"] is True
    assert payload["api_key_source"] == "saved"
    assert payload["asr"]["model"] == "qwen3-asr-flash-realtime"
    assert payload["asr"]["sample_rate"] == 16000
    assert payload["tts"]["model"] == "qwen3-tts-flash-realtime"
    assert payload["tts"]["voice"] == "Cherry"


def test_create_voice_session_links_existing_interview_session(tmp_path):
    client, _settings = make_client(tmp_path)
    interview_session = create_interview_session(client)

    response = client.post(
        "/api/voice-interviews",
        json={"interview_session_id": interview_session["session_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["voice_session_id"]
    assert payload["interview_session_id"] == interview_session["session_id"]
    assert payload["status"] == "active"
    assert payload["websocket_url"] == f"/ws/voice-interviews/{payload['voice_session_id']}"

    read_response = client.get(f"/api/voice-interviews/{payload['voice_session_id']}")
    assert read_response.status_code == 200
    assert read_response.json()["interview_session_id"] == interview_session["session_id"]


def test_voice_websocket_can_submit_final_transcript_as_interview_turn(tmp_path):
    client, _settings = make_client(tmp_path)
    interview_session = create_interview_session(client)
    voice_session = client.post(
        "/api/voice-interviews",
        json={"interview_session_id": interview_session["session_id"]},
    ).json()

    with client.websocket_connect(voice_session["websocket_url"]) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "control"
        assert ready["action"] == "ready"

        websocket.send_json({
            "type": "control",
            "action": "submit_text",
            "text": "我负责过一个客服 Agent，主要做工具调用编排、知识库检索和失败兜底。",
        })

        subtitle = websocket.receive_json()
        assert subtitle == {
            "type": "subtitle",
            "text": "我负责过一个客服 Agent，主要做工具调用编排、知识库检索和失败兜底。",
            "isFinal": True,
        }

        result = websocket.receive_json()
        assert result["type"] == "interview_session"
        updated_session = result["session"]
        assert len(updated_session["turns"]) == 1
        assert updated_session["turns"][0]["answer_source"] == "speech"
        assert updated_session["turns"][0]["answer_metadata"]["source"] == "speech"
        assert updated_session["turns"][0]["answer_metadata"]["finalized"] is True


def test_voice_websocket_streams_audio_through_asr_and_tts(tmp_path, monkeypatch):
    emitted_audio_chunks = []

    class FakeAsrStream:
        def __init__(self, api_key, settings, on_subtitle, on_error):
            self.api_key = api_key
            self.settings = settings
            self.on_subtitle = on_subtitle
            self.on_error = on_error

        async def connect(self):
            return None

        async def append_audio(self, audio_base64):
            await self.on_subtitle({
                "type": "subtitle",
                "text": "我负责过 RAG 检索和工具调用。",
                "isFinal": True,
            })

        async def close(self):
            return None

    class FakeTtsClient:
        def __init__(self, api_key, settings):
            self.api_key = api_key
            self.settings = settings

        async def synthesize(self, text):
            emitted_audio_chunks.append(text)
            yield "ZmFrZS1hdWRpbw=="

    monkeypatch.setattr("app.main.DashScopeAsrStream", FakeAsrStream)
    monkeypatch.setattr("app.main.DashScopeTtsClient", FakeTtsClient)
    client, _settings = make_client(tmp_path)
    client.put("/api/settings/model-providers/dashscope/api-key", json={"api_key": "sk-test"})
    interview_session = create_interview_session(client)
    voice_session = client.post(
        "/api/voice-interviews",
        json={"interview_session_id": interview_session["session_id"]},
    ).json()

    with client.websocket_connect(voice_session["websocket_url"]) as websocket:
        assert websocket.receive_json()["action"] == "ready"
        initial_audio = websocket.receive_json()
        assert initial_audio["type"] == "audio_chunk"
        initial_done = websocket.receive_json()
        assert initial_done["type"] == "audio_chunk"
        assert initial_done["isLast"] is True

        websocket.send_json({"type": "audio", "data": "AAECAw=="})

        subtitle = websocket.receive_json()
        assert subtitle == {
            "type": "subtitle",
            "text": "我负责过 RAG 检索和工具调用。",
            "isFinal": True,
        }

        session_message = websocket.receive_json()
        assert session_message["type"] == "interview_session"
        assert session_message["session"]["turns"][0]["answer"] == "我负责过 RAG 检索和工具调用。"

        audio_chunk = websocket.receive_json()
        assert audio_chunk == {
            "type": "audio_chunk",
            "data": "ZmFrZS1hdWRpbw==",
            "index": 0,
            "isLast": False,
        }
        audio_done = websocket.receive_json()
        assert audio_done == {
            "type": "audio_chunk",
            "data": "",
            "index": 1,
            "isLast": True,
        }
        assert emitted_audio_chunks


def test_stream_current_question_tts_uses_session_current_question(tmp_path, monkeypatch):
    spoken_texts = []

    class FakeTtsClient:
        def __init__(self, api_key, settings):
            self.api_key = api_key
            self.settings = settings

        async def synthesize(self, text):
            spoken_texts.append(text)
            yield "aW5pdGlhbC1hdWRpbw=="

    monkeypatch.setattr("app.main.DashScopeTtsClient", FakeTtsClient)
    from app.main import _stream_current_question_tts

    client, _settings = make_client(tmp_path)
    interview_session = create_interview_session(client)

    async def run_stream():
        queue = asyncio.Queue()
        await _stream_current_question_tts(
            InterviewSession.model_validate(interview_session),
            queue,
            "sk-test",
            VoiceSettingsResponse(),
        )
        return queue.get_nowait()

    assert asyncio.run(run_stream()) == {
        "type": "audio_chunk",
        "data": "aW5pdGlhbC1hdWRpbw==",
        "index": 0,
        "isLast": False,
    }
    assert spoken_texts == [interview_session["current_question"]["question"]]


def test_voice_websocket_replays_current_question_tts(tmp_path, monkeypatch):
    spoken_texts = []

    class FakeAsrStream:
        def __init__(self, api_key, settings, on_subtitle, on_error):
            self.api_key = api_key
            self.settings = settings
            self.on_subtitle = on_subtitle
            self.on_error = on_error

        async def connect(self):
            return None

        async def close(self):
            return None

    class FakeTtsClient:
        def __init__(self, api_key, settings):
            self.api_key = api_key
            self.settings = settings

        async def synthesize(self, text):
            spoken_texts.append(text)
            yield "cmVwbGF5LWF1ZGlv"

    monkeypatch.setattr("app.main.DashScopeAsrStream", FakeAsrStream)
    monkeypatch.setattr("app.main.DashScopeTtsClient", FakeTtsClient)
    client, _settings = make_client(tmp_path)
    client.put("/api/settings/model-providers/dashscope/api-key", json={"api_key": "sk-test"})
    interview_session = create_interview_session(client)
    voice_session = client.post(
        "/api/voice-interviews",
        json={"interview_session_id": interview_session["session_id"]},
    ).json()

    with client.websocket_connect(voice_session["websocket_url"]) as websocket:
        assert websocket.receive_json()["action"] == "ready"
        assert websocket.receive_json()["type"] == "audio_chunk"
        assert websocket.receive_json()["isLast"] is True

        websocket.send_json({"type": "control", "action": "speak_current_question"})

        replay = websocket.receive_json()
        assert replay == {
            "type": "audio_chunk",
            "data": "cmVwbGF5LWF1ZGlv",
            "index": 0,
            "isLast": False,
        }
        assert spoken_texts == [
            interview_session["current_question"]["question"],
            interview_session["current_question"]["question"],
        ]
