"""Unit tests for the public extraction contract and catalog invariants."""

import pytest

from birdseye.skill_extraction import extract_skills
from birdseye.skills_catalog import SKILLS


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Python, PYTHON and Postgres/PostgreSQL", ["Python", "PostgreSQL"]),
        ("JavaScript development", ["JavaScript"]),
        ("C++, C# and .NET", ["C++", "C#", ".NET"]),
        ("SQL and PostgreSQL", ["SQL", "PostgreSQL"]),
        ("Strong communication skills", ["Communication"]),
        ("No matching vocabulary here", []),
        ("", []),
        (" \t\n ", []),
        ("POWER\n BI and machine\t learning", ["Power BI", "Machine Learning"]),
        ("(Python); [SQL], C++/C#; .NET.", ["Python", "C++", "C#", ".NET", "SQL"]),
        ("dotnet, C Sharp, K8s, sklearn", ["C#", ".NET", "Kubernetes", "scikit-learn"]),
        ("React.js ReactJS React", ["React"]),
        ("AWS then Python then AWS", ["Python", "Amazon Web Services"]),
        ("Python-based tools", ["Python"]),
        ("No Python experience required", ["Python"]),
    ],
)
def test_extract_skills(description, expected):
    assert extract_skills(description) == expected


@pytest.mark.parametrize(
    "description",
    ["Javanese", "JavaScripted", "MySQLConnector", "GitHub", "CPython",
     "C+++", "C#sharp", ".NETwork", "python_tools", "éPython", "Go R JS"],
)
def test_does_not_match_partial_words_or_unsupported_short_names(description):
    assert extract_skills(description) == []


@pytest.mark.parametrize("description", [None, 123, [], {}, b"Python"])
def test_rejects_non_string_input(description):
    with pytest.raises(TypeError, match="description must be a string"):
        extract_skills(description)


def test_every_catalog_name_and_alias_resolves_to_its_canonical_skill():
    for skill in SKILLS:
        for term in (skill.name, *skill.aliases):
            assert extract_skills(term) == [skill.name], term


def test_catalog_terms_are_nonempty_and_unique_after_normalization():
    terms = [
        " ".join(term.casefold().split())
        for skill in SKILLS
        for term in (skill.name, *skill.aliases)
    ]
    assert all(terms)
    assert len(terms) == len(set(terms))


def test_calls_return_independent_results():
    result = extract_skills("Python")
    result.clear()
    assert extract_skills("Python") == ["Python"]
