from __future__ import annotations

from typing import Any

try:
    from realtor_outreach import build_master_feed_fields, build_realtor_contact_package
except ImportError:
    try:
        from ..realtor_outreach import build_master_feed_fields, build_realtor_contact_package
    except ImportError:
        from war_room_offer