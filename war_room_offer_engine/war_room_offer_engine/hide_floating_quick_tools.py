from __future__ import annotations


FLOATING_PANEL_MARKERS = (
    'class="wr-tool-dock"',
    "class='wr-tool-dock'",
)


def is_floating_quick_tools_html(body) -> bool:
    text = str(body or "")
    return any(marker in text for marker in FLOATING_PANEL_MARKERS)


def install() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False

    if getattr(st, "_war_room_hide_floating_quick_tools_installed", False):
        return True

    original_markdown = st.markdown

    def markdown_without_floating_tools(body, *args, **kwargs):
        # The source renderer still builds the old right-side floating panel.
        # Block that one HTML payload every rerun. Separate sidebar calls continue,
        # so the left Quick Tools workspace selector remains fully functional.
        if is_floating_quick_tools_html(body):
            return None
        return original_markdown(body, *args, **kwargs)

    st.markdown = markdown_without_floating_tools
    st._war_room_hide_floating_quick_tools_installed = True
    return True


install()
