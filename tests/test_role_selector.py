"""Role dropdown checks (TA4-52)."""

import pytest

from birdseye.role_selector import ALL_POSTINGS, role_options
from birdseye.roles import NEEDS_REVIEW, ROLE_RULES, UNKNOWN


def test_options_are_every_defined_role_in_order():
    assert role_options(ROLE_RULES) == list(ROLE_RULES)
    assert len(role_options(ROLE_RULES)) == 7


def test_catch_all_labels_and_repeats_are_not_offered():
    names = ["Data Analyst", UNKNOWN, "Data Analyst", NEEDS_REVIEW, "Data Engineer"]
    assert role_options(names) == ["Data Analyst", "Data Engineer"]


def test_all_postings_comes_first_only_when_asked_for():
    assert role_options(["Data Analyst"], include_all=True) == [ALL_POSTINGS, "Data Analyst"]
    assert ALL_POSTINGS not in role_options(["Data Analyst"])


# --- Streamlit behaviour (skipped when Streamlit's test runner is unavailable) ---

def _dropdown_app(include_all):
    import streamlit as st

    from birdseye.role_selector import render_role_dropdown
    from birdseye.roles import ROLE_RULES

    st.session_state["result"] = render_role_dropdown(ROLE_RULES, key="role", include_all=include_all)


@pytest.fixture
def make_app():
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    return lambda include_all=False: AppTest.from_function(_dropdown_app, args=(include_all,))


def test_dropdown_lists_every_role_and_starts_with_nothing_chosen(make_app):
    at = make_app().run()
    assert not at.exception
    assert list(at.selectbox[0].options) == list(ROLE_RULES)
    assert at.selectbox[0].value is None
    assert at.session_state["result"] is None


def test_choosing_an_item_selects_it_and_choosing_another_replaces_it(make_app):
    at = make_app().run()
    at.selectbox[0].select("Data Analyst").run()
    assert at.session_state["result"] == "Data Analyst"
    at.selectbox[0].select("Registered Nurse").run()
    assert at.selectbox[0].value == "Registered Nurse"
    assert at.session_state["result"] == "Registered Nurse"  # the previous choice is gone


def test_dropdown_with_all_postings_starts_on_all_postings(make_app):
    at = make_app(include_all=True).run()
    assert at.selectbox[0].value == ALL_POSTINGS
    assert list(at.selectbox[0].options) == [ALL_POSTINGS, *ROLE_RULES]