"""Starter vocabulary for TA4-25; extend deliberately as coverage is reviewed.

Aliases are alternate names, not related skills. The canonical name is also
a match term. Avoid ambiguous aliases such as R, Go, JS, or Excel on its own.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    """One canonical skill and its alternate spellings."""

    name: str
    aliases: tuple[str, ...] = ()
    category: str | None = None


SKILLS: tuple[Skill, ...] = (
    Skill("Python"),
    Skill("Java"),
    Skill("JavaScript"),
    Skill("TypeScript"),
    Skill("C++"),
    Skill("C#", ("C Sharp",)),
    Skill(".NET", ("dotnet",)),
    Skill("SQL", ("Structured Query Language",)),
    Skill("PostgreSQL", ("Postgres",)),
    Skill("MySQL"),
    Skill("SQLite"),
    Skill("MongoDB"),
    Skill("HTML", ("HTML5",)),
    Skill("CSS", ("CSS3",)),
    Skill("React", ("React.js", "ReactJS")),
    Skill("Angular"),
    Skill("Vue.js", ("VueJS",)),
    Skill("Node.js", ("NodeJS",)),
    Skill("Django"),
    Skill("Flask"),
    Skill("FastAPI"),
    Skill("Git"),
    Skill("Docker"),
    Skill("Kubernetes", ("K8s",)),
    Skill("Linux"),
    Skill("Amazon Web Services", ("AWS",)),
    Skill("Microsoft Azure", ("Azure",)),
    Skill("Google Cloud Platform", ("GCP", "Google Cloud")),
    Skill("Microsoft Excel", ("MS Excel",)),
    Skill("Power BI", ("PowerBI",)),
    Skill("Tableau"),
    Skill("pandas"),
    Skill("NumPy"),
    Skill("scikit-learn", ("sklearn",)),
    Skill("TensorFlow"),
    Skill("PyTorch"),
    Skill("Machine Learning"),
    Skill("Data Analysis"),
    Skill("Project Management"),
    Skill("Communication", ("Communication Skills",)),
)
