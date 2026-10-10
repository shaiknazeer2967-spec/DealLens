from flask import Flask, jsonify, render_template, request, redirect, url_for

from agent.analysis import DEAL_FIELDS, analyze_deal
from hindsight.memory import HindsightMemory
from experiment_store import all_experiments, analysis_for, create as create_experiment, get_experiment, insights as experiment_insights, load_demo, remove as remove_experiment

app = Flask(__name__)
memory = HindsightMemory()


@app.teardown_appcontext
def close_memory(exception):
    memory.close()


@app.context_processor
def inject_shell():
    return {
        "memory_count": len(memory.all()),
        "memory_ready": memory.ready,
        "nav_path": request.path,
    }


@app.template_filter("money")
def money_filter(value):
    if value is None:
        return "Not available"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _form_deal():
    deal = {key: request.form.get(key, "").strip() for key in DEAL_FIELDS}
    # New analyses are predictions, never confirmed outcomes. The detailed
    # context fields remain available to the existing analysis and recall logic.
    deal["outcome"] = "Open"
    deal["customer"] = deal.get("company", "")
    return deal


@app.route("/")
def home():
    # DealLens is the primary product and entry point. The separate prototype
    # routes remain isolated from the customer-facing deal workflow.
    return render_template("index.html", stats=memory.overview_stats(), memory_error=memory.error)


@app.route("/deal-overview")
def deal_overview():
    return redirect(url_for("home"))


@app.route("/analyze", methods=["GET"])
def analyze():
    return render_template(
        "analyze.html",
        form_data={},
        memory_error=memory.error,
    )


@app.route("/deal", methods=["GET", "POST"])
def deal():
    if request.method == "GET":
        return redirect(url_for("analyze"))
    current = _form_deal()
    required = {
        "company": "Deal name",
        "situation": "Deal description",
        "expected_outcome": "Expected outcome",
    }
    missing = [label for key, label in required.items() if not current.get(key)]
    if missing:
        return render_template(
            "analyze.html",
            memory_error=f"Please provide: {', '.join(missing)}.",
            form_data=current,
        ), 400
    try:
        recalled = memory.recall(current)
        analysis = analyze_deal(current, recalled)
        retained = memory.retain(current, analysis)
        memory.last_brief = {
            "deal": current,
            **analysis,
        }
        return render_template(
            "deal.html",
            deal=current,
            recalled=analysis.get("similar_deals") or recalled,
            analysis=analysis,
            retained=retained,
            memory_error=memory.error,
        )
    except Exception as exc:
        error = f"Hindsight request failed: {memory._safe_error(exc)}"
        return render_template(
            "analyze.html",
            memory_error=error,
            form_data=current,
        ), 502


@app.route("/history")
def history():
    past = memory.all()
    rows = []
    for item in sorted(past, key=lambda row: row.get("created_at") or "", reverse=True):
        view = dict(item)
        view["risk"] = memory.estimate_risk(item)
        rows.append(view)
    return render_template(
        "history.html",
        deals=rows,
        memory_error=memory.error,
    )


@app.route("/history/<document_id>")
def history_detail(document_id):
    record = next((item for item in memory.all() if item.get("document_id") == document_id), None)
    if not record:
        return render_template("history_detail.html", record=None, memory_error=memory.error), 404
    view = dict(record)
    view["risk"] = memory.estimate_risk(record)
    return render_template("history_detail.html", record=view, memory_error=memory.error)


@app.post("/history/<document_id>/outcome")
def record_deal_outcome(document_id):
    try:
        memory.record_outcome(
            document_id,
            request.form.get("outcome", ""),
            request.form.get("lesson", ""),
            request.form.get("expectation_gap", ""),
        )
        return redirect(url_for("history_detail", document_id=document_id, saved="1"))
    except (ValueError, KeyError) as exc:
        record = memory.get(document_id)
        if not record:
            return render_template("history_detail.html", record=None, memory_error=str(exc)), 404
        record["risk"] = memory.estimate_risk(record)
        return render_template("history_detail.html", record=record, memory_error=str(exc)), 400


@app.route("/hindsight")
def hindsight():
    dash = memory.dashboard_context()
    return render_template(
        "hindsight.html",
        memories=dash["past_deals"],
        similar_deals=dash["similar_deals"],
        patterns=dash["patterns"],
        successful_strategies=dash["successful_strategies"],
        failed_strategies=dash["failed_strategies"],
        lessons=dash["lessons"],
        current_insights=dash["current_insights"],
        memory_error=memory.error,
    )


@app.route("/insights")
def insights():
    return render_template(
        "insights.html",
        insights=memory.risk_insights(),
        memory_error=memory.error,
    )


@app.route("/experiments")
def experiment_home():
    return render_template("experiment_overview.html", stats=experiment_insights(), recent=all_experiments()[:5])


@app.route("/experiments/new")
def experiment_new():
    return render_template("experiment_new.html")


@app.route("/experiments/history")
def experiment_history():
    return render_template("experiment_history.html", experiments=all_experiments())


@app.route("/experiments/insights")
def experiment_insight_page():
    return render_template("experiment_insights.html", data=experiment_insights())


@app.route("/experiments/settings")
def experiment_settings():
    return render_template("experiment_settings.html")


@app.route("/experiments/<experiment_id>")
def experiment_detail(experiment_id):
    record = get_experiment(experiment_id)
    if not record:
        return render_template("experiment_not_found.html"), 404
    return render_template("experiment_detail.html", experiment=record, analysis=analysis_for(record))


@app.get("/api/experiments")
def api_experiments():
    return jsonify(all_experiments(request.args.get("q", ""), request.args.get("result", "")))


@app.post("/api/experiments")
def api_create_experiment():
    try:
        record = create_experiment(request.get_json(silent=True) or request.form)
        return jsonify({"experiment": record, "analysis_url": url_for("experiment_detail", experiment_id=record["id"])}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.delete("/api/experiments/<experiment_id>")
def api_delete_experiment(experiment_id):
    if not remove_experiment(experiment_id):
        return jsonify({"error": "Experiment not found."}), 404
    return jsonify({"ok": True})


@app.post("/api/experiments/demo")
def api_experiment_demo():
    return jsonify({"inserted": load_demo()})


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
