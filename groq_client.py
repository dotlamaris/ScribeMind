"""
Groq Cloud API Client Module
Handles all interactions with Groq Cloud's AI models
"""

import os
from typing import Optional, Dict, Any, List
from groq import Groq
from logger import ExecutionLogger


class GroqClient:
    """Client for interacting with Groq Cloud API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Groq client

        Args:
            api_key: Groq API key (if not provided, reads from GROQ_API_KEY env var)
        """
        api_key = api_key or os.getenv("GROQ_KEY_2")
        if not api_key:
            raise ValueError("Groq API key not provided. Set GROQ_API_KEY environment variable or pass api_key parameter.")

        self.client = Groq(api_key=api_key)
        self.retries = False  # Track if we've already retried

    def transcribe_audio(
        self,
        audio_file_path: str,
        model: str = "whisper-large-v3",
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Transcribe audio using Groq's Whisper models

        Args:
            audio_file_path: Path to audio file
            model: Model to use (whisper-large-v3, whisper-large-v3-turbo)
            language: Optional language code (e.g., 'en', 'es')
            prompt: Optional prompt to guide transcription
            temperature: Sampling temperature (0-1)

        Returns:
            Dict with transcription results
        """
        logger = ExecutionLogger()

        header_names = [
            "x-ratelimit-limit-requests",
            "x-ratelimit-remaining-requests",
            "x-ratelimit-reset-requests",
            "x-ratelimit-limit-audio-seconds",
            "x-ratelimit-remaining-audio-seconds",
            "x-ratelimit-reset-audio-seconds",
            "x-request-id",
            "request-id",
        ]

        try:
            with open(audio_file_path, 'rb') as audio_file:
                raw = self.client.audio.transcriptions.with_raw_response.create(
                    file=audio_file,
                    model=model,
                    temperature=temperature,
                    language=language,
                    prompt=prompt
                )
                transcription = raw.parse()

                result = transcription.model_dump()
                all_headers = dict(raw.headers)
                headers = {name: raw.headers[name] for name in header_names if name in raw.headers}

                logger.log("Audio transcription successful", log_data={
                    "model": model,
                    "text_length": len(result.get('text', '')),
                    "headers": headers,
                    "all_headers": all_headers
                }, truncate=False)

                return {
                    "success": True,
                    "text": result.get('text', ''),
                    "model": model,
                    "full_response": result,
                    "headers": headers
                }

        except Exception as e:
            logger.log("Audio transcription failed", log_type="ERROR", log_data=str(e))
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }

    def get_groq_error_data(self, error):
        """
        Extract error data from Groq API error object
        """
        logger = ExecutionLogger()
        error_data = {}
        try:
            # Try to extract error data from Groq API error object
            error_data = {
                "type": type(error),
                "message": error.__dict__.get('body', {}).get('error', {}).get('message', None),
                "error_code": error.__dict__.get('body', {}).get('error', {}).get('code', None),
                "details": error.__dict__.get('message', None)
            }
            logger.log("Extracted Groq error data", log_data={})
            return error_data
        # if it doesnt work then just return basic error data
        except Exception as e:
            error_data = {
                "error": str(e),
                "error_type": type(e),
                "original_error": str(error)
            }
            logger.log("Error extracting Groq error data", log_type="ERROR", log_data=error_data)
            logger.commit()
            return error_data
    
    def retry_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama-3.1-8b-instant",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        fallback_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retry chat completion with a different model if retries haven't been attempted yet
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (llama-3.1-8b-instant, mixtral-8x7b-32768, etc.)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream response

        Returns:
            Dict with completion results
        """
        logger = ExecutionLogger()

        try:
            
            if self.retries:
                logger.log("Retry already attempted, failing", log_type="ERROR", log_data= {})
                logger.commit()
                return {"success": False, "error": "Retry already attempted"}
            
            # Mark that we've attempted a retry
            self.retries = True
            
            # Use caller-supplied fallback if provided, else default lighter model
            if not fallback_model:
                fallback_model = "llama-3.1-8b-instant"
            logger.log("Retrying with fallback model", log_data={
                "original_model": model,
                "fallback_model": fallback_model
            })
            
            # Call chat_completion again with the fallback model
            return self.chat_completion(
                messages=messages,
                model=fallback_model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )

        except Exception as e:
            logger.log("Retry failed", log_type="ERROR", log_data=str(e))
        

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama-3.1-8b-instant",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        fallback_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate chat completion using Groq's LLM models

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (llama-3.1-8b-instant, llama-3.3-70b-versatile, etc.)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream response

        Returns:
            Dict with completion results
        """
        logger = ExecutionLogger()

        try:
            
            raw = self.client.chat.completions.with_raw_response.create(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            completion = raw.parse()

            result = completion.model_dump()

            header_names = [
                "x-ratelimit-limit-requests",
                "x-ratelimit-remaining-requests",
                "x-ratelimit-reset-requests",
                "x-ratelimit-limit-tokens",
                "x-ratelimit-remaining-tokens",
                "x-ratelimit-reset-tokens",
                "x-request-id",
                "request-id",
            ]
            headers = {name: raw.headers[name] for name in header_names if name in raw.headers}

            logger.log("Chat completion successful", log_data={
                "model": model,
                "message_count": len(messages),
                "full_response": result,
                "headers": headers,
            }, truncate=False)

            return {
                # "success": True,
                "content": result['choices'][0]['message']['content'],
                # "model": model,
                # "usage": result.get('usage', {}),
                "full_response": result,
                "headers": headers
            }

        except Exception as e:
            error_data = self.get_groq_error_data(e)
            error_code = error_data.get('error_code', None)
            
            # Check if we should retry
            if error_code in ['model_not_found', 'rate_limit_exceeded']:
                logger.log(f"Error: {error_code} - attempting retry", log_type="RETRY", log_data={"error_code": error_code, "error_data": error_data, "model": model, "messages": messages})
                logger.commit()
                
                
                return self.retry_chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    fallback_model=fallback_model
                )
            
            logger.log("Chat completion failed", log_type="ERROR", log_data=error_data)
            logger.commit()
            raise Exception(error_data)

    def list_models(self) -> Dict[str, Any]:
        """
        List available models from Groq

        Returns:
            Dict with available models
        """
        logger = ExecutionLogger()

        try:
            models = self.client.models.list()
            result = models.model_dump()

            logger.log("Models list retrieved", log_data={
                "model_count": len(result.get('data', []))
            })

            return {
                "success": True,
                "models": result.get('data', []),
                "full_response": result
            }

        except Exception as e:
            logger.log("List models failed", log_type="ERROR", log_data=str(e))
            return {
                "success": False,
                "error": str(e),
                "models": []
            }


# Convenience functions for quick use
def transcribe_audio(audio_file_path: str, **kwargs) -> str:
    """Quick transcription function - returns just the text"""
    client = GroqClient()
    result = client.transcribe_audio(audio_file_path, **kwargs)
    return result.get('text', '')


def chat(prompt: str, model: str = "llama-3.1-8b-instant", **kwargs) -> str:
    """Quick chat function - returns just the response text"""
    client = GroqClient()
    messages = [{"role": "user", "content": prompt}]
    result = client.chat_completion(messages, model=model, **kwargs)
    return result.get('content', '')


def main():
    """Test the Groq client functionality"""
    import sys

    print("=== Testing Groq Client Module ===\n")

    try:
        client = GroqClient()
        print("✅ Groq client initialized successfully\n")

        # Test 1: List available models
        print("Test 1: Listing available models...")
        models_result = client.list_models()
        if models_result['success']:
            print(f"✅ Found {len(models_result['models'])} models")
            print("Available models:")
            for model in models_result['models']:  # Show first 5
                print(f"  - {model.get('id', 'unknown')}")
        else:
            print(f"❌ Failed to list models: {models_result['error']}")

        print()

        # Test 2: Simple chat completion
        print("Test 2: Testing chat completion...")
        test_messages = [
            {"role": "user", "content": "Say 'Hello from Groq!' and nothing else."}
        ]
        chat_result = client.chat_completion(test_messages, max_tokens=50)
        if chat_result['success']:
            print(f"✅ Chat completion successful")
            print(f"Response: {chat_result['content']}")
            print(f"Tokens used: {chat_result.get('usage', {})}")
        else:
            print(f"❌ Chat completion failed: {chat_result['error']}")

        print()

        # Test 3: Convenience function
        print("Test 3: Testing convenience chat function...")
        quick_response = chat("What is 2+2? Answer with just the number.")
        print(f"Quick chat response: {quick_response}")

        print("\n=== All tests complete ===")

    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("\nTo use this module, set your GROQ_API_KEY environment variable:")
        print("  export GROQ_API_KEY='your-api-key-here'")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()