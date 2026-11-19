# Legacy handwriting sample sheet — not currently accepted by the web app

**Status:** Handwriting-to-font export is disabled. The current service does not have a genuine handwritten-text recognizer or verified text-to-glyph alignment. Preparing this sheet will not enable handwriting PDF export in the current release. Use the standard printable lesson PDF instead.

This page documents the former fixed-sheet experiment and may be useful as a future calibration/evaluation artifact. It must not be presented as a currently supported workflow.

## Experimental six-row order

If the fixed-sheet experiment is used for offline research, write one isolated character per position, left to right, keeping each row separate:

**Row 1 — uppercase A–M**
`A B C D E F G H I J K L M`

**Row 2 — uppercase N–Z**
`N O P Q R S T U V W X Y Z`

**Row 3 — lowercase a–m**
`a b c d e f g h i j k l m`

**Row 4 — lowercase n–z**
`n o p q r s t u v w x y z`

**Row 5 — digits**
`0 1 2 3 4 5 6 7 8 9`

**Row 6 — punctuation and symbols**
`. , ; : ! ? ' " ( ) - + = / *`

Do not add headings, arrows, annotations, or extra text inside the character rows. This ordering alone does not prove the system has identified a character correctly. Any future implementation must validate segmentation and label alignment before compiling or exporting a font.

## Capture notes for future evaluation

Use a sharp, evenly lit, directly overhead image with all rows visible. Record the writer's intended character sequence separately so recognition/alignment can be compared with human ground truth. A clear image by itself is not evidence that automatic recognition is correct.
