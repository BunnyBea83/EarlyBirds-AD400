"""Compare posting shares for the most requested skills across roles."""

from collections import Counter

import plotly.graph_objects as go


def skill_heatmap(roles):
    totals = Counter()
    by_role = {}
    for role, row in roles.items():
        by_role[role] = {skill["skill"]: skill["posting_count"] for skill in row["skills"]}
        totals.update(by_role[role])
    top = sorted(totals, key=lambda skill: (-totals[skill], skill.casefold(), skill))[:20]
    fig = go.Figure()
    if not top:
        fig.add_annotation(text="No skills detected across these roles", showarrow=False,
                           x=0.5, y=0.5, xref="paper", yref="paper")
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        return fig.update_layout(title="No skill demand to compare")

    values = [
        [100 * by_role[role].get(skill, 0) / row["total_postings"] if row["total_postings"]
         else None for role, row in roles.items()]
        for skill in top
    ]
    labels = [f"{role}<br>({row['total_postings']:,} postings)" for role, row in roles.items()]
    fig.add_heatmap(
        x=labels, y=top, z=values, zmin=0, zmax=100, colorscale="Blues",
        colorbar=dict(title="Share of<br>postings", ticksuffix="%"),
        hovertemplate="%{y}<br>%{x}<br>%{z:.1f}%<extra></extra>",
    )
    for skill, row in zip(top, values):
        for label, share in zip(labels, row):
            fig.add_annotation(x=label, y=skill, text="N/A" if share is None else f"{share:.1f}%",
                               showarrow=False, font=dict(color="white" if share is not None
                                                          and share >= 65 else "#17212b"))
    fig.update_xaxes(side="top", automargin=True)
    fig.update_yaxes(autorange="reversed", automargin=True)
    return fig.update_layout(
        title=f"{top[0]} ranks first across these roles",
        height=max(360, 160 + len(top) * 28),
        width=max(800, 155 * len(labels)),
    )
