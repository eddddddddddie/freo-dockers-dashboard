"""Admin pages: the Wharf-ai usage log, shown only to the people listed in
WHARF_ADMINS (comma separated emails, in secrets: the repo is public)."""

import pandas as pd
import streamlit as st

import auth
import usage as U


@st.dialog("Wharf-ai usage", width="large")
def usage_log():
    """Questions asked, tools used, tokens and estimated cost."""
    if not U.is_admin((auth.current_user() or {}).get("email")):
        return                     # only for the people in WHARF_ADMINS
    s = U.summary()
    c = st.columns(4)
    c[0].metric("Questions today", f"{s['today']} / {s['cap']}")
    c[1].metric("Cost today (US$)", f"{s['today_cost']:.2f}")
    c[2].metric("Questions, last 7 days", s["week"])
    c[3].metric("Cost, last 7 days (US$)", f"{s['week_cost']:.2f}")
    rows = U.recent()
    if not rows:
        st.info("No questions logged yet.")
        return
    df = pd.DataFrame(rows)
    for col in ("user_email", "answer", "unbacked"):
        df[col] = df.get(col, pd.Series([None] * len(df))).fillna("")
    df["rating"] = df.get("rating", pd.Series([None] * len(df))).map({1: "👍", 0: "👎"}).fillna("")
    df["unbacked"] = df["unbacked"].str.replace(r'[\[\]"]', "", regex=True)
    df["tools"] = df["tools"].str.replace(r'[\[\]"]', "", regex=True)
    df["ok"] = df["ok"].map({1: "yes", 0: "failed"})
    rated = (df["rating"] != "").sum()
    down = (df["rating"] == "👎").sum()
    flagged = (df["unbacked"] != "").sum()
    st.caption(f"Rated answers: {rated} ({down} thumbs down) · answers with a number not matched "
               f"to a calculation: {flagged}")
    view = df[["ts", "user_email", "rating", "question", "unbacked", "tools", "steps",
               "input_tokens", "output_tokens", "cache_read", "cost_usd", "ok"]]
    st.dataframe(view.rename(columns={
        "ts": "When", "user_email": "Who", "rating": "Rated", "question": "Question",
        "unbacked": "Not matched", "tools": "Tools", "steps": "Steps", "input_tokens": "Input",
        "output_tokens": "Output", "cache_read": "Cache read", "cost_usd": "US$", "ok": "OK"}),
        hide_index=True, width="stretch", height=340)
    # With the answers, for review (evals/review_feedback.py turns thumbs down
    # into candidate test cases). Download before a redeploy wipes the log.
    st.download_button("Download the log with answers (CSV)",
                       df.drop(columns=["sid"], errors="ignore").to_csv(index=False),
                       file_name=f"wharf_usage_{U.today()}.csv", mime="text/csv")
    st.caption("Costs are estimates at claude-sonnet-5-5 list prices. The log is stored on the "
               "app's own disk: on Streamlit Cloud it starts again after a restart or redeploy, "
               "so download it first if you want to keep the ratings.")
