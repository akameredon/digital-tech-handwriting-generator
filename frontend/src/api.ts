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
