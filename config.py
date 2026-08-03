# =============================
# Flask web panel settings
# =============================
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000

# =============================
# HTTP Basic Authentication
# =============================
USERNAME = "admin"      # CHANGE
PASSWORD = "changeme"   # CHANGE

# =============================
# SteamCMD / Updates
# =============================
# Nuclear Option Dedicated Server AppID
STEAM_APP_ID = 3930080
STEAM_LOGIN = "anonymous"

AUTO_RESTART_AFTER_UPDATE = True

# =============================
# Ports tab storage
# =============================
PORTS_FILE = "ports.json"
DEFAULT_SERVER_PORTS = [{"port": 7779, "name": "Default Server"}]

# Optional hard fallback used only if ports.json is missing/corrupt
SERVER_PORTS = [7779]

# Panel security / proxy settings
TRUST_REVERSE_PROXY = False
TRUSTED_PROXY_IPS = ["127.0.0.1", "::1"]
# Set True only when the panel is served over HTTPS by a trusted reverse proxy.
SESSION_COOKIE_SECURE = False
# Optional static secret. Leave empty to auto-generate and persist to .panel_secret_key.
SECRET_KEY = ""

# Embedded persistence. Relative paths are resolved from the panel directory.
# NO_PANEL_DATABASE_PATH can override this value for packaged/test deployments.
DATABASE_PATH = "data/panel.sqlite3"
