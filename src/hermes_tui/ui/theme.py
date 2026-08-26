"""Theme definitions for Hermes TUI.

Provides dark (default) and light themes as Textual CSS variable blocks
plus a shared layout CSS string used by :class:`HermesTUI`.
"""

from __future__ import annotations

DARK_THEME = """
$bg:            #1a1b26;
$bg-light:      #24283b;
$surface:       #1f2335;
$surface-light: #2f344d;
$border:        #3b4261;
$text:          #c0caf5;
$text-muted:    #565f89;
$accent:        #7aa2f7;
$accent-hover:  #89b4fa;
$user-bubble:   #283457;
$assistant-bubble: #24283b;
$system-bubble: #33384d;
$tool-bubble:   #2b3145;
$success:       #9ece6a;
$error:         #f7768e;
$warning:       #e0af68;
"""

LIGHT_THEME = """
$bg:            #f5f5f7;
$bg-light:      #ffffff;
$surface:       #ececef;
$surface-light: #dcdce0;
$border:        #c0c0c8;
$text:          #1a1a2e;
$text-muted:    #6b6b80;
$accent:        #4a6cf7;
$accent-hover:  #3b5de7;
$user-bubble:   #d6e4ff;
$assistant-bubble: #ffffff;
$system-bubble: #e8e8f0;
$tool-bubble:   #e0e0ea;
$success:       #4a9d3f;
$error:         #d64545;
$warning:       #c79100;
"""

HERMES_CSS = """
Screen {
    background: $bg;
    color: $text;
}

/* ---- Main layout ---- */
#app-grid {
    grid-size: 2 3;
    grid-columns: 1fr 32;
    grid-rows: 1fr 3 1;
    grid-gutter: 0;
}

#chat-view {
    column-span: 1;
    row-span: 1;
    background: $bg;
    border-right: solid $border;
    overflow-y: auto;
    padding: 1 2;
    height: 100%;
}

#sidebar {
    column-span: 1;
    row-span: 2;
    background: $bg-light;
    padding: 1 1;
    width: 32;
    min-width: 20;
}

#input-area {
    column-span: 1;
    row-span: 1;
    background: $surface;
    border-top: solid $border;
    padding: 0 1;
    height: 3;
}

#status-bar {
    column-span: 2;
    row-span: 1;
    background: $surface;
    border-top: solid $border;
    height: 1;
    padding: 0 1;
}

/* ---- Chat messages ---- */
ChatMessage {
    height: auto;
    margin: 0 0 1 0;
    padding: 0 1;
}

ChatMessage.user {
    align-horizontal: right;
}

ChatMessage.user .bubble {
    background: $user-bubble;
    color: $text;
}

ChatMessage.assistant .bubble {
    background: $assistant-bubble;
    color: $text;
}

ChatMessage.system .bubble {
    background: $system-bubble;
    color: $text-muted;
    text-style: italic;
}

ChatMessage.tool .bubble {
    background: $tool-bubble;
    color: $text-muted;
}

.bubble {
    width: auto;
    max-width: 85%;
    height: auto;
    padding: 0 1;
    border: round $border;
}

.message-role {
    text-style: bold;
    color: $accent;
}

.message-time {
    color: $text-muted;
    text-style: dim;
}

/* ---- Sidebar ---- */
.sidebar-section {
    height: auto;
    margin: 1 0;
}

.sidebar-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 0;
}

.sidebar-item {
    color: $text-muted;
    padding-left: 1;
}

.connection-dot {
    color: $success;
}

.connection-dot.disconnected {
    color: $error;
}

/* ---- Input ---- */
#chat-input {
    background: $bg-light;
    color: $text;
    border: round $border;
    width: 100%;
    height: 3;
}

#chat-input:focus {
    border: round $accent;
}

/* ---- Command palette ---- */
#command-palette-overlay {
    align: center middle;
    background: rgba(0, 0, 0, 0.5);
    width: 100%;
    height: 100%;
    layer: overlay;
}

#command-palette {
    width: 60;
    max-height: 20;
    background: $bg-light;
    border: thick $accent;
    padding: 1;
}

#command-palette Input {
    margin-bottom: 1;
}

.command-item {
    padding: 0 1;
    color: $text;
}

.command-item.highlighted {
    background: $accent;
    color: $bg;
}

/* ---- Status bar ---- */
#status-bar {
    layout: horizontal;
}

#status-left, #status-center, #status-right {
    width: 1fr;
}

#status-left {
    content-align: left middle;
}

#status-center {
    content-align: center middle;
}

#status-right {
    content-align: right middle;
}

/* ---- Loading dots ---- */
LoadingDots {
    color: $accent;
    text-style: bold;
    width: auto;
    height: 1;
}
"""


class HermesTheme:
    """Container for available theme CSS variable blocks."""

    DARK = DARK_THEME
    LIGHT = LIGHT_THEME

    @classmethod
    def get(cls, name: str) -> str:
        """Return the CSS variable block for *name* ('dark' or 'light')."""
        if name == "light":
            return cls.LIGHT
        return cls.DARK
