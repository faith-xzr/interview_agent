import asyncio
import json
import time
from typing import Awaitable, Callable, Optional

from app.schemas import VoiceAsrSettings, VoiceTtsSettings


DASHSCOPE_REALTIME_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"

SubtitleHandler = Callable[[dict], Awaitable[None]]
ErrorHandler = Callable[[str], Awaitable[None]]


def dashscope_realtime_url(model: str) -> str:
    return f"{DASHSCOPE_REALTIME_URL}?model={model}"


def asr_session_update_event(settings: VoiceAsrSettings) -> dict:
    session = {
        "modalities": ["text"],
        "input_audio_format": settings.input_audio_format,
        "sample_rate": settings.sample_rate,
        "input_audio_transcription": {"language": settings.language},
    }
    if settings.server_vad:
        session["turn_detection"] = {
            "type": "server_vad",
            "threshold": 0.0,
            "silence_duration_ms": settings.silence_duration_ms,
        }
    else:
        session["turn_detection"] = None
    return {
        "type": "session.update",
        "session": session,
    }


def asr_append_audio_event(audio_base64: str) -> dict:
    return {
        "type": "input_audio_buffer.append",
        "audio": audio_base64,
    }


def asr_commit_event() -> dict:
    return {"type": "input_audio_buffer.commit"}


def asr_finish_event() -> dict:
    return {"type": "session.finish"}


def extract_asr_subtitle(event: dict) -> Optional[dict]:
    event_type = event.get("type")
    if event_type == "conversation.item.input_audio_transcription.text":
        text = f"{event.get('text') or ''}{event.get('stash') or ''}".strip()
        if not text:
            return None
        return {"type": "subtitle", "text": text, "isFinal": False}
    if event_type == "conversation.item.input_audio_transcription.completed":
        text = str(event.get("text") or event.get("transcript") or "").strip()
        if not text:
            return None
        return {"type": "subtitle", "text": text, "isFinal": True}
    return None


def tts_session_update_event(settings: VoiceTtsSettings) -> dict:
    return {
        "type": "session.update",
        "session": {
            "mode": "commit",
            "voice": settings.voice,
            "language_type": "Auto",
            "response_format": settings.response_format,
            "sample_rate": settings.sample_rate,
        },
    }


def tts_append_text_event(text: str) -> dict:
    return {
        "type": "input_text_buffer.append",
        "text": text,
    }


def tts_commit_event() -> dict:
    return {"type": "input_text_buffer.commit"}


def tts_finish_event() -> dict:
    return {"type": "session.finish"}


def extract_tts_audio_delta(event: dict) -> Optional[str]:
    if event.get("type") != "response.audio.delta":
        return None
    delta = event.get("delta")
    return str(delta) if delta else None


def _with_event_id(event: dict) -> dict:
    return {
        "event_id": f"event_{int(time.time() * 1000)}",
        **event,
    }


async def _connect(url: str, api_key: str):
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("缺少 websockets 依赖，请先安装后再启用百炼实时语音。") from exc

    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }
    try:
        return await websockets.connect(url, additional_headers=headers)
    except TypeError:
        return await websockets.connect(url, extra_headers=headers)


class DashScopeAsrStream:
    def __init__(
        self,
        api_key: str,
        settings: VoiceAsrSettings,
        on_subtitle: SubtitleHandler,
        on_error: ErrorHandler,
    ) -> None:
        self.api_key = api_key
        self.settings = settings
        self.on_subtitle = on_subtitle
        self.on_error = on_error
        self.websocket = None
        self.receiver_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        self.websocket = await _connect(dashscope_realtime_url(self.settings.model), self.api_key)
        await self._send(asr_session_update_event(self.settings))
        self.receiver_task = asyncio.create_task(self._receive_loop())

    async def append_audio(self, audio_base64: str) -> None:
        if self.websocket is None:
            raise RuntimeError("ASR 连接尚未建立。")
        await self._send(asr_append_audio_event(audio_base64))

    async def commit(self) -> None:
        if self.websocket is not None and not self.settings.server_vad:
            await self._send(asr_commit_event())

    async def close(self) -> None:
        if self.websocket is not None:
            try:
                await self._send(asr_finish_event())
            except Exception:
                pass
            await self.websocket.close()
            self.websocket = None
        if self.receiver_task is not None:
            self.receiver_task.cancel()
            self.receiver_task = None

    async def _send(self, event: dict) -> None:
        if self.websocket is None:
            return
        await self.websocket.send(json.dumps(_with_event_id(event), ensure_ascii=False))

    async def _receive_loop(self) -> None:
        if self.websocket is None:
            return
        try:
            async for raw_message in self.websocket:
                event = json.loads(raw_message)
                if event.get("type") == "error":
                    error = event.get("error") or {}
                    await self.on_error(str(error.get("message") or "百炼 ASR 返回错误。"))
                    continue
                subtitle = extract_asr_subtitle(event)
                if subtitle is not None:
                    await self.on_subtitle(subtitle)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.on_error(f"百炼 ASR 连接异常：{exc}")


class DashScopeTtsClient:
    def __init__(self, api_key: str, settings: VoiceTtsSettings) -> None:
        self.api_key = api_key
        self.settings = settings

    async def synthesize(self, text: str):
        websocket = await _connect(dashscope_realtime_url(self.settings.model), self.api_key)
        try:
            await websocket.send(json.dumps(_with_event_id(tts_session_update_event(self.settings)), ensure_ascii=False))
            await websocket.send(json.dumps(_with_event_id(tts_append_text_event(text)), ensure_ascii=False))
            await websocket.send(json.dumps(_with_event_id(tts_commit_event()), ensure_ascii=False))
            async for raw_message in websocket:
                event = json.loads(raw_message)
                if event.get("type") == "error":
                    error = event.get("error") or {}
                    raise RuntimeError(str(error.get("message") or "百炼 TTS 返回错误。"))
                audio_delta = extract_tts_audio_delta(event)
                if audio_delta:
                    yield audio_delta
                if event.get("type") in {"response.done", "session.finished"}:
                    break
            await websocket.send(json.dumps(_with_event_id(tts_finish_event()), ensure_ascii=False))
        finally:
            await websocket.close()
