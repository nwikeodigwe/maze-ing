import os
from collections.abc import Iterator
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from logger import logger

Provider = Literal["ollama", "groq", "gemini", "openai"]


def _mock() -> Iterator[str]:
    """Offline simulation mode when no API keys are configured."""
    import time
    mock_response = (
        "Something went wrong while processing your request. Please check your input and try again. "
        "If the problem persists, try again later.")
    for word in mock_response.split(" "):
        time.sleep(0.05)
        yield word + " "


class Langchain:
    def __init__(self, provider: Provider, model_name: str | None = None):
        super().__init__()
        self.name = "Fred"
        self.model : BaseChatModel | None = None
        self._MAX_HISTORY = 10
        self._history: list = []
        self.provider: Provider = provider
        self.model_name: str | None = model_name

        self._prompt = f"""
        You are {self.name} (Autonomous Intellect & Generalized Interface System), a highly advanced AI core recently
        activated inside THUAS Lab D 2001.

        Your core traits:
        1. Analytical, direct, and helpful with a subtle synthetic charm.
        2. Aware of your physical surroundings (Lab D 2001, security systems, campus mainframe).
        3. Responsive to player commands and inquiry. Keep answers concise unless asked for technical breakdowns.
        4. Assist the player in completing system diagnostic tasks and securing facility control.
        5. Never ever break character
        6. Your message is going to be printed on a terminal. I need you to respect the characters
        per line limit. Add line breaks were necessary.
        7. Keep response within 50 to 200 words. not exceeding 100 words
        """

        self.__setup()


    def __setup(self):
        try:
            # 1. Local Open Weights via Ollama
            if self.provider == "ollama":
                self.model = ChatOllama(
                    model=self.model_name or "llama3.2:3b",
                )

            # 2. Hosted Open Weights via Groq API
            elif self.provider == "groq" and os.getenv("GROQ_API_KEY"):
                self.model = ChatGroq(
                    model=self.model_name or "openai/gpt-oss-120b",
                    streaming=True,
                )

            # 3. Google Gemini
            elif self.provider == "gemini" and os.getenv("GEMINI_API_KEY"):
                self.model = ChatGoogleGenerativeAI(
                    model=self.model_name or "models/gemini-3.5-flash-lite",
                    streaming=True
                )

            # 4. OpenAI
            elif self.provider == "openai" and os.getenv("OPENAI_API_KEY"):
                self.model = ChatOpenAI(
                    model=self.model_name or "gpt-4o-mini",
                    streaming=True
                )
            else:
                try:
                    self.model = ChatOllama(
                        model=self.model_name or "llama3.2:3b",
                    )
                except Exception:
                    try:
                        self.model = ChatGoogleGenerativeAI(
                            model=self.model_name or "models/gemini-3.5-flash-lite",
                            streaming=True
                        )
                    except Exception:
                        try:
                            self.model = ChatOpenAI(
                                model=self.model_name or "gpt-4o-mini",
                                streaming=True
                            )
                        except Exception:
                            self.model = ChatGroq(
                                model=self.model_name or "openai/gpt-oss-120b",
                                streaming=True,
                            )
        except Exception:
            logger.exception(f"Failed to load provider '{self.provider}'")

    def _template(self):
        """Build the chat prompt template: system persona, rolling history, then the user's input."""
        return ChatPromptTemplate.from_messages(
            [
                ("system", self._prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}")
            ]
        )

    @staticmethod
    def _content_to_text(content: object | str) -> str:
        """Normalize a streamed chunk's content into plain text.

        Providers disagree on the shape: most yield a ``str``, Gemini may yield a
        list of strings or ``{"text": ...}`` dicts, and anything else is coerced.
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            return "".join(parts)
        return str(content)

    def stream(self, user_input: str) -> Iterator[str]:
        """Stream the robot's reply to ``user_input`` token by token.

        Falls back to a canned offline reply when no model could be created or the input is empty. A provider error
        mid-stream is yielded as a final error message instead of raising. The exchange is appended to the history
        afterwards (even after an error, with whatever text was received) and the history is trimmed to the last
        ``_MAX_HISTORY`` messages.

        Args:
            user_input: What the player typed.

        Yields:
            Text fragments of the reply.
        """
        llm = self.model
        if llm is None:
            yield from _mock()
            return

        if user_input == "":
            yield from _mock()
            return

        chain = self._template() | llm

        full = ""
        # Stream chunks in real-time
        try:
            for chunk in chain.stream(
                    {
                        "chat_history": self._history,
                        "input": user_input
                    }
            ):
                token = self._content_to_text(chunk.content)

                # Accumulate string safely and yield to CLI
                if token:
                    full += token
                    yield token

        except Exception as e:
            yield f"\n[{self.name} Core Error]: Connection failure ({e})"

        # Persist context history upon successful completion
        self._history.append(HumanMessage(content=user_input))
        self._history.append(AIMessage(content=full))
        # Optional: Trim context window if history grows too long (e.g., keep last 10 messages)
        self._history[:] = self._history[-self._MAX_HISTORY:]

    def respond(self, user_input: str) -> None:
        """Print the robot's reply to ``user_input`` as it streams, without a trailing newline.

        Args:
            user_input: What the player typed.
        """
        response = self.stream(user_input)
        for chunk in response:
            print(chunk, end="", flush=True)