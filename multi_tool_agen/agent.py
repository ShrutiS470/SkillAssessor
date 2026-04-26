import json
import re
from typing import Dict, Any

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext


# =========================
# Constants
# =========================
GEMINI_MODEL = "gemini-2.5-flash"
MAX_ROUNDS = 5
COMPLETION_PHRASE = "ASSESSMENT_COMPLETE"

# State keys
STATE_RESUME = "resume"
STATE_JD = "job_description"
STATE_INTERVIEW_ROUND = "interview_round"
STATE_TRANSCRIPT = "transcript"
STATE_REQUIRED_SKILLS = "required_skills"
STATE_PRIORITY_SKILLS = "priority_skills"
STATE_CURRENT_SKILL = "current_skill"
STATE_ASSESSOR_QUESTION = "assessor_question"
STATE_CANDIDATE_ANSWER = "candidate_answer"
STATE_SKILL_EVIDENCE = "skill_evidence"
STATE_SKILL_ASSESSMENT = "skill_assessment"
STATE_GAPS = "gaps"
STATE_LEARNING_PLAN = "learning_plan"
STATE_READY = "intake_ready"
STATE_EVALUATION_BUNDLE = "evaluation_bundle"


# =========================
# Helpers
# =========================
def _safe_json_loads(value: str, default):
    try:
        return json.loads(value)
    except Exception:
        return default


# =========================
# Tools
# =========================
def save_pasted_resume_jd(raw_input: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Parse a pasted message in this exact format and store it in session state:

    RESUME:
    ...

    JD:
    ...

    Call this only when the user has pasted both sections in one message.
    """
    pattern = r"RESUME:\s*(.*?)\s*JD:\s*(.*)"
    match = re.search(pattern, raw_input, re.DOTALL | re.IGNORECASE)

    if not match:
        return {
            "status": "error",
            "message": "Could not find both RESUME and JD sections. Ask the user to paste them in the required format."
        }

    resume = match.group(1).strip()
    jd = match.group(2).strip()

    if not resume or not jd:
        return {
            "status": "error",
            "message": "Resume or JD was empty after parsing."
        }

    tool_context.state[STATE_RESUME] = resume
    tool_context.state[STATE_JD] = jd
    tool_context.state[STATE_READY] = True

    return {
        "status": "ok",
        "resume_chars": len(resume),
        "jd_chars": len(jd)
    }


def merge_evaluation_bundle(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Read the JSON string stored at state['evaluation_bundle'] and merge it into session state.
    """
    raw = tool_context.state.get(STATE_EVALUATION_BUNDLE, "")
    bundle = _safe_json_loads(raw, {})

    if not isinstance(bundle, dict):
        return {"status": "error", "message": "evaluation_bundle is not valid JSON object"}

    if "interview_round" in bundle:
        tool_context.state[STATE_INTERVIEW_ROUND] = bundle["interview_round"]

    if "transcript" in bundle:
        tool_context.state[STATE_TRANSCRIPT] = bundle["transcript"]

    if "skill_evidence" in bundle:
        current = tool_context.state.get(STATE_SKILL_EVIDENCE, {})
        if not isinstance(current, dict):
            current = {}
        current.update(bundle["skill_evidence"])
        tool_context.state[STATE_SKILL_EVIDENCE] = current

    if "skill_assessment" in bundle:
        current = tool_context.state.get(STATE_SKILL_ASSESSMENT, {})
        if not isinstance(current, dict):
            current = {}
        current.update(bundle["skill_assessment"])
        tool_context.state[STATE_SKILL_ASSESSMENT] = current

    return {"status": "ok"}


def exit_loop(tool_context: ToolContext) -> Dict[str, Any]:
    """
    End the iterative interview loop.
    """
    tool_context.actions.escalate = True
    tool_context.actions.skip_summarization = True
    return {"status": "ok"}


# =========================
# Callback
# =========================
def initialize_state(callback_context: CallbackContext):
    state = callback_context.state
    state[STATE_RESUME] = state.get(STATE_RESUME, "")
    state[STATE_JD] = state.get(STATE_JD, "")
    state[STATE_INTERVIEW_ROUND] = state.get(STATE_INTERVIEW_ROUND, 0)
    state[STATE_TRANSCRIPT] = state.get(STATE_TRANSCRIPT, [])
    state[STATE_REQUIRED_SKILLS] = state.get(STATE_REQUIRED_SKILLS, "")
    state[STATE_PRIORITY_SKILLS] = state.get(STATE_PRIORITY_SKILLS, "")
    state[STATE_CURRENT_SKILL] = state.get(STATE_CURRENT_SKILL, "")
    state[STATE_ASSESSOR_QUESTION] = state.get(STATE_ASSESSOR_QUESTION, "")
    state[STATE_CANDIDATE_ANSWER] = state.get(STATE_CANDIDATE_ANSWER, "")
    state[STATE_SKILL_EVIDENCE] = state.get(STATE_SKILL_EVIDENCE, {})
    state[STATE_SKILL_ASSESSMENT] = state.get(STATE_SKILL_ASSESSMENT, {})
    state[STATE_GAPS] = state.get(STATE_GAPS, "")
    state[STATE_LEARNING_PLAN] = state.get(STATE_LEARNING_PLAN, "")
    state[STATE_READY] = state.get(STATE_READY, False)
    state[STATE_EVALUATION_BUNDLE] = state.get(STATE_EVALUATION_BUNDLE, "")


# =========================
# Intake agent
# =========================
intake_agent = LlmAgent(
    name="IntakeAgent",
    model=GEMINI_MODEL,
    include_contents="default",
    instruction="""
You are an intake assistant for a resume-vs-JD assessment workflow.

Session state fields:
- {resume}
- {job_description}
- {intake_ready}

Behavior:
1. If both {resume} and {job_description} are already present and {intake_ready} is true,
   respond exactly with:
   READY_FOR_ASSESSMENT

2. Otherwise ask the user to paste both in this exact format:

RESUME:
[paste full resume]

JD:
[paste full job description]

3. If the user's latest message contains both RESUME: and JD:, call the tool
   save_pasted_resume_jd using the ENTIRE user message as raw_input.

4. If the tool succeeds, respond exactly with:
   READY_FOR_ASSESSMENT

5. If the format is wrong, ask the user to paste again in the exact format.
""",
    tools=[save_pasted_resume_jd]
)


# =========================
# Skill extraction
# =========================
skill_extractor_agent = LlmAgent(
    name="SkillExtractorAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction="""
You are an assessment setup agent.

Resume:
```{resume}```

Job Description:
```{job_description}```

Task:
Extract required skills from the JD and compare them with the resume.

Output ONLY valid JSON in this format:
{
  "required_skills": [
    {
      "skill": "...",
      "category": "core|secondary|tool|behavioral",
      "priority": "high|medium|low",
      "resume_signal": "demonstrated|partial|adjacent|missing",
      "evidence": ["..."]
    }
  ]
}
""",
    output_key=STATE_REQUIRED_SKILLS
)

priority_projection_agent = LlmAgent(
    name="PriorityProjectionAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction="""
Read this JSON:
{required_skills}

Extract and rank the most important unresolved skills to assess first.

Output ONLY a valid JSON array of skill names.
""",
    output_key=STATE_PRIORITY_SKILLS
)


# =========================
# Interview loop agents
# =========================
assessor_agent = LlmAgent(
    name="AssessorAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction="""
You are a rigorous technical assessor.

Inputs:
- Resume:
```{resume}```
- JD:
```{job_description}```
- Priority skills:
{priority_skills}
- Transcript:
{transcript}
- Skill evidence:
{skill_evidence}
- Interview round:
{interview_round}

Task:
Select the single most important unresolved skill and ask exactly one probing question
that tests real proficiency through specifics: project, action, tooling, debugging,
tradeoffs, ownership, outcome.

Output ONLY valid JSON:
{
  "current_skill": "...",
  "question": "..."
}
""",
    output_key=STATE_ASSESSOR_QUESTION
)

candidate_agent = LlmAgent(
    name="CandidateAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction="""
You are role-playing the candidate.

Use ONLY:
- the resume,
- prior transcript evidence,
- cautious and honest inference from adjacent skills.

Inputs:
- Resume:
```{resume}```
- Transcript:
{transcript}
- Assessor question JSON:
{assessor_question}

Rules:
- Do not invent employers, projects, numbers, or tools.
- If experience is weak, say so clearly.
- Be concise and interview-like.

Output only the candidate answer text.
""",
    output_key=STATE_CANDIDATE_ANSWER
)

evaluator_agent = LlmAgent(
    name="EvaluatorAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction=f"""
You are an evidence-based evaluator.

Inputs:
- Resume:
```{{resume}}```
- JD:
```{{job_description}}```
- Required skills:
{{required_skills}}
- Assessor question JSON:
{{assessor_question}}
- Candidate answer:
{{candidate_answer}}
- Existing transcript:
{{transcript}}
- Existing skill evidence:
{{skill_evidence}}
- Existing skill assessment:
{{skill_assessment}}
- Interview round:
{{interview_round}}

Tasks:
1. Append this round to the transcript.
2. Update evidence for the assessed skill.
3. Rate the assessed skill as one of:
   - demonstrated
   - partial
   - adjacent
   - missing
4. Add confidence: high, medium, or low.
5. Increment the round by 1.

Output ONLY valid JSON:
{{
  "interview_round": <int>,
  "transcript": [
    {{
      "round": 1,
      "skill": "...",
      "question": "...",
      "answer": "...",
      "evaluation": {{
        "rating": "demonstrated|partial|adjacent|missing",
        "confidence": "high|medium|low",
        "notes": "...",
        "gaps": ["..."]
      }}
    }}
  ],
  "skill_evidence": {{
    "skill_name": {{
      "rating": "demonstrated|partial|adjacent|missing",
      "confidence": "high|medium|low",
      "evidence": ["..."],
      "gaps": ["..."]
    }}
  }},
  "skill_assessment": {{
    "skill_name": "demonstrated|partial|adjacent|missing"
  }}
}}
""",
    output_key=STATE_EVALUATION_BUNDLE
)

merge_agent = LlmAgent(
    name="MergeAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction="""
Call the merge_evaluation_bundle tool now. Do not output anything else.
""",
    tools=[merge_evaluation_bundle]
)

stop_decider_agent = LlmAgent(
    name="StopDeciderAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction=f"""
Decide whether to stop the interview.

Inputs:
- Interview round: {{interview_round}}
- Priority skills: {{priority_skills}}
- Skill assessment: {{skill_assessment}}

Rules:
- If interview_round >= {MAX_ROUNDS}, respond exactly: {COMPLETION_PHRASE}
- If all priority skills have at least one assessment, respond exactly: {COMPLETION_PHRASE}
- Otherwise respond exactly: CONTINUE
""",
    output_key="loop_decision"
)

loop_exit_agent = LlmAgent(
    name="LoopExitAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction=f"""
If loop_decision is exactly "{COMPLETION_PHRASE}", call the exit_loop tool.
Otherwise do nothing and output nothing.
""",
    tools=[exit_loop]
)

interview_loop = LoopAgent(
    name="InterviewLoop",
    sub_agents=[
        assessor_agent,
        candidate_agent,
        evaluator_agent,
        merge_agent,
        stop_decider_agent,
        loop_exit_agent,
    ],
    max_iterations=MAX_ROUNDS
)


# =========================
# Final analysis agents
# =========================
gap_analysis_agent = LlmAgent(
    name="GapAnalysisAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction="""
You are a hiring gap analyst.

Inputs:
- Required skills:
{required_skills}
- Skill evidence:
{skill_evidence}
- Skill assessment:
{skill_assessment}

Task:
Classify each required skill as:
- hire-ready
- workable-gap
- major-gap

Also identify adjacent foundations that make some missing skills realistic to learn.

Output ONLY valid JSON:
{
  "gaps": [
    {
      "skill": "...",
      "severity": "hire-ready|workable-gap|major-gap",
      "why": "...",
      "adjacent_foundation": ["..."]
    }
  ]
}
""",
    output_key=STATE_GAPS
)

learning_plan_agent = LlmAgent(
    name="LearningPlanAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction="""
You are a career coach creating a practical personalized learning plan.

Inputs:
- Resume:
```{resume}```
- JD:
```{job_description}```
- Required skills:
{required_skills}
- Skill evidence:
{skill_evidence}
- Gaps:
{gaps}

Task:
Create a realistic learning plan focused on adjacent, achievable next skills first.

Include:
1. Immediate next skills (1-2 weeks)
2. Short-term skills (2-6 weeks)
3. Medium-term skills (6-12 weeks)

For each skill include:
- why it matters for this JD
- why it is realistic for this candidate
- 2-4 curated resources
- estimated time
- one practice project

End with:
- what is realistically bridgeable soon
- what is not realistic in the near term

Output in Markdown.
""",
    output_key=STATE_LEARNING_PLAN
)

final_report_agent = LlmAgent(
    name="FinalReportAgent",
    model=GEMINI_MODEL,
    include_contents="none",
    instruction="""
You are the final reporting agent.

Inputs:
- Required skills:
{required_skills}
- Transcript:
{transcript}
- Skill evidence:
{skill_evidence}
- Skill assessment:
{skill_assessment}
- Gaps:
{gaps}
- Learning plan:
{learning_plan}

Write a clear final report in Markdown with these sections:
## Assessment summary
## Interview findings
## Skill ratings
## Major gaps
## Personalized learning plan

Be direct, structured, and practical.
""",
    output_key="final_report"
)


# =========================
# Root pipeline
# =========================
assessment_pipeline = SequentialAgent(
    name="AssessmentPipeline",
    sub_agents=[
        skill_extractor_agent,
        priority_projection_agent,
        interview_loop,
        gap_analysis_agent,
        learning_plan_agent,
        final_report_agent,
    ],
    description="Runs the full resume-vs-JD interview assessment after intake is complete."
)

root_agent = SequentialAgent(
    name="ResumeJDAssessmentApp",
    sub_agents=[
        intake_agent,
        assessment_pipeline,
    ],
    before_agent_callback=initialize_state,
    description="ADK Web app that accepts pasted resume and JD, then runs a 5-round simulated assessment."
)
