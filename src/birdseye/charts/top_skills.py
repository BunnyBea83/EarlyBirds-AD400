"""Show the most frequently requested skills for one role."""

import plotly.graph_objects as go


def top_skills_chart(role, summary):
    skills = summary["top_skills"]
    total = summary["total_postings"]
    title = f"{role}: {skills[0]['skill']} ranks first" if skills else f"{role}: No skills detected"
    fig = go.Figure()
    if skills:
        shares = [row["percentage"] for row in skills]
        labels = [row["skill"] for row in skills]
        fig.add_bar(
            x=shares, y=labels, orientation="h", text=[f"{share:.1f}%" for share in shares],
            textposition="auto", marker_color="#246a83",
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
        )
        fig.update_yaxes(autorange="reversed", automargin=True, categoryorder="array",
                         categoryarray=labels)
    else:
        fig.add_annotation(text="No skills detected", showarrow=False,
                           x=0.5, y=0.5, xref="paper", yref="paper")
        fig.update_yaxes(visible=False)
    fig.update_xaxes(range=[0, 100], ticksuffix="%", title="Share of postings")
    fig.update_layout(title=f"{title}<br><sup>{total:,} postings</sup>",
                      height=max(260, 125 + 30 * len(skills)),
                      margin=dict(l=24, r=40, t=75, b=50))
    return fig
