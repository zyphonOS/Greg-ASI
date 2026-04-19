from __future__ import annotations

import os


os.environ["DISABLE_TICK_LOOP"] = "true"

from main import app  # noqa: E402


def main() -> None:
    with app.test_client() as client:
        home = client.get("/")
        html = home.get_data(as_text=True)
        assert home.status_code == 200
        assert 'id="wordcode-terminal"' in html
        assert 'id="wordcode-output"' in html
        assert 'id="wordcode-input"' in html
        assert "greg &gt;" in html

        js = client.get("/static/js/homepage.js")
        js_text = js.get_data(as_text=True)
        assert js.status_code == 200
        assert 'event.key === "/"' in js_text
        assert 'event.key === "Escape"' in js_text
        assert 'event.key === "`"' in js_text
        assert 'event.key === "ArrowUp"' in js_text
        assert 'fetch("/api/state"' in js_text
        assert 'fetch("/pikkaio/status"' in js_text
        assert 'fetch("/pikkaio/intent"' in js_text
        assert 'trimmed === "status"' in js_text
        assert 'trimmed === "drift"' in js_text
        assert 'trimmed === "help"' in js_text
        assert 'trimmed === "exit"' in js_text
        assert 'trimmed.startsWith("declare ")' in js_text

        state = client.get("/api/state")
        state_json = state.get_json()
        assert state.status_code == 200
        assert state_json["ok"] is True
        assert "reality_score" in state_json
        assert "epsilon" in state_json

    print("task9_verify.py: PASS")


if __name__ == "__main__":
    main()
