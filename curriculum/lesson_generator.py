"""Deterministic complete lesson-note generation from the official curriculum."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Optional

from .nerdc_schemes import get_lesson
from .validator import validate_lesson_structure


@dataclass(frozen=True)
class LessonDraft:
    class_level: str
    term: str
    week: int
    topic: str
    markdown: str
    validation: dict


class CompleteLessonGenerator:
    """Produce a coherent, curriculum-bounded lesson note without inventing a topic."""

    @staticmethod
    def _concepts(content: str, topic: str) -> List[str]:
        parts = [part.strip(" .") for part in re.split(r";|\.|\n|,", content) if part.strip()]
        concepts = []
        for part in parts:
            phrase = part if len(part) <= 90 else part[:87].rstrip() + "..."
            if phrase.casefold() not in {item.casefold() for item in concepts}:
                concepts.append(phrase)
        return (concepts or [topic])[:6]

    @staticmethod
    def _objectives(topic: str, concepts: List[str]) -> List[str]:
        verbs = ["define", "explain", "identify", "apply", "evaluate"]
        objectives = [f"{verb.title()} {concept.lower()} in the context of {topic}." for verb, concept in zip(verbs, concepts)]
        return objectives[:5] or [f"Explain the main ideas in {topic}."]

    def generate(self, class_level: str, term: str, week: int) -> Optional[LessonDraft]:
        lesson = get_lesson(class_level, term, week)
        if not lesson:
            return None
        topic, content = lesson["topic"], lesson["content"]
        concepts = self._concepts(content, topic)
        objectives = self._objectives(topic, concepts)
        concept_lines = "\n".join(f"- **{concept.split(':', 1)[0].strip().title()}:** {concept}" for concept in concepts)
        objective_lines = "\n".join(f"{index}. {objective}" for index, objective in enumerate(objectives, 1))
        explanation = "\n\n".join(
            f"**Step {index}: {concept.split(':', 1)[0].strip().title()}**\n"
            f"The teacher introduces {concept.lower()} using a familiar classroom example. "
            f"Learners observe the idea, discuss why it matters, and connect it to the topic of {topic.lower()}. "
            "The class records the important terms and checks each step before moving forward."
            for index, concept in enumerate(concepts[:5], 1)
        )
        markdown = f"""**Class:** {class_level}
**Term:** {term}
**Week:** {week}
**Topic:** {topic}

## Behavioral Learning Objectives
By the end of this lesson, students should be able to:
{objective_lines}

## Key Concepts / Definitions
{concept_lines}

## Step-by-Step Conceptual Explanation
{explanation}

## Practical / Worked Example
A teacher can demonstrate **{topic}** with a short classroom example. Begin by writing the task on the board, identify the relevant concept, and complete one step at a time. Students then repeat the example in pairs, compare their result with the worked steps, and explain where an error would occur. Where a computer is required, learners should save their work with a clear filename and check the output before submitting it.

## Class Activity / Guided Practice
In groups of three, students create a simple example related to **{topic}**. One learner performs or describes the steps, the second checks the definitions, and the third records the result. After ten minutes, two groups share their work. The class gives one accurate observation and one improvement suggestion for each presentation.

## End-of-Lesson Quick Test
1. Define one key term from **{topic}**.
2. Explain one step in the process using your own words.
3. Give a practical school or community example.
4. State one common error and how to avoid it.
5. True or false: a result should be checked before it is accepted. Give a reason.

## Assignment
Write a one-page explanation of **{topic}**. Include three definitions, a numbered worked example, one labelled illustration or output, and two sentences explaining how the topic is useful in school or the community.
"""
        validation = validate_lesson_structure(markdown)
        return LessonDraft(class_level, term, week, topic, markdown, validation)


def generate_complete_lesson(class_level: str, term: str, week: int) -> Optional[str]:
    """Convenience API returning a validated complete lesson or ``None``."""
    draft = CompleteLessonGenerator().generate(class_level, term, week)
    return draft.markdown if draft and draft.validation["valid"] else None
