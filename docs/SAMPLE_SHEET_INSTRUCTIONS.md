# Optional handwriting calibration worksheet

The web app now offers a generated worksheet for an experimental handwriting-style PDF path. This sheet is optional for the product overall: ordinary printable lesson PDFs do not require it. Natural notebook-page handwriting recognition is not available through this workflow.

## How to use it

1. In the Handwriting PDF section, choose a class, term, and week, then download the generated A4 landscape worksheet.
2. Print the full page. Write each printed character once inside its own box using dark ink. Do not add notes or marks outside the boxes.
3. Check that each written character matches the printed label in that box. The export flow requires the teacher to confirm this check because the software uses the known worksheet cell positions; it does not automatically recognize whether the written shape matches the label.
4. Scan or photograph the entire page upright as a JPG or PNG. Keep all four corners visible and avoid cropping. Upload a file smaller than 12 MB.
5. Create the PDF. The result reports how many of the 77 worksheet characters were captured. Missing characters use standard text instead of synthetic handwriting glyphs.

The current generated order is six rows: uppercase `A–M`, uppercase `N–Z`, lowercase `a–m`, lowercase `n–z`, digits `0–9`, then `. , ; : ! ? ' \" ( ) - + = / *`. Only known positions on the generated worksheet are used to label glyph crops.

## Important limitation

A clear scan and the teacher's checkbox do not prove that every crop is labeled correctly. The teacher must inspect the written characters before confirming. The worksheet endpoint rejects ordinary notebook pages instead of assigning labels by position. It is not an HTR model, and it does not complete the intended natural-page handwriting feature.
