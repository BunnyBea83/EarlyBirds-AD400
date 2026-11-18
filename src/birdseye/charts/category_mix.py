"""Compare the composition of skill–posting matches across roles."""

import plotly.graph_objects as go
from plotly.colors import qualitative


def category_mix_chart(roles):
    categories_by_role = {
        role: {row["category"]: row for row in summary["categories"]}
        for role, summary in roles.items()
    }
    names = sorted({category for rows in categories_by_role.values() for category in rows})
    fig = go.Figure()
    if names:
        for index, name in enumerate(names):
            rows = [categories_by_role[role].get(name, {}) for role in roles]
            shares = [row.get("match_percentage", 0) for row in rows]
            fig.add_bar(
                name=name, x=shares, y=list(roles), orientation="h",
                marker_color=qualitative.Safe[index % len(qualitative.Safe)],
                text=[f"{share:.1f}%" if share else "" for share in shares],
                textposition="inside",
                customdata=[row.get("match_count", 0) for row in rows],
                hovertemplate="%{y}<br>" + name + ": %{x:.1f}% (%{customdata} matches)<extra></extra>",
            )
    for role, categories in categories_by_role.items():
        if not categories:
            fig.add_annotation(x=0, y=role, text="No skills detected", showarrow=False, xanchor="left")

    match_totals = {
        name: sum(rows.get(name, {}).get("match_count", 0) for rows in categories_by_role.values())
        for name in names
    }
    leader = max(names, key=match_totals.get) if names else None
    title = f"{leader} has the most skill matches across roles" if leader else "No skill mix to compare"
    fig.update_xaxes(range=[0, 100], ticksuffix="%", title="Share of skill matches within each role")
    fig.update_yaxes(autorange="reversed", automargin=True, categoryorder="array",
                     categoryarray=list(roles))
    return fig.update_layout(
        title=title, barmode="stack", height=max(400, 175 + 40 * len(roles)),
        legend_title="Skill category", uniformtext_minsize=9, uniformtext_mode="hide",
    )
