"""Batter search box and the generic spray-chart background."""

import os

import pytest
from PIL import Image

os.environ.setdefault("USE_API_MODE", "true")

import app as app_module  # noqa: E402

ROOT = os.path.dirname(app_module.__file__)


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_index_has_the_batter_search_box(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Search players or teams" in res.data
    # The search box is a text field, so it must not inherit the dropdown arrow.
    assert b".field-search" in res.data


def test_default_background_is_the_generic_image():
    assert app_module.DEFAULT_BACKGROUND == "img/background_generic.png"
    assert os.path.exists(os.path.join(ROOT, app_module.DEFAULT_BACKGROUND))


def test_generic_background_matches_the_pixel_calibration():
    """Dots are placed by pixel math, so the image must be the size it assumes."""
    with Image.open(os.path.join(ROOT, app_module.DEFAULT_BACKGROUND)) as img:
        w, h = img.size
    cfg = app_module.SPRAY_PIXEL_CONFIG
    for key in ("lf_pole_x_px", "rf_pole_x_px", "home_x_px"):
        assert 0 <= cfg[key] < w, f"{key} falls outside the background image"
    for key in ("outfield_top_px", "outfield_bottom_px", "lf_pole_y_px", "rf_pole_y_px"):
        assert 0 <= cfg[key] < h, f"{key} falls outside the background image"
    assert (w, h) == (2340, 1560)


def test_generic_background_script_matches_app_calibration():
    """scripts/make_generic_background.py hard-codes the same pixels as app.py."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mgb", os.path.join(ROOT, "scripts", "make_generic_background.py"))
    mgb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mgb)
    cfg = app_module.SPRAY_PIXEL_CONFIG
    assert mgb.HOME == (cfg["home_x_px"], cfg["home_y_px"])
    assert mgb.LF_POLE == (cfg["lf_pole_x_px"], cfg["lf_pole_y_px"])
    assert mgb.RF_POLE == (cfg["rf_pole_x_px"], cfg["rf_pole_y_px"])


def test_json_picker_only_lists_batters_with_enough_data(monkeypatch):
    """A batter with too few balls draws an empty chart, so the picker drops them."""
    import pandas as pd

    good = {"player_id": "g", "player_name": "Good, Gary"}
    bad = {"player_id": "b", "player_name": "Bad, Bob"}
    monkeypatch.setattr(app_module, "_json_qualifying_cache", None)
    monkeypatch.setattr(app_module, "get_unique_players_with_spray_data", lambda: [good, bad])
    n = app_module.MIN_QUALIFYING_BALLS
    frames = {"g": pd.DataFrame({"x": range(n), "y": range(n)}),
              "b": pd.DataFrame({"x": [1, 2], "y": [1, 2]})}
    monkeypatch.setattr(app_module, "get_player_spray_dataframe", lambda pid: frames[pid])
    assert app_module._json_players_with_enough_data() == [good]
