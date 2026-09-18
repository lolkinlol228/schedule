import { Fragment, useState, useEffect, useMemo, useRef } from "react";
import {
  Play,
  Download,
  Printer,
  Undo2,
  Redo2,
  Save,
  LockKeyhole,
  CalendarDays,
  List,
  CheckCircle2,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Field,
  FieldLabel,
  FieldGroup,
  FieldDescription,
} from "@/components/ui/field";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
} from "@/components/ui/empty";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { api } from "@/api";
import type { SchoolData, Version, Lesson, Quality } from "@/types";
import { days, words } from "@/types";

type Props = {
  data: SchoolData;
  versions: any[];
  reload: () => Promise<void>;
  initialId?: string;
  onDirty: (dirty: boolean) => void;
};
export default function Schedule({
  data,
  versions,
  reload,
  initialId,
  onDirty,
}: Props) {
  const [selectedId, setSelectedId] = useState(
    initialId ?? versions[0]?.id ?? "",
  );
  const [version, setVersion] = useState<Version | null>(null);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [past, setPast] = useState<Lesson[][]>([]);
  const [future, setFuture] = useState<Lesson[][]>([]);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [view, setView] = useState("calendar");
  const [filter, setFilter] = useState({
    class_id: data.classes[0]?.id ?? "",
    teacher_id: "",
    room_id: "",
    subject_id: "",
    language: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Lesson | null>(null);
  const [genOpen, setGenOpen] = useState(false);
  const [week, setWeek] = useState("");
  const [job, setJob] = useState<any>(null);
  const [recommendations, setRecommendations] = useState<any>(null);
  const [elapsed, setElapsed] = useState(0);
  const [repairScope, setRepairScope] = useState("teachers");
  const [repairResource, setRepairResource] = useState("");
  const [repairDays, setRepairDays] = useState([0, 1, 2, 3, 4]);
  const [expand, setExpand] = useState(5);
  const [compare, setCompare] = useState<any>(null);
  const [compareId, setCompareId] = useState("");
  const dirty =
    !!version && JSON.stringify(version.lessons) !== JSON.stringify(lessons);
  const busyRef = useRef(false);
  useEffect(() => {
    onDirty(dirty);
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => {
      window.removeEventListener("beforeunload", handler);
      onDirty(false);
    };
  }, [dirty, onDirty]);
  useEffect(() => {
    let live = true;
    if (selectedId) {
      api<Version>("/versions/" + selectedId)
        .then((v) => {
          if (live) {
            setVersion(v);
            setLessons(v.lessons);
            setQuality(v.quality);
            setPast([]);
            setFuture([]);
            setError("");
            setWeek(v.week);
          }
        })
        .catch((e) => setError(e.message));
    }
    return () => {
      live = false;
    };
  }, [selectedId]);
  useEffect(() => {
    if (!job || job.status !== "running") return;
    let live = true;
    const started = Date.now();
    let timeout: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await api("/jobs/" + job.id);
        if (live) {
          setJob(next);
          setElapsed((Date.now() - started) / 1000);
          if (next.status === "running") timeout = setTimeout(poll, 650);
        }
      } catch (e) {
        if (live) {
          setError((e as Error).message);
          timeout = setTimeout(poll, 2000);
        }
      }
    }
    timeout = setTimeout(poll, 350);
    return () => {
      live = false;
      clearTimeout(timeout);
    };
  }, [job?.id, job?.status === "running"]);
  const snapshot = version?.snapshot ?? data;
  const shiftGroups = useMemo(() => {
    const groups: { shift: number; slots: number[] }[] = [];
    snapshot.settings.bells.forEach((bell: any, slot: number) => {
      const shift = bell.shift ?? 1;
      let group = groups.find((g) => g.shift === shift);
      if (!group) {
        group = { shift, slots: [] };
        groups.push(group);
      }
      group.slots.push(slot);
    });
    return groups;
  }, [snapshot]);
  const diagnostics = useMemo(() => {
    const grouped = new Map<string, any>();
    for (const item of job?.diagnostics ?? []) {
      const key = item.title + "\n" + item.reason;
      const group = grouped.get(key);
      if (group) group.count++;
      else grouped.set(key, { ...item, count: 1 });
    }
    return [...grouped.values()];
  }, [job?.diagnostics]);
  // The list of soft violations repeats the same wording for every lesson, so the
  // panel groups identical causes and keeps the total penalty visible.
  const qualityRows = useMemo(() => {
    const grouped = new Map<string, { message: string; penalty: number; count: number }>();
    for (const item of quality?.warnings ?? []) {
      const row = grouped.get(item.message);
      if (row) {
        row.penalty += item.penalty;
        row.count++;
      } else grouped.set(item.message, { ...item, count: 1 });
    }
    return [...grouped.values()];
  }, [quality]);
  const stride = Math.max(8, snapshot.settings.bells.length);
  const bellLabel = (slot: number) => {
    const bells = snapshot.settings.bells;
    const shift = bells[slot]?.shift ?? 1;
    const number = bells
      .slice(0, slot + 1)
      .filter((b: any) => (b.shift ?? 1) === shift).length;
    return `${shift} смена · ${number} урок`;
  };
  const names = useMemo(
    () =>
      Object.fromEntries(
        ["classes", "teachers", "rooms", "subjects", "courses", "groups"].map(
          (kind) => [
            kind,
            Object.fromEntries(
              (snapshot[kind] ?? []).map((r) => [r.id, r.name]),
            ),
          ],
        ),
      ),
    [snapshot],
  );
  const events = useMemo(
    () => new Map(version?.events.map((e) => [e.id, e]) ?? []),
    [version],
  );
  const visible = useMemo(
    () =>
      lessons.filter((l) => {
        const e = events.get(l.id);
        return (
          e &&
          (!filter.class_id || e.class_ids.includes(filter.class_id)) &&
          (!filter.teacher_id ||
            l.parts.some((p) => p.teacher_id === filter.teacher_id)) &&
          (!filter.room_id ||
            l.parts.some((p) => p.room_id === filter.room_id)) &&
          (!filter.subject_id || e.subject_id === filter.subject_id) &&
          (!filter.language ||
            e.class_ids.some(
              (cid) =>
                snapshot.classes.find((c) => c.id === cid)?.language ===
                filter.language,
            ))
        );
      }),
    [lessons, filter, events, snapshot],
  );
  const bySlot = useMemo(() => {
    const map = new Map<number, Lesson[]>();
    for (const l of visible) map.set(l.slot, [...(map.get(l.slot) ?? []), l]);
    return map;
  }, [visible]);
  function title(l: Lesson) {
    const e = events.get(l.id);
    return e ? names.subjects[e.subject_id] : "Занятие";
  }
  async function change(
    next: Lesson[],
    history: "new" | "undo" | "redo" = "new",
  ) {
    if (busyRef.current || !version) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api("/versions/" + version.id + "/validate", {
        lessons: next,
      });
      if (history === "new") {
        setPast((p) => [...p, lessons]);
        setFuture([]);
      } else if (history === "undo") {
        setPast((p) => p.slice(0, -1));
        setFuture((f) => [lessons, ...f]);
      } else {
        setFuture((f) => f.slice(1));
        setPast((p) => [...p, lessons]);
      }
      setLessons(next);
      setQuality(result.quality);
      setEditing(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  async function save() {
    if (!version) return;
    setBusy(true);
    try {
      const result = await api("/versions/" + version.id + "/edit", {
        lessons,
      });
      await reload();
      setSelectedId(result.id);
      toast.success("Сохранён новый черновик");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function generate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api("/generate", {
        week,
        source_id: version?.id ?? "",
        repair_scope: repairScope,
        repair_resource: repairResource,
        repair_days: repairDays,
        expand_percent: expand,
      });
      setJob({ id: result.id, status: "running" });
      setGenOpen(false);
      setElapsed(0);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function accept() {
    setBusy(true);
    try {
      const result = await api("/jobs/" + job.id + "/accept", {});
      await reload();
      setSelectedId(result.id);
      setJob(null);
      toast.success("Результат сохранён как черновик");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function status(next: string) {
    if (!version) return;
    setBusy(true);
    try {
      await api("/versions/" + version.id + "/status", { status: next });
      setVersion((v) => (v ? { ...v, status: next } : v));
      await reload();
      toast.success("Статус обновлён");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const nextStatus: Record<string, string> = {
    draft: "review",
    review: "approved",
    approved: "published",
  };
  return (
    <div className="flex flex-col gap-5">
      <div className="page-heading no-print">
        <div>
          <p className="eyebrow">ПЛАНИРОВАНИЕ УЧЕБНОЙ НЕДЕЛИ</p>
          <h1>Расписание</h1>
          <p className="subtitle">Единая сетка занятий, ресурсов и замен.</p>
        </div>
        <Button
          disabled={dirty || job?.status === "running"}
          onClick={() => setGenOpen(true)}
        >
          <Play data-icon="inline-start" />
          Составить расписание
        </Button>
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Изменение не применено</AlertTitle>
          <AlertDescription className="whitespace-pre-line">
            {error}
          </AlertDescription>
        </Alert>
      ) : null}
      {job ? (
        <Card className="no-print">
          <CardHeader>
            <CardTitle>
              {job.status === "running"
                ? "Составляем расписание…"
                : (words[job.status] ?? job.status)}
            </CardTitle>
            <CardDescription>
              {job.status === "running"
                ? `Проверка ограничений и поиск решения · ${elapsed.toFixed(1)} с`
                : `Размещено ${job.lessons?.length ?? 0} из ${(job.lessons?.length ?? 0) + (job.missing?.length ?? 0)} занятий · ${job.elapsed ?? elapsed.toFixed(1)} с`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div role="status" aria-live="polite">
              {job.status === "running" ? (
                <p>Можно продолжать просмотр. Результат появится здесь.</p>
              ) : null}
            </div>
            {job.errors?.map((e: string) => (
              <p key={e}>{e}</p>
            ))}
            {job.missing?.length ? (
              <Alert className="mb-4">
                <AlertTitle>
                  {job.capacity_issues?.length
                    ? "Подтверждён дефицит ресурсов"
                    : "Полное расписание пока не найдено"}
                </AlertTitle>
                <AlertDescription>
                  {job.capacity_issues?.length ? (
                    <>
                      <p>
                        При текущих ограничениях весь план не помещается.
                        Ресурсный час — один урок для одного учителя или
                        кабинета; подгруппы используют несколько ресурсов.
                      </p>
                      <ul>
                        {job.capacity_issues.map((issue: any) => (
                          <li key={issue.resource}>
                            <strong>{issue.message}</strong>
                            <p>{issue.action}</p>
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p>
                      Список ниже показывает пропуски найденного варианта. Он не
                      означает, что полное расписание невозможно. Для остальных
                      ограничений причина может быть не установлена за
                      отведённое время.
                    </p>
                  )}
                </AlertDescription>
              </Alert>
            ) : null}
            {job.proposal ? (
              <Alert>
                <AlertTitle>{job.proposal.title}</AlertTitle>
                <AlertDescription>
                  Дополнительно размещено часов классов:{" "}
                  {job.proposal.additional_class_hours}. Изменения применятся
                  только к новой версии после принятия.
                  <ul>
                    {job.proposal.changes.map((x: string) => (
                      <li key={x}>{x}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            ) : null}
            {job.diagnostics?.length ? (
              <details>
                <summary>
                  Неразмещённые занятия и рекомендации ({job.diagnostics.length}
                  )
                </summary>
                <div className="diagnostic-list">
                  {diagnostics.map((d: any) => (
                    <article key={d.lesson_id}>
                      <strong>
                        {d.title} · не размещено: {d.count}
                      </strong>
                      <p>{d.reason}</p>
                      <ul>
                        {d.actions.map((a: string) => (
                          <li key={a}>{a}</li>
                        ))}
                      </ul>
                      <small>{d.effect}</small>
                    </article>
                  ))}
                </div>
              </details>
            ) : null}
            {recommendations ? (
              <div className="flex flex-col gap-4 mt-4">
                <p className="text-sm">{recommendations.message}</p>
                {recommendations.items.map((r: any) => (
                  <Alert key={r.id}>
                    <AlertTitle>{r.title}</AlertTitle>
                    <AlertDescription>
                      Дополнительно размещено часов: {r.additional_class_hours}.
                      Штраф пожеланий: {r.penalty}.
                      <Button
                        variant="outline"
                        disabled={busy}
                        onClick={() =>
                          api("/jobs/" + r.id)
                            .then((j) => {
                              setJob(j);
                              setRecommendations(null);
                            })
                            .catch((e) => setError(e.message))
                        }
                      >
                        Посмотреть вариант
                      </Button>
                    </AlertDescription>
                  </Alert>
                ))}
              </div>
            ) : null}
            {job.lessons && version ? (
              <p className="text-sm text-muted-foreground">
                Перемещено относительно выбранной версии:{" "}
                {
                  job.lessons.filter((l: Lesson) => {
                    const old = version.lessons.find((x) => x.id === l.id);
                    return (
                      old &&
                      (old.slot !== l.slot ||
                        JSON.stringify(old.parts) !== JSON.stringify(l.parts))
                    );
                  }).length
                }
                . Применение создаст отдельный черновик.
              </p>
            ) : null}
          </CardContent>
          <CardFooter className="flex flex-wrap gap-3">
            {job.status === "running" ? (
              <Button
                variant="outline"
                onClick={() =>
                  api("/jobs/" + job.id + "/cancel", {}).catch((e) =>
                    setError(e.message),
                  )
                }
              >
                Отменить расчёт
              </Button>
            ) : (
              <>
                <Button variant="outline" onClick={() => setJob(null)}>
                  Закрыть результат
                </Button>
                {job.diagnostics?.length ? (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        setRecommendations(
                          await api("/jobs/" + job.id + "/recommendations", {}),
                        );
                      } catch (e) {
                        setError((e as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    {busy ? "Проверка вариантов…" : "Проверить варианты"}
                  </Button>
                ) : null}
                {["complete", "partial"].includes(job.status) ? (
                  <Button disabled={busy} onClick={accept}>
                    Принять результат
                  </Button>
                ) : null}
              </>
            )}
          </CardFooter>
        </Card>
      ) : null}
      {versions.length ? (
        <div className="toolbar no-print">
          <Field orientation="horizontal">
            <FieldLabel htmlFor="version">Версия</FieldLabel>
            <NativeSelect
              id="version"
              value={selectedId}
              disabled={dirty || busy}
              onChange={(e) => setSelectedId(e.target.value)}
            >
              {versions.map((v) => (
                <NativeSelectOption key={v.id} value={v.id}>
                  {v.week || "Базовая неделя"} ·{" "}
                  {new Date(v.created).toLocaleString("ru-RU")} ·{" "}
                  {words[v.status]}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </Field>
          {version ? (
            <Badge
              variant={version.status === "published" ? "default" : "secondary"}
            >
              {words[version.status]}
            </Badge>
          ) : null}
        </div>
      ) : null}
      {version ? (
        <>
          <div className="filter-bar no-print">
            {[
              ["class_id", "classes", "Все классы"],
              ["teacher_id", "teachers", "Все учителя"],
              ["room_id", "rooms", "Все кабинеты"],
              ["subject_id", "subjects", "Все предметы"],
            ].map(([key, kind, label]) => (
              <NativeSelect
                key={key}
                aria-label={label}
                value={filter[key as keyof typeof filter]}
                onChange={(e) =>
                  setFilter((f) => ({ ...f, [key]: e.target.value }))
                }
              >
                <NativeSelectOption value="">{label}</NativeSelectOption>
                {snapshot[kind].map((r) => (
                  <NativeSelectOption key={r.id} value={r.id}>
                    {r.name}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            ))}
            <NativeSelect
              aria-label="Язык потока"
              value={filter.language}
              onChange={(e) =>
                setFilter((f) => ({ ...f, language: e.target.value }))
              }
            >
              <NativeSelectOption value="">Все языки</NativeSelectOption>
              <NativeSelectOption value="ru">Русский</NativeSelectOption>
              <NativeSelectOption value="kk">Казахский</NativeSelectOption>
            </NativeSelect>
          </div>
          <div className="toolbar no-print">
            <ToggleGroup
              type="single"
              variant="outline"
              value={view}
              onValueChange={(v) => v && setView(v)}
              aria-label="Вид расписания"
            >
              <ToggleGroupItem value="calendar">
                <CalendarDays />
                Неделя
              </ToggleGroupItem>
              <ToggleGroupItem value="list">
                <List />
                Список
              </ToggleGroupItem>
            </ToggleGroup>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                aria-label="Отменить изменение"
                disabled={!past.length || busy}
                onClick={() => change(past[past.length - 1], "undo")}
              >
                <Undo2 />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Повторить изменение"
                disabled={!future.length || busy}
                onClick={() => change(future[0], "redo")}
              >
                <Redo2 />
              </Button>
              {dirty ? (
                <Badge variant="outline">Не сохранено</Badge>
              ) : (
                <span className="saved-label">
                  <CheckCircle2 />
                  Сохранено
                </span>
              )}
              <Button
                variant="outline"
                disabled={!dirty || busy}
                onClick={save}
              >
                <Save data-icon="inline-start" />
                Сохранить
              </Button>
            </div>
          </div>
          <div className="print-title">
            <h2>{snapshot.settings.school}</h2>
            <p>
              {version.week || "Базовая неделя"} · {words[version.status]} ·
              Версия {version.id.slice(0, 8)}
            </p>
            <p>Сформировано: {new Date().toLocaleString("ru-RU")}</p>
          </div>
          {view === "calendar" ? (
            <>
              <div className="schedule-context">
                <strong>
                  {filter.class_id
                    ? `Расписание класса ${names.classes[filter.class_id] ?? ""}`
                    : "Общая сетка школы"}
                </strong>
                <p>
                  Сетка этой версии:{" "}
                  {shiftGroups
                    .map((g) => `${g.shift} смена — ${g.slots.length} звонков`)
                    .join("; ")}
                  . Это доступные позиции, а не обязательное число уроков у
                  каждого класса.
                </p>
                <p className="text-sm text-muted-foreground">
                  Смена задаётся в звонках и карточке класса, а не определяется
                  временем на часах.
                  {shiftGroups.length === 1
                    ? " В этой версии вторая смена не настроена."
                    : ""}
                </p>
                {!filter.class_id ? (
                  <p className="text-sm text-muted-foreground">
                    Для подробного просмотра выберите класс, учителя или кабинет
                    в фильтрах выше.
                  </p>
                ) : null}
              </div>
              <div
                className="calendar-scroll surface"
                role="region"
                aria-label="Недельная сетка расписания"
                tabIndex={0}
              >
                <table className="calendar">
                  <caption className="sr-only">
                    Расписание по дням, сменам и времени занятий
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Урок</th>
                      {days.map((day) => (
                        <th scope="col" key={day}>
                          {day}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {snapshot.settings.bells.map((bell: any, slot: number) => (
                      <Fragment key={slot}>
                        {slot === 0 ||
                        (snapshot.settings.bells[slot - 1].shift ?? 1) !==
                          (bell.shift ?? 1) ? (
                          <tr className="shift-divider">
                            <th colSpan={6} scope="colgroup">
                              Смена {bell.shift ?? 1}
                              <span>
                                {" "}
                                ·{" "}
                                {
                                  shiftGroups.find(
                                    (g) => g.shift === (bell.shift ?? 1),
                                  )?.slots.length
                                }{" "}
                                звонков
                              </span>
                            </th>
                          </tr>
                        ) : null}
                        <tr>
                          <th scope="row" aria-label={bellLabel(slot)}>
                            <span className="slot-number">
                              {
                                snapshot.settings.bells
                                  .slice(0, slot + 1)
                                  .filter(
                                    (b: any) =>
                                      (b.shift ?? 1) === (bell.shift ?? 1),
                                  ).length
                              }{" "}
                              урок
                            </span>
                            <span className="slot-time">
                              {bell.start}
                              {"–"}
                              {bell.end}
                            </span>
                          </th>
                          {days.map((day, d) => (
                            <td
                              key={day}
                              onDragOver={(e) => {
                                if (!busy) e.preventDefault();
                              }}
                              onDrop={(e) => {
                                e.preventDefault();
                                const id = e.dataTransfer.getData("text/plain");
                                const l = lessons.find((x) => x.id === id);
                                if (l)
                                  change(
                                    lessons.map((x) =>
                                      x.id === id
                                        ? {
                                            ...x,
                                            slot: d * stride + slot,
                                            origin: "manual",
                                          }
                                        : x,
                                    ),
                                  );
                              }}
                            >
                              {(bySlot.get(d * stride + slot) ?? []).map(
                                (l) => {
                                  const e = events.get(l.id)!;
                                  return (
                                    <button
                                      key={l.id}
                                      className="lesson"
                                      type="button"
                                      draggable={!busy && l.lock !== "locked"}
                                      onDragStart={(ev) =>
                                        ev.dataTransfer.setData(
                                          "text/plain",
                                          l.id,
                                        )
                                      }
                                      onClick={() => {
                                        setError("");
                                        setEditing(structuredClone(l));
                                      }}
                                      disabled={busy}
                                      aria-label={`${title(l)}, ${e.class_ids.map((c) => names.classes[c]).join(", ")}, ${day}, ${bellLabel(slot)}`}
                                    >
                                      <span className="lesson-heading">
                                        {title(l)}
                                        {l.lock === "locked" ? (
                                          <LockKeyhole aria-label="Заблокирован" />
                                        ) : null}
                                      </span>
                                      <span className="lesson-class">
                                        {e.class_ids
                                          .map((c) => names.classes[c])
                                          .join(" + ")}{" "}
                                        · Тема {e.topic}
                                      </span>
                                      {l.parts.map((p, i) => (
                                        <span
                                          className="lesson-resource"
                                          key={i}
                                        >
                                          {names.teachers[p.teacher_id]}
                                          <span>
                                            каб. {names.rooms[p.room_id]}
                                          </span>
                                        </span>
                                      ))}
                                    </button>
                                  );
                                },
                              )}
                              {!bySlot.get(d * stride + slot)?.length ? (
                                <span className="free-slot">—</span>
                              ) : null}
                            </td>
                          ))}
                        </tr>
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="surface">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>День / урок</TableHead>
                    <TableHead>Класс</TableHead>
                    <TableHead>Предмет</TableHead>
                    <TableHead>Учитель · кабинет</TableHead>
                    <TableHead className="no-print">Действие</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visible
                    .toSorted((a, b) => a.slot - b.slot)
                    .map((l) => (
                      <TableRow key={l.id}>
                        <TableCell>
                          {days[Math.floor(l.slot / stride)]} ·{" "}
                          {bellLabel(l.slot % stride)}
                        </TableCell>
                        <TableCell>
                          {events
                            .get(l.id)
                            ?.class_ids.map((c) => names.classes[c])
                            .join(", ")}
                        </TableCell>
                        <TableCell>{title(l)}</TableCell>
                        <TableCell>
                          {l.parts
                            .map(
                              (p) =>
                                `${names.teachers[p.teacher_id]} · ${names.rooms[p.room_id]}`,
                            )
                            .join("; ")}
                        </TableCell>
                        <TableCell className="no-print">
                          <Button
                            variant="ghost"
                            onClick={() => setEditing(structuredClone(l))}
                          >
                            Изменить
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </div>
          )}
          <div className="schedule-footer no-print">
            <span>{visible.length} занятий в выбранном представлении</span>
            <div className="flex flex-wrap gap-2">
              {["xlsx", "pdf", "csv"].map((fmt) => (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={dirty}
                  key={fmt}
                  asChild={!dirty}
                >
                  {dirty ? (
                    <span>{fmt.toUpperCase()}</span>
                  ) : (
                    <a
                      href={`/api/versions/${version.id}/export/${fmt}?${new URLSearchParams(filter)}`}
                    >
                      <Download data-icon="inline-start" />
                      {fmt.toUpperCase()}
                    </a>
                  )}
                </Button>
              ))}
              <Button
                variant="outline"
                size="sm"
                disabled={dirty}
                onClick={() => window.print()}
              >
                <Printer data-icon="inline-start" />
                Печать
              </Button>
            </div>
          </div>
          <div className="bottom-panels no-print">
            <Card>
              <CardHeader>
                <CardTitle>Проверка и публикация</CardTitle>
                <CardDescription>
                  {version.complete
                    ? "Все занятия учебного плана размещены."
                    : "Часть занятий не размещена. Публикация недоступна."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Каждый переход проходит серверную проверку обязательных
                  правил.
                </p>
              </CardContent>
              <CardFooter className="flex flex-wrap gap-2">
                {nextStatus[version.status] ? (
                  <Button
                    disabled={dirty || busy || !version.complete}
                    onClick={() => status(nextStatus[version.status])}
                  >
                    {words[nextStatus[version.status]]}
                  </Button>
                ) : null}
                {version.status !== "archived" ? (
                  <Button
                    variant="outline"
                    disabled={dirty || busy}
                    onClick={() => status("archived")}
                  >
                    В архив
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    onClick={async () => {
                      try {
                        const v = await api(
                          "/versions/" + version.id + "/restore",
                          {},
                        );
                        await reload();
                        setSelectedId(v.id);
                      } catch (e) {
                        setError((e as Error).message);
                      }
                    }}
                  >
                    Восстановить черновик
                  </Button>
                )}
              </CardFooter>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Качество расписания</CardTitle>
                <CardDescription>
                  Штраф за пожелания: {quality?.penalty ?? 0}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <details>
                  <summary>
                    Причины мягких нарушений ({quality?.warnings.length ?? 0})
                  </summary>
                  <ul className="quality-list">
                    {qualityRows.map((w) => (
                      <li key={w.message}>
                        {w.message}
                        {w.count > 1 ? ` · ${w.count} раз` : ""}
                        <Badge variant="outline">+{w.penalty}</Badge>
                      </li>
                    ))}
                  </ul>
                </details>
              </CardContent>
            </Card>
          </div>
          <Card className="no-print">
            <CardHeader>
              <CardTitle>Сравнение версий</CardTitle>
              <CardDescription>
                Добавленные, удалённые и изменённые занятия относительно
                выбранной версии.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-3">
                <NativeSelect
                  aria-label="Версия для сравнения"
                  value={compareId}
                  onChange={(e) => setCompareId(e.target.value)}
                >
                  <NativeSelectOption value="">
                    Выберите версию
                  </NativeSelectOption>
                  {versions
                    .filter((v) => v.id !== version.id)
                    .map((v) => (
                      <NativeSelectOption key={v.id} value={v.id}>
                        {new Date(v.created).toLocaleString("ru-RU")} ·{" "}
                        {words[v.status]}
                      </NativeSelectOption>
                    ))}
                </NativeSelect>
                <Button
                  variant="outline"
                  disabled={!compareId}
                  onClick={() =>
                    api(
                      "/compare?" +
                        new URLSearchParams({
                          before: compareId,
                          after: version.id,
                        }),
                    )
                      .then(setCompare)
                      .catch((e) => setError(e.message))
                  }
                >
                  Сравнить
                </Button>
              </div>
              {compare ? (
                <div>
                  <p>
                    Добавлено: {compare.added.length} · Удалено:{" "}
                    {compare.removed.length} · Изменено:{" "}
                    {compare.changed.length}
                  </p>
                  <ul className="quality-list">
                    {compare.added.map((x: any) => (
                      <li key={"add-" + x.id}>Добавлено: {x.label}</li>
                    ))}
                    {compare.removed.map((x: any) => (
                      <li key={"remove-" + x.id}>Удалено: {x.label}</li>
                    ))}
                    {compare.changed.map((x: any) => (
                      <li key={x.after.id}>
                        {x.before_label} → {x.after_label}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </>
      ) : (
        <Empty className="surface">
          <EmptyHeader>
            <EmptyTitle>Первая учебная неделя начинается здесь</EmptyTitle>
            <EmptyDescription>
              Заполните исходные данные и нажмите «Составить расписание».
              Готовый результат появится в этой сетке.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}
      <Dialog open={genOpen} onOpenChange={setGenOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Составить расписание</DialogTitle>
            <DialogDescription>
              Обязательные ограничения применяются ко всем занятиям. Лимит
              расчёта — 10 секунд.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={generate} className="flex flex-col gap-5">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="week">Неделя</FieldLabel>
                <Input
                  id="week"
                  type="date"
                  value={week}
                  onChange={(e) => setWeek(e.target.value)}
                />
                <FieldDescription>
                  Оставьте пустым для базового шаблона. Для конкретной недели
                  выберите понедельник.
                </FieldDescription>
              </Field>
              {version ? (
                <>
                  <Field>
                    <FieldLabel htmlFor="repair-type">
                      Локальная замена
                    </FieldLabel>
                    <NativeSelect
                      id="repair-type"
                      value={repairScope}
                      onChange={(e) => {
                        setRepairScope(e.target.value);
                        setRepairResource("");
                      }}
                    >
                      <NativeSelectOption value="teachers">
                        Недоступен учитель
                      </NativeSelectOption>
                      <NativeSelectOption value="rooms">
                        Недоступен кабинет
                      </NativeSelectOption>
                    </NativeSelect>
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="repair-resource">
                      Ресурс на выбранную неделю
                    </FieldLabel>
                    <NativeSelect
                      id="repair-resource"
                      value={repairResource}
                      onChange={(e) => setRepairResource(e.target.value)}
                    >
                      <NativeSelectOption value="">
                        Без локального ремонта
                      </NativeSelectOption>
                      {data[repairScope]
                        .filter((r) => r.active)
                        .map((r) => (
                          <NativeSelectOption value={r.id} key={r.id}>
                            {r.name}
                          </NativeSelectOption>
                        ))}
                    </NativeSelect>
                  </Field>
                  {repairResource ? (
                    <>
                      <Field>
                        <FieldLabel>Дни недоступности</FieldLabel>
                        <div className="flex flex-wrap gap-3">
                          {days.map((d, i) => (
                            <label className="choice" key={d}>
                              <input
                                type="checkbox"
                                checked={repairDays.includes(i)}
                                onChange={(e) =>
                                  setRepairDays(
                                    e.target.checked
                                      ? [...repairDays, i]
                                      : repairDays.filter((x) => x !== i),
                                  )
                                }
                              />
                              {d}
                            </label>
                          ))}
                        </div>
                      </Field>
                      <Field>
                        <FieldLabel htmlFor="expand">
                          Дополнительно разрешить менять, %
                        </FieldLabel>
                        <Input
                          id="expand"
                          type="number"
                          min={0}
                          max={100}
                          value={expand}
                          onChange={(e) => setExpand(Number(e.target.value))}
                        />
                        <FieldDescription>
                          По умолчанию сохраняются незатронутые уроки, кроме 5%
                          окружения. Результат потребует подтверждения.
                        </FieldDescription>
                      </Field>
                    </>
                  ) : null}
                </>
              ) : null}
            </FieldGroup>
            <DialogFooter>
              <Button disabled={busy}>
                <Play data-icon="inline-start" />
                {busy ? "Запуск…" : "Начать расчёт"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!editing}
        onOpenChange={(open) => !open && setEditing(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? title(editing) : "Занятие"}</DialogTitle>
            <DialogDescription>
              Укажите время и ресурсы. При коллизии изменение будет отклонено.
            </DialogDescription>
          </DialogHeader>
          {editing ? (
            <form
              className="flex flex-col gap-5"
              onSubmit={(e) => {
                e.preventDefault();
                change(
                  lessons.map((l) =>
                    l.id === editing.id ? { ...editing, origin: "manual" } : l,
                  ),
                );
              }}
            >
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="lesson-day">День</FieldLabel>
                  <NativeSelect
                    id="lesson-day"
                    value={Math.floor(editing.slot / stride)}
                    onChange={(e) =>
                      setEditing({
                        ...editing,
                        slot:
                          Number(e.target.value) * stride +
                          (editing.slot % stride),
                      })
                    }
                  >
                    {days.map((d, i) => (
                      <NativeSelectOption value={i} key={d}>
                        {d}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </Field>
                <Field>
                  <FieldLabel htmlFor="lesson-slot">Урок</FieldLabel>
                  <NativeSelect
                    id="lesson-slot"
                    value={editing.slot % stride}
                    onChange={(e) =>
                      setEditing({
                        ...editing,
                        slot:
                          Math.floor(editing.slot / stride) * stride +
                          Number(e.target.value),
                      })
                    }
                  >
                    {snapshot.settings.bells.map((b: any, i: number) => (
                      <NativeSelectOption value={i} key={i}>
                        {bellLabel(i)} · {b.start}–{b.end}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </Field>
                {editing.parts.map((p, i) => (
                  <FieldGroup key={i}>
                    {[
                      ["teacher_id", "teachers", "Учитель"],
                      ["room_id", "rooms", "Кабинет"],
                    ].map(([key, kind, label]) => (
                      <Field key={key}>
                        <FieldLabel htmlFor={`${key}-${i}`}>
                          {label}
                          {editing.parts.length > 1
                            ? ` · подгруппа ${i + 1}`
                            : ""}
                        </FieldLabel>
                        <NativeSelect
                          id={`${key}-${i}`}
                          value={p[key as keyof typeof p]}
                          onChange={(e) =>
                            setEditing({
                              ...editing,
                              parts: editing.parts.map((part, j) =>
                                j === i
                                  ? { ...part, [key]: e.target.value }
                                  : part,
                              ),
                            })
                          }
                        >
                          {snapshot[kind]
                            .filter((r) => r.active)
                            .map((r) => (
                              <NativeSelectOption value={r.id} key={r.id}>
                                {r.name}
                              </NativeSelectOption>
                            ))}
                        </NativeSelect>
                      </Field>
                    ))}
                  </FieldGroup>
                ))}
                <Field>
                  <FieldLabel htmlFor="lesson-lock">Фиксация</FieldLabel>
                  <NativeSelect
                    id="lesson-lock"
                    value={editing.lock}
                    onChange={(e) =>
                      setEditing({
                        ...editing,
                        lock: e.target.value as Lesson["lock"],
                      })
                    }
                  >
                    <NativeSelectOption value="free">
                      Свободный
                    </NativeSelectOption>
                    <NativeSelectOption value="preferred">
                      Желательно сохранить
                    </NativeSelectOption>
                    <NativeSelectOption value="locked">
                      Заблокирован
                    </NativeSelectOption>
                  </NativeSelect>
                </Field>
              </FieldGroup>
              {error ? (
                <Alert variant="destructive">
                  <AlertTitle>Изменение отклонено</AlertTitle>
                  <AlertDescription className="whitespace-pre-line">
                    {error}
                  </AlertDescription>
                </Alert>
              ) : null}
              <DialogFooter>
                <Button disabled={busy}>
                  <SlidersHorizontal data-icon="inline-start" />
                  {busy ? "Проверка…" : "Проверить и применить"}
                </Button>
              </DialogFooter>
            </form>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
