from __future__ import annotations

import os


os.environ["DISABLE_TICK_LOOP"] = "true"

from main import app  # noqa: E402


def main() -> None:
    routes = ["/", "/pikkaio", "/truth", "/dashboard", "/revenue", "/zyphonos"]
    with app.test_client() as client:
        for route in routes:
            response = client.get(route, follow_redirects=True)
            html = response.get_data(as_text=True)
            assert response.status_code == 200, (route, response.status_code)
            assert "static/css/base.css" in html, route
            assert "static/js/base.js" in html, route
            assert 'id="nav-menu"' in html, route
            assert 'id="tick-pulse"' in html, route
            assert ">GREG<" in html, route
    print("shell_verify: PASS")


if __name__ == "__main__":
    main()
