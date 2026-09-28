from flask import Flask, render_template, request, redirect, url_for

from agent.analysis import analyze_deal
from hindsight.memory import HindsightMemory

app = Flask(__name__)
memory = HindsightMemory()


@app.teardown_appcontext
def close_memory(exception):
    memory.close()


@app.route("/")
def home():
    return render_template("index.html", memory_count=len(memory.all()), memory_ready=memory.ready, memory_error=memory.error, form_data={})


@app.route("/deal", methods=["GET", "POST"])
def deal():
    if request.method == "GET":
        return redirect(url_for("home"))
    current = {key: request.form.get(key, "").strip() for key in ("company", "deal_value", "customer", "industry", "situation")}
    if not memory.ready:
        return render_template("index.html", memory_count=0, memory_ready=False, memory_error=memory.error, form_data=current), 503
    try:
        recalled = memory.recall(current)
        analysis = analyze_deal(current, recalled)
        retained = memory.retain(current, analysis)
        return render_template("deal.html", deal=current, recalled=recalled, analysis=analysis, retained=retained, memory_count=len(memory.all()))
    except Exception as exc:
        error = f"Hindsight request failed: {memory._safe_error(exc)}"
        return render_template("index.html", memory_count=0, memory_ready=False, memory_error=error, form_data=current), 502


@app.route("/hindsight")
def hindsight():
    return render_template("hindsight.html", memories=memory.all(), memory_count=len(memory.all()), memory_ready=memory.ready, memory_error=memory.error)


if __name__ == "__main__":
    # VS Code's debugger and Flask's reloader can otherwise start two processes.
    app.run(debug=True, use_reloader=False)
