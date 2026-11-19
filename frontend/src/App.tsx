import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  exportLessonPdf,
  getLesson,
  getPrompt,
  getTopics,
  type Lesson,
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
  const [loadingTopics, setLoadingTopics] = useState(true);
  const [loadingLesson, setLoadingLesson] = useState(false);
  const [loadingPrompt, setLoadingPrompt] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [copied, setCopied] = useState(false);
  const lessonRequestId = useRef(0);

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
    setLesson(null);
    setPrompt("");
    setPdfUrl("");
    setLoadingLesson(false);
    setExportingPdf(false);
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
              <div className="page-heading"><div className="eyebrow"><span className="eyebrow-line" /> HANDWRITING WORKFLOW</div><h1>Handwriting export is not ready.</h1><p>This feature is paused so the app does not mislabel handwriting or create a misleading font.</p></div>
              <section className="panel">
                <div className="panel-heading"><div><span className="step-kicker">FEATURE STATUS</span><h2>No handwriting sample is needed for printable PDFs.</h2><p>The current server has no configured handwriting recognizer or reliable text-to-glyph alignment. Uploading a page could otherwise produce the wrong letters.</p></div></div>
                <div className="callout"><strong>What works now</strong><p>Choose a lesson and download a ruled printable PDF in standard text. Handwriting-font export will remain disabled until recognition and real-sample validation are available.</p></div>
                <button className="button button-primary" onClick={() => changeSection("create")}>Start a lesson <span aria-hidden="true">→</span></button>
              </section>
            </>
          )}

          {section === "help" && (
            <>
              <div className="page-heading"><div className="eyebrow"><span className="eyebrow-line" /> TEACHER SUPPORT</div><h1>Here when you need us.</h1><p>A few quick answers to help you get a good result.</p></div>
              <section className="panel help-list">
                <HelpItem title="How do I find my topic?" body="Choose your class, term and week. The curriculum topic and its content summary appear automatically." />
                <HelpItem title="Why does my lesson say “Curriculum outline”?" body="A full prepared lesson note is not available for every week yet. You can copy a curriculum-aligned prompt and use it in your preferred AI tool." />
                <HelpItem title="Can I create a handwriting-style PDF?" body="Not yet. The server does not have reliable handwriting recognition and text-to-glyph alignment configured, so that feature is disabled rather than returning falsely labeled handwriting. You can download a standard printable PDF." />
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

export default App;
