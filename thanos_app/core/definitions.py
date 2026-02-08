# thanos_app/core/definitions.py

CATEGORIES = [
    "Banques & Finance",
    "Réseaux Sociaux",
    "Sites Web",
    "Applications",
    "Travail",
    "Sensible",
    "Autre"
]

IMPORTANCE_LEVELS = {
    3: {"label": "🔴 Critique",   "color": "#e53935"},
    2: {"label": "🟠 Important", "color": "#ffb300"},
    1: {"label": "🟡 Moyen",     "color": "#fdd835"},
    0: {"label": "🟢 Faible",    "color": "#43a047"}
}

CATEGORY_TO_IMPORTANCE = {
    "Banques & Finance": 3,
    "Sensible": 3,
    "Réseaux Sociaux": 2,
    "Travail": 2,
    "Applications": 1,
    "Sites Web": 1,
    "Autre": 0
}

# Dictionnaire pour la suggestion automatique d'URL
SERVICE_TO_URL = {
    "google": "https://accounts.google.com",
    "gmail": "https://mail.google.com",
    "facebook": "https://facebook.com",
    "instagram": "https://instagram.com",
    "twitter": "https://twitter.com",
    "linkedin": "https://linkedin.com",
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "amazon": "https://amazon.com",
    "netflix": "https://netflix.com",
    "spotify": "https://spotify.com",
    "paypal": "https://paypal.com",
    "apple": "https://appleid.apple.com",
    "microsoft": "https://login.live.com",
    "outlook": "https://outlook.com",
    "discord": "https://discord.com",
    "reddit": "https://reddit.com",
}

# Log Event Types
LOG_EVENT_INCORRECT_ATTEMPT = "INCORRECT_ATTEMPT"
LOG_EVENT_SECURITY_TRIGGER = "SECURITY_TRIGGER"
LOG_EVENT_PHOTO_CAPTURE = "PHOTO_CAPTURE"
LOG_EVENT_EMAIL_ALERT = "EMAIL_ALERT"
LOG_EVENT_LOGIN_SUCCESS = "LOGIN_SUCCESS"