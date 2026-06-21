# ModAgent

Dynamic parallel debate graph architecture for content moderation, built on
LangGraph, Groq, and Instructor, with a Streamlit frontend.

## Architecture

```
intake -> classify (single combined Groq call) -> route (pure function)
       -> fan-out per destination (LangGraph Send)
           -> debate loop (Advocate vs Enforcer superagents) -> judge -> verdict
           -> hard-routed categories bypass debate -> escalate verdict
       -> fan-in -> verdicts
```

See `backend/` for the decoupled layers:
- `models/` -- typed Pydantic schema shared across the graph
- `config/policy_table.yaml` -- the category policy table (severity, debatable, rubric)
- `routing/router.py` -- pure function, zero network calls, fully unit-testable
- `classification/` -- the single LLM boundary call that scores all categories at once
- `debate/` -- superagents, judge, termination logic, and the LangGraph wiring
- `graph_runner.py` -- headless entry point used by both Streamlit and tests

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env  # set GROQ_API_KEY
```

## Run

```bash
streamlit run app/streamlit_app.py
```

## Test

```bash
pytest
```
