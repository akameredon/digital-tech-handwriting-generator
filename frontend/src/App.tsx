import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  analyzeNaturalPage,
  downloadCalibrationSheet,
  exportLessonPdf,
  exportHandwritingPdf,
  getLesson,
  getPrompt,
  getTopics,
  type Lesson,
  type NaturalPageAnalysis,
  type Topic
} from "./api";

type Section = "create" | "curriculum" | "handwriting" | "help";
const TERMS = ["First Term", "Second Term", "Third Term"];
const CLASSES = ["SS1", "SS2", "SS3"];

function App() {
  const [section, setSection] = useState<Section>("create");
  const [classLevel, setClassLevel] = useState("SS2");
  const [term, setTerm] = useState("Second Term");
  const [week, setWeek] = useState(2);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [prompt, setPrompt] = useState("");
  const [pdfUrl, setPdfUrl] = useState("");
  const [exportingPdf, setExportingPdf] = useState(false);
  const [handwritingScan, setHandwritingScan] = useState<File | null>(null);
  const [naturalPage, setNaturalPage] = useState<File | null>(null);
  const [naturalPagePreview, setNaturalPagePreview] = useState("");
  const [naturalAnalysis, setNaturalAnalysis] = useState<NaturalPageAnalysis | null>(null);
  const [analyzingNaturalPage, setAnalyzingNaturalPage] = useState(false);
  const [labelsConfirmed, setLabelsConfirmed] = useState(false);
  const [downloadingCalibration, setDownloadingCalibration] = useState(false);
  const [exportingHandwriting, setExportingHandwriting] = useState(false);
  const [loadingTopics, setLoadingTopics] = useState(true);
  const [loadingLesson, setLoadingLesson] = useState(false);
  const [loadingPrompt, setLoadingPrompt] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [copied, setCopied] = useState(false);
  const lessonRequestId = useRef(0);
  const handwritingRequestId = useRef(0);

  useEffect(() => {
    let active = true;
    setLoadingTopics(true);
    getTopics(classLevel)
      .then((items) => { if (active) setTopics(items); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "Could not load the curriculum."); })
      .finally(() => { if (active) setLoadingTopics(false); });
    return () => { active = false; };
  }, [classLevel]);

  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
  }, [pdfUrl]);

  useEffect(() => {
    return () => {
      if (naturalPagePreview) URL.revokeObjectURL(naturalPagePreview);
    };
  }, [naturalPagePreview]);

  const selectedTopic = useMemo(
    () => topics.find((item) => item.term === term && item.week === week),
    [topics, term, week]
  );

  const filteredTopics = useMemo(
    () => topics.filter((item) => item.term === term),
    [topics, term]
  );

  function clearFeedback() {
    setError("");
    setNotice("");
    setCopied(false);
  }

  function invalidateLesson() {
    lessonRequestId.current += 1;
    handwritingRequestId.current += 1;
    setLesson(null);
    setPrompt("");
    setPdfUrl("");
    setLoadingLesson(false);
    setExportingPdf(false);
    setExportingHandwriting(false);
  }

  async function reviewLesson() {
    clearFeedback();
    setLoadingLesson(true);
    setPrompt("");
    const requestId = ++lessonRequestId.current;
    try {
      const result = await getLesson(classLevel, term, week);
      if (requestId === lessonRequestId.current) {
        setLesson(result);
        setNotice("Your lesson details are ready to review.");
      }
    } catch (reason) {
      if (requestId === lessonRequestId.current) {
        setError(reason instanceof Error ? reason.message : "We couldn't load this lesson.");
      }
    } finally {
      if (requestId === lessonRequestId.current) setLoadingLesson(false);
    }
  }

  async function copyPrompt() {
    clearFeedback();
    setLoadingPrompt(true);
    try {
      const value = await getPrompt(classLevel, term, week);
      setPrompt(value);
      try {
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setNotice("AI prompt copied. You can paste it into your preferred AI tool.");
      } catch {
        setNotice("Your prompt is ready below. Select the text and copy it into your preferred AI tool.");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We couldn't prepare the prompt.");
    } finally {
      setLoadingPrompt(false);
    }
  }

  async function downloadPrintablePdf() {
    clearFeedback();
    setExportingPdf(true);
    const requestId = lessonRequestId.current;
    try {
      const blob = await exportLessonPdf(classLevel, term, week);
      const nextUrl = URL.createObjectURL(blob);
      if (requestId !== lessonRequestId.current) {
        URL.revokeObjectURL(nextUrl);
        return;
      }
      setPdfUrl(nextUrl);
      const link = document.createElement("a");
      link.href = nextUrl;
      link.download = `${classLevel}_${term.replaceAll(" ", "_")}_Week${week}_lesson.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setNotice("Your printable lesson PDF is ready and the download has started.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We couldn't prepare the PDF.");
    } finally {
      if (requestId === lessonRequestId.current) setExportingPdf(false);
    }
  }

  async function getCalibrationSheet() {
    clearFeedback();
    setDownloadingCalibration(true);
    try {
      const blob = await downloadCalibrationSheet();
      saveBlob(blob, "digital-technologies-handwriting-calibration.pdf");
      setNotice("The optional worksheet is downloading. Print it, write one character in each box, then scan the whole page upright.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We couldn't create the calibration sheet.");
    } finally {
      setDownloadingCalibration(false);
    }
  }

  async function inspectNaturalPage() {
    clearFeedback();
    if (!naturalPage) {
      setError("Choose a clear photo of an ordinary handwritten notebook page first.");
      return;
    }
    setAnalyzingNaturalPage(true);
    setNaturalAnalysis(null);
    try {
      const result = await analyzeNaturalPage(naturalPage);
      setNaturalAnalysis(result);
      setNotice("Your notebook page has been analyzed. Review the image-quality and line-detection results below.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "We couldn't analyze this notebook page.");
    } finally {
      setAnalyzingNaturalPage(false);
    }
  }

  async function downloadHandwritingStylePdf() {
    clearFeedback();
    if (!handwritingScan || !labelsConfirmed) {
      setError("Choose a worksheet scan and confirm that each handwritten character matches its printed label.");
      return;
    }
    setExportingHandwriting(true);
    const requestId = ++handwritingRequestId.current;
    try {
      const result = await exportHandwritingPdf(classLevel, term, week, handwritingScan, labelsConfirmed);
      if (requestId !== handwritingRequestId.current) return;
      saveBlob(result.blob, `${classLevel}_${term.replaceAll(" ", "_")}_Week${week}_handwriting_style.pdf`);
      setNotice(
        `Your handwriting-style PDF is ready. The worksheet provided ${result.coveredCharacters} of ${result.totalCharacters} characters; ${result.missingCharacters} missing characters use standard text. Ordinary notebook-page handwriting recognition is not included.`
      );
    } catch (reason) {
      if (requestId === handwritingRequestId.current) {
        setError(reason instanceof Error ? reason.message : "We couldn't create the handwriting-style PDF.");
      }
    } finally {
      if (requestId === handwritingRequestId.current) setExportingHandwriting(false);
    }
  }

  function changeSection(next: Section) {
    setSection(next);
    clearFeedback();
  }

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => { event.preventDefault(); changeSection("create"); }}>
          <span className="brand-mark">D<span>.</span></span>
          <span className="brand-copy"><strong>Lesson Studio</strong><small>Digital Technologies</small></span>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <NavButton active={section === "create"} onClick={() => changeSection("create")} mark="＋">Create lesson</NavButton>
          <NavButton active={section === "curriculum"} onClick={() => changeSection("curriculum")} mark="▤">Curriculum</NavButton>
          <NavButton active={section === "handwriting"} onClick={() => changeSection("handwriting")} mark="✎">Handwriting PDF</NavButton>
          <NavButton active={section === "help"} onClick={() => changeSection("help")} mark="?">Help & guidance</NavButton>
        </nav>
        <div className="sidebar-bottom">
          <div className="support-card">
            <span className="support-dot" />
            <div><strong>Curriculum workspace</strong><small>SS1 · SS2 · SS3</small></div>
          </div>
          <small className="sidebar-foot">Built for the classroom.</small>
        </div>
      </aside>

      <main className="main-area" id="main-content" tabIndex={-1}>
        <header className="topbar">
          <div className="mobile-brand"><span className="brand-mark">D<span>.</span></span><strong>Lesson Studio</strong></div>
          <div className="topbar-context"><span>TEACHER WORKSPACE</span><span className="context-separator">/</span><strong>{sectionLabel(section)}</strong></div>
          <span className="version-chip">NERDC 2025 · SS1–SS3</span>
        </header>
        <nav className="mobile-nav" aria-label="Main navigation">
          <NavButton active={section === "create"} onClick={() => changeSection("create")} mark="＋">Create</NavButton>
          <NavButton active={section === "curriculum"} onClick={() => changeSection("curriculum")} mark="▤">Curriculum</NavButton>
          <NavButton active={section === "handwriting"} onClick={() => changeSection("handwriting")} mark="✎">Handwriting</NavButton>
          <NavButton active={section === "help"} onClick={() => changeSection("help")} mark="?">Help</NavButton>
        </nav>

        <div className="page-wrap">
          {section === "create" && (
            <>
              <div className="page-heading">
                <div className="eyebrow"><span className="eyebrow-line" /> YOUR TEACHING WORKFLOW</div>
                <h1>Prepare your next lesson.</h1>
                <p>Choose a class, term and week. We’ll bring the curriculum and lesson materials together.</p>
              </div>
              <StepBar activeStep={pdfUrl ? 3 : lesson ? 2 : 1} />
              <section className="panel setup-panel">
                <div className="panel-heading">
                  <div><span className="step-kicker">STEP 01</span><h2>Choose your lesson</h2><p>Start with the class and week you’re preparing for.</p></div>
                  <span className="panel-icon">01</span>
                </div>
                <div className="form-grid">
                  <Field label="Class">
                    <select value={classLevel} onChange={(event) => { invalidateLesson(); setClassLevel(event.target.value); }}>
                      {CLASSES.map((value) => <option key={value}>{value}</option>)}
                    </select>
                  </Field>
                  <Field label="Term">
                    <select value={term} onChange={(event) => { invalidateLesson(); setTerm(event.target.value); }}>
                      {TERMS.map((value) => <option key={value}>{value}</option>)}
                    </select>
                  </Field>
                  <Field label="Week">
                    <select value={week} onChange={(event) => { invalidateLesson(); setWeek(Number(event.target.value)); }}>
                      {Array.from({ length: 13 }, (_, index) => index + 1).map((value) => <option key={value} value={value}>Week {value}</option>)}
                    </select>
                  </Field>
                </div>
                <div className="topic-preview">
                  <div className="topic-symbol">↗</div>
                  <div className="topic-copy">
                    <span>CURRICULUM TOPIC</span>
                    <strong>{loadingTopics ? "Loading curriculum…" : selectedTopic?.topic ?? "Topic not available"}</strong>
                    <p>{selectedTopic?.content ?? "Choose another week or check your connection."}</p>
                  </div>
                  {selectedTopic && isSpecialWeek(selectedTopic.topic) && <span className="status-pill warning">School calendar</span>}
                </div>
                <div className="panel-actions">
                  <span className="helper-text">Your selection is matched against the curriculum.</span>
                  <button className="button button-primary" onClick={reviewLesson} disabled={loadingLesson || loadingTopics || !selectedTopic}>
                    {loadingLesson ? "Loading lesson…" : "Review lesson"} <span aria-hidden="true">→</span>
                  </button>
                </div>
              </section>

              {lesson && (
                <section className="panel lesson-panel">
                  <div className="panel-heading">
                    <div><span className="step-kicker">STEP 02</span><h2>Review your lesson</h2><p>Check the topic and content before preparing your document.</p></div>
                    <span className="status-pill">{lesson.content_status === "prepared" ? "Prepared note" : "Curriculum outline"}</span>
                  </div>
                  <div className="lesson-meta">
                    <span>{lesson.class_level}</span><span>{lesson.term}</span><span>Week {lesson.week}</span>
                  </div>
                  <h3 className="lesson-title">{lesson.topic}</h3>
                  <p className="official-content">{lesson.official_content}</p>
                  <div className="lesson-body">{lesson.lesson_note.split("\n").map((line, index) => (
                    <p key={index} className={line.startsWith("**") ? "lesson-line heading-line" : "lesson-line"}>{line.replaceAll("**", "").replaceAll("`", "") || " "}</p>
                  ))}</div>
                  {lesson.content_status !== "prepared" && (
                    <div className="outline-notice">
                      <strong>This week currently has a curriculum outline.</strong>
                      <p>The app can prepare an AI prompt from the curriculum, but it has not generated a full AI lesson note itself.</p>
                      <button className="button button-secondary" onClick={copyPrompt} disabled={loadingPrompt}>
                        {loadingPrompt ? "Preparing prompt…" : copied ? "Prompt copied" : "Copy AI prompt"} <span aria-hidden="true">↗</span>
                      </button>
                      {prompt && <textarea className="prompt-output" readOnly value={prompt} aria-label="AI generation prompt" />}
                    </div>
                  )}
                </section>
              )}

              {lesson && (
                <section className="panel export-panel">
                  <div className="panel-heading">
                    <div><span className="step-kicker">STEP 03</span><h2>Download a printable copy</h2><p>Get a ruled PDF in standard text. The file uses the selected lesson content without pretending to reproduce handwriting.</p>{lesson.content_status === "outline" && <p className="export-note">This PDF contains the curriculum outline currently available, not a fully expanded lesson note.</p>}</div>
                    <span className="panel-icon">03</span>
                  </div>
                  <div className="panel-actions">
                    <span className="helper-text">PDF · A4 ruled pages · Temporary server-side file.</span>
                    <button className="button button-primary" onClick={downloadPrintablePdf} disabled={exportingPdf}>
                      {exportingPdf ? "Preparing your PDF…" : "Download printable PDF"} <span aria-hidden="true">→</span>
                    </button>
                  </div>
                  {pdfUrl && <div className="download-ready"><span>✓ Your PDF is ready.</span><a href={pdfUrl} download={`${classLevel}_${term.replaceAll(" ", "_")}_Week${week}_lesson.pdf`}>Download PDF again →</a></div>}
                </section>
              )}
            </>
          )}

          {section === "curriculum" && (
            <>
              <div className="page-heading"><div className="eyebrow"><span className="eyebrow-line" /> CURRICULUM LIBRARY</div><h1>Explore the curriculum.</h1><p>Browse the Digital Technologies topics available for each senior secondary class.</p></div>
              <section className="panel">
                <div className="form-grid two-fields">
                  <Field label="Class"><select value={classLevel} onChange={(event) => { invalidateLesson(); setClassLevel(event.target.value); }}>{CLASSES.map((value) => <option key={value}>{value}</option>)}</select></Field>
                  <Field label="Term"><select value={term} onChange={(event) => { invalidateLesson(); setTerm(event.target.value); }}>{TERMS.map((value) => <option key={value}>{value}</option>)}</select></Field>
                </div>
                <div className="topic-list">
                  {loadingTopics ? <p className="muted">Loading topics…</p> : filteredTopics.map((item) => (
                    <button className={week === item.week ? "topic-row selected" : "topic-row"} key={item.week} onClick={() => { invalidateLesson(); setWeek(item.week); setSection("create"); }}>
                      <span className="week-number">{String(item.week).padStart(2, "0")}</span>
                      <span className="topic-row-copy"><strong>{item.topic}</strong><small>{item.content}</small></span>
                      <span className="row-arrow">→</span>
                    </button>
                  ))}
                </div>
              </section>
            </>
          )}

          {section === "handwriting" && (
            <>
              <div className="page-heading"><div className="eyebrow"><span className="eyebrow-line" /> HANDWRITING WORKFLOW</div><h1>Analyze your handwriting sample.</h1><p>Upload an ordinary notebook page to check image quality, correct page geometry and detect natural writing lines. Text recognition and personal handwriting generation are separate later stages.</p></div>
              <section className="panel natural-page-panel">
                <div className="panel-heading">
                  <div><span className="step-kicker">GROUP 2 · NATURAL PAGE INTAKE</span><h2>Upload a real notebook page</h2><p>Use a normal photo or scan. No printed calibration worksheet or character labels are required for this analysis.</p></div>
                  <span className="panel-icon">01</span>
                </div>
                <label className="upload-box natural-upload">
                  <span className="upload-symbol" aria-hidden="true">↑</span>
                  <span className="upload-copy"><strong>{naturalPage?.name ?? "Choose a notebook-page photo"}</strong><small>JPG, PNG or WebP · up to 12 MB · 24 megapixels maximum</small></span>
                  <span className="button button-secondary upload-button" aria-hidden="true">Browse files</span>
                  <input type="file" accept="image/jpeg,image/png,image/webp" aria-label="Choose an ordinary handwritten notebook page"
                    onChange={(event) => {
                      clearFeedback();
                      setNaturalAnalysis(null);
                      const file = event.target.files?.[0] ?? null;
                      if (file && file.size > 12 * 1024 * 1024) {
                        setNaturalPage(null);
                        setNaturalPagePreview("");
                        setError("The image must be 12 MB or smaller.");
                        return;
                      }
                      setNaturalPage(file);
                      setNaturalPagePreview(file ? URL.createObjectURL(file) : "");
                    }} />
                </label>
                <p className="sample-help">For best results, photograph the full page in even light, keep the camera parallel to the paper and make the writing sharp and readable.</p>
                {naturalPagePreview && <div className="natural-preview-wrap"><img className="natural-preview" src={naturalPagePreview} alt="Selected handwritten notebook page preview" /><div className="natural-preview-caption">Original upload preview · retained in this browser session only</div></div>}
                <div className="panel-actions">
                  <span className="helper-text">The original upload is not saved as a teacher profile.</span>
                  <button className="button button-primary" onClick={inspectNaturalPage} disabled={!naturalPage || analyzingNaturalPage}>
                    {analyzingNaturalPage ? "Analyzing page…" : "Analyze notebook page"} <span aria-hidden="true">→</span>
                  </button>
                </div>
                {naturalAnalysis && (
                  <div className="natural-results" role="status" aria-live="polite">
                    <div className="natural-result-heading"><div><span className="step-kicker">IMAGE ANALYSIS</span><h3>Page analysis results</h3></div><span className={naturalAnalysis.analysis.quality === "usable" ? "status-pill" : "status-pill warning"}>{naturalAnalysis.analysis.quality === "usable" ? "Usable image" : "Needs improvement"}</span></div>
                    <div className="natural-metrics">
                      <div><strong>{naturalAnalysis.analysis.width} × {naturalAnalysis.analysis.height}</strong><small>Processed dimensions</small></div>
                      <div><strong>{naturalAnalysis.analysis.line_count}</strong><small>Writing lines detected</small></div>
                      <div><strong>{naturalAnalysis.analysis.blur_score}</strong><small>Sharpness score</small></div>
                      <div><strong>{naturalAnalysis.analysis.deskew_degrees}°</strong><small>Deskew correction</small></div>
                    </div>
                    <ul className="natural-checks">
                      <li>{naturalAnalysis.analysis.perspective_corrected ? "Page perspective correction applied" : "No confident page boundary found; original framing retained"}</li>
                      {naturalAnalysis.analysis.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
                      {naturalAnalysis.analysis.warnings.length === 0 && <li>No image-quality warnings were detected.</li>}
                    </ul>
                    <div className="recognition-boundary"><strong>Recognition status: not yet configured.</strong><p>This stage detects and prepares writing lines; it does not transcribe the teacher's handwriting or create a personal font. Those require a genuine handwriting-recognition model and a verified writer-profile pipeline.</p></div>
                  </div>
                )}
              </section>

              <section className="panel">
                <div className="panel-heading"><div><span className="step-kicker">STEP 01 · CHOOSE A LESSON</span><h2>Choose the note for your PDF</h2><p>The regular printable PDF remains available without a worksheet or handwriting sample.</p></div></div>
                <div className="form-grid">
                  <Field label="Class"><select value={classLevel} onChange={(event) => { invalidateLesson(); setClassLevel(event.target.value); }}>{CLASSES.map((value) => <option key={value}>{value}</option>)}</select></Field>
                  <Field label="Term"><select value={term} onChange={(event) => { invalidateLesson(); setTerm(event.target.value); }}>{TERMS.map((value) => <option key={value}>{value}</option>)}</select></Field>
                  <Field label="Week"><select value={week} onChange={(event) => { invalidateLesson(); setWeek(Number(event.target.value)); }}>{Array.from({ length: 13 }, (_, index) => index + 1).map((value) => <option key={value} value={value}>Week {value}</option>)}</select></Field>
                </div>
                <div className="topic-preview">
                  <div className="topic-symbol" aria-hidden="true">↗</div>
                  <div className="topic-copy"><span>LESSON CONTENT</span><strong>{loadingTopics ? "Loading curriculum…" : selectedTopic?.topic ?? "Topic not available"}</strong><p>{selectedTopic?.content ?? "Choose another week or check your connection."}</p></div>
                </div>
                <div className="callout"><strong>What this workflow does—and does not do</strong><p>The worksheet is the required input for this experimental handwriting path. Character labels come from the printed boxes, with your confirmation; an ordinary notebook page is not recognized and will be rejected. Missing characters in the PDF use standard text. The regular printable PDF remains available separately without a handwriting sample.</p></div>
              </section>
              <section className="panel">
                <div className="panel-heading"><div><span className="step-kicker">STEP 02 · REQUIRED WORKSHEET</span><h2>Print, write and scan</h2><p>For this handwriting workflow, fill the printed boxes with dark ink. Scan the full A4 landscape page upright as a JPG or PNG.</p></div><span className="panel-icon">02</span></div>
                <div className="panel-actions">
                  <span className="helper-text">Required for this handwriting workflow · A4 landscape · JPG/PNG scan</span>
                  <button className="button button-secondary" onClick={getCalibrationSheet} disabled={downloadingCalibration}>
                    {downloadingCalibration ? "Preparing worksheet…" : "Download handwriting worksheet"} <span aria-hidden="true">↓</span>
                  </button>
                </div>
              </section>
              <section className="panel">
                <div className="panel-heading"><div><span className="step-kicker">STEP 03 · CREATE PDF</span><h2>Upload the completed worksheet</h2><p>Only characters found inside their labeled cells are compiled into the partial font.</p></div><span className="panel-icon">03</span></div>
                <label className="upload-box">
                  <span className="upload-symbol" aria-hidden="true">↑</span>
                  <span className="upload-copy"><strong>{handwritingScan?.name ?? "Choose a worksheet scan"}</strong><small>JPG or PNG, full page, upright, under 12 MB</small></span>
                  <span className="button button-secondary upload-button" aria-hidden="true">Browse files</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png"
                    aria-label="Choose a full-page calibration worksheet scan"
                    aria-describedby="calibration-scan-help"
                    onChange={(event) => {
                      clearFeedback();
                      handwritingRequestId.current += 1;
                      setExportingHandwriting(false);
                      const file = event.target.files?.[0] ?? null;
                      if (file && file.size > 12 * 1024 * 1024) {
                        setHandwritingScan(null);
                        setLabelsConfirmed(false);
                        setError("The scan must be smaller than 12 MB. Choose a smaller JPG or PNG file.");
                      } else {
                        setHandwritingScan(file);
                        setLabelsConfirmed(false);
                      }
                    }}
                  />
                </label>
                <p className="sample-help" id="calibration-scan-help">The scan is processed for this request only and is not kept as a teacher profile.</p>
                <label className="confirmation-check">
                  <input type="checkbox" checked={labelsConfirmed} onChange={(event) => { handwritingRequestId.current += 1; setExportingHandwriting(false); setLabelsConfirmed(event.target.checked); }} />
                  <span>I checked the scan: every written character matches the printed label in its box.</span>
                </label>
                <div className="panel-actions">
                  <span className="helper-text">The result reports character coverage and uses standard text for missing glyphs.</span>
                  <button className="button button-primary" onClick={downloadHandwritingStylePdf} disabled={!handwritingScan || !labelsConfirmed || exportingHandwriting}>
                    {exportingHandwriting ? "Creating your PDF…" : "Create handwriting-style PDF"} <span aria-hidden="true">→</span>
                  </button>
                </div>
              </section>
            </>
          )}

          {section === "help" && (
            <>
              <div className="page-heading"><div className="eyebrow"><span className="eyebrow-line" /> TEACHER SUPPORT</div><h1>Here when you need us.</h1><p>A few quick answers to help you get a good result.</p></div>
              <section className="panel help-list">
                <HelpItem title="How do I find my topic?" body="Choose your class, term and week. The curriculum topic and its content summary appear automatically." />
                <HelpItem title="Why does my lesson say “Curriculum outline”?" body="A full prepared lesson note is not available for every week yet. You can copy a curriculum-aligned prompt and use it in your preferred AI tool." />
                <HelpItem title="How does the handwriting-style PDF work?" body="The handwriting workflow uses a generated, labeled worksheet as its required input. It compiles a partial font from characters in those boxes after you confirm the labels, then uses standard text for unsupported characters. It does not recognize arbitrary notebook pages or perform handwriting OCR. A regular printable PDF is available separately without a handwriting sample." />
                <HelpItem title="Where does my printable PDF go?" body="Your browser downloads the generated PDF to its normal downloads location. The server writes the file to a temporary directory and removes it after sending the response." />
              </section>
            </>
          )}

          {(error || notice) && (
            <div className={error ? "feedback feedback-error" : "feedback feedback-success"} role={error ? "alert" : "status"} aria-live="polite">
              <span>{error ? "!" : "✓"}</span><p>{error || notice}</p><button onClick={() => { setError(""); setNotice(""); }} aria-label="Dismiss message">×</button>
            </div>
          )}
          <footer className="page-footer"><span>Digital Technologies Lesson Studio</span><span>Curriculum-led. Teacher-friendly.</span></footer>
        </div>
      </main>
    </div>
  );
}

function sectionLabel(section: Section) {
  return ({ create: "Create lesson", curriculum: "Curriculum", handwriting: "Handwriting PDF", help: "Help & guidance" })[section];
}

function NavButton({ active, onClick, mark, children }: { active: boolean; onClick: () => void; mark: string; children: string }) {
  return <button className={active ? "nav-button active" : "nav-button"} onClick={onClick} aria-current={active ? "page" : undefined}><span className="nav-mark" aria-hidden="true">{mark}</span>{children}</button>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function StepBar({ activeStep }: { activeStep: number }) {
  const steps = ["Choose lesson", "Review content", "Export PDF"];
  return <div className="stepbar" aria-label="Lesson preparation steps">
    {steps.map((label, index) => {
      const number = index + 1;
      const active = number === activeStep;
      const complete = number < activeStep;
      return <span className={`stepbar-item ${active ? "active" : ""} ${complete ? "complete" : ""}`} aria-current={active ? "step" : undefined} key={label}>
        <span>{complete ? "✓" : number}</span><strong>{label}</strong>
      </span>;
    }).flatMap((item, index) => index < steps.length - 1 ? [item, <i key={`connector-${index}`} />] : [item])}
  </div>;
}

function HelpItem({ title, body }: { title: string; body: string }) {
  return <details className="help-item"><summary>{title}<span>＋</span></summary><p>{body}</p></details>;
}

function isSpecialWeek(topic: string) {
  return /exam|test|break|revision|closing|holiday/i.test(topic);
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default App;
