from typing import Dict, Optional, List, TypeVar, Callable
import anthropic
from loguru import logger
import asyncio
import functools

from env import get_settings

T = TypeVar("T")


def retry_on_overload(max_retries: int = 3, initial_delay: float = 1.0):
    """
    Decorator that retries the function on Anthropic API overload errors with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds between retries (doubles with each retry)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except anthropic.APIError as e:
                    if "overloaded_error" in str(e).lower() or "529" in str(e):
                        if attempt < max_retries:
                            logger.warning(
                                f"Anthropic API overloaded (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay}s..."
                            )
                            await asyncio.sleep(delay)
                            delay *= 2  # Exponential backoff
                            last_exception = e
                            continue
                    raise
                except Exception:
                    raise

            raise last_exception

        return wrapper

    return decorator


class ClaudeClient:
    def __init__(self):
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-3-opus-20240229"  # Latest model as of March 2024
        self.max_tokens = 4096

    @retry_on_overload()
    async def send_message(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Send a message to Claude and get a response.

        Args:
            prompt: The user's message/prompt
            system: Optional system prompt to set context/behavior
            temperature: Controls randomness (0.0-1.0, lower is more deterministic)
            max_tokens: Maximum number of tokens to generate

        Returns:
            Dict containing the response and metadata
        """
        try:
            params = {
                "model": self.model,
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                params["system"] = system

            message = self.client.messages.create(**params)
            return {
                "content": message.content[0].text,
                "model": message.model,
                "role": message.role,
                "usage": {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                },
            }
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in send_message: {str(e)}")
            raise

    @retry_on_overload()
    async def send_messages(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Send a conversation history to Claude and get a response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system: Optional system prompt to set context/behavior
            temperature: Controls randomness (0.0-1.0, lower is more deterministic)
            max_tokens: Maximum number of tokens to generate

        Returns:
            Dict containing the response and metadata
        """
        try:
            params = {
                "model": self.model,
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system:
                params["system"] = system

            message = self.client.messages.create(**params)
            return {
                "content": message.content[0].text,
                "model": message.model,
                "role": message.role,
                "usage": {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                },
            }
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in send_messages: {str(e)}")
            raise

    @retry_on_overload()
    async def stream_message(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
    ):
        """
        Stream a response from Claude token by token.

        Args:
            prompt: The user's message/prompt
            system: Optional system prompt to set context/behavior
            temperature: Controls randomness (0.0-1.0, lower is more deterministic)
            max_tokens: Maximum number of tokens to generate

        Yields:
            Response text tokens as they are generated
        """
        try:
            params = {
                "model": self.model,
                "max_tokens": max_tokens or self.max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            }
            if system:
                params["system"] = system

            stream = await self.client.messages.create(**params)
            async for message in stream:
                if message.type == "content_block_delta":
                    yield message.delta.text
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error in stream_message: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in stream_message: {str(e)}")
            raise


# Create a singleton instance
_claude_client = None


def get_claude_client() -> ClaudeClient:
    """
    Get or create a singleton instance of ClaudeClient.
    """
    global _claude_client
    if _claude_client is None:
        _claude_client = ClaudeClient()
    return _claude_client
