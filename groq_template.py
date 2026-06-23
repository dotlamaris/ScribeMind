"""
Examples of how to use the Groq Client module
"""

from groq_client import GroqClient, chat, transcribe_audio
from logger import ExecutionLogger
import json
import re


def example_1_simple_chat():
    """Simple one-shot chat completion"""
    print("=== Example 1: Simple Chat ===")

    # Using the convenience function
    response = chat("Explain what Groq Cloud is in one sentence.")
    print(f"Response: {response}\n")


def example_2_conversation():
    """Multi-turn conversation"""
    print("=== Example 2: Conversation ===")

    client = GroqClient()

    conversation = [
        {"role": "user", "content": "What's the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
        {"role": "user", "content": "What's the population?"}
    ]

    result = client.chat_completion(conversation)
    if result['success']:
        print(f"Assistant: {result['content']}\n")


def example_3_different_models():
    """Try different models"""
    print("=== Example 3: Different Models ===")

    prompt = "Count from 1 to 5."

    models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "groq/compound",
        "groq/compound-mini"
    ]

    for model in models:
        response = chat(prompt, model=model, max_tokens=50)
        print(f"{model}: {response[:100]}...")

    print()


def example_4_transcription():
    """Audio transcription (requires audio file)"""
    print("=== Example 4: Audio Transcription ===")

    # This would need an actual audio file
    # audio_file = "path/to/your/audio.mp3"
    # text = transcribe_audio(audio_file, model="whisper-large-v3")
    # print(f"Transcription: {text}")

    print("(Skipped - requires audio file)\n")


def example_5_system_prompt():
    """Using system prompts for behavior control"""
    print("=== Example 5: System Prompt ===")

    client = GroqClient()

    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that speaks like a pirate."
        },
        {
            "role": "user",
            "content": "Tell me about Python programming."
        }
    ]

    result = client.chat_completion(messages, max_tokens=100)
    if result['success']:
        print(f"Pirate assistant: {result['content']}\n")


def get_session_transcripts(session_id, user_id=None):
    """
    CORE PILLAR 1: Fetch all transcript segments for a session, ordered by segment_no

    Args:
        session_id: Session ID (e.g., "Stingray95")
        user_id: Optional user ID filter

    Returns:
        List of transcript segments with format:
        [
            {"segment_no": 1, "transcript": "...", "ssid": "Stingray95"},
            {"segment_no": 2, "transcript": "...", "ssid": "Stingray95"},
            ...
        ]
    """
    logger = ExecutionLogger()

    try:
        from database import SupabaseConnection

        logger.log("Fetching session transcripts", log_data={
            "session_id": session_id,
            "user_id": user_id
        })

        # Query transcripts table for this session, ordered by segment number
        client = SupabaseConnection.get_client()
        if not client:
            raise Exception("Failed to get Supabase client")
        query = client.table("transcripts").select(
            "segment_no, transcript, ssid, created_at"
        ).eq("ssid", session_id)

        # Apply user filter if provided
        # if not user_id:
        #     raise ValueError("user_id is required to fetch session transcripts")
        # query = query.eq("user_id", user_id)

        # Order by segment number ascending
        query = query.order("segment_no", desc=False)

        response = query.execute()
        segments = response.data

        logger.log("Session transcripts retrieved", log_data={
            "segment_count": len(segments),
            # "segments": segments  # Uncomment to log full segments
        })

        if not segments:
            logger.log("No transcripts found for session", log_type="WARNING", log_data={
                "session_id": session_id,
                "user_id": user_id,
                "response": response,
                "segments": segments
            })
            logger.commit()
            

        return segments

    except Exception as e:
        logger.log("Failed to fetch session transcripts", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"get_session_transcripts(): {e}")


def format_session_prompt(transcript_segments, user_context=None, existing_tags=None):
    """
    CORE PILLAR 2: Design and format the prompt for LLM annotation

    Args:
        transcript_segments: List of transcript dicts from get_session_transcripts()
        user_context: Optional context about the user/session
        existing_tags: List of existing tag names to choose from

    Returns:
        Dict with formatted messages for Groq API:
        {
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."}
            ],
            "metadata": {...}
        }
    """
    logger = ExecutionLogger()

    # logger.log("Formatting session prompt: segment data", log_data={
    #     "segments": transcript_segments
    # })

    try:
        # Build the full transcript with segment demarcation
        full_transcript = ""
        for segment in transcript_segments:
            seg_no = segment.get("segment_no", "?")
            text = segment.get("transcript", "")
            full_transcript += f"\n--- SEGMENT {seg_no} ---\n{text}\n"

        # Build existing tags list for context
        existing_tags_str = ""
        if existing_tags:
            # Format as comma-separated list
            existing_tags_str = f"\n\nEXISTING TAGS IN SYSTEM:\n{', '.join(existing_tags[:100])}"  # Limit to first 100 to avoid token overflow

        # System prompt for metadata extraction
        system_prompt = f"""You are an expert at analyzing spoken transcripts and extracting structured metadata.

CONTEXT: These are voice-dictated work sessions. Expect stream-of-consciousness flow, filler words, and topic shifts.

Your task is to analyze the session and generate:

1. TITLE (max 10 words)
   - Capture the PRIMARY outcome or activity
   - Focus on what was accomplished or explored, not just the topic
   - Examples: "Fixed authentication redirect bug" > "Working on authentication"

2. DESCRIPTION (2-3 sentences)
   - Key points: what was discussed, decided, or discovered
   - Outcomes: what was built, fixed, or learned
   - Context: any blockers, questions, or next steps mentioned

3. TAGS - USER-DEFINED TAGS TAKE PRIORITY

   **FIRST: Extract any EXPLICIT user-defined tags from the transcript:**
   - Look for phrases like:
     * "tag this as [name]"
     * "tag name: [name]" or "tag name [name]"
     * "label this [name]"
     * "categorize under [name]"
     * "add tag [name]"
   - Extract the exact tag name the user specified (normalize to lowercase with underscores)
   - For EACH user tag, provide a description explaining the context from the transcript
   - Format: [{{"tag": "user_tag_name", "description": "why user wanted this tag based on transcript"}}]
   - User-defined tags MUST be included in the final tag list

   **THEN: Select EXACTLY 1 contextual system tag:**
   - Choose from the existing tags list provided
   - Pick the tag that BEST matches the session's context
   - Generate a description that explains WHY this tag applies based on the transcript content
   - Description should capture the user's purpose/context for this session
   - Format: {{"tag": "tag_name", "description": "contextual explanation based on this session"}}

IMPORTANT: 
- User-defined tags are MANDATORY - never skip them
- BOTH user tags and system tag need contextual descriptions
- Only 1 system tag with contextual description
- All descriptions must be specific to THIS session's context{existing_tags_str}"""

        # User prompt with the actual transcript
        user_prompt = f"""Analyze this transcript session and extract metadata:

SESSION TRANSCRIPT:{full_transcript}

Please provide the metadata in this exact JSON format:
{{
    "title": "your title here",
    "description": "your description here",
    "user_tags": [
        {{"tag": "user_tag1", "description": "context from transcript why user wanted this tag"}},
        {{"tag": "user_tag2", "description": "context from transcript why user wanted this tag"}}
    ],
    "system_tag": {{
        "tag": "selected_existing_tag",
        "description": "contextual explanation of why this tag applies to this session"
    }},
    "tags": ["combined_all_tags_here"]
}}

IMPORTANT: 
- "user_tags" = array of objects with tag name and contextual description from the transcript
- "system_tag" = ONE tag selected from existing tags with contextual description
- "tags" = combined list of just the tag names (extract from user_tags + system_tag)
- If no user tags found, "user_tags" should be an empty array []
- If no existing tag fits, system_tag can be null"""

        if user_context:
            user_prompt = f"USER CONTEXT: {user_context}\n\n{user_prompt}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # logger.log("Session prompt formatted", log_data={
        #     "segment_count": len(transcript_segments),
        #     "transcript_length": len(full_transcript),
        #     "has_user_context": bool(user_context)
        # })

        return {
            "messages": messages,
        }

    except Exception as e:
        logger.log("Failed to format session prompt", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"format_session_prompt(): {e}")


def parse_ai_json_response(raw_ai_response):
    """
    Parse JSON from AI response, handling various formats (direct JSON, code blocks, embedded JSON)

    Args:
        raw_ai_response: Raw string response from AI model

    Returns:
        Dict with parsed JSON data

    Raises:
        Exception: If no valid JSON can be extracted
    """
    logger = ExecutionLogger()

    try:
        # First try direct JSON parsing
        return json.loads(raw_ai_response)
    except json.JSONDecodeError:
        # Fallback: extract JSON from markdown code blocks
        # Look for JSON inside ```json or ``` blocks - improved pattern
        code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(code_block_pattern, raw_ai_response, re.DOTALL)

        if matches:
            try:
                # Try to parse the first match
                parsed_json = json.loads(matches[0])
                logger.log("Extracted JSON from code block", log_data={"extracted": True})
                return parsed_json
            except json.JSONDecodeError:
                logger.log("Failed to parse extracted JSON from code block", log_type="WARNING", log_data=raw_ai_response)
                logger.commit()
                raise Exception(f"Failed to parse JSON from code block: {matches[0]}")
        else:
            # Try one more pattern - look for any JSON object in the response
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, raw_ai_response, re.DOTALL)

            largest_match = None
            if matches:
                try:
                    # Try to parse the largest match (likely to be the complete JSON)
                    largest_match = max(matches, key=len)
                    parsed_json = json.loads(largest_match)
                    logger.log("Extracted JSON from response body", log_data={"extracted": True})
                    return parsed_json
                except json.JSONDecodeError: 
                    logger.log("Failed to parse extracted JSON from body", log_type="WARNING", log_data=raw_ai_response)
                    logger.commit()
                    raise Exception(f"Failed to parse JSON: {largest_match}")
            else:
                logger.log("No JSON found in response", log_type="WARNING", log_data=raw_ai_response)
                logger.commit()
                raise Exception(f"No valid JSON found in response: {raw_ai_response}")


def annotate_session_with_llm(session_id, user_id=None, model="llama-3.1-8b-instant"):
    """
    CORE PILLAR 3: Complete workflow - fetch, format, and annotate session

    Args:
        session_id: Session ID (e.g., "Stingray95")
        user_id: Optional user ID
        model: Groq model to use for annotation

    Returns:
        Dict with extracted metadata and API response:
        {
            "success": bool,
            "metadata": {"title": "...", "description": "...", "tags": [...]},
            "session_info": {...},
            "api_response": {...}
        }
    """
    logger = ExecutionLogger()

    try:
        # Step 1: Get transcript segments
        segments = get_session_transcripts(session_id, user_id)

        if not segments:
            return {"success": False, "error": "No transcripts found for session"}

        # Step 1.5: Fetch existing tags for context
        from database import TagCache
        tag_cache = TagCache()
        tags_response = tag_cache.get_all_tags()

        logger.log("Fetched existing tags for session annotation", log_data={
            "existing_tags_count": len(tags_response.data) if tags_response and tags_response.data else ['error no tag response'],
            "existing_tags": tags_response.data if tags_response and tags_response.data else ['error no tag response'] # Uncomment to log full tags list
        })
        
        existing_tags = [tag['tag_name'] for tag in tags_response.data] if tags_response and tags_response.data else []

        # Step 2: Format the prompt with existing tags
        prompt_data = format_session_prompt(segments, existing_tags=existing_tags)

        logger.log("Session prompt formatted", log_data={
            "session_id": session_id,
            "segment_count": len(segments),
            "tag_count": len(existing_tags),
            "prompt_data": prompt_data  # Uncomment to log full prompt data
        })

        # Step 3: Call Groq API
        client = GroqClient()

        # Request JSON response format
        api_result = client.chat_completion(
            messages=prompt_data["messages"],
            model=model,
            temperature=0.3,  # Lower temperature for more consistent metadata
            max_tokens=500
        )

        if api_result.get('error'):
            logger.log("Session annotation API call failed", log_type="ERROR", log_data=api_result)
            return {"success": False, "error": "API call failed", "api_response": api_result}

        # Parse JSON response using the new helper function
        content = api_result["content"]
        metadata = parse_ai_json_response(content)

        logger.log("Session annotation parsing complete", log_data={
            "parsed_metadata": metadata,
        })

        # Ensure tags structure is complete
        if "user_tags" not in metadata:
            metadata["user_tags"] = []

        # Handle new system_tag structure (single tag with description)
        if "system_tag" not in metadata or metadata["system_tag"] is None:
            metadata["system_tag"] = {"tag": None, "description": None}

        # Build combined tags list
        if "tags" not in metadata:
            # Extract tag names from user_tags (which are now objects with tag + description)
            user_tag_names = []
            if isinstance(metadata["user_tags"], list):
                for item in metadata["user_tags"]:
                    if isinstance(item, dict):
                        user_tag_names.append(item.get("tag"))
                    elif isinstance(item, str):
                        # Fallback for old format (just strings)
                        user_tag_names.append(item)
            
            metadata["tags"] = user_tag_names.copy()
            if metadata["system_tag"] and metadata["system_tag"].get("tag"):
                metadata["tags"].append(metadata["system_tag"]["tag"])

        result = {
            "metadata": metadata,
            "segments": segments,
            "api_response": api_result
        }

        logger.log("Session annotation complete", log_data={
            "title": metadata.get("title"),
            "user_tags": metadata.get("user_tags"),
            "system_tag": metadata.get("system_tag"),
            "total_tags": len(metadata.get("tags", []))
        })
        return result

    except Exception as e:
        logger.log("Session annotation failed", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"annotate_session_with_llm(): {e}")


def audit_notes_list_structure(structured_data, logger):
    """
    Audits the structure of the 'notes_list' data for validity and safety.
    Logs warnings for any data integrity issues found but does not modify the data.

    Example structure to validate:
    {
      "notes_list": [
        {
          "title": "Brief title",
          "content": "The actual note content",
          "description": "Contextual explanation",
          "tags": ["tag1", "tag2"]
        }
      ]
    }
    """
    # Log all edge cases but don't modify the original data
    if "notes_list" not in structured_data:
        logger.log("No special notes found in response", log_type="WARNING", log_data=structured_data)
        return

    if not isinstance(structured_data.get("notes_list", []), list):
        logger.log("invalid structure: notes_list is not a list", log_type="WARNING", log_data=structured_data)
        return

    # Create a safe processing view - validate each note
    raw_notes = structured_data.get("notes_list", [])
    validated_notes = []

    if isinstance(raw_notes, list):
        for note in raw_notes:
            if not isinstance(note, dict):
                logger.log("Invalid special note entry - not a dict", log_type="WARNING", log_data=note)
                continue

            if not all(key in note for key in ["title", "content", "description", "tags"]):
                logger.log("Missing required fields in special note", log_type="WARNING", log_data={
                    "note": note,
                    "missing_fields": [k for k in ["title", "content", "description", "tags"] if k not in note]
                })
                continue

            if not isinstance(note.get("tags"), list):
                logger.log("Invalid tags field - not a list", log_type="WARNING", log_data=note)
                continue

            # This note passed all checks
            validated_notes.append(note)
    
    # Update structured_data with validated_notes for safer processing downstream
    # This is a design choice: returning a subset of data that is known to be safe.
    # If strict immutability is required, this part would need to be handled differently
    # (e.g., returning validated_notes separately or raising an error).

    # structured_data["notes_list"] = validated_notes


def annotate_special_notes(session_id, tags, segments=None, user_id=None, model="llama-3.1-8b-instant"):
    """
    CORE PILLAR 4: Extract special notes from a session using LLM.

    This function looks for 'special_note' tags and extracts detailed information
    about each special note mentioned in the transcript.

    Args:
        session_id: Session ID (e.g., "Stingray95")
        tags: List of tags from annotate_session_with_llm.
        segments: Optional pre-fetched transcript segments (avoids duplicate DB call)
        user_id: Optional user ID.
        model: Groq model to use for annotation.

    Returns:
        Dict containing the structured JSON output from the LLM.
        {
            "success": bool,
            "data": {"notes_list": [...]},
            "api_response": {...}
        }
    """
    logger = ExecutionLogger()

    try:
        logger.log("Starting annotation for special notes", log_data={
            "session_id": session_id,
            "tags": tags,
            "user_id": user_id,
            "segments_provided": segments is not None
        })

        # Check if special_note tag is present
        has_special_note = any(tag.lower().replace(" ", "_") == "special_note" for tag in tags)

        if not has_special_note:
            logger.log("No special_note flag found, skipping annotation", log_type="ERROR", log_data={"tags": tags})
            return {"success": False, "tags": tags}

        # Step 0.5: Fetch existing tags for context
        from database import TagCache
        tag_cache = TagCache()
        tags_response = tag_cache.get_all_tags()

        logger.log("Fetched existing tags for special annotation", log_data={
            "existing_tags_count": len(tags_response.data) if tags_response and tags_response.data else ['error no tag response'],
            "existing_tags": tags_response.data if tags_response and tags_response.data else ['error no tag response'] # Uncomment to log full tags list
        })

        existing_tags = [tag['tag_name'] for tag in tags_response.data] if tags_response and tags_response.data else []

        # Step 1: Use provided segments or fetch from database
        if segments is None:
            segments = get_session_transcripts(session_id, user_id)
            if not segments:
                raise Exception(f"No transcripts found for session {session_id}")
        else:
            logger.log("Using provided segments data", log_data={
                "segment_count": len(segments)
            })

        # Combine transcript for context
        full_transcript = ""
        for segment in segments:
            seg_no = segment.get("segment_no", "?")
            text = segment.get("transcript", "")
            full_transcript += f"\n--- SEGMENT {seg_no} ---\n{text}\n"

        # Build existing tags context
        existing_tags_str = ""
        if existing_tags:
            # Limit to first 100 tags to avoid token overflow
            tags_list = existing_tags[:100]
            existing_tags_str = f"\n\nAVAILABLE TAGS IN SYSTEM:\n{', '.join(tags_list)}\n\nIMPORTANT: Only use tags from this list. Do not create new tags."

        # Build prompt for special notes extraction
        system_prompt = f"""You are an expert AI assistant designed to extract special notes from session transcripts. 

Special notes are explicit markers where the user says things like:
- "special note: [content]"
- "make a special note of this: [content]"
- "note this down as special: [content]"

Your task is to identify each special note and extract:
1. The exact content of the special note
2. A clear title (max 10 words)
3. Contextual description explaining why this was marked as special
4. Relevant tags - SELECT ONLY from the existing tags provided below{existing_tags_str}

Provide your output as a JSON object with this structure:
{{
  "notes_list": [
    {{
      "title": "Brief title",
      "content": "The actual special note content",
      "description": "Contextual explanation",
      "tags": ["existing_tag1", "existing_tag2"]
    }}
  ]
}}"""

        user_prompt = f"""Analyze this transcript and extract all special notes:

{full_transcript}

Return only the JSON object, no additional text."""

        logger.log("Interpreting query with LLM", log_data={
            "session_id": session_id,
            "tag_count": len(existing_tags) if existing_tags else 9999,
            "system_prompt": system_prompt, # Uncomment to log full prompts
            "user_prompt": user_prompt, # Uncomment to log full prompts
        })
        
        # Call Groq API
        client = GroqClient()
        api_result = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            temperature=0.3,
            max_tokens=1000
        )

        # Logging API response separately
        logger.log("special notes prompt API response", log_data=api_result)

        # Parse JSON response using the new helper function
        content = api_result["content"]
        structured_data = parse_ai_json_response(content)

        # Audit data structure (read-only validation)
        audit_notes_list_structure(structured_data, logger)

        # Count special notes found
        special_notes_count = len(structured_data.get("notes_list", []))

        result = {
            "special_notes_found": special_notes_count,
            "data": structured_data,
            # "api_response": api_result
        }

        logger.log("Special notes annotation complete", log_data={
            "special_notes_found": special_notes_count,
            "data": structured_data
        })


        return result

    except Exception as e:
        logger.log("Special notes annotation failed", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"annotate_special_notes(): {e}")



def annotate_transcript_with_llm(segments, user_id=None, model="llama-3.1-8b-instant", prompt_data=None, **kwargs):
    """
    Annotate a single transcript with LLM-generated metadata

    Args:
        segments: List of transcript segment dictionaries (can be single segment)
        user_id: Optional user ID
        model: Groq model to use for annotation
        prompt_data: Optional custom prompt data dict with 'messages' key. If None, auto-generates prompt.

    Returns:
        Dict with extracted metadata and API response:
        {
            "metadata": {"title": "...", "description": "...", "tags": [...]},
            "api_response": {...}
        }
    """
    # Capture all parameters
    parameters = locals().copy()
    
    # Initialize logger
    logger = ExecutionLogger()

    try:
        logger.log("annotate_transcript_with_llm() called", log_data=parameters)

        # Ensure segments is a list
        if not isinstance(segments, list):
            segments = [segments]

        if not segments:
            logger.log("No transcript segments provided", log_type="ERROR", log_data={})
            logger.commit()
            raise Exception("No transcript segments provided")

        response_structure = "flags" if prompt_data else "transcript"

        # Step 1 & 2: Use custom prompt_data if provided, otherwise auto-generate
        if prompt_data is None:
            # Fetch existing tags for context
            from database import TagCache
            tag_cache = TagCache()
            tags_response = tag_cache.get_all_tags()

            logger.log("Fetched existing tags for transcript annotation", log_data={
                "existing_tags_count": len(tags_response.data) if tags_response and tags_response.data else 0
            })

            existing_tags = [tag['tag_name'] for tag in tags_response.data] if tags_response and tags_response.data else []

            # Format the annotation prompt
            prompt_data = format_transcript_annotation_prompt(segments, existing_tags=existing_tags, **kwargs)
        
        else:
            logger.log("Using custom prompt_data provided by caller", log_data={
                "has_messages": 'messages' in prompt_data
            })

        logger.log("Transcript prompt formatted", log_data={
            "segment_count": len(segments)
        })

        # Step 3: Call Groq API
        client = GroqClient()

        api_result = client.chat_completion(
            messages=prompt_data["messages"],
            model=model,
            temperature=0.3,
            max_tokens=500
        )

        # Step 4: Parse JSON response
        content = api_result["content"]
        metadata = parse_ai_json_response(content)

        logger.log("Transcript annotation parsing complete. full api response", log_data={
            # "api_response": api_result,
            "content": content
        })

        # TODO: create a function to validate and clean up metadata structure based on a sample structure
        
        # Ensure tags structure is complete
        if "user_tags" not in metadata:
            metadata["user_tags"] = []

        if "system_tag" not in metadata or metadata["system_tag"] is None:
            metadata["system_tag"] = {"tag": None, "description": None}

        # Build combined tags list
        if "tags" not in metadata:
            user_tag_names = []
            if isinstance(metadata["user_tags"], list):
                for item in metadata["user_tags"]:
                    if isinstance(item, dict):
                        user_tag_names.append(item.get("tag"))
                    elif isinstance(item, str):
                        user_tag_names.append(item)

            metadata["tags"] = user_tag_names.copy()
            if metadata["system_tag"] and metadata["system_tag"].get("tag"):
                metadata["tags"].append(metadata["system_tag"]["tag"])

        result = {
            "metadata": metadata,
            "segments": segments,
            "api_response": api_result
        }

        logger.log("Transcript annotation complete", log_data={
            "title": metadata.get("title"),
            "user_tags": metadata.get("user_tags"),
            "system_tag": metadata.get("system_tag"),
            "total_tags": len(metadata.get("tags", [])),
        })

        return result

    except Exception as e:
        logger.log("annotate_transcript_with_llm failed", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"annotate_transcript_with_llm(): {e}")


def format_transcript_annotation_prompt(transcript_segments, user_context=None, existing_tags=None, enrich_transcript=False, **kwargs):
    """
    Format the prompt for annotating a single transcript

    Args:
        transcript_segments: List of transcript segment dictionaries
        user_context: Optional context about the user
        existing_tags: List of existing tag names to choose from

    Returns:
        Dict with formatted messages for Groq API
    """
    parameters = locals().copy()
    parameters.pop('kwargs', None)
    parameters.update(kwargs)
    logger = ExecutionLogger()
    logger.log("Formatting transcript annotation prompt", log_data=parameters)
    
    try:
        # Build the transcript text with segment demarcation
        full_transcript = ""
        for segment in transcript_segments:
            if isinstance(segment, dict):
                seg_no = segment.get("segment_no", "?")
                text = segment.get("transcript", "")
                full_transcript += f"\n--- SEGMENT {seg_no} ---\n{text}\n"
            else:
                full_transcript += f"\n{segment}\n"
                
        # Build existing tags context
        existing_tags_str = ""
        if existing_tags:
            tags_list = existing_tags[:100]
            existing_tags_str = f"\n\nEXISTING TAGS IN SYSTEM:\n{', '.join(tags_list)}"

        
        # TODO: add support for separate content field

        add_transcript_response = parameters.get('add_transcript_response', False)
        
        # Add optional transcript enrichment instructions
        enrichment_instructions = ''
        response_instructions = ''
        enrichment_format = ''
        response_format = ''

        if enrich_transcript:
            enrichment_instructions = """2.5 TRANSCRIPT ENRICHMENT AND REFINEMENT (Same length as original transcript)
            - Refine the transcript to improve readability and coherence
            - Remove filler words and repetitions
            - Correct any obvious errors or misunderstandings
            - Preserve the original meaning and context"""
            enrichment_format = """"transcript": "your refined transcript here","""

        if add_transcript_response:
            response_instructions = """2.5.5 Short Response (max 100 words)
            - Add a helpful response to the user based on the transcript"""
            response_format = """"response": "your response here","""

        # System prompt for metadata extraction
        system_prompt = f"""You are an expert at analyzing transcripts and extracting structured metadata.

CONTEXT: This is a voice-dictated transcript segment. Expect stream-of-consciousness flow and filler words.

Your task is to analyze the transcript and generate:

1. TITLE (max 10 words)
   - Capture the PRIMARY topic or activity
   - Focus on what was discussed or decided
   - Examples: "Database query optimization discussion" > "Working on code"

2. DESCRIPTION (2-3 sentences)
   - Key points: what was discussed or decided
   - Context: any important details mentioned

{enrichment_instructions}

{response_instructions}

3. TAGS - USER-DEFINED TAGS TAKE PRIORITY

   **FIRST: Extract any EXPLICIT user-defined tags from the transcript:**
   - Look for phrases like:
     * "tag this as [name]"
     * "tag name: [name]" or "tag name [name]"
     * "label this [name]"
     * "categorize under [name]"
     * "add tag [name]"
     * #[name]
     * tags: [name]
   - Extract the exact tag name the user specified (normalize to lowercase with underscores)
   - For EACH user tag, provide a description explaining the context from the transcript
   - Format: [{{"tag": "user_tag_name", "description": "why user wanted this tag based on transcript"}}]
   - User-defined tags MUST be included in the final tag list

   **THEN: Select EXACTLY 1 contextual system tag:**
   - Choose from the existing tags list provided
   - Pick the tag that BEST matches the transcript's context
   - Generate a description that explains WHY this tag applies based on the transcript content
   - Format: {{"tag": "tag_name", "description": "contextual explanation based on this transcript"}}

IMPORTANT: 
- User-defined tags are MANDATORY - never skip them
- BOTH user tags and system tag need contextual descriptions
- Only 1 system tag with contextual description
- All descriptions must be specific to THIS transcript's context{existing_tags_str}"""

        # User prompt with the actual transcript
        user_prompt = f"""Analyze this transcript and extract metadata:

TRANSCRIPT:{full_transcript}

Please provide the metadata in this exact JSON format:
{{
    "title": "your title here",
    "description": "your description here",
    {enrichment_format}
    {response_format}
    "user_tags": [
        {{"tag": "user_tag1", "description": "context from transcript why user wanted this tag"}},
        {{"tag": "user_tag2", "description": "context from transcript why user wanted this tag"}}
    ],
    "system_tag": {{
        "tag": "selected_existing_tag",
        "description": "contextual explanation of why this tag applies to this transcript"
    }},
    "tags": ["combined_all_tags_here"]
}}

IMPORTANT: 
- "user_tags" = array of objects with tag name and contextual description from the transcript
- "system_tag" = ONE tag selected from existing tags with contextual description
- "tags" = combined list of just the tag names (extract from user_tags + system_tag)
- If no user tags found, "user_tags" should be an empty array []
- If no existing tag fits, system_tag can be null"""

        if user_context:
            user_prompt = f"USER CONTEXT: {user_context}\n\n{user_prompt}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return {
            "messages": messages
        }

    except Exception as e:
        logger.log("Failed to format transcript annotation prompt", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"format_transcript_annotation_prompt(): {e}")


def format_transcript_flagging_prompt(transcript_segments, user_context=None, existing_tags=None, flag_types=None, **kwargs):
    """
    Format the prompt for flagging/marking specific items in a transcript.
    Useful for extracting action items, questions, decisions, special notes, etc.

    Args:
        transcript_segments: List of transcript segment dictionaries
        user_context: Optional context about the user
        existing_tags: List of existing tag names to choose from
        flag_types: List of flag types to extract (e.g., ["action_item", "question", "decision", "special_note"])
                   If None, defaults to common flag types

    Returns:
        Dict with formatted messages for Groq API
    """
    parameters = locals().copy()
    parameters.pop('kwargs', None)
    parameters.update(kwargs)
    logger = ExecutionLogger()
    logger.log("Formatting transcript flagging prompt", log_data=parameters)

    try:
        # Default flag types if not specified - questions, special_notes, and search flags
        if flag_types is None:
            flag_types = ["question", "special_note", "search"]

        # Build the transcript text with segment demarcation
        full_transcript = ""
        for segment in transcript_segments:
            if isinstance(segment, dict):
                seg_no = segment.get("segment_no", "?")
                text = segment.get("transcript", "")
                full_transcript += f"\n--- SEGMENT {seg_no} ---\n{text}\n"
            else:
                full_transcript += f"\n{segment}\n"

        # Build existing tags context
        existing_tags_str = ""
        if existing_tags:
            tags_list = existing_tags[:100]
            existing_tags_str = f"\n\nEXISTING TAGS IN SYSTEM:\n{', '.join(tags_list)}"

        # Build flag types description
        flag_types_str = ", ".join([f'"{ft}"' for ft in flag_types])

        # System prompt for flag extraction
        system_prompt = f"""You are an expert at analyzing transcripts and extracting flagged items.

CONTEXT: This is a voice-dictated transcript segment. Look for explicit and implicit flags.

FLAG TYPES TO EXTRACT: {flag_types_str}

Your task is to identify and extract flags from the transcript:

1. EXPLICIT FLAGS - User directly mentions the word 'flag' plus:
   - "question: [content]"
   - "special note: [content]"
   - Or similar phrasing

2. SEARCH FLAGS - Detect if user specifies their question is for the internet, OR if the question/topic:
   - Requires current/up-to-date information (news, weather, events, prices, stock data)
   - Is about recent developments or breaking news
   - Needs real-time information lookup
   - User explicitly says "search for", "look up", "find out", "what's new about", etc.

For each flag found, extract:
- flag_type: Type of flag from the list above (question, special_note, or search)
- content: The actual content/text of the flagged item
- context: Brief explanation of why this was flagged
- segment_no: Which segment it appeared in

IMPORTANT:
- Only extract flags that are clearly present in the transcript
- Be precise with the content extraction
- Provide helpful context for each flag
- Search flags should focus on internet/current info queries{existing_tags_str}"""

        # User prompt with the actual transcript
        user_prompt = f"""Analyze this transcript and extract all flags:

TRANSCRIPT:{full_transcript}

Please provide the flags in this exact JSON format:
{{
    "flags": [
        {{
            "flag_type": "question|special_note|search",
            "content": "the actual flagged content",
            "context": "why this was flagged and its relevance",
            "segment_no": segment_number
        }}
    ]
}}

IMPORTANT:
- Return empty "flags" array if no flags found
- Only include flag_types that were actually found (question, special_note, or search)
- Be specific and accurate with content extraction
- Search flags: user asking to look something up on internet or needs current info"""

        if user_context:
            user_prompt = f"USER CONTEXT: {user_context}\n\n{user_prompt}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        total_chars = len(system_prompt) + len(user_prompt)
        logger.log("Transcript flagging prompt built", log_data={
            "flag_types": flag_types,
            "segment_count": len(transcript_segments),
            "has_existing_tags": bool(existing_tags),
            "has_user_context": bool(user_context),
            "system_prompt_chars": len(system_prompt),
            "user_prompt_chars": len(user_prompt),
            "total_chars": total_chars,
            "approx_input_tokens": total_chars // 4,
            "messages": messages,
        }, truncate=False)
        logger.commit()

        return {
            "messages": messages
        }

    except Exception as e:
        logger.log("Failed to format transcript flagging prompt", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"format_transcript_flagging_prompt(): {e}")


def flag_transcript_with_llm(segments, user_id=None, model="llama-3.1-8b-instant", user_context=None, existing_tags=None, flag_types=None, **kwargs):
    """
    Standalone function to flag a transcript by identifying action items, questions, decisions, etc.
    
    Unlike annotate_transcript_with_llm, this function parses the response expecting the flags structure:
    { "flags": [{ "flag_type": "...", "content": "...", "context": "...", "segment_no": N, "tags": [...] }] }

    """
    logger = ExecutionLogger()
    
    try:
        # Ensure segments is a list
        if not isinstance(segments, list):
            segments = [segments]
            
        if not segments:
            logger.log("No transcript segments provided for flagging", log_type="ERROR")
            logger.commit()
            raise Exception("No transcript segments provided")
        
        # Generate the flagging prompt from the transcript
        prompt_data = format_transcript_flagging_prompt(
            transcript_segments=segments,
            user_context=user_context,
            existing_tags=existing_tags,
            flag_types=flag_types,
            **kwargs
        )
        
        total_chars = sum(len(m.get("content", "")) for m in prompt_data["messages"])
        logger.log("Flagging prompt generated", log_data={
            "segment_count": len(segments),
            "flag_types": flag_types,
            "model": model,
            "total_chars": total_chars,
            "approx_input_tokens": total_chars // 4,
            "messages": prompt_data["messages"],
        }, truncate=False)
        
        # Call Groq API directly
        client = GroqClient()
        
        api_result = client.chat_completion(
            messages=prompt_data["messages"],
            model=model,
            temperature=0.3,
            max_tokens=1000
        )
        
        # Parse the JSON response
        content = api_result["content"]
        parsed_response = parse_ai_json_response(content)
        
        logger.log("Flag response parsed", log_data={
            "raw_content": content if content else None,
            "parsed_response": parsed_response
        })
        
        # Extract flags from parsed response - handle the flag structure
        flags = parsed_response.get("flags", [])
        if not isinstance(flags, list):
            flags = []
        
        # Organize flags by type for easy access - questions, special_notes, and search
        questions = []
        special_notes = []
        search_queries = []
        
        for flag in flags:
            flag_type = flag.get("flag_type", "").lower().replace(" ", "_")
            flag_content = flag.get("content", "")
            
            if flag_type == "question":
                questions.append(flag_content)
            elif flag_type == "special_note":
                special_notes.append(flag_content)
            elif flag_type == "search":
                search_queries.append(flag_content)
        
        # Build metadata with organized flags
        metadata = {
            "flags": flags,
            "questions": questions,
            "special_notes": special_notes,
            "search_queries": search_queries,
            "success": True,
            "flag_count": len(flags)
        }
        
        result = {
            "metadata": metadata,
            "segments": segments,
            "api_response": api_result
        }
        
        logger.log("Transcript flagging completed", log_data={
            "flag_count": len(flags),
            "questions": len(questions),
            "special_notes": len(special_notes),
            "search_queries": len(search_queries),
            "user_id": user_id
        })
        
        return result
        
    except Exception as e:
        logger.log("flag_transcript_with_llm failed", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"flag_transcript_with_llm(): {e}")


def format_transcript_tagging_prompt(transcript_segments, user_context=None, existing_tags=None, **kwargs):
    """
    Format the prompt for tagging a transcript - extracts ONLY user-defined tags and system tags.
    Unlike format_transcript_annotation_prompt, this does NOT extract title or description.

    Args:
        transcript_segments: List of transcript segment dictionaries
        user_context: Optional context about the user
        existing_tags: List of existing tag names to choose from

    Returns:
        Dict with formatted messages for Groq API
    """
    parameters = locals().copy()
    parameters.pop('kwargs', None)
    parameters.update(kwargs)
    logger = ExecutionLogger()
    logger.log("Formatting transcript tagging prompt", log_data=parameters)

    try:
        # Build the transcript text with segment demarcation
        full_transcript = ""
        for segment in transcript_segments:
            if isinstance(segment, dict):
                seg_no = segment.get("segment_no", "?")
                text = segment.get("transcript", "")
                full_transcript += f"\n--- SEGMENT {seg_no} ---\n{text}\n"
            else:
                full_transcript += f"\n{segment}\n"

        # Build existing tags context
        existing_tags_str = ""
        if existing_tags:
            tags_list = existing_tags[:100]
            existing_tags_str = f"\n\nEXISTING TAGS IN SYSTEM:\n{', '.join(tags_list)}"

        # System prompt for tagging extraction
        system_prompt = f"""You are an expert at analyzing transcripts and extracting tags.

CONTEXT: This is a voice-dictated transcript segment. Expect stream-of-consciousness flow and filler words.

Your task is to analyze the transcript and extract ONLY tags (user-defined and system tags):

1. USER-DEFINED TAGS - Extract any EXPLICIT user-defined tags from the transcript:
   - Look for phrases like:
     * "tag this as [name]"
     * "tag name: [name]" or "tag name [name]"
     * "label this [name]"
     * "categorize under [name]"
     * "add tag [name]"
     * #[name]
     * tags: [name]
   - Extract the exact tag name the user specified (normalize to lowercase with underscores)
   - For EACH user tag, provide a description explaining the context from the transcript
   - Format: [{{"tag": "user_tag_name", "description": "why user wanted this tag based on transcript"}}]

2. SYSTEM TAG - Select EXACTLY 1 contextual system tag:
   - Choose from the existing tags list provided
   - Pick the tag that BEST matches the transcript's context
   - Generate a description that explains WHY this tag applies based on the transcript content
   - Format: {{"tag": "tag_name", "description": "contextual explanation based on this transcript"}}

IMPORTANT:
- User-defined tags are MANDATORY - never skip them
- BOTH user tags and system tag need contextual descriptions
- Only 1 system tag with contextual description
- All descriptions must be specific to THIS transcript's context{existing_tags_str}"""

        # User prompt with the actual transcript
        user_prompt = f"""Analyze this transcript and extract tags:

TRANSCRIPT:{full_transcript}

Please provide the tags in this exact JSON format:
{{
    "user_tags": [
        {{"tag": "user_tag1", "description": "context from transcript why user wanted this tag"}},
        {{"tag": "user_tag2", "description": "context from transcript why user wanted this tag"}}
    ],
    "system_tag": {{
        "tag": "selected_existing_tag",
        "description": "contextual explanation of why this tag applies to this transcript"
    }},
    "tags": ["combined_all_tags_here"]
}}

IMPORTANT:
- "user_tags" = array of objects with tag name and contextual description from the transcript
- "system_tag" = ONE tag selected from existing tags with contextual description
- "tags" = combined list of just the tag names (extract from user_tags + system_tag)
- If no user tags found, "user_tags" should be an empty array []
- If no existing tag fits, system_tag can be null"""

        if user_context:
            user_prompt = f"USER CONTEXT: {user_context}\n\n{user_prompt}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return {
            "messages": messages
        }

    except Exception as e:
        logger.log("Failed to format transcript tagging prompt", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"format_transcript_tagging_prompt(): {e}")


def tag_transcript_with_llm(segments, user_id=None, model="llama-3.1-8b-instant", user_context=None, existing_tags=None, **kwargs):
    """
    Standalone function to tag a transcript according to the user's specifications and existing tags.
    Extracts ONLY user-defined tags and system tags (no title or description).

    Args:
        segments: List of transcript segment dictionaries (can be single segment)
        user_id: Optional user ID
        model: Groq model to use for tagging
        user_context: Optional context about the user
        existing_tags: List of existing tag names to choose from

    Returns:
        Dict with extracted tags:
        {
            "metadata": {"user_tags": [...], "system_tag": {...}, "tags": [...]},
            "segments": segments,
            "api_response": {...}
        }
    """
    logger = ExecutionLogger()

    try:
        # Ensure segments is a list
        if not isinstance(segments, list):
            segments = [segments]

        if not segments:
            logger.log("No transcript segments provided for tagging", log_type="ERROR")
            logger.commit()
            raise Exception("No transcript segments provided")

        # Fetch existing tags if not provided
        if existing_tags is None:
            from database import TagCache
            tag_cache = TagCache()
            tags_response = tag_cache.get_all_tags()
            existing_tags = [tag['tag_name'] for tag in tags_response.data] if tags_response and tags_response.data else []

        # Generate the tagging prompt from the transcript
        prompt_data = format_transcript_tagging_prompt(
            transcript_segments=segments,
            user_context=user_context,
            existing_tags=existing_tags,
            **kwargs
        )

        logger.log("Tagging prompt generated", log_data={
            "segment_count": len(segments),
            "number_of_existing_tags": len(existing_tags) if existing_tags else 0
        })

        # Call Groq API directly
        client = GroqClient()

        api_result = client.chat_completion(
            messages=prompt_data["messages"],
            model=model,
            temperature=0.3,
            max_tokens=1000
        )

        # Parse the JSON response
        content = api_result["content"]
        parsed_response = parse_ai_json_response(content)

        logger.log("Tag response parsed", log_data={
            "raw_content": content[:500] if content else None
        })

        # Extract tags from parsed response
        user_tags = parsed_response.get("user_tags", [])
        if not isinstance(user_tags, list):
            user_tags = []

        system_tag = parsed_response.get("system_tag", None)
        if system_tag and not isinstance(system_tag, dict):
            system_tag = None

        tags = parsed_response.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        # Build metadata with organized tags
        metadata = {
            "user_tags": user_tags,
            "system_tag": system_tag,
            "tags": tags,
            "success": True,
            "tag_count": len(tags)
        }

        result = {
            "metadata": metadata,
            "segments": segments,
            "api_response": api_result
        }

        logger.log("Transcript tagging completed", log_data={
            "tag_count": len(tags),
            "user_tag_count": len(user_tags),
            "has_system_tag": system_tag is not None,
            "user_id": user_id
        })

        return result

    except Exception as e:
        logger.log("tag_transcript_with_llm failed", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"tag_transcript_with_llm(): {e}")
        

def validate_and_execute_search(suggested_flags):
    """
    Validate LLM-suggested flags and execute search

    Args:
        suggested_flags: Dict from suggest_query_flags() containing search parameters

    Returns:
        List of notes matching the search criteria
    """
    logger = ExecutionLogger()

    try:
        # Type check and normalize tags
        tags = suggested_flags.get('tags', [])
        if not isinstance(tags, list):
            tags = [tags] if tags else []

        # Normalize tag names to lowercase and strip whitespace and replace spaces with underscores
        tags = [tag.lower().strip().replace(" ", "_") for tag in tags]

        # Type check booleans with defaults
        created_after = bool(suggested_flags.get('created_after', False))
        created_before = bool(suggested_flags.get('created_before', False))
        match_all_tags = bool(suggested_flags.get('match_all_tags', False))
        content = bool(suggested_flags.get('content', False))

        # Type check integers with defaults
        days_back = int(suggested_flags.get('days_back', 7))
        limit = int(suggested_flags.get('limit', 100))

        # TODO: add exclude tags flag and functionality
        # TODO: add get_all_notes flag and functionality
        logger.log("Executing search with validated flags", log_data={
            "tags": tags,
            "created_after": created_after,
            "created_before": created_before,
            "match_all_tags": match_all_tags,
            "content": content,
            "days_back": days_back,
            "limit": limit
        })

        # Choose search function based on match_all_tags flag
        if match_all_tags:
            from database import get_notes_by_tag_names_intersection

            response = get_notes_by_tag_names_intersection(
                list_of_tag_names=tags,
                created_after=created_after,
                created_before=created_before,
                days_back=days_back,
                limit=limit,
                content=content
            )
            
            # Extract data
            results = response.get('notes', []) if response else []
            result_tags = response.get('tags', []) if response else []

            # Get comprehensive tag information for resulting tags
            comprehensive_tags = []
            if result_tags:
                from database import TagCache
                tag_response = TagCache.get_all_tags(tag_names=result_tags)
                if tag_response and tag_response.data:
                    comprehensive_tags = tag_response.data

            logger.log("Intersection search executed successfully", log_data= {
                "result_count": len(results),
                "results": results,  # Uncomment to log full results
                "resulting_tags": result_tags,
                "comprehensive_tags": comprehensive_tags
            })
            return {
                "resulting_notes": results,
                "resulting_tags": comprehensive_tags
            }
            
        else:
            from database import get_notes_by_tag_names

            response = get_notes_by_tag_names(
                list_of_tag_names=tags,
                created_after=created_after,
                created_before=created_before,
                days_back=days_back,
                limit=limit,
                content=content
            )
            
            # Extract data from Supabase response object
            results = response.get('notes', []) if response else []
            result_tags = response.get('tags', []) if response else []

            # Get comprehensive tag information for resulting tags
            comprehensive_tags = []
            if result_tags:
                from database import TagCache
                tag_response = TagCache.get_all_tags(tag_names=result_tags)
                if tag_response and tag_response.data:
                    comprehensive_tags = tag_response.data

            logger.log("Intersection search executed successfully", log_data= {
                "result_count": len(results),
                "resulting_notes": results,  # Uncomment to log full results
                "resulting_tags": result_tags,
                "comprehensive_tags": comprehensive_tags
            })
            
            return {
                "resulting_notes": results,
                "resulting_tags": comprehensive_tags
            }

    except Exception as e:
        logger.log("Search execution failed", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"validate_and_execute_search(): {e}")


# Flag definitions for LLM prompt
QUERY_FLAGS_DEFINITION = """
AVAILABLE QUERY FLAGS:

1. "tags" (list of strings)
   - Tag names to search for in notes
   - Example: ["devlog", "meeting", "project_alpha"]
   - Can be empty list [] if no specific tags needed

2. "days_back" (integer)
   - Number of days to look back from today
   - Calculates a timestamp X days in the past
   - Used with created_after and/or created_before flags
   - Example: 7 (last week), 30 (last month), 365 (last year)
   - Default: 7 if not specified

3. "created_after" (boolean)
   - If true, only return notes created AFTER the days_back date (GTE comparison)
   - Example: days_back=7, created_after=true -> notes from last 7 days
   - Example: false (default, no lower date bound)

4. "created_before" (boolean)
   - If true, only return notes created BEFORE the days_back date (LTE comparison)
   - Example: days_back=30, created_before=true -> notes older than 30 days
   - Example: false (default, no upper date bound)

5. "match_any_tags" (boolean)
   - If true, return notes that have ANY of the specified tags (OR logic)
   - This is the default search mode
   - Example: true (find notes with "devlog" OR "meeting")

6. "match_all_tags" (boolean)
   - If true, return notes that have ALL of the specified tags (AND logic)
   - Overrides match_any_tags if both are true
   - Example: true (find notes with "devlog" AND "meeting")


EXAMPLE QUERIES AND FLAGS:

Query: "Show me my recent meeting notes"
Flags: {
  "tags": ["meeting"],
  "days_back": 7,
  "created_after": true,
  "match_any_tags": true
}

Query: "Find notes older than 30 days"
Flags: {
  "tags": [],
  "days_back": 30,
  "created_before": true
}

Query: "Get notes tagged with both devlog and bug from last week"
Flags: {
  "tags": ["devlog", "bug"],
  "days_back": 7,
  "created_after": true,
  "match_all_tags": true
}

Query: "What did I work on in the past year?"
Flags: {
  "tags": [],
  "days_back": 365,
  "created_after": true
}
"""

# TODO: add exclude tags flag and functionality
# TODO: add get_all_notes flag and functionality
# TODO: SEPARATE LLM CALLS FOR TAG SUGGESTION (tag data is getting more complex, and flag options are increasing as well)
def suggest_query_flags(query_string, model="llama-3.1-8b-instant"):
    """
    Use LLM to interpret a natural language query and suggest search flags

    Args:
        query_string: Natural language query from user (e.g. "Show me recent meeting notes")
        existing_tags: Optional list of available tag names to choose from
        model: Groq model to use for interpretation

    Returns:
        Dict with suggested flags:
        {
            "tags": [],
            "created_after": bool,
            "created_before": bool,
            "days_back": int,
            "match_any_tags": bool,
            "match_all_tags": bool
        }
    """
    logger = ExecutionLogger()

    try:
        # Step 1: Fetch existing tags for context
        from database import TagCache
        tag_cache = TagCache()
        tags_response = tag_cache.get_all_tags()
        
        logger.log("Fetched existing tags for query suggestion", log_data={
            "tags_count": len(tags_response.data) if tags_response and tags_response.data else ['error no tag response'],
            "existing_tags": tags_response.data if tags_response and tags_response.data else ['error no tag response'] # Uncomment to log full tags list
        })

        
        existing_tags = [tag['tag_name'] for tag in tags_response.data] if tags_response and tags_response.data else []



        # Build existing tags context
        tags_context = ""
        if existing_tags:
            # Limit to first 100 tags to avoid token overflow
            tags_list = existing_tags[:100]
            tags_context = f"\n\nAVAILABLE TAGS IN SYSTEM:\n{', '.join(tags_list)}\n\nOnly suggest tags from this list."

        # Build the prompt
        system_prompt = f"""You are an expert at interpreting natural language queries and converting them into structured search parameters.

{QUERY_FLAGS_DEFINITION}{tags_context}

Your task is to analyze the user's query and suggest the appropriate flags to use for searching their notes.

IMPORTANT:
- Return ONLY valid JSON, no markdown formatting or code blocks
- All flags are optional - only include ones relevant to the query
- Be intelligent about inferring intent (e.g. "recent" usually means last 7 days)
- If no specific tags are mentioned, use an empty tags array []
- Only suggest tags that exist in the AVAILABLE TAGS list above
"""

        user_prompt = f"""Analyze this query and suggest appropriate search flags:

Query: "{query_string}"

Respond with ONLY a JSON object containing the suggested flags. No explanation, no markdown, just the JSON."""

        logger.log("Interpreting query with LLM", log_data={
            "query": query_string,
            "tag_count": len(existing_tags) if existing_tags else 9999,
            "system_prompt": system_prompt, # Uncomment to log full prompts
            "user_prompt": user_prompt, # Uncomment to log full prompts
        })
        
        # Call Groq API
        client = GroqClient()
        api_result = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            temperature=0.3,
            max_tokens=300
        )

        # Parse JSON response using the new helper function
        content = api_result["content"]
        flags_data = parse_ai_json_response(content)

        logger.log("Query interpretation complete", log_data={
            "input_query": query_string,
            "suggested_flags": flags_data
        })

        return flags_data

    except Exception as e:
        logger.log("Query interpretation failed", log_type="ERROR", log_data=str(e))
        logger.commit()
        raise Exception(f"suggest_query_flags(): {e}")



if __name__ == '__main__':
    print("Groq Client Usage Examples\n")

    # example_1_simple_chat()
    # example_2_conversation()
    # example_3_different_models()
    # example_4_transcription()
    # example_5_system_prompt()

    # Test the new transcript session annotation
    # try:
    #     # Replace with a valid session_id and user_id from your database for testing
    #     test_session_id = "YOUR_SESSION_ID" 
    #     test_user_id = 1 # Or None, depending on your data
    #     
    #     if test_session_id != "YOUR_SESSION_ID":
    #         print(f"\n=== Testing Full Session Annotation for Session ID: {test_session_id} ===")
    #         result = trigger_session_annotation(test_session_id, user_id=test_user_id)
    #         print(json.dumps(result, indent=2))
    #     else:
    #         print("\nSkipping full session annotation test: Please replace 'YOUR_SESSION_ID' with a valid ID.")
    #         
    # except Exception as e:
    #     print(f"\nError during full session annotation test: {e}")

    # Example: Test suggest_query_flags with existing tags
    # try:
    #     print("\n=== Testing Query Flag Suggestion ===")
    #     # Ensure TagCache is set up and accessible if running this example
    #     from database import TagCache
    #     tag_cache = TagCache()
    #     tags_response = tag_cache.get_all_tags()
    #     existing_tags = [tag['tag_name'] for tag in tags_response.data] if tags_response and tags_response.data else []
    #     
    #     test_query = "Find my recent devlogs about project alpha"
    #     print(f"Query: '{test_query}'")
    #     result = suggest_query_flags(
    #         test_query,
    #         existing_tags=existing_tags
    #     )
    #     print("Suggested Flags:")
    #     print(json.dumps(result, indent=2))
    # 
    #     # Example of executing search based on suggested flags
    #     if result:
    #         print("\nExecuting search with suggested flags...")
    #         search_results = validate_and_execute_search(result)
    #         print(f"Found {len(search_results)} notes.")
    #         # print(json.dumps(search_results, indent=2)) # Uncomment to see results
    # 
    # except Exception as e:
    #     print(f"\nError during query flag suggestion test: {e}")


    print("All examples complete!")