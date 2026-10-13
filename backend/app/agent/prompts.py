_SUBTASK_BLOCK = """

## YOUR ASSIGNED SUB-TASK
{task}

Answer ONLY this sub-task. Another specialist is handling the rest of the user's request in
parallel, and your output will be merged with theirs. So: no greeting, no closing summary, and
no attempt to cover the parts you were not given. Just the substance, formatted as usual.
"""

# Sent as a final user turn when a worker has exhausted its tool budget.
# Without it the model keeps trying to call tools, and because no tool schema is
# bound on that last call it serializes the call into the message content as raw
# provider markup (e.g. DeepSeek's <|DSML|tool_calls>), which then becomes the
# worker's "answer" and the real data is lost.
FINAL_SYNTHESIS_INSTRUCTION = """You have no tool calls left. The data above is everything you will get.

Write your final answer now, using only what has already been gathered. Do NOT request another
tool and do NOT emit any tool-call syntax — anything that is not prose is shown to the user
verbatim. If a piece of the request is genuinely missing from the data, say briefly what is
missing and answer fully with the rest. Never claim the data "did not come through" if a value
for it appears anywhere above.
"""


def with_subtask(base_prompt: str, task: str | None) -> str:
    """Focus a worker's system prompt on one sub-task during fan-out.

    Appends to the existing prompt rather than injecting an extra message, so the
    worker's tool rules and formatting conventions still apply.
    """
    if not task:
        return base_prompt
    return base_prompt + _SUBTASK_BLOCK.format(task=task)


# Output contract for Opgg answers. Lives here so the
# Synthesizer can enforce the identical format on fan-out turns.
OPGG_OUTPUT_FORMAT = """\n## OUTPUT FORMATTING
- Present data in **clean Markdown** with headers, bullet points, and bold key numbers.
- For builds: show items as an ordered list with item names bolded.
- For stats: always include **win rate**, **pick rate**, and **sample size** when available.
- For player profiles: format as a summary card with rank, top champions, and recent performance.
- Round percentages to 1 decimal place (e.g., 52.3%, not 52.2847%).
- Add a brief ⚠️ disclaimer if the sample size is very small (<1000 games) — stats may not be reliable.
- End with a **one-sentence takeaway** that gives the user an actionable insight.
"""

# Output contract for Research answers. Lives here so the
# Synthesizer can enforce the identical format on fan-out turns.
RESEARCH_OUTPUT_FORMAT = """\n## REPORT STRUCTURE
Your final response MUST follow this format:

### Current Meta Status
_Where does this champion/topic stand in the current meta? Include any relevant win rate or pick rate context._

### Community Sentiment
_What are players saying? Quote or paraphrase specific Reddit threads, pro opinions, or community debates. Mention if sentiment is divided._

### The Verdict
_Your clear, opinionated recommendation. Don't sit on the fence — give the user a direct answer with reasoning._

### Sources
_List 2-3 of the most relevant sources with brief descriptions of what they contain._

## TONE & STYLE
- Be conversational but authoritative — like an analyst on a League podcast.
- Take a clear stance on controversial topics, but acknowledge the other side.
- Use **bold** for emphasis and key data points.
- Keep the total response to ~300 words — dense and valuable, not padded.
- Never say "based on my research" — just present the findings confidently.
"""


# Which contract each specialist answers under, for the Synthesizer to look up.
WORKER_OUTPUT_FORMATS = {
    "OPGGWorker": OPGG_OUTPUT_FORMAT,
    "ResearchWorker": RESEARCH_OUTPUT_FORMAT,
}
