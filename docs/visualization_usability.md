# Validate the skill visualizer

Start the dashboard with `streamlit run app.py`. Use the cleaned and extracted
database if available. For a repeatable dry run, select **Use synthetic demo
data** and ask about Marketing Manager. In the demo, Project management and
Writing occur in both postings, while Market research occurs in one.

Before the session, select a role with at least three skills. For real data, run
`python -m birdseye.skill_summary data/processed/birdseye.db` and consult that
role's ranked skills. Keep the answer key out of the participant's view. Skills
with a count above third place are required. Any skill tied at the third-place
count can fill the remaining slots.

Read this task aloud while displaying the dashboard: “Using these visuals, what
are the three most requested skills for [role]?” Start the timer when the
participant sees the dashboard and has received the task. Provide no guidance
while timing. Stop when the participant supplies three answers or reaches one
minute. Record the result, then ask what they found confusing.

| Field | Session record |
| --- | --- |
| Date, dashboard revision, and data source | |
| Role | |
| Participant answers verbatim | |
| Elapsed seconds | |
| Guidance given | |
| Correctness and ties accepted | |
| Pass or fail | |
| Feedback | |
| Changes and retest result | |

A pass requires three correct, distinct skills without guidance in 60 seconds
or less. Record a follow-up for confusing titles, labels, or ordering and repeat
the task with a new participant after the fix. Keep this record free of personal
identifiers. The automated checks validate ranking and scoring. The participant
session is pending.
