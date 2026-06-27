import os
import tempfile
import datetime
from collections import defaultdict
from flask import request, jsonify
from logger import ExecutionLogger
from groq_client import GroqClient
from groq_template import flag_transcript_with_llm, tag_transcript_with_llm
from nanobot_template import run_agent

# In-memory transcript history keyed by user_id
# Each entry: {"segment_no": int, "transcript": str}
_transcript_history = defaultdict(list)
_MAX_HISTORY = 20  # per user


def _store_transcript(user_id: str, segment_no: int, transcript: str):
    """Append a transcript to in-memory history for this user."""
    history = _transcript_history[user_id]
    history.append({"segment_no": segment_no, "transcript": transcript})
    if len(history) > _MAX_HISTORY:
        history.pop(0)


def get_recent_transcripts(
    user_id: str, limit: int = 3, exclude_segment: int = None
) -> list:
    """
    Return the last N transcripts for a user from in-memory history,
    optionally excluding a specific segment number.
    """
    history = _transcript_history.get(user_id, [])
    filtered = [t for t in history if t.get("segment_no") != exclude_segment]
    return filtered[-limit:]


def question_answer_response(
    questions: list,
    context: str = "",
    model: str = "nemotron-3-nano:30b",
    answer_type: str = "detailed",
) -> dict:
    """
    Generate answers to multiple questions in one batch using Groq LLM with optional context.
    """
    logger = ExecutionLogger()
    now = datetime.datetime.now()

    try:
        system_prompt = "You are a helpful and accurate assistant. Provide clear, concise answers to user questions."
        if answer_type == "concise":
            system_prompt += (
                " Keep answers brief and to the point. 10-50 words per answer max."
            )
        if answer_type == "detailed":
            system_prompt += " Provide thorough explanations, focusing on insightful brevity. 50-200 words per answer max."
        if answer_type == "poetic":
            system_prompt += " Respond in a chinese poetic style with philosophical depth and conceptual brevity. 40-80 words per answer max."
        if answer_type == "hermes":
            system_prompt += " Respond in a reddit post top comment poetic style with philosophical depth, conceptual brevity, and absolute clarity. 40-80 words per answer max."

        questions_text = "\n".join([f"{i + 1}. {q}" for i, q in enumerate(questions)])

        if context:
            user_message = (
                f"CONTEXT:\n{context}\n\nANSWER THESE QUESTIONS:\n{questions_text}"
            )
        else:
            user_message = f"ANSWER THESE QUESTIONS:\n{questions_text}"

        full_prompt = f"{system_prompt}\n\n{user_message}"

        # log it
        logger.log(
            "question_answer_response() initiated",
            log_data={
                "num_questions": len(questions),
                "full_prompt": full_prompt,
                "model": model,
                "answer_type": answer_type,
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
                "num_questions": len(questions),
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


def register_presence_routes(app):
    """Register presence-related routes with the Flask app"""

    @app.route("/api/upload/audio", methods=["POST"])
    def upload_audio():
        """Upload audio recording segment, transcribe, flag, tag, and answer questions"""
        logger = ExecutionLogger()
        temp_file_path = None

        try:
            if "audio" not in request.files:
                return jsonify({"error": "No audio file provided"}), 400

            audio_file = request.files["audio"]
            user_id = request.form.get("user_id")
            segment_no = request.form.get("segment_no")
            session_animal = request.form.get("sessionAnimal")
            session_number = request.form.get("sessionNumber")
            answer_type = request.form.get("answer_type", "detailed")

            if not user_id:
                return jsonify({"error": "user_id is required"}), 400
            if not segment_no:
                return jsonify({"error": "segment_no is required"}), 400
            if not session_animal:
                return jsonify({"error": "sessionAnimal is required"}), 400
            if not session_number:
                return jsonify({"error": "sessionNumber is required"}), 400
            if answer_type not in ["concise", "detailed", "poetic"]:
                return jsonify(
                    {
                        "error": "Invalid answer_type. Must be 'concise', 'detailed', or 'poetic'."
                    }
                ), 400

            logger.log(
                "Audio upload received",
                log_data={
                    "user_id": user_id,
                    "segment_no": segment_no,
                    "filename": audio_file.filename,
                    "answer_type": answer_type,
                },
            )

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
                    "Transcription failed",
                    log_type="ERROR",
                    log_data=transcription_result,
                )
                return jsonify(
                    {
                        "error": "Transcription failed",
                        "details": transcription_result.get("error"),
                    }
                ), 500

            transcript_text = transcription_result.get("text", "")

            logger.log(
                "Transcription successful",
                log_data={
                    "segment_no": segment_no,
                    "transcript_length": len(transcript_text),
                    "transcript": transcript_text,
                },
            )

            # Store in memory for future context lookups
            _store_transcript(user_id, int(segment_no), transcript_text)

            flag_result = None
            try:
                segments = [
                    {"segment_no": int(segment_no), "transcript": transcript_text}
                ]
                flag_result = flag_transcript_with_llm(
                    segments=segments, user_id=user_id
                )
                logger.log(
                    "Flagging complete",
                    log_data={
                        "flags_found": flag_result.get("metadata", {}).get(
                            "success", False
                        )
                        if flag_result
                        else False
                    },
                )
            except Exception as e:
                logger.log(
                    "Flagging failed (non-fatal)", log_type="WARNING", log_data=str(e)
                )
                flag_result = {"error": str(e)}

            tag_result = None
            try:
                segments = [
                    {"segment_no": int(segment_no), "transcript": transcript_text}
                ]
                tag_result = tag_transcript_with_llm(segments=segments, user_id=user_id)
                logger.log(
                    "Tagging complete",
                    log_data={
                        "tags_found": tag_result.get("metadata", {}).get("tag_count", 0)
                        if tag_result
                        else 0
                    },
                )
            except Exception as e:
                logger.log(
                    "Tagging failed (non-fatal)", log_type="WARNING", log_data=str(e)
                )
                tag_result = {"error": str(e)}

            question_answers = None
            try:
                questions = (
                    flag_result.get("metadata", {}).get("questions", [])
                    if flag_result
                    else []
                )
                if questions:
                    recent_transcripts = get_recent_transcripts(
                        user_id, limit=3, exclude_segment=int(segment_no)
                    )
                    context_parts = []
                    for t in reversed(recent_transcripts):
                        context_parts.append(
                            f"[Segment {t.get('segment_no', '?')}] {t.get('transcript', '')}"
                        )
                    context_parts.append(f"[Segment {segment_no}] {transcript_text}")
                    combined_context = "\n\n".join(context_parts)

                    logger.log(
                        "Q&A context prepared",
                        log_data={
                            "questions": questions,
                            "recent_segments": len(recent_transcripts),
                            "context_chars": len(combined_context),
                        },
                    )

                    question_answers = question_answer_response(
                        questions=questions,
                        context=combined_context,
                        answer_type=answer_type,
                    )
                    logger.log(
                        "Question answering complete",
                        log_data={
                            "success": question_answers.get("success", False),
                        },
                    )
                else:
                    logger.log("No questions flagged, skipping Q&A")
            except Exception as e:
                logger.log(
                    "Question answering failed (non-fatal)",
                    log_type="WARNING",
                    log_data=str(e),
                )
                question_answers = {"error": str(e)}

            return jsonify(
                {
                    "status": "success",
                    "message": "Audio uploaded and transcribed successfully",
                    "user_id": user_id,
                    "segment_no": segment_no,
                    "size_bytes": file_size,
                    "transcript": transcript_text,
                    "flags": flag_result,
                    "tags": tag_result,
                    "question_answers": question_answers,
                    "ready": True,
                }
            )

        except Exception as e:
            logger.log("Audio upload failed", log_type="ERROR", log_data=str(e))
            return jsonify({"error": str(e)}), 500

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
            logger.commit()
