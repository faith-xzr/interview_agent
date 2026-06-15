from app.schemas import VoiceAsrSettings, VoiceTtsSettings
from app.voice.dashscope import (
    asr_session_update_event,
    extract_asr_subtitle,
    extract_tts_audio_delta,
    tts_append_text_event,
    tts_commit_event,
    tts_session_update_event,
)


def test_asr_session_update_event_uses_qwen_realtime_pcm_contract():
    event = asr_session_update_event(
        VoiceAsrSettings(
            model="qwen3-asr-flash-realtime",
            sample_rate=16000,
            input_audio_format="pcm",
            language="zh",
            server_vad=True,
            silence_duration_ms=400,
        )
    )

    assert event["type"] == "session.update"
    assert event["session"]["modalities"] == ["text"]
    assert event["session"]["input_audio_format"] == "pcm"
    assert event["session"]["sample_rate"] == 16000
    assert event["session"]["input_audio_transcription"] == {"language": "zh"}
    assert event["session"]["turn_detection"] == {
        "type": "server_vad",
        "threshold": 0.0,
        "silence_duration_ms": 400,
    }


def test_asr_event_mapping_returns_partial_and_final_subtitles():
    partial = extract_asr_subtitle({
        "type": "conversation.item.input_audio_transcription.text",
        "text": "我负责",
        "stash": "过工具调用",
    })
    final = extract_asr_subtitle({
        "type": "conversation.item.input_audio_transcription.completed",
        "text": "我负责过工具调用。",
    })

    assert partial == {"type": "subtitle", "text": "我负责过工具调用", "isFinal": False}
    assert final == {"type": "subtitle", "text": "我负责过工具调用。", "isFinal": True}


def test_tts_events_use_commit_mode_and_extract_audio_delta():
    settings = VoiceTtsSettings(
        model="qwen3-tts-flash-realtime",
        voice="Cherry",
        response_format="pcm",
        sample_rate=24000,
    )

    session_event = tts_session_update_event(settings)
    append_event = tts_append_text_event("请继续介绍项目细节。")

    assert session_event["type"] == "session.update"
    assert session_event["session"]["mode"] == "commit"
    assert session_event["session"]["voice"] == "Cherry"
    assert session_event["session"]["response_format"] == "pcm"
    assert session_event["session"]["sample_rate"] == 24000
    assert append_event == {
        "type": "input_text_buffer.append",
        "text": "请继续介绍项目细节。",
    }
    assert tts_commit_event() == {"type": "input_text_buffer.commit"}
    assert extract_tts_audio_delta({"type": "response.audio.delta", "delta": "YWJj"}) == "YWJj"
    assert extract_tts_audio_delta({"type": "response.done"}) is None
