# thanos_app/utils/password_validator.py
import re

def validate_master_password(password: str) -> dict:
    """
    Valide le mot de passe principal selon des règles strictes.
    Retourne un dictionnaire avec le statut, le score, le label et les feedbacks.
    """
    if len(password) < 16:
        return {
            "valid": False, "score": 0, "label": "❌ Trop court", "color": "#ff4444",
            "feedback": "16 caractères minimum requis."
        }

    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'\d', password))
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))

    if not (has_upper and has_lower and has_digit and has_special):
        missing = []
        if not has_upper: missing.append("Majuscule")
        if not has_lower: missing.append("Minuscule")
        if not has_digit: missing.append("Chiffre")
        if not has_special: missing.append("Spécial")
        return {
            "valid": False, "score": 1, "label": "❌ Incomplet", "color": "#ff4444",
            "feedback": f"Manquant : {', '.join(missing)}"
        }

    common_patterns = ["1234", "azerty", "qwerty", "password", "admin", "abcd"]
    if any(pat in password.lower() for pat in common_patterns):
        return {
            "valid": False, "score": 1, "label": "❌ Trop prévisible", "color": "#ff4444",
            "feedback": "Évitez les suites logiques ou mots courants."
        }

    # Calcul du score (2 à 5)
    score = 2
    if len(password) >= 20: score += 1
    if len(set(password)) > len(password) * 0.7: score += 1  # Haute entropie
    if not re.search(r'(.)\1\1', password): score += 1       # Pas de triple répétition

    levels = {2: ("🟡 Acceptable", "#ffbb33"), 3: ("🟢 Fort", "#00C851"), 4: ("🔵 Très fort", "#33b5e5"), 5: ("🟣 Légendaire", "#AA66CC")}
    label, color = levels.get(score, ("🟡 Acceptable", "#ffbb33"))

    return {"valid": True, "score": score, "label": label, "color": color, "feedback": "✔ Mot de passe valide"}