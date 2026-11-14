from birdseye.roles import map_roles


def test_role_mapping_preserves_titles_and_distinguishes_occupations():
    titles = [" Sr. DATA analyst II ", "Data Engineer", "Data Scientist",
              "Marketing Mgr.", None, "Data Analyst / Data Engineer",
              "Specialist", " Sr. DATA analyst II "]
    rows, report = map_roles({"job_id": i, "title": title} for i, title in enumerate(titles))
    assert [row["role"] for row in rows] == [
        "Data Analyst", "Data Engineer", "Data Scientist", "Marketing Manager",
        "Unknown", "Needs review", "Unknown", "Data Analyst",
    ]
    assert rows[0] == {"job_id": 0, "title": titles[0],
                       "normalized_title": "senior data analyst ii", "role": "Data Analyst"}
    assert report["counts"] == {"mapped": 5, "unmapped": 2, "ambiguous": 1}
    assert report["examples"]["ambiguous"] == [titles[5]]
