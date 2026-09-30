from flask import Flask, render_template, request, redirect, url_for

from agent.analysis import DEAL_FIELDS, analyze_deal
from hindsight.memory import HindsightMemory

app = Flask(__name__)
memory = HindsightMemory()


@app.teardown_appcontext
def close_memory(exception):
    memory.close()


def _form_deal():
    return {key: request.form.get(key, "").strip() for key in DEAL_FIELDS}


@app.route("/")
def home():
    return render_template(
        "index.html",
        memory_count=len(memory.all()),
        memory_ready=memory.ready,
        memory_error=memory.error,
        form_data={},
    )


@app.route("/deal", methods=["GET", "POST"])
def deal():
    if request.method == "GET":
        return redirect(url_for("home"))
    current = _form_deal()
    try:
        # RECALL similar past deals, REFLECT + DECIDE in analyze_deal, then RETAIN.
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
            memory_count=len(memory.all()),
            memory_ready=memory.ready,
            memory_error=memory.error,
        )
    except Exception as exc:
        error = f"Hindsight request failed: {memory._safe_error(exc)}"
        return render_template(
            "index.html",
            memory_count=len(memory.all()),
            memory_ready=memory.ready,
            memory_error=error,
            form_data=current,
        ), 502


@app.route("/hindsight")
def hindsight():
    dash = memory.dashboard_context()
    return render_template(
        "hindsight.html",
        memories=dash["past_deals"],
        memory_count=len(dash["past_deals"]),
        memory_ready=True,
        memory_error=memory.error,
        similar_deals=dash["similar_deals"],
        patterns=dash["patterns"],
        successful_strategies=dash["successful_strategies"],
        failed_strategies=dash["failed_strategies"],
        lessons=dash["lessons"],
        current_insights=dash["current_insights"],
    )


if __name__ == "__main__":
    # VS Code's debugger and Flask's reloader can otherwise start two processes.
    app.run(debug=True, use_reloader=False)
