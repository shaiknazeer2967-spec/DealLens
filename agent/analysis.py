ISSUE_TERMS = {
    "pricing": ("price", "pricing", "budget", "cost", "discount"),
    "competition": ("competitor", "competitive", "alternative", "vendor"),
    "security": ("security", "compliance", "legal", "privacy", "audit"),
    "decision": ("decision maker", "economic buyer", "stakeholder", "approval", "procurement"),
}


def analyze_deal(deal, recalled):
    text = deal["situation"].lower()
    signals = {name: any(term in text for term in terms) for name, terms in ISSUE_TERMS.items()}
    pairs = (("pricing", "Pricing pressure"), ("competition", "Competitive threat"), ("security", "Security or compliance review"), ("decision", "Decision path unclear"))
    risks = [label for key, label in pairs if signals[key]]
    health = max(48, 82 - len(risks) * 9 + min(len(recalled), 2) * 3)
    actions = []
    if signals["pricing"]: actions.append("Quantify business value with an ROI narrative before discussing discounting.")
    if signals["security"]: actions.append("Bring security and compliance stakeholders into the next meeting early.")
    if signals["competition"]: actions.append("Map the competitor's gaps to the customer's stated priority.")
    if signals["decision"]: actions.append("Confirm the economic buyer, approval criteria, and next decision date.")
    if not actions: actions.append("Confirm success criteria and capture the next concrete commitment.")
    return {"health": health, "risk": "High" if health < 60 else "Medium" if health < 75 else "Low", "risks": risks or ["No critical risk signal detected"], "actions": actions, "memory_impact": recalled[0]["lesson"] if recalled else "No close match yet—create the first reusable playbook.", "confidence": "High" if len(recalled) >= 2 else "Moderate" if recalled else "Early signal"}
