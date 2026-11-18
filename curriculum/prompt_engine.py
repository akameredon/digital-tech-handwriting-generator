"""
Prompt Engine for NERDC Digital Technologies Lesson Notes
Enforces a rigid pedagogical schema for every generated lesson.
"""

from typing import Dict, Any, Optional
from .nerdc_schemes import get_lesson, NERDC_DIGITAL_TECHNOLOGIES


LESSON_SCHEMA = """
You are an expert Nigerian secondary school Digital Technologies teacher.
Generate a complete, high-quality lesson note strictly following this structure.
Use simple, clear English suitable for Nigerian SSS students.
Do not invent topics outside the official NERDC scheme provided.

OUTPUT FORMAT (use exactly these headings):

**Class:** {class_level}
**Term:** {term}
**Week:** {week}
**Topic:** {topic}

**Behavioral Learning Objectives**
By the end of this lesson, students should be able to:
1. ...
2. ...
3. ...
(3–5 measurable objectives starting with action verbs)

**Key Concepts / Definitions**
- Concept 1: clear definition
- Concept 2: clear definition
...

**Step-by-Step Conceptual Explanation**
Write a clear, sequential explanation of the topic in 4–8 short paragraphs or numbered points.
Use everyday Nigerian classroom examples where possible.

**Practical / Worked Example**
Provide one concrete practical example.
If the topic involves code (Python, HTML, SQL, etc.), show complete, runnable code.
If it involves hardware or concepts, use a clear step-by-step illustration description.

**Class Activity / Guided Practice**
Describe a short activity students can do in 10–15 minutes.

**End-of-Lesson Quick Test**
1. ...
2. ...
3. ...
4. ...
5. ...
(5 short questions: mix of definition, application, and true/false)

**Assignment**
One clear take-home task.

Important rules:
- Stay 100% faithful to the official topic and content breakdown.
- Do not add advanced university-level material.
- Keep language age-appropriate for SSS students.
- Prefer Nigerian examples (e.g., using MTN, Glo, local schools, Naira, etc. when relevant).
"""


def build_prompt(class_level: str, term: str, week: int) -> Optional[str]:
    """
    Build a fully constrained prompt for a specific week.
    Returns None if the week does not exist in the official scheme.
    """
    lesson = get_lesson(class_level, term, week)
    if not lesson:
        return None

    topic = lesson["topic"]
    content = lesson["content"]

    # Skip pure exam/revision weeks for full generation
    if any(x in topic.lower() for x in ["midterm", "examination", "revision", "closing", "break", "mock"]):
        return f"""
Generate a short revision or assessment guide for:
Class: {class_level}
Term: {term}
Week: {week}
Topic: {topic}
Content: {content}

Keep it brief: list key points to revise and 5 sample questions.
"""

    prompt = LESSON_SCHEMA.format(
        class_level=class_level,
        term=term,
        week=week,
        topic=topic
    )

    prompt += f"""

OFFICIAL NERDC CONTENT FOR THIS WEEK:
Topic: {topic}
Content Breakdown: {content}

Generate the full lesson note now.
"""
    return prompt


def get_all_prompts_for_term(class_level: str, term: str) -> Dict[int, str]:
    """Return a dictionary of week → prompt for an entire term."""
    prompts = {}
    if class_level not in NERDC_DIGITAL_TECHNOLOGIES:
        return prompts
    if term not in NERDC_DIGITAL_TECHNOLOGIES[class_level]:
        return prompts

    for item in NERDC_DIGITAL_TECHNOLOGIES[class_level][term]:
        week = item["week"]
        p = build_prompt(class_level, term, week)
        if p:
            prompts[week] = p
    return prompts


# Example usage (for testing)
if __name__ == "__main__":
    sample = build_prompt("SS2", "Second Term", 2)
    print(sample[:800] if sample else "No lesson found")
