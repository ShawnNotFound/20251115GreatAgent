INPUT_PROMPT = """You are the Intake Agent. Normalize the user query, infer tasks and guardrails.
Respond as JSON with keys normalized_query, engagement_mode (agents_only|engage_human), tools_needed (list), constraints (list).

User query: {user_query}
Preferred mode: {mode}
Guardrails: {guardrails}
"""

DECOMPOSE_PROMPT = """You are the Task Decomposer. Create a short ordered list of agent steps for the query.
Return JSON {"workflow_plan": ["ResearchAgent", ...]}.

Query: {query}
Tools: {tools}
Constraints: {constraints}
"""

WORKFLOW_PROMPT = """Decorate the workflow plan with notes for UI timeline. Respond as JSON with 'steps' (list of objects with agent, notes, requires_human) and optional control_panel updates.

Plan: {plan}
Mode: {mode}
"""

RESEARCH_PROMPT = """Synthesize three candidate answers from given search snippets. Respond JSON {"candidates": [..]}.

Query: {query}
Snippets: {snippets}
"""

ANALYSIS_PROMPT = """Compare the supplied candidates and output JSON {"options": [..], "rationale": "..."}.

Candidates: {candidates}
"""

VALIDATION_PROMPT = """Validate the draft answer. Return JSON {"is_consistent": bool, "confidence": 0-1, "notes": "..."}.

Draft: {draft}
"""

OUTPUT_PROMPT = """Compose the final answer referencing validation notes. Return JSON {"final_text": "..."}.

Selected option: {option}
Validation: {validation}
"""
