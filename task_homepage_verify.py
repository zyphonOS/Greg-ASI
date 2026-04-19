from __future__ import annotations

import os


os.environ["DISABLE_TICK_LOOP"] = "true"

from main import app  # noqa: E402


def main() -> None:
    with app.test_client() as client:
        home = client.get("/")
        html = home.get_data(as_text=True)
        assert home.status_code == 200
        assert "State what you are actually building." in html
        assert 'placeholder="I am building..."' in html
        assert 'id="nav-menu"' in html and "hidden" in html
        assert 'id="intent-submit"' in html and "hidden" in html
        assert "GregASI is running as a lightweight layered ecosystem." not in html
        assert 'static/css/homepage.css' in html
        assert 'static/js/homepage.js' in html

        css = client.get("/static/css/homepage.css")
        css_text = css.get_data(as_text=True)
        assert css.status_code == 200
        assert "#0a0a0a" in css_text
        assert "#00ff88" in css_text
        assert "JetBrains Mono" in css_text
        assert "border-radius" not in css_text
        assert "box-shadow" not in css_text
        assert "gradient" not in css_text

        js = client.get("/static/js/homepage.js")
        js_text = js.get_data(as_text=True)
        assert js.status_code == 200
        assert 'fetch("/pikkaio/intent"' in js_text
        assert 'fetch("/api/state"' in js_text
        assert "form.requestSubmit()" in js_text
        assert "setInterval(pollState, 3000)" in js_text
        assert 'Logged. Greg is watching.' in js_text
        assert 'Recorded. The line is open.' in js_text
        assert 'Declared. Drift measurement begins now.' in js_text

        tick = client.post("/api/greg/tick")
        assert tick.status_code == 200

        state = client.get("/api/state")
        state_json = state.get_json()
        assert state.status_code == 200
        assert state_json["ok"] is True
        assert "tick" in state_json
        assert "reality_score" in state_json
        assert "epsilon" in state_json
        assert "alive_age_seconds" in state_json

        declared = client.post("/pikkaio/intent", json={"description": "Verify the homepage declaration flow."})
        declared_json = declared.get_json()
        assert declared.status_code == 200
        assert declared_json["ok"] is True
        assert declared_json["intent"]["intent"] == "Verify the homepage declaration flow."

    print("task_homepage_verify.py: PASS")


if __name__ == "__main__":
    main()
