import { api } from '../api.ts';
import { setSpeechLang } from './speech.ts';
import type { CourseMeta, CourseOverview } from './types.ts';

/** The course that's open, shared by the course, lesson and review pages. */
export const course = $state<{ id: string; meta: CourseMeta | null; chinese: boolean }>({
	id: '',
	meta: null,
	chinese: false
});

export function setCourse(id: string, meta: CourseMeta) {
	course.id = id;
	course.meta = meta;
	course.chinese = meta.lang.startsWith('zh');
	setSpeechLang(meta.lang);
}

export async function loadCourse(id: string): Promise<CourseMeta> {
	if (course.id === id && course.meta) return course.meta;
	const overview = await api<CourseOverview>(`/learn/${id}/course`);
	setCourse(id, overview.meta);
	return overview.meta;
}

/** Feedback shows "hanzi · pinyin" for Chinese; only the characters should be read aloud. */
export function spoken(expected: string): string {
	return expected.split(' · ')[0];
}
