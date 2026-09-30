"""Deal intelligence: detect signals, then REFLECT on recalled deals and DECIDE."""

ISSUE_TERMS = {
    "pricing": ("price", "pricing", "budget", "cost", "discount", "cheaper", "expensive"),
    "competition": ("competitor", "competitive", "alternative", "vendor", "rival"),
    "security": ("security", "compliance", "legal", "privacy", "audit"),
    "decision": ("decision maker", "economic buyer", "stakeholder", "approval", "procurement"),
    "implementation": ("implementation", "rollout", "time-to-value", "go-live", "onboarding", "deployment", "implementation time"),
}

SIGNAL_LABELS = (
    ("pricing", "Pricing pressure"),
    ("competition", "Competitive threat"),
    ("implementation", "Implementation / time-to-value concern"),
    ("security", "Security or compliance review"),
    ("decision", "Decision path unclear"),
)

DEAL_FIELDS = (
    "company",
    "deal_value",
    "customer",
    "industry",
    "situation",
    "objections",
    "competitor",
    "requirements",
    "negotiation",
    "outcome",
)


def deal_text(deal):
    """Combine all user-entered deal fields for matching and signal detection."""
    return " ".join(str(deal.get(key) or "") for key in DEAL_FIELDS).lower()


def detect_signals(deal):
    """Tag a deal with the objection / risk themes DealLens uses for recall."""
    text = deal_text(deal)
    return {name: any(term in text for term in terms) for name, terms in ISSUE_TERMS.items()}


def active_signal_names(signals):
    return [name for name, present in signals.items() if present]


def analyze_deal(deal, recalled):
    """
    Hindsight-memory reasoning for the current deal.

    RECALL is supplied by HindsightMemory.recall (similar past deals).
    This function REFLECTs on those deals and DECIDEs a suggested action,
    always attributing the suggestion to historical patterns (not certainty).
    """
    signals = detect_signals(deal)
    risks = [label for key, label in SIGNAL_LABELS if signals.get(key)]
    health = max(48, 82 - len(risks) * 9 + min(len(recalled), 2) * 3)

    similar = list(recalled)
    reflection = reflect_on_history(deal, similar, signals)
    decision = decide_from_history(deal, similar, signals, reflection)

    actions = list(decision.get("actions") or [])
    if not actions:
        actions = _default_actions(signals)

    memory_impact = decision.get("headline") or (similar[0].get("lesson") if similar else "No close match yet—this analysis will be retained for the next deal.")

    return {
        "health": health,
        "risk": "High" if health < 60 else "Medium" if health < 75 else "Low",
        "risks": risks or ["No critical risk signal detected"],
        "signals": signals,
        "actions": actions,
        "similar_deals": similar,
        "what_happened": reflection["what_happened"],
        "lessons": reflection["lessons"],
        "patterns": reflection["patterns"],
        "successful_strategies": reflection["successful_strategies"],
        "failed_strategies": reflection["failed_strategies"],
        "decision": decision,
        "memory_impact": memory_impact,
        "confidence": "High" if len(similar) >= 2 else "Moderate" if similar else "Early signal",
    }


def reflect_on_history(deal, similar, signals):
    """
    REFLECT: turn recalled deals into lessons, patterns, and win/loss strategies.

    Does not merely list old deals — extracts what worked, what failed, and
    which objections repeatedly decided the outcome.
    """
    what_happened = []
    for item in similar:
        outcome = (item.get("outcome") or "Unknown").strip() or "Unknown"
        lesson = (item.get("lesson") or "").strip()
        company = item.get("company") or "Past deal"
        story = item.get("what_happened") or item.get("situation") or item.get("text") or ""
        what_happened.append({
            "company": company,
            "outcome": outcome,
            "story": story,
            "lesson": lesson,
            "why_similar": item.get("why_similar") or "",
        })

    won = [item for item in similar if _is_win(item.get("outcome"))]
    lost = [item for item in similar if _is_loss(item.get("outcome"))]

    successful_strategies = []
    for item in won:
        successful_strategies.append({
            "strategy": item.get("lesson") or "Value and execution were made concrete before commercial concessions.",
            "company": item.get("company") or "Past deal",
            "outcome": item.get("outcome") or "Won",
            "why": f"This approach coincided with a win at {item.get('company') or 'a similar account'}.",
        })

    failed_strategies = []
    for item in lost:
        failed_strategies.append({
            "strategy": item.get("lesson") or "Conceding on the stated objection without addressing the underlying concern.",
            "company": item.get("company") or "Past deal",
            "outcome": item.get("outcome") or "Lost",
            "why": f"This pattern coincided with a loss at {item.get('company') or 'a similar account'}.",
        })

    patterns = _detect_patterns(similar, signals)
    lessons = _extract_lessons(similar, signals, won, lost)

    if not similar:
        lessons = [{
            "title": "No comparable memory yet",
            "detail": "This deal will be retained so future analyses can recall what happens here.",
            "source": "Current deal will seed memory",
        }]

    return {
        "what_happened": what_happened,
        "lessons": lessons,
        "patterns": patterns,
        "successful_strategies": successful_strategies,
        "failed_strategies": failed_strategies,
    }


def decide_from_history(deal, similar, signals, reflection):
    """
    DECIDE: recommend a next move grounded in recalled evidence.

    The recommendation is framed as pattern-based decision support, not a
    guarantee that the same tactic will win this deal.
    """
    company = deal.get("company") or "this account"
    won = [item for item in similar if _is_win(item.get("outcome"))]
    lost = [item for item in similar if _is_loss(item.get("outcome"))]
    evidence = [
        f"{item.get('company') or 'Past deal'} · {(item.get('outcome') or 'unknown outcome')} — {item.get('lesson') or item.get('why_similar') or 'similar situation recalled'}"
        for item in similar[:4]
    ]

    pattern = (reflection["patterns"][0]["statement"] if reflection["patterns"] else "No repeated historical pattern is strong enough to treat as a rule yet.")
    headline, suggested, risk, reason, actions = _decision_copy(signals, similar, won, lost, company)

    return {
        "headline": headline,
        "evidence": evidence,
        "pattern": pattern,
        "suggested_action": suggested,
        "risk": risk,
        "reason": reason,
        "disclaimer": "This is decision support based on patterns from previous deals, not a guarantee that the same action will work here.",
        "actions": actions,
    }


def _decision_copy(signals, similar, won, lost, company):
    actions = _default_actions(signals)

    if signals.get("pricing") and won and lost:
        headline = (
            f"Historical pattern detected: price objections were handled more successfully when the discussion "
            f"focused on ROI and implementation value rather than discounting alone."
        )
        suggested = (
            f"For {company}, lead with a quantified ROI and implementation plan before any discount conversation. "
            f"{len(won)} similar win(s) used that framing; {len(lost)} similar loss(es) leaned on price cuts."
        )
        risk = "Discounting first can train the buyer to treat price as the only remaining issue, which is how several recalled losses unfolded."
        reason = "Recalled wins and losses share a price objection, but outcomes diverged based on whether value and time-to-value were made explicit."
        return headline, suggested, risk, reason, actions

    if signals.get("pricing") and won:
        headline = "Similar past deals were more likely to move forward when ROI and delivery proof replaced a pure price debate."
        suggested = f"Show {company} the business case and implementation path used in comparable wins before negotiating price."
        risk = "Without a value frame, a cheaper competitor can still define the evaluation."
        reason = "Recalled memories with a pricing objection and a win emphasized measurable value, not only a lower number."
        return headline, suggested, risk, reason, actions

    if signals.get("pricing") and lost:
        headline = "Similar past deals were lost when the team treated a price objection as a discount request only."
        suggested = f"Do not open with a concession at {company}. Diagnose what the price objection is standing in for (risk, implementation, competitor, or ROI)."
        risk = "A fast discount may not address the concern that actually decided previous losses."
        reason = "Recalled losses with pricing pressure show discounting alone did not close the gap."
        return headline, suggested, risk, reason, actions

    if signals.get("implementation"):
        headline = "Implementation time has shown up in recalled deals as a hidden decision criterion, not a side note."
        suggested = f"Give {company} a concrete rollout plan, owners, and time-to-value milestones in the next conversation."
        risk = "If implementation stays vague, a cheaper or 'faster' competitor can win on perceived effort even when product fit is weaker."
        reason = "Recalled deals that named implementation or time-to-value were decided by how credible the delivery plan sounded."
        return headline, suggested, risk, reason, actions

    if signals.get("competition"):
        headline = "When a competitor was in play, recalled wins mapped their gaps to the customer's stated priority instead of reacting to list price."
        suggested = f"Build a side-by-side for {company} against the named alternative on the requirements that matter most."
        risk = "Competing only on price repeats losses where the competitor already owned the cheap-option narrative."
        reason = "Historical competitive deals turned on requirement fit and risk, not on matching the other vendor's number."
        return headline, suggested, risk, reason, actions

    if signals.get("security"):
        headline = "Security and compliance reviews delayed or decided several recalled deals when they were scheduled late."
        suggested = f"Bring security/compliance into the next {company} meeting with evidence mapped to their requirements."
        risk = "A late review can stall the economic buyer even after commercial agreement."
        reason = "Recalled deals with compliance pressure moved faster when proof was prepared before procurement locked a timeline."
        return headline, suggested, risk, reason, actions

    if similar:
        headline = f"{len(similar)} similar past experience(s) were recalled; use them as evidence, not as a script that will automatically repeat."
        suggested = actions[0]
        risk = "Overfitting to one past deal can miss what is unique about this customer."
        reason = "The recommendation follows the closest recalled lessons while remaining explicit that history is a guide, not a guarantee."
        return headline, suggested, risk, reason, actions

    headline = "No close historical match yet — capture this interaction so the next similar deal can recall it."
    suggested = actions[0]
    risk = "Acting without comparable memory means the team cannot yet cite what worked or failed in like situations."
    reason = "Retain this deal's facts, objections, and eventual outcome so DealLens can reflect on it later."
    return headline, suggested, risk, reason, actions


def _default_actions(signals):
    actions = []
    if signals.get("pricing"):
        actions.append("Quantify business value with an ROI narrative before discussing discounting.")
    if signals.get("implementation"):
        actions.append("Present a dated implementation plan and time-to-value milestones, not only product features.")
    if signals.get("security"):
        actions.append("Bring security and compliance stakeholders into the next meeting early.")
    if signals.get("competition"):
        actions.append("Map the competitor's gaps to the customer's stated priority.")
    if signals.get("decision"):
        actions.append("Confirm the economic buyer, approval criteria, and next decision date.")
    if not actions:
        actions.append("Confirm success criteria and capture the next concrete commitment.")
    return actions


def _detect_patterns(similar, signals):
    patterns = []
    if not similar:
        return patterns

    price_deals = [item for item in similar if detect_signals(item).get("pricing") or signals.get("pricing")]
    if len(price_deals) >= 2:
        wins = sum(1 for item in price_deals if _is_win(item.get("outcome")))
        losses = sum(1 for item in price_deals if _is_loss(item.get("outcome")))
        patterns.append({
            "name": "Price objection pattern",
            "count": len(price_deals),
            "statement": (
                "Price objections were handled more successfully when the discussion focused on ROI and "
                "implementation value rather than discounting alone."
                if wins and losses else
                f"{len(price_deals)} recalled deals share a pricing objection ({wins} won / {losses} lost)."
            ),
            "evidence": [item.get("company") or "Past deal" for item in price_deals[:4]],
        })

    impl_deals = [item for item in similar if detect_signals(item).get("implementation")]
    if impl_deals:
        patterns.append({
            "name": "Implementation concern pattern",
            "count": len(impl_deals),
            "statement": "Implementation time and time-to-value repeatedly influenced whether the customer would pay or wait.",
            "evidence": [item.get("company") or "Past deal" for item in impl_deals[:4]],
        })

    comp_deals = [item for item in similar if detect_signals(item).get("competition") or (item.get("competitor") or "").strip()]
    if comp_deals:
        patterns.append({
            "name": "Competitor-in-deal pattern",
            "count": len(comp_deals),
            "statement": "When a cheaper alternative was present, matching price without differentiating delivery rarely recovered the deal.",
            "evidence": [item.get("company") or "Past deal" for item in comp_deals[:4]],
        })

    overlooked = [item for item in similar if "overlook" in (item.get("lesson") or "").lower() or "requirements" in (item.get("lesson") or "").lower()]
    if overlooked:
        patterns.append({
            "name": "Overlooked requirements",
            "count": len(overlooked),
            "statement": "Some recalled losses mention customer requirements that were not addressed until too late.",
            "evidence": [item.get("company") or "Past deal" for item in overlooked[:4]],
        })

    return patterns


def _extract_lessons(similar, signals, won, lost):
    lessons = []
    if lost:
        lessons.append({
            "title": "What failed",
            "detail": lost[0].get("lesson") or "Treating the loudest objection as a concession request, without testing the underlying concern.",
            "source": ", ".join(item.get("company") or "Past deal" for item in lost[:3]),
        })
    if won:
        lessons.append({
            "title": "What worked",
            "detail": won[0].get("lesson") or "Making ROI, implementation, and risk concrete before commercial negotiation.",
            "source": ", ".join(item.get("company") or "Past deal" for item in won[:3]),
        })
    if signals.get("pricing") and lost:
        lessons.append({
            "title": "Objections that caused losses",
            "detail": "Price was the stated objection, but recalled losses show discounting alone did not resolve the customer's concern.",
            "source": ", ".join(item.get("company") or "Past deal" for item in lost[:3]),
        })
    if similar:
        lessons.append({
            "title": "Requirements to keep visible",
            "detail": "Across recalled deals, implementation time, compliance proof, and economic-buyer access were easy to under-serve while debating price.",
            "source": ", ".join(item.get("company") or "Past deal" for item in similar[:3]),
        })
    return lessons


def _is_win(outcome):
    value = (outcome or "").lower()
    return any(token in value for token in ("won", "win", "recovered", "closed-won"))


def _is_loss(outcome):
    value = (outcome or "").lower()
    return any(token in value for token in ("lost", "loss", "closed-lost", "churn"))
