import {
  useState,
  useEffect,
  useCallback,
  useRef,
  lazy,
  Suspense,
} from "react";
import {
  CalendarDays,
  LayoutDashboard,
  Users,
  GraduationCap,
  BookOpen,
  DoorOpen,
  Settings2,
  History,
  ShieldCheck,
  ArrowRight,
  Menu,
  LogOut,
  CheckCircle2,
  Clock3,
  Layers3,
  School,
  LifeBuoy,
} from "lucide-react";
import { toast, Toaster } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field, FieldLabel, FieldGroup } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { SchemaForm } from "@/components/schema-form";
import { api, setCsrf } from "@/api";
import { cn } from "@/lib/utils";
import { labels, words } from "@/types";
import type { SchoolData, Schema } from "@/types";
const MasterData = lazy(() => import("@/pages/master-data"));
const Schedule = lazy(() => import("@/pages/schedule"));
const Demonstrations = lazy(() => import("@/pages/demonstrations"));

function Auth({
  setup,
  mustChange,
  onLogin,
}: {
  setup: boolean;
  mustChange: boolean;
  onLogin: () => Promise<void>;
}) {
  const [password, setPassword] = useState("");
  const [current, setCurrent] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if ((setup || mustChange) && password !== confirm)
        throw new Error("Пароли не совпадают");
      if (mustChange) {
        await api("/auth/password", { current, password });
        toast.success("Пароль изменён. Войдите с новым паролем");
      } else {
        if (setup) await api("/auth/setup", { password });
        const result = await api("/auth/login", { password });
        setCsrf(result.csrf);
      }
      setPassword("");
      setCurrent("");
      setConfirm("");
      await onLogin();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <div className="auth-intro">
        <div className="brand">
          <div className="brand-symbol">
            <CalendarDays />
          </div>
          <span>
            ритм<span className="brand-dot">.</span>
          </span>
        </div>
        <p className="eyebrow">ШКОЛЬНОЕ РАСПИСАНИЕ</p>
        <h1>
          Порядок в каждом
          <br />
          учебном дне.
        </h1>
        <p>
          Уроки, преподаватели и кабинеты —<br />в одной согласованной сетке.
        </p>
      </div>
      <Card className="auth-card">
        <CardHeader>
          <CardTitle>
            {mustChange
              ? "Задайте постоянный пароль"
              : setup
                ? "Первый запуск"
                : "Вход администратора"}
          </CardTitle>
          <CardDescription>
            {mustChange
              ? "Первоначальный пароль необходимо заменить перед началом работы."
              : setup
                ? "Создайте первоначальный пароль администратора."
                : "Продолжите работу с расписанием вашей школы."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form id="auth-form" onSubmit={submit}>
            <FieldGroup>
              {mustChange ? (
                <Field data-invalid={!!error}>
                  <FieldLabel htmlFor="current">Текущий пароль</FieldLabel>
                  <Input
                    id="current"
                    type="password"
                    autoComplete="current-password"
                    required
                    value={current}
                    onChange={(e) => setCurrent(e.target.value)}
                    aria-invalid={!!error}
                  />
                </Field>
              ) : null}
              <Field data-invalid={!!error}>
                <FieldLabel htmlFor="password">
                  {mustChange ? "Новый пароль" : "Пароль"}
                </FieldLabel>
                <Input
                  id="password"
                  type="password"
                  autoComplete={
                    setup || mustChange ? "new-password" : "current-password"
                  }
                  required
                  minLength={setup || mustChange ? 12 : 1}
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-invalid={!!error}
                />
              </Field>
              {setup || mustChange ? (
                <Field data-invalid={!!error}>
                  <FieldLabel htmlFor="confirm">Повторите пароль</FieldLabel>
                  <Input
                    id="confirm"
                    type="password"
                    autoComplete="new-password"
                    minLength={12}
                    required
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    aria-invalid={!!error}
                  />
                  <p className="text-sm text-muted-foreground">
                    Не менее 12 символов.
                  </p>
                </Field>
              ) : null}
              {error ? (
                <Alert variant="destructive">
                  <AlertTitle>Не удалось продолжить</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
            </FieldGroup>
          </form>
        </CardContent>
        <CardFooter>
          <Button form="auth-form" className="w-full" disabled={busy}>
            {busy
              ? "Проверка…"
              : mustChange
                ? "Сохранить пароль"
                : setup
                  ? "Создать администратора"
                  : "Войти в систему"}
            <ArrowRight data-icon="inline-end" />
          </Button>
        </CardFooter>
      </Card>
    </main>
  );
}
const nav = [
  {
    group: "РАБОЧЕЕ ПРОСТРАНСТВО",
    items: [
      ["overview", "Обзор", LayoutDashboard],
      ["schedule", "Расписание", CalendarDays],
    ],
  },
  {
    group: "ИСХОДНЫЕ ДАННЫЕ",
    items: [
      ["settings", "Учебный год и звонки", Clock3],
      ["classes", "Классы", GraduationCap],
      ["groups", "Подгруппы", Layers3],
      ["teachers", "Учителя", Users],
      ["subjects", "Предметы", BookOpen],
      ["courses", "Курсы и темы", BookOpen],
      ["plans", "Учебный план", Layers3],
      ["rooms", "Кабинеты", DoorOpen],
      ["merges", "Объединения", Users],
      ["periods", "Учебные периоды", CalendarDays],
      ["exceptions", "Календарь исключений", CalendarDays],
    ],
  },
  {
    group: "УПРАВЛЕНИЕ",
    items: [
      ["rules", "Правила решателя", ShieldCheck],
      ["audit", "Журнал действий", History],
      ["account", "Безопасность", Settings2],
      ["help", "Руководство", LifeBuoy],
      ["demonstrations", "Демонстрации", School],
    ],
  },
] as const;
function Navigation({ page, go }: { page: string; go: (p: string) => void }) {
  return (
    <nav aria-label="Основная навигация">
      {nav.map((group) => (
        <div className="nav-group" key={group.group}>
          <p>{group.group}</p>
          {group.items.map(([id, label, Icon]) => (
            <a
              href={"#" + id}
              key={id}
              className={cn("nav-link", page === id && "active")}
              aria-current={page === id ? "page" : undefined}
              onClick={(e) => {
                if (!e.ctrlKey && !e.metaKey && !e.shiftKey) {
                  e.preventDefault();
                  go(id);
                }
              }}
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
              {page === id ? <span className="nav-active-dot" /> : null}
            </a>
          ))}
        </div>
      ))}
    </nav>
  );
}
function Loading() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-label="Загрузка">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-80 w-full" />
    </div>
  );
}
function SettingsPage({
  data,
  schema,
  revision,
  reload,
}: {
  data: SchoolData;
  schema: Schema;
  revision: number;
  reload: () => Promise<void>;
}) {
  const [value, setValue] = useState(data.settings);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const feedback = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (error) {
      feedback.current?.focus();
      feedback.current?.scrollIntoView({ block: "nearest" });
    }
  }, [error]);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/settings", { revision, settings: value }, "PUT");
      await reload();
      toast.success("Настройки сохранены");
      setError("");
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
      toast.error(
        "Настройки не сохранены. Проверьте сообщение рядом с кнопкой",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="eyebrow">ИСХОДНЫЕ ДАННЫЕ</p>
        <h1>Учебный год и звонки</h1>
        <p className="subtitle">
          Настройте учебный календарь и проверьте нормативы школы.
        </p>
      </div>
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Параметры школы</CardTitle>
          <CardDescription>
            Для генерации необходимы недельные пределы для всех активных
            параллелей в разделе «Правила решателя».
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            id="settings-form"
            onSubmit={save}
            className="flex flex-col gap-6"
          >
            <SchemaForm
              schema={schema}
              value={value}
              onChange={(next) => {
                setValue(next);
                setSaved(false);
              }}
              data={data}
            />
          </form>
        </CardContent>
        <CardFooter className="flex flex-col items-stretch gap-3">
          {error ? (
            <Alert ref={feedback} tabIndex={-1} variant="destructive">
              <AlertTitle>Настройки не сохранены</AlertTitle>
              <AlertDescription className="whitespace-pre-line">
                {error}
              </AlertDescription>
            </Alert>
          ) : null}
          {saved ? (
            <p role="status" className="text-sm">
              Настройки сохранены
            </p>
          ) : null}
          <Button disabled={busy} aria-busy={busy} form="settings-form">
            {busy ? "Сохранение…" : "Сохранить настройки"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
function Audit() {
  const [rows, setRows] = useState<any[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    api("/audit?offset=" + offset)
      .then((r) => live && setRows(r))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [offset]);
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="eyebrow">УПРАВЛЕНИЕ</p>
        <h1>Журнал действий</h1>
        <p className="subtitle">
          История операций администратора. Записи доступны только для чтения.
        </p>
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      ) : null}
      <div className="surface">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Время</TableHead>
              <TableHead>Операция</TableHead>
              <TableHead>Пользователь</TableHead>
              <TableHead>Результат</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell>
                  {new Date(r.created).toLocaleString("ru-RU")}
                </TableCell>
                <TableCell>{r.action}</TableCell>
                <TableCell>{r.payload.user}</TableCell>
                <TableCell>
                  {r.payload.result === "success"
                    ? "Выполнено"
                    : (words[r.payload.result] ?? r.payload.result)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex gap-3">
        <Button
          variant="outline"
          disabled={!offset}
          onClick={() => setOffset((n) => Math.max(0, n - 100))}
        >
          Назад
        </Button>
        <Button
          variant="outline"
          disabled={rows.length < 100}
          onClick={() => setOffset((n) => n + 100)}
        >
          Далее
        </Button>
      </div>
    </div>
  );
}
function Help() {
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <p className="eyebrow">ПОМОЩЬ АДМИНИСТРАТОРУ</p>
        <h1>Начало работы</h1>
      </div>
      {[
        [
          "1. Подготовьте данные",
          "Создайте предметы, классы, кабинеты и преподавателей. Затем добавьте курсы и строки учебного плана. Подгруппы должны в сумме покрывать весь класс.",
        ],
        [
          "2. Проверьте правила",
          "В разделе правил укажите недельный максимум для каждой параллели. В учебном годе подтвердите проверку нормативов. Задайте недоступность ресурсов и календарные исключения.",
        ],
        [
          "3. Составьте расписание",
          "Откройте расписание и запустите расчёт. Для базового шаблона не указывайте дату. Для календарной недели выберите понедельник. Примите результат после просмотра диагностики.",
        ],
        [
          "4. Проверьте и опубликуйте",
          "Нажмите занятие, чтобы изменить время или ресурсы. Доступно перетаскивание мышью. Каждое изменение проверяется сервером; сохранение создаёт новый черновик. Последовательно отправьте на проверку, утвердите и опубликуйте.",
        ],
        [
          "5. Оформите замену",
          "Выберите версию и запустите локальную замену с недоступным учителем или кабинетом. У разрешённых альтернативных преподавателей должна быть подходящая квалификация. Сравните результат до принятия.",
        ],
        [
          "6. Экспортируйте",
          "Выберите версию и фильтры класса, преподавателя или кабинета. Скачайте XLSX, PDF, CSV либо используйте печать. Сначала сохраните ручные изменения.",
        ],
      ].map(([title, text]) => (
        <Card key={title}>
          <CardHeader>
            <CardTitle>{title}</CardTitle>
          </CardHeader>
          <CardContent>
            <p>{text}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
export default function App() {
  const [auth, setAuth] = useState<
    "loading" | "setup" | "login" | "change" | "ready"
  >("loading");
  const [page, setPage] = useState(() =>
    nav.some((g) => g.items.some(([id]) => id === location.hash.slice(1)))
      ? location.hash.slice(1)
      : "overview",
  );
  const [mobile, setMobile] = useState(false);
  const [data, setData] = useState<SchoolData | null>(null);
  const [schemas, setSchemas] = useState<Record<string, Schema>>({});
  const [revision, setRevision] = useState(0);
  const [readiness, setReadiness] = useState<string[]>([]);
  const [versions, setVersions] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  useEffect(() => {
    const change = () => {
      const target = location.hash.slice(1);
      if (dirty) {
        history.replaceState(null, "", "#" + page);
        return;
      }
      if (nav.some((g) => g.items.some(([id]) => id === target)))
        setPage(target);
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, [dirty, page]);
  const checkAuth = useCallback(async () => {
    const status = await api("/auth/status");
    if (status.setup_required) {
      setAuth("setup");
      return;
    }
    try {
      const me = await api("/auth/me");
      setCsrf(me.csrf);
      setAuth(me.must_change ? "change" : "ready");
    } catch {
      setAuth("login");
    }
  }, []);
  const reload = useCallback(async () => {
    const [d, v] = await Promise.all([api("/data"), api("/versions")]);
    setData(d.data);
    setRevision(d.revision);
    setReadiness(d.readiness);
    setVersions(v);
  }, []);
  useEffect(() => {
    checkAuth().catch((e) => setError(e.message));
    const expired = () => {
      setAuth("login");
      setData(null);
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, [checkAuth]);
  useEffect(() => {
    if (auth === "ready")
      Promise.all([reload(), api("/schema").then(setSchemas)]).catch((e) =>
        setError(e.message),
      );
  }, [auth, reload]);
  function go(next: string) {
    if (dirty) {
      toast.error(
        "Сохраните изменения расписания или отмените их перед переходом",
      );
      return;
    }
    setPage(next);
    history.pushState(null, "", "#" + next);
    setMobile(false);
    window.scrollTo(0, 0);
  }
  async function exitDemo() {
    if (dirty) {
      toast.error("Сохраните или отмените правки расписания перед выходом");
      return;
    }
    setDemoBusy(true);
    try {
      await api("/demo/workspace", { revision });
      await reload();
      go("overview");
      toast.success("Рабочие данные школы восстановлены");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setDemoBusy(false);
    }
  }
  if (auth === "loading")
    return (
      <>
        <div className="p-8">
          <Loading />
          {error ? <p role="alert">{error}</p> : null}
        </div>
        <Toaster />
      </>
    );
  if (auth !== "ready")
    return (
      <>
        <Auth
          key={auth}
          setup={auth === "setup"}
          mustChange={auth === "change"}
          onLogin={checkAuth}
        />
        <Toaster position="bottom-right" />
      </>
    );
  return (
    <>
      <a className="skip-link" href="#main">
        Перейти к содержимому
      </a>
      <div className="app-shell">
        <aside className="sidebar no-print">
          <div className="brand">
            <div className="brand-symbol">
              <CalendarDays />
            </div>
            <span>
              ритм<span className="brand-dot">.</span>
            </span>
          </div>
          <div className="school-label">
            <School />
            <div>
              <strong>{data?.settings.school ?? "Школа"}</strong>
              <small>Управление расписанием</small>
            </div>
          </div>
          <Navigation page={page} go={go} />
          <div className="sidebar-bottom">
            <ShieldCheck />
            <span>
              Локальная система
              <br />
              <small>Администратор школы</small>
            </span>
          </div>
        </aside>
        <div className="workspace">
          <header className="topbar no-print">
            <div className="flex min-w-0 items-center gap-3">
              <Sheet open={mobile} onOpenChange={setMobile}>
                <SheetTrigger asChild>
                  <Button
                    className="mobile-menu"
                    variant="ghost"
                    size="icon"
                    aria-label="Открыть меню"
                  >
                    <Menu />
                  </Button>
                </SheetTrigger>
                <SheetContent side="left" className="overflow-y-auto">
                  <SheetHeader>
                    <SheetTitle>Ритм · навигация</SheetTitle>
                    <SheetDescription>{data?.settings.school}</SheetDescription>
                  </SheetHeader>
                  <Navigation page={page} go={go} />
                </SheetContent>
              </Sheet>
              <span className="topbar-crumb">
                Рабочее пространство <span>/</span>{" "}
                <strong>
                  {labels[page] ??
                    (
                      {
                        overview: "Обзор",
                        schedule: "Расписание",
                        audit: "Журнал действий",
                        account: "Безопасность",
                        help: "Руководство",
                      } as Record<string, string>
                    )[page]}
                </strong>
              </span>
            </div>
            <div className="flex items-center gap-4">
              <span className="year-label">
                {data?.settings.year_start.slice(0, 4)} /{" "}
                {data?.settings.year_end.slice(0, 4)}
              </span>
              <Separator orientation="vertical" className="h-5" />
              <Button
                variant="ghost"
                size="icon"
                aria-label="Выйти"
                onClick={async () => {
                  if (dirty) {
                    toast.error("Сначала сохраните расписание");
                    return;
                  }
                  try {
                    await api("/auth/logout", {});
                    setAuth("login");
                    setData(null);
                  } catch (e) {
                    toast.error((e as Error).message);
                  }
                }}
              >
                <LogOut />
              </Button>
            </div>
          </header>
          <main id="main" className="main-content" tabIndex={-1}>
            {data?._demo ? (
              <Alert className="mb-6 no-print">
                <AlertTitle>Демонстрационный режим</AlertTitle>
                <AlertDescription>
                  <p>
                    Вы работаете с вымышленными данными. Рабочие данные школы
                    сохранены.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => go("demonstrations")}
                    >
                      Сменить сценарий
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={demoBusy}
                      onClick={exitDemo}
                    >
                      {demoBusy ? "Возврат…" : "Вернуться к данным школы"}
                    </Button>
                  </div>
                </AlertDescription>
              </Alert>
            ) : null}
            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Не удалось загрузить данные</AlertTitle>
                <AlertDescription>
                  {error}
                  <Button
                    variant="outline"
                    onClick={() =>
                      reload()
                        .then(() => setError(""))
                        .catch((e) => setError(e.message))
                    }
                  >
                    Повторить
                  </Button>
                </AlertDescription>
              </Alert>
            ) : null}
            {!data || !schemas.settings ? (
              <Loading />
            ) : (
              <Suspense fallback={<Loading />}>
                {page === "overview" ? (
                  <div className="flex flex-col gap-7">
                    <div className="page-heading">
                      <div>
                        <p className="eyebrow">ШКОЛА В ОДНОМ ОКНЕ</p>
                        <h1>Обзор расписания</h1>
                        <p className="subtitle">
                          Подготовьте учебную неделю и держите всё под
                          контролем.
                        </p>
                      </div>
                      <Button onClick={() => go("schedule")}>
                        <CalendarDays data-icon="inline-start" />К расписанию
                        <ArrowRight data-icon="inline-end" />
                      </Button>
                    </div>
                    <div className="stats-grid">
                      {[
                        [
                          GraduationCap,
                          "Классов",
                          data.classes.filter((r) => r.active).length,
                          "В учебном плане",
                        ],
                        [
                          Users,
                          "Преподавателей",
                          data.teachers.filter((r) => r.active).length,
                          "Активные сотрудники",
                        ],
                        [
                          DoorOpen,
                          "Кабинетов",
                          data.rooms.filter((r) => r.active).length,
                          "Доступные помещения",
                        ],
                        [
                          BookOpen,
                          "Уроков в неделю",
                          data.plans
                            .filter((r) => r.active)
                            .reduce((s, p) => s + Number(p.hours), 0),
                          "По активным строкам плана",
                        ],
                      ].map(([Icon, label, value, hint]) => {
                        const I = Icon as typeof Users;
                        return (
                          <Card key={String(label)}>
                            <CardHeader>
                              <CardDescription>{String(label)}</CardDescription>
                              <div className="stat-icon">
                                <I aria-hidden="true" />
                              </div>
                            </CardHeader>
                            <CardContent>
                              <p className="stat-value">{String(value)}</p>
                              <p className="stat-hint">{String(hint)}</p>
                            </CardContent>
                          </Card>
                        );
                      })}
                    </div>
                    <div className="overview-columns">
                      <Card className="readiness-card">
                        <CardHeader>
                          <CardTitle>Готовность к составлению</CardTitle>
                          <CardDescription>
                            {readiness.length
                              ? "Проверьте исходные данные перед запуском расчёта."
                              : "Исходные данные прошли предварительную проверку."}
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="checklist">
                            {[
                              [
                                "Классы и преподаватели",
                                !!data.classes.length && !!data.teachers.length,
                                "classes",
                              ],
                              [
                                "Кабинеты и оборудование",
                                !!data.rooms.length,
                                "rooms",
                              ],
                              ["Учебный план", !!data.plans.length, "plans"],
                              [
                                "Нормативы и учебный год",
                                !readiness.length,
                                "settings",
                              ],
                            ].map(([label, done, target]) => (
                              <button
                                type="button"
                                key={String(label)}
                                onClick={() => go(String(target))}
                              >
                                <span
                                  className={cn(
                                    "check-icon",
                                    !!done && "is-done",
                                  )}
                                >
                                  {done ? <CheckCircle2 /> : <span />}
                                </span>
                                <span>{String(label)}</span>
                                <span className="check-status">
                                  {done ? "Готово" : "Заполнить"}
                                </span>
                                <ArrowRight />
                              </button>
                            ))}
                          </div>
                          {readiness.length ? (
                            <details className="mt-5">
                              <summary>
                                Что ещё проверить ({readiness.length})
                              </summary>
                              <ul className="readiness-errors">
                                {readiness.map((e) => (
                                  <li key={e}>{e}</li>
                                ))}
                              </ul>
                            </details>
                          ) : null}
                        </CardContent>
                        <CardFooter>
                          <Button
                            variant="outline"
                            onClick={() => go("schedule")}
                          >
                            Открыть генерацию
                            <ArrowRight data-icon="inline-end" />
                          </Button>
                        </CardFooter>
                      </Card>
                      <Card>
                        <CardHeader>
                          <CardTitle>Последняя версия</CardTitle>
                          <CardDescription>
                            Статус текущей работы над расписанием.
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          {versions[0] ? (
                            <div className="flex flex-col items-start gap-4">
                              <Badge variant="secondary">
                                {words[versions[0].status]}
                              </Badge>
                              <p className="text-xl font-medium">
                                {versions[0].week || "Базовая неделя"}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                {versions[0].count} занятий ·{" "}
                                {new Date(versions[0].created).toLocaleString(
                                  "ru-RU",
                                )}
                              </p>
                            </div>
                          ) : (
                            <div className="latest-empty">
                              <CalendarDays />
                              <p>Расписание ещё не создано</p>
                              <small>
                                Начните с исходных данных или ознакомьтесь с
                                демонстрацией.
                              </small>
                            </div>
                          )}
                        </CardContent>
                        <CardFooter>
                          {!data.classes.length ? (
                            <Button
                              variant="outline"
                              onClick={() => go("demonstrations")}
                            >
                              Выбрать демонстрацию
                            </Button>
                          ) : (
                            <Button
                              variant="outline"
                              onClick={() => go("schedule")}
                            >
                              Открыть расписание
                            </Button>
                          )}
                        </CardFooter>
                      </Card>
                    </div>
                    <div className="principle-strip">
                      <ShieldCheck />
                      <div>
                        <strong>
                          Обязательные правила проверяются автоматически
                        </strong>
                        <p>
                          Система проверяет пересечения, нагрузку, доступность и
                          вместимость перед публикацией.
                        </p>
                      </div>
                      <Button variant="ghost" onClick={() => go("rules")}>
                        Настроить правила
                        <ArrowRight data-icon="inline-end" />
                      </Button>
                    </div>
                  </div>
                ) : page === "schedule" ? (
                  <Schedule
                    data={data}
                    versions={versions}
                    reload={reload}
                    onDirty={setDirty}
                  />
                ) : page === "demonstrations" ? (
                  <Demonstrations
                    data={data}
                    revision={revision}
                    reload={reload}
                    go={go}
                  />
                ) : page === "settings" ? (
                  <SettingsPage
                    data={data}
                    schema={schemas.settings}
                    revision={revision}
                    reload={reload}
                  />
                ) : page === "audit" ? (
                  <Audit />
                ) : page === "help" ? (
                  <Help />
                ) : page === "account" ? (
                  <Auth setup={false} mustChange={true} onLogin={checkAuth} />
                ) : (
                  <MasterData
                    key={page}
                    kind={page}
                    data={data}
                    schemas={schemas}
                    revision={revision}
                    reload={reload}
                  />
                )}
              </Suspense>
            )}
          </main>
          <footer className="workspace-footer no-print">
            <span>Ритм · система школьного расписания</span>
            <span>5–11 классы / пятидневная неделя</span>
          </footer>
        </div>
      </div>
      <Toaster
        position="bottom-right"
        closeButton
        toastOptions={{
          style: {
            background: "white",
            color: "#1e293b",
            borderColor: "#ced6e1",
          },
        }}
      />
    </>
  );
}
