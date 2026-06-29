import os
import re
import tempfile
import datetime
from flask import request, jsonify
from logger import ExecutionLogger
from groq_client import GroqClient
from groq_template import flag_transcript_with_llm, tag_transcript_with_llm
from nanobot_template import run_agent

# In-memory transcript history keyed by user_id (used for nanobot context)
# Each entry: {"segment_no": int, "transcript": str}
_transcript_history = {}
_MAX_HISTORY = 20  # per user

# In-memory session store keyed by user_id (full segment results, survives until End Session)
# Each entry: {segment_no, transcript, timestamp, flags, tags, question_answers}
_session_store = {}


def _store_transcript(user_id: str, segment_no: int, transcript: str):
    """Append a transcript to in-memory history for this user."""
    if user_id not in _transcript_history:
        _transcript_history[user_id] = []
    _transcript_history[user_id].append(
        {"segment_no": segment_no, "transcript": transcript}
    )
    if len(_transcript_history[user_id]) > _MAX_HISTORY:
        _transcript_history[user_id].pop(0)


def _store_segment_result(
    user_id: str,
    segment_no: int,
    transcript: str,
    timestamp: str,
    flags: dict,
    tags: dict,
    question_answers: dict,
):
    """Store a full segment result in the session store."""
    if user_id not in _session_store:
        _session_store[user_id] = []
    _session_store[user_id] = [
        s for s in _session_store[user_id] if s.get("segment_no") != segment_no
    ]
    _session_store[user_id].append(
        {
            "segment_no": segment_no,
            "transcript": transcript,
            "timestamp": timestamp,
            "flags": flags,
            "tags": tags,
            "question_answers": question_answers,
        }
    )
    _session_store[user_id].sort(key=lambda s: s["segment_no"])


def get_session_data(user_id: str) -> dict:
    """Return stored session data for a user."""
    segments = _session_store.get(user_id, [])
    max_segment_no = max((s["segment_no"] for s in segments), default=0)
    return {"segments": segments, "max_segment_no": max_segment_no}


def clear_session(user_id: str):
    """Clear all session data for a user."""
    _session_store.pop(user_id, None)
    _transcript_history.pop(user_id, None)


def get_recent_transcripts(user_id: str, limit: int = 5) -> list:
    """Return the last N transcripts for a user, oldest first."""
    history = _transcript_history.get(user_id, [])
    return history[-limit:]


DEFAULT_FLAG_PAIRS_DICT = {
    "question": ["?", "question"],
    "special_note": ["special note", "make a note", "note this down", "note that"],
    "search": ["search for", "look up", "google", "find out"],
}


def flag_transcript_with_simple_regex(
    segments, user_id=None, flag_pairs_dict=None, **kwargs
):
    """Regex-based transcript flagging. Drop-in replacement for flag_transcript_with_llm.

    flag_pairs_dict: {flag_name: [trigger_string, ...]}
    Any sentence containing a trigger string produces a flag of that name.
    """
    logger = ExecutionLogger()

    try:
        if flag_pairs_dict is None:
            flag_pairs_dict = DEFAULT_FLAG_PAIRS_DICT
        if not isinstance(segments, list):
            segments = [segments]

        logger.log(
            "Starting regex flagging",
            log_data={
                "segment_count": len(segments),
                "flag_types": list(flag_pairs_dict.keys()),
                "user_id": user_id,
            },
        )

        compiled = {
            flag_type: re.compile(
                r"[^.!?]*(?:" + "|".join(re.escape(t) for t in triggers) + r")[^.!?]*",
                re.IGNORECASE,
            )
            for flag_type, triggers in flag_pairs_dict.items()
        }

        flags = []
        by_type = {flag_type: [] for flag_type in flag_pairs_dict}

        for segment in segments:
            seg_no = segment.get("segment_no")
            text = segment.get("transcript", "")
            for flag_type, pattern in compiled.items():
                for match in pattern.findall(text):
                    content = match.strip()
                    if content:
                        flags.append(
                            {
                                "flag_type": flag_type,
                                "content": content,
                                "context": text,
                                "segment_no": seg_no,
                                "tags": [],
                            }
                        )
                        by_type[flag_type].append(content)

        flagged_items = {k: len(v) for k, v in by_type.items()}

        logger.log(
            "Regex flagging complete",
            log_data={
                "flag_count": len(flags),
                "by_type": flagged_items,
                "flags": flags,
            },
        )

        return {
            "metadata": {
                "flags": flags,
                "questions": by_type.get("question", []),
                "special_notes": by_type.get("special_note", []),
                "search_queries": by_type.get("search", []),
                "success": True,
                "flag_count": len(flags),
            },
            "segments": segments,
            "api_response": None,
        }

    finally:
        logger.commit()


def question_answer_response(
    context: str = "",
    model: str = "nemotron-3-nano:30b",
) -> dict:
    """
    Generate answers to multiple questions in one batch using Groq LLM with optional context.
    """
    logger = ExecutionLogger()
    now = datetime.datetime.now()

    try:
        system_prompt = "This is a voice transcript. Consider the following text, focus on the last part, and follow any instructions throughout, but keep your response clear, concise and audio friendly. 20-50 words max."

        user_message = f"\nUSER TRANSCRIPT:\n{context}"

        full_prompt = f"{system_prompt}\n{user_message}"
        # full_prompt = f"{user_message}"

        # log it
        logger.log(
            "question_answer_response() initiated",
            log_data={
                # "num_questions": len(questions),
                "full_prompt": full_prompt,
                # "model": model,
                # "answer_type": answer_type,
            },
            truncate=False,
        )

        #

        # Use nanobot to answer the questions
        try:
            response = run_agent(full_prompt)
            result = response

            # calculate time elapsed
            start_time = now
            end_time = datetime.datetime.now()
            time_elapsed = end_time - start_time

        except Exception as e:
            logger.log(
                "question_answer_response() failed", log_type="ERROR", log_data=str(e)
            )
            raise e

        logger.log(
            "question_answer_response() completed",
            log_data={
                "full_response": result,
                # "num_questions": len(questions),
                "response_length": len(result),
            },
        )
        logger.commit()

        return {
            "success": True,
            "answer": result,
            "context_provided": bool(context),
            "model": model,
        }

    except Exception as e:
        logger.log(
            "question_answer_response() failed", log_type="ERROR", log_data=str(e)
        )
        logger.commit()
        return {
            "success": False,
            "error": str(e),
            "answer": None,
            "context_provided": bool(context),
        }


def transcribe_audio_segment(audio_file, user_id, segment_no):
    """Save audio to a temp file, transcribe it, and store the result. Returns (transcript_text, file_size)."""
    logger = ExecutionLogger()
    temp_file_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
            temp_file_path = temp_file.name
            audio_file.save(temp_file_path)
            file_size = os.path.getsize(temp_file_path)

        logger.log("Audio saved to temp file", log_data={"size_bytes": file_size})

        groq_client = GroqClient()
        transcription_result = groq_client.transcribe_audio(
            audio_file_path=temp_file_path,
            model="whisper-large-v3",
            temperature=0.0,
        )

        if not transcription_result.get("success"):
            logger.log(
                "Transcription failed", log_type="ERROR", log_data=transcription_result
            )
            raise RuntimeError(
                transcription_result.get("error", "Transcription failed")
            )

        transcript_text = transcription_result.get("text", "")
        logger.log(
            "Transcription successful",
            log_data={
                "segment_no": segment_no,
                "transcript_length": len(transcript_text),
                "transcript": transcript_text,
            },
        )

        _store_transcript(user_id, int(segment_no), transcript_text)

        return transcript_text, file_size

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
        logger.commit()


def flag_transcript(segments, user_id):
    """Run regex-based flagging on segments. Returns flag_result dict."""
    logger = ExecutionLogger()
    try:
        result = flag_transcript_with_simple_regex(segments=segments, user_id=user_id)
        logger.log(
            "Flagging complete",
            log_data={
                "flag_count": result.get("metadata", {}).get("flag_count", 0),
            },
        )
        return result
    except Exception as e:
        logger.log("Flagging failed (non-fatal)", log_type="WARNING", log_data=str(e))
        return {"error": str(e)}
    finally:
        logger.commit()


def tag_transcript(segments, user_id):
    """Run LLM-based tagging on segments. Returns tag_result dict."""
    logger = ExecutionLogger()
    try:
        result = tag_transcript_with_llm(segments=segments, user_id=user_id)
        logger.log(
            "Tagging complete",
            log_data={
                "tag_count": result.get("metadata", {}).get("tag_count", 0),
            },
        )
        return result
    except Exception as e:
        logger.log("Tagging failed (non-fatal)", log_type="WARNING", log_data=str(e))
        return {"error": str(e)}
    finally:
        logger.commit()


def analyze_transcript(transcript_text, user_id, segment_no):
    """Flag, tag, and run nanobot response on every transcript. Returns a result dict."""
    logger = ExecutionLogger()
    segments = [{"segment_no": int(segment_no), "transcript": transcript_text}]
    flag_result = flag_transcript(segments, user_id)
    tag_result = tag_transcript(segments, user_id)

    try:
        recent_transcripts = get_recent_transcripts(user_id)
        context_parts = [
            f"[Segment {t.get('segment_no', '?')}] {t.get('transcript', '')}"
            for t in recent_transcripts
        ]
        combined_context = "\n\n".join(context_parts)

        logger.log(
            "Nanobot context prepared",
            log_data={
                "recent_segments": len(recent_transcripts),
                "context_chars": len(combined_context),
            },
        )

        nanobot_response = question_answer_response(
            context=combined_context,
        )
    except Exception as e:
        logger.log(
            "Nanobot response failed (non-fatal)", log_type="WARNING", log_data=str(e)
        )
        nanobot_response = {"error": str(e)}
    finally:
        logger.commit()

    return {
        "flags": flag_result,
        "tags": tag_result,
        "question_answers": nanobot_response,
    }


def process_audio_segment(audio_file, user_id, segment_no):
    """Transcribe audio and run the full analysis pipeline. Returns a result dict."""
    transcript_text, file_size = transcribe_audio_segment(
        audio_file, user_id, segment_no
    )
    analysis = analyze_transcript(transcript_text, user_id, segment_no)
    timestamp = datetime.datetime.now().strftime("%I:%M:%S %p")
    _store_segment_result(
        user_id=user_id,
        segment_no=int(segment_no),
        transcript=transcript_text,
        timestamp=timestamp,
        flags=analysis.get("flags"),
        tags=analysis.get("tags"),
        question_answers=analysis.get("question_answers"),
    )
    return {"size_bytes": file_size, "transcript": transcript_text, **analysis}


def register_presence_routes(app):
    """Register presence-related routes with the Flask app"""

    @app.route("/api/session/<user_id>", methods=["GET"])
    def get_session(user_id):
        """Return stored session data for a user."""
        data = get_session_data(user_id)
        return jsonify(data)

    @app.route("/api/session/<user_id>/end", methods=["POST"])
    def end_session(user_id):
        """Clear all session data for a user."""
        clear_session(user_id)
        return jsonify(
            {"status": "success", "message": f"Session cleared for {user_id}"}
        )

    @app.route("/api/upload/audio", methods=["POST"])
    def upload_audio():
        """Validate the request and delegate to process_audio_segment."""
        logger = ExecutionLogger()

        try:
            if "audio" not in request.files:
                return jsonify({"error": "No audio file provided"}), 400

            audio_file = request.files["audio"]
            user_id = request.form.get("user_id")
            segment_no = request.form.get("segment_no")
            session_animal = request.form.get("sessionAnimal")
            session_number = request.form.get("sessionNumber")
            if not user_id:
                return jsonify({"error": "user_id is required"}), 400
            if not segment_no:
                return jsonify({"error": "segment_no is required"}), 400
            if not session_animal:
                return jsonify({"error": "sessionAnimal is required"}), 400
            if not session_number:
                return jsonify({"error": "sessionNumber is required"}), 400

            logger.log(
                "Audio upload received",
                log_data={
                    "user_id": user_id,
                    "segment_no": segment_no,
                    "filename": audio_file.filename,
                },
            )

            result = process_audio_segment(audio_file, user_id, segment_no)

            qa = result.get("question_answers") or {}
            audio_update = (
                qa.get("answer") if qa.get("success") and qa.get("answer") else None
            )

            return jsonify(
                {
                    "status": "success",
                    "message": "Audio uploaded and transcribed successfully",
                    "user_id": user_id,
                    "segment_no": segment_no,
                    **result,
                    "audio_update": audio_update,
                    "ready": True,
                }
            )

        except Exception as e:
            logger.log("Audio upload failed", log_type="ERROR", log_data=str(e))
            return jsonify({"error": str(e)}), 500

        finally:
            logger.commit()
