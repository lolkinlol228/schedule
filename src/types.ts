export type RecordData = {
  id: string;
  name: string;
  active: boolean;
  [key: string]: unknown;
};
export type SchoolData = Record<string, RecordData[]> & { settings: any; _demo?: any };
export type Schema = {
  title?: string;
  type?: string;
  properties?: Record<string, Schema>;
  items?: Schema;
  enum?: Array<string | number>;
  default?: any;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  format?: string;
  $ref?: string;
  $defs?: Record<string, Schema>;
  required?: string[];
};
export type Lesson = {
  id: string;
  slot: number;
  parts: { teacher_id: string; room_id: string }[];
  lock: "free" | "preferred" | "locked";
  origin: string;
};
export type Event = {
  id: string;
  class_ids: string[];
  subject_id: string;
  course_id: string;
  topic: number;
  parts: { group_id: string }[];
};
export type Quality = {
  penalty: number;
  warnings: { message: string; penalty: number }[];
};
export type Version = {
  id: string;
  created: string;
  status: string;
  week: string;
  lessons: Lesson[];
  events: Event[];
  snapshot: SchoolData;
  quality: Quality;
  complete: boolean;
};
export const labels: Record<string, string> = {
  classes: "Классы",
  groups: "Подгруппы",
  teachers: "Учителя",
  rooms: "Кабинеты",
  subjects: "Предметы",
  courses: "Курсы и темы",
  plans: "Учебный план",
  merges: "Объединения",
  exceptions: "Исключения календаря",
  periods: "Учебные периоды",
  rules: "Правила решателя",
  settings: "Учебный год и звонки",
};
export const words: Record<string, string> = {
  ru: "Русский",
  kk: "Казахский",
  primary: "Основная",
  acceptable: "Допустимая",
  emergency: "Экстренная",
  unavailable: "Недоступно",
  undesirable: "Нежелательно",
  possible: "Можно",
  preferred: "Предпочтительно",
  normal: "Обычный",
  lab: "Лабораторный / практический",
  test: "Контрольная работа",
  groups: "Синхронные подгруппы",
  hard: "Обязательное",
  soft: "Пожелание",
  informational: "Справочно",
  low: "Низкий",
  medium: "Средний",
  high: "Высокий",
  critical: "Критический",
  school: "Вся школа",
  classes: "Класс",
  teachers: "Учитель",
  rooms: "Кабинет",
  draft: "Черновик",
  review: "На проверке",
  approved: "Утверждено",
  published: "Опубликовано",
  archived: "Архив",
  free: "Свободный",
  locked: "Заблокирован",
  lesson_minutes: "Длительность урока",
  break_minutes: "Минимальная перемена",
  daily_max: "Дневной максимум",
  weekly_max: "Недельный максимум",
  tests_daily: "Контрольных за день",
  availability: "Доступность",
  teacher_gaps: "Окна учителей",
  teacher_load: "Нагрузка учителей",
  consecutive: "Уроки подряд",
  method_day: "Методический день",
  difficulty: "Сложность предметов",
  distribution: "Распределение по неделе",
  room_changes: "Смена кабинетов",
  qualification: "Уровень квалификации",
  merge: "Объединения и вместимость",
  stability: "Сохранение уроков",
  complete: "Полное расписание",
  partial: "Частичное расписание",
  invalid: "Проверьте исходные данные",
  infeasible: "Условия несовместимы",
  timeout: "Время расчёта истекло",
  cancelled: "Расчёт отменён",
  failed: "Расчёт не завершён",
  interrupted: "Расчёт прерван",
};
export const days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"];
