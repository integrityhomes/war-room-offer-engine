from __future__ import annotations


def install() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False

    if getattr(st, "_war_room_hide_floating_quick_tools_installed", False):
        return True

    original_markdown = st.markdown
    css_injected = {"done": False}

    def markdown_without_floating_tools(body, *args, **kwargs):
        if not css_injected["done"]:
            original_markdown(
                "<style>.wr-tool-dock{display:none!important;}</style>",
                unsafe_allow_html=True,
            )
            css_injected["done"] = True
        return original_markdown(body, *args, **kwargs)

    st.markdown = markdown_without_floating_tools
    st._war_room_hide_floating_quick_tools_installed = True
    return True


install()
