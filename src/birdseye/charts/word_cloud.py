"""Size canonical skill labels by the number of postings mentioning them."""

from wordcloud import WordCloud

CAPTION = "Larger text means the skill appears in more postings for this role."


def skill_word_cloud(summary):
    frequencies = {row["skill"]: row["posting_count"] for row in summary["skills"]}
    if not frequencies:
        return None
    return WordCloud(
        width=1000, height=500, background_color="white", colormap="viridis",
        random_state=15, prefer_horizontal=1, max_words=30, min_font_size=14,
    ).generate_from_frequencies(frequencies)
