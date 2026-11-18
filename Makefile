.PHONY: install run test notes list clean

install:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

run:
	. venv/bin/activate && python main.py

test:
	. venv/bin/activate && python -m pytest tests/ -v || python tests/test_curriculum.py

notes:
	@echo "Example: make note CLASS=SS2 TERM='Second Term' WEEK=2"
	@echo "Or run: python scripts/generate_note.py --class SS2 --term \"Second Term\" --week 2"

list:
	. venv/bin/activate && python scripts/generate_note.py --list SS2

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -f *.pdf test_*.pdf
	rm -rf debug_glyphs/
