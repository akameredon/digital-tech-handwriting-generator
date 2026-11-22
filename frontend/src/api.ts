export type Topic = {
  class: string;
  term: string;
  week: number;
  topic: string;
  content: string;
};

export type Lesson = {
  class_level: string;
  term: string;
  week: number;
  topic: string;
  official_content: string;
  is_exam_or_break: boolean;
  lesson_note: string;
  content_status?: "prepared" | "outline";
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the plain-language fallback for non-JSON errors.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

async function readBlob(response: Response): Promise<Blob> {
  if (!response.ok) {
    let message = "We couldn't create the printable PDF. Please try again.";
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the plain-language fallback for non-JSON errors.
    }
    throw new Error(message);
  }
  return response.blob();
}

export async function getTopics(classLevel: string): Promise<Topic[]> {
  const query = new URLSearchParams({ class_level: classLevel });
  return readJson<Topic[]>(await fetch(`${API_BASE}/topics?${query}`));
}

export async function getLesson(classLevel: string, term: string, week: number): Promise<Lesson> {
  const path = [classLevel, term, String(week)].map(encodeURIComponent).join("/");
  return readJson<Lesson>(await fetch(`${API_BASE}/lesson/${path}`));
}

export async function getPrompt(classLevel: string, term: string, week: number): Promise<string> {
  const path = [classLevel, term, String(week)].map(encodeURIComponent).join("/");
  const body = await readJson<{ prompt: string }>(await fetch(`${API_BASE}/prompt/${path}`));
  return body.prompt;
}

export async function exportLessonPdf(
  classLevel: string,
  term: string,
  week: number
): Promise<Blob> {
  const form = new FormData();
  form.append("class_level", classLevel);
  form.append("term", term);
  form.append("week", String(week));
  return readBlob(await fetch(`${API_BASE}/export/lesson-pdf`, {
    method: "POST",
    body: form
  }));
}

export type HandwritingPdfResult = {
  blob: Blob;
  coveredCharacters: number;
  totalCharacters: number;
  missingCharacters: number;
};

export async function downloadCalibrationSheet(): Promise<Blob> {
  return readBlob(await fetch(`${API_BASE}/handwriting/calibration-sheet`));
}

export async function exportHandwritingPdf(
  classLevel: string,
  term: string,
  week: number,
  scan: File,
  confirmLabels: boolean
): Promise<HandwritingPdfResult> {
  const form = new FormData();
  form.append("class_level", classLevel);
  form.append("term", term);
  form.append("week", String(week));
  form.append("calibration_scan", scan);
  form.append("confirm_labels", String(confirmLabels));

  const response = await fetch(`${API_BASE}/export/handwriting-pdf`, {
    method: "POST",
    body: form
  });
  const blob = await readBlob(response);
  const [coveredCharacters, totalCharacters] = (response.headers.get("X-Handwriting-Coverage") ?? "0/77")
    .split("/")
    .map((value) => Number(value));
  const missingCharacters = Number(response.headers.get("X-Handwriting-Missing-Count") ?? totalCharacters);
  return { blob, coveredCharacters, totalCharacters, missingCharacters };
}

export type HandwritingAnalysis = {
  analysis: {
    width: number;
    height: number;
    quality: string;
    warnings: string[];
    line_count: number;
    lines: Array<{ index: number; bbox: number[]; ink_ratio: number }>;
  };
  recognition: {
    text: string;
    provider: string;
    needs_review: boolean;
    warnings: string[];
    lines: Array<{
      line_index: number;
      bbox: number[];
      text: string;
      confidence: number;
      alternatives: string[];
      needs_review: boolean;
      review_reasons: string[];
      character_boxes: Array<{ bbox?: number[]; confidence?: number }>;
    }>;
  };
  glyph_alignment: {
    line_count: number;
    candidate_count: number;
    needs_review: boolean;
    warnings: string[];
    lines: Array<{
      candidate_count: number;
      review_count: number;
      candidates: Array<{ label: string; source_bbox: number[]; confidence: number; source: string; review_reasons: string[] }>;
      review: Array<{ reason: string; message?: string; label?: string; index?: number }>;
      warnings: string[];
    }>;
  };
};

export async function analyzeHandwritingPage(page: File): Promise<HandwritingAnalysis> {
  const form = new FormData();
  form.append("page", page);
  return readJson<HandwritingAnalysis>(await fetch(`${API_BASE}/analyze/handwriting`, {
    method: "POST",
    body: form,
  }));
}

export type ConfirmedProfileResult = {
  profile: {
    name: string;
    version: number;
    approved: boolean;
    coverage: string[];
    glyph_evidence: Record<string, { sample_count: number; mean_confidence: number; sources: string[] }>;
  };
  confirmed_count: number;
  learning: { coverage: Record<string, number>; missing: string[]; coverage_ratio: number; evidence: Record<string, unknown> };
};

export async function confirmHandwritingPage(
  page: File,
  writerName: string,
  confirmations: Record<string, string>,
): Promise<ConfirmedProfileResult> {
  const form = new FormData();
  form.append("page", page);
  form.append("writer_name", writerName);
  form.append("confirmations", JSON.stringify(confirmations));
  return readJson<ConfirmedProfileResult>(await fetch(`${API_BASE}/analyze/handwriting/confirm`, {
    method: "POST",
    body: form,
  }));
}
