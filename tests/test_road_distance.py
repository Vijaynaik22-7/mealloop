"""Road distance: parsing, fallbacks and the on/off switch.

No test here touches the internet: urllib is replaced by a fake.
"""
import json
from types import SimpleNamespace

import pytest

from app import create_app
from app.recipients import distance


class FakeResponse:
    """Stands in for what urlopen returns."""

    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def place(pid, lat, lng):
    return SimpleNamespace(id=pid, latitude=lat, longitude=lng)


NGO = place(1, 12.2958, 76.6394)
FOOD_A = place(10, 12.3051, 76.6551)
FOOD_B = place(11, 12.3100, 76.6200)

GOOD_ANSWER = {"code": "Ok", "distances": [[0, 2945.2, 3592.9]]}


@pytest.fixture(autouse=True)
def reset_pause():
    """Every test starts with no 'OSRM is down' pause."""
    distance._skip_until = 0.0
    yield
    distance._skip_until = 0.0


def fake_urlopen_returning(payload, calls):
    def fake(http_request, timeout=None):
        calls.append(http_request.full_url)
        return FakeResponse(payload)
    return fake


def test_road_distances_are_parsed_in_km(monkeypatch):
    calls = []
    monkeypatch.setattr(
        distance.urllib.request, "urlopen",
        fake_urlopen_returning(GOOD_ANSWER, calls))

    result = distance.road_distances_km(NGO, [FOOD_A, FOOD_B])

    assert result == {10: pytest.approx(2.9452), 11: pytest.approx(3.5929)}
    assert len(calls) == 1  # ONE call for all donations


def test_coordinates_are_sent_longitude_first(monkeypatch):
    calls = []
    monkeypatch.setattr(
        distance.urllib.request, "urlopen",
        fake_urlopen_returning(GOOD_ANSWER, calls))

    distance.road_distances_km(NGO, [FOOD_A, FOOD_B])

    assert "76.6394,12.2958;76.6551,12.3051;76.62,12.31" in calls[0]


def test_no_call_when_ngo_has_no_location(monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("the network must not be used")
    monkeypatch.setattr(distance.urllib.request, "urlopen", must_not_run)

    no_location = place(2, None, None)
    assert distance.road_distances_km(no_location, [FOOD_A]) == {}


def test_donation_without_location_is_skipped(monkeypatch):
    calls = []
    monkeypatch.setattr(
        distance.urllib.request, "urlopen",
        fake_urlopen_returning(
            {"code": "Ok", "distances": [[0, 2945.2]]}, calls))

    result = distance.road_distances_km(NGO, [FOOD_A, place(12, None, None)])

    assert list(result) == [10]


def test_failure_returns_empty_and_pauses_further_calls(monkeypatch):
    calls = []

    def broken(http_request, timeout=None):
        calls.append(1)
        raise OSError("no internet")
    monkeypatch.setattr(distance.urllib.request, "urlopen", broken)

    assert distance.road_distances_km(NGO, [FOOD_A]) == {}
    assert distance.road_distances_km(NGO, [FOOD_A]) == {}
    assert len(calls) == 1  # the second call was skipped during the pause


@pytest.mark.parametrize("bad_answer", [
    {"code": "InvalidQuery"},
    {"code": "Ok", "distances": [[0]]},      # wrong size
    {"code": "Ok"},                          # no distances at all
    ["not", "a", "dict"],
])
def test_bad_answers_fall_back(monkeypatch, bad_answer):
    monkeypatch.setattr(
        distance.urllib.request, "urlopen",
        fake_urlopen_returning(bad_answer, []))

    assert distance.road_distances_km(NGO, [FOOD_A]) == {}


def test_unreachable_place_is_left_out(monkeypatch):
    monkeypatch.setattr(
        distance.urllib.request, "urlopen",
        fake_urlopen_returning(
            {"code": "Ok", "distances": [[0, None, 3592.9]]}, []))

    result = distance.road_distances_km(NGO, [FOOD_A, FOOD_B])

    assert list(result) == [11]


def test_labels():
    assert distance.distance_label(2.94, by_road=True) == (
        "about 2.9 km by road")
    assert distance.distance_label(2.04) == "about 2.0 km (straight line)"
    assert distance.best_distance_label(NGO, FOOD_A, 2.94) == (
        "about 2.9 km by road")
    # No road distance: straight-line text, about 1.9 km for these points
    assert "(straight line)" in distance.best_distance_label(NGO, FOOD_A)
    assert distance.best_distance_label(
        NGO, place(13, None, None)) == "distance unknown"


def test_switch_is_off_in_tests_and_can_be_forced():
    testing_app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with testing_app.app_context():
        assert distance.road_distance_enabled() is False

    forced_app = create_app({
        "TESTING": True,
        "ROAD_DISTANCE_ENABLED": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with forced_app.app_context():
        assert distance.road_distance_enabled() is True


def test_environment_variable_turns_it_off(monkeypatch):
    live_app = create_app({
        "TESTING": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with live_app.app_context():
        monkeypatch.delenv("ROAD_DISTANCE", raising=False)
        assert distance.road_distance_enabled() is True
        monkeypatch.setenv("ROAD_DISTANCE", "off")
        assert distance.road_distance_enabled() is False
