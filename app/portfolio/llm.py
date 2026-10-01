"""
Cliente LLM para el módulo Portfolio Health.

Usa Google Gemini como proveedor principal (free tier disponible).
- gemini-1.5-flash: tareas rápidas (parsing fallback, chat simple)
- gemini-1.5-pro: análisis complejo (reporte Health, escenarios)

Diseño:
- Clase abstracta LLMClient con métodos complete() y stream().
- GeminiClient implementa la clase con el SDK oficial google-generativeai.
- get_llm_client() retorna la instancia correcta según AI_PROVIDER del entorno.
- stream() usa AsyncGenerator para streaming token por token.
"""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Clase base abstracta
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    """Interfaz común para proveedores de IA."""

    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Genera una respuesta completa (no streaming)."""
        ...

    @abstractmethod
    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Genera la respuesta en chunks (streaming)."""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Chat con historial de conversación en streaming."""
        ...


# ---------------------------------------------------------------------------
# Cliente Gemini
# ---------------------------------------------------------------------------


class GeminiClient(LLMClient):
    """
    Cliente para Google Gemini usando el SDK oficial google-generativeai.

    Modelos usados:
    - DEFAULT_MODEL (análisis/reporte): gemini-1.5-pro
    - FAST_MODEL (chat/parsing): gemini-1.5-flash
    """

    DEFAULT_MODEL = "gemini-1.5-pro"
    FAST_MODEL = "gemini-1.5-flash"

    def __init__(self, api_key: str):
        import google.generativeai as genai  # importación diferida
        genai.configure(api_key=api_key)
        self._genai = genai

    def _get_model(self, model_name: str, system_prompt: str):
        return self._genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
        )

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        model_name = model or self.DEFAULT_MODEL
        gen_model = self._get_model(model_name, system_prompt)

        try:
            # Ejecutar en thread pool para no bloquear el event loop
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: gen_model.generate_content(
                    user_prompt,
                    generation_config=self._genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.3,
                    ),
                ),
            )
            return response.text or ""
        except Exception as exc:
            logger.error("Error en Gemini complete(): %s", exc)
            raise

    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        model_name = model or self.DEFAULT_MODEL
        gen_model = self._get_model(model_name, system_prompt)

        try:
            # Gemini streaming es síncrono; lo ejecutamos en un thread
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: gen_model.generate_content(
                    user_prompt,
                    stream=True,
                    generation_config=self._genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.3,
                    ),
                ),
            )

            async def _iter():
                for chunk in response:
                    text = chunk.text if hasattr(chunk, "text") else ""
                    if text:
                        yield text
                        await asyncio.sleep(0)  # ceder el event loop

            return _iter()
        except Exception as exc:
            logger.error("Error en Gemini stream(): %s", exc)
            raise

    async def chat_stream(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        model: str | None = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        Chat con historial.
        history: lista de {"role": "user"|"model", "parts": "..."}
        """
        model_name = model or self.FAST_MODEL
        gen_model = self._get_model(model_name, system_prompt)

        # Convertir historial al formato Gemini
        gemini_history = []
        for msg in history:
            role = "model" if msg.get("role") == "assistant" else "user"
            gemini_history.append({
                "role": role,
                "parts": [msg.get("content", "")],
            })

        try:
            chat = gen_model.start_chat(history=gemini_history)

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: chat.send_message(
                    user_message,
                    stream=True,
                    generation_config=self._genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.5,
                    ),
                ),
            )

            async def _iter():
                for chunk in response:
                    text = chunk.text if hasattr(chunk, "text") else ""
                    if text:
                        yield text
                        await asyncio.sleep(0)

            return _iter()
        except Exception as exc:
            logger.error("Error en Gemini chat_stream(): %s", exc)
            raise


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_client_cache: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """
    Retorna el cliente LLM configurado según las variables de entorno.
    Cachea la instancia para reutilizar la configuración.
    """
    global _client_cache
    if _client_cache is not None:
        return _client_cache

    provider = os.getenv("AI_PROVIDER", "gemini").lower()

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY no está configurada. "
                "Obtené tu API key en https://aistudio.google.com/ y agregala al entorno."
            )
        _client_cache = GeminiClient(api_key=api_key)
        logger.info("Cliente LLM: Google Gemini inicializado.")
        return _client_cache

    raise ValueError(f"Proveedor de IA no soportado: '{provider}'. Usá 'gemini'.")


def is_llm_available() -> bool:
    """Verifica si hay una API key configurada sin lanzar excepción."""
    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY"))
    return False
