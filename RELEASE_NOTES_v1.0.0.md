# Release v1.0.0 – Digital Technologies Lesson Note Generator

**Date:** 2026-11-18  
**Status:** Production Ready for Nigerian SS1–SS3 Digital Technologies teachers

## Highlights

- Official NERDC 2025 Digital Technologies schemes fully mapped (SS1, SS2, SS3)
- 35+ ready classroom lesson notes with full pedagogical structure
- Handwriting sample → glyph extraction → TrueType font → Classmate PDF pipeline
- Simple web form on homepage (Class / Term / Week selector)
- FastAPI + CLI + Docker + GitHub Actions CI
- 2-up print helper for exercise book pasting
- Teacher Guide and Sample Sheet instructions

## How to use immediately

```bash
git clone https://github.com/akameredon/digital-tech-handwriting-generator.git
cd digital-tech-handwriting-generator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Get a lesson note
python scripts/generate_note.py --class SS2 --term "Second Term" --week 2

# Or start the web UI
./run.sh
# open http://127.0.0.1:8000
```

## Handwriting end-to-end

```bash
python scripts/end_to_end_pipeline.py \
  --sample your_handwriting_photo.jpg \
  --class SS2 --term "Second Term" --week 2 \
  --output my_lesson.pdf
```

## Known limitations

- Font quality depends on the clarity of the handwriting sample
- Some weeks still return a structured skeleton (use `--prompt` to expand with any LLM)
- Cursive writing is not fully supported

## License
MIT
