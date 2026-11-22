# Notebook layout and PDF rendering

`renderer/notebook_layout.py` implements Rank 9. It converts lesson Markdown into a stable layout model before rendering, preserving headings, wrapping long lines, splitting content across ruled pages, and recording page numbers.

`NotebookLayoutEngine` produces `NotebookPage` and `LayoutLine` records so pagination can be tested without opening a PDF. `NotebookPDFRenderer` draws the planned pages with a pink margin, blue ruled lines, underlined headings, and a footer containing the current page and total page count.

```python
from renderer.notebook_layout import NotebookPDFRenderer

layout = NotebookPDFRenderer().render(markdown, "lesson.pdf")
print(layout.page_count)
```

The layout model prevents content from being silently clipped: every wrapped line belongs to exactly one page, and the PDF test checks that the rendered page count matches the planner.
