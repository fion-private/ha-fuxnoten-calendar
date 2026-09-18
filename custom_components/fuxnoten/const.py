"""Constants for the FuxNoten Elternportal integration."""

DOMAIN = "fuxnoten"

# Config entry keys
CONF_SCHOOL_NUMBER = "school_number"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_CHILD_ID = "child_id"
CONF_CHILD_NAME = "child_name"
CONF_TARGET_CALENDAR = "target_calendar"
CONF_SYNC_TIME = "sync_time"

# Defaults
DEFAULT_SYNC_TIME = "06:00:00"
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_LOOKAHEAD_DAYS = 120

# category_id in the FuxNoten calendar JSON: 2 = "Leistungen" (graded
# assignments / tests), 1 = "Ferien / Feiertage" (holidays, intentionally
# not synced).
CATEGORY_ID_LEISTUNGEN = 2

# Storage key prefix for the list of already-created event IDs (dedup)
STORAGE_KEY_PREFIX = f"{DOMAIN}_synced_ids"
STORAGE_VERSION = 1


def build_base_url(school_number: str) -> str:
    """Build the portal base URL from the school number.

    The FuxNoten Elternportal is hosted on a subdomain that is exactly
    the school's number, e.g. school number "100213" maps to
    "https://100213.fuxnoten.com".
    """
    return f"https://{school_number}.fuxnoten.com"
