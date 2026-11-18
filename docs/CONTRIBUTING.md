# Contributing to the Digital Technologies Lesson Note Generator

Thank you for your interest in improving this project for Nigerian teachers and students.

## Ways to Contribute

1. **Add missing lesson notes** – Follow the existing pedagogical structure exactly.
2. **Improve existing notes** – Make language clearer or add better Nigerian examples.
3. **Fix bugs** – Especially in the CLI, PDF exporter or curriculum mapping.
4. **Improve documentation** – Teacher guides, examples, or installation instructions.
5. **Add tests** – Help increase reliability.

## Lesson Note Structure (Must Follow)

Every content note should contain:

- Class, Term, Week, Topic
- Behavioral Learning Objectives (3–5 measurable objectives)
- Key Concepts / Definitions
- Step-by-Step Conceptual Explanation
- Practical / Worked Example
- Class Activity / Guided Practice
- End-of-Lesson Quick Test (5 questions)
- Assignment

Use simple English suitable for Nigerian SS students. Prefer local examples where possible.

## Development Setup

```bash
git clone https://github.com/akameredon/digital-tech-handwriting-generator.git
cd digital-tech-handwriting-generator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Submitting Changes

1. Create a new branch.
2. Make your changes.
3. Test that the CLI and basic imports still work.
4. Open a Pull Request with a clear description.

## Code of Conduct

Be respectful. This project exists to help teachers and students across Nigeria.
