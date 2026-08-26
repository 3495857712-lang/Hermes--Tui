"""Chat message and chat view widgets."""

from __future__ import annotations

from datetime import datetime

from rich.markdown import Markdown
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from ..utils.helpers import format_timestamp
from .widgets import LoadingDots


class ChatMessage(Static):
    """A single chat message bubble with role-based styling."""

    DEFAULT_CSS = """
    ChatMessage {
        height: auto;
        width: 100%;
        margin: 0 0 1 0;
        padding: 0 1;
    }

    ChatMessage .bubble {
        width: auto;
        max-width: 85%;
        height: auto;
        padding: 0 1;
        border: round $border;
        background: $assistant-bubble;
    }

    ChatMessage.user .bubble {
        background: $user-bubble;
    }

    ChatMessage.system .bubble {
        background: $system-bubble;
        color: $text-muted;
    }

    ChatMessage.tool .bubble {
        background: $tool-bubble;
        color: $text-muted;
    }

    .message-role {
        text-style: bold;
        color: $accent;
    }

    .message-time {
        color: $text-muted;
        text-style: dim;
    }
    """

    def __init__(
        self,
        role: str,
        content: str = "",
        timestamp: datetime | None = None,
        **kwargs,
    ) -> None:
        """Initialise a chat message.

        Args:
            role: One of ``user``, ``assistant``, ``system``, ``tool``.
            content: Message text (may contain Markdown).
            timestamp: When the message was created.
        """
        super().__init__(**kwargs)
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.add_class(role)

    def compose(self):
        """Render the header and bubble."""
        header = Static(
            f"[message-role]{self.role.capitalize()}[/]  "
            f"[message-time]{format_timestamp(self.timestamp)}[/]",
            classes="msg-header",
        )
        self._bubble = Static(
            Markdown(self.content) if self.content else "",
            classes="bubble",
        )
        yield header
        yield self._bubble

    def append_text(self, chunk: str) -> None:
        """Append a streaming chunk to the message content.

        Args:
            chunk: The text delta to add.
        """
        self.content += chunk
        try:
            self._bubble.update(Markdown(self.content))
        except Exception:
            self._bubble.update(self.content)

    def set_content(self, content: str) -> None:
        """Replace the message content.

        Args:
            content: The new full content.
        """
        self.content = content
        try:
            self._bubble.update(Markdown(content))
        except Exception:
            self._bubble.update(content)


class ChatView(VerticalScroll):
    """Scrollable chat view with auto-scroll and loading indicator."""

    DEFAULT_CSS = """
    ChatView {
        background: $bg;
        padding: 1 2;
        overflow-y: auto;
        height: 100%;
    }

    #loading-dots {
        height: 1;
        margin: 0 0 0 2;
    }
    """

    is_generating: reactive[bool] = reactive(False)

    def __init__(self, **kwargs) -> None:
        """Initialise the chat view."""
        super().__init__(**kwargs)
        self._streaming_msg: ChatMessage | None = None

    def compose(self):
        """Yield the loading indicator."""
        self._loading = LoadingDots(id="loading-dots")
        yield self._loading

    def on_mount(self) -> None:
        """Hide the loading indicator initially."""
        self._loading.visible = False

    def add_message(
        self,
        role: str,
        content: str,
        timestamp: datetime | None = None,
    ) -> ChatMessage:
        """Add a complete message to the view.

        Args:
            role: Message role.
            content: Full message content.
            timestamp: Optional timestamp.

        Returns:
            The created :class:`ChatMessage` widget.
        """
        msg = ChatMessage(role=role, content=content, timestamp=timestamp)
        self.mount(msg)
        self._scroll_to_bottom()
        return msg

    def start_streaming(self, role: str = "assistant") -> ChatMessage:
        """Create an empty message and begin streaming into it.

        Args:
            role: The role of the streaming message.

        Returns:
            The :class:`ChatMessage` being streamed into.
        """
        self._streaming_msg = self.add_message(role=role, content="")
        return self._streaming_msg

    def append_streaming_chunk(self, chunk: str) -> None:
        """Append a text chunk to the currently streaming message.

        Args:
            chunk: Text delta.
        """
        if self._streaming_msg is not None:
            self._streaming_msg.append_text(chunk)
            self._scroll_to_bottom()

    def end_streaming(self) -> None:
        """Finalise the current streaming message."""
        self._streaming_msg = None
        self._scroll_to_bottom()

    def show_loading(self) -> None:
        """Show the loading indicator."""
        self.is_generating = True
        self._loading.start()
        self._scroll_to_bottom()

    def hide_loading(self) -> None:
        """Hide the loading indicator."""
        self.is_generating = False
        self._loading.stop()

    def clear(self) -> None:
        """Remove all messages from the view."""
        for child in list(self.children):
            if isinstance(child, ChatMessage):
                child.remove()
        self._streaming_msg = None

    def _scroll_to_bottom(self) -> None:
        """Smooth-scroll to the latest message."""
        self.scroll_end(animate=False)
