import { useState, useDeferredValue } from "react";
import { Plus, Search, Archive, FilePenLine } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
} from "@/components/ui/empty";
import { SchemaForm, defaults } from "@/components/schema-form";
import { api } from "@/api";
import type { Schema, SchoolData, RecordData } from "@/types";
import { labels, words } from "@/types";

export default function MasterData({
  kind,
  data,
  schemas,
  revision,
  reload,
}: {
  kind: string;
  data: SchoolData;
  schemas: Record<string, Schema>;
  revision: number;
  reload: () => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const query = useDeferredValue(search.toLocaleLowerCase("ru"));
  const [editing, setEditing] = useState<RecordData | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const schema = schemas[kind];
  const rows = (data[kind] ?? []).filter((r) =>
    r.name.toLocaleLowerCase("ru").includes(query),
  );
  const columns = Object.entries(schema.properties ?? {})
    .filter(
      ([k, s]) => !["id", "name", "active"].includes(k) && s.type !== "array",
    )
    .slice(0, 3);
  function display(key: string, value: unknown) {
    const ref: Record<string, string> = {
      class_id: "classes",
      course_id: "courses",
      subject_id: "subjects",
      group_id: "groups",
    };
    return ref[key]
      ? (data[ref[key]]?.find((r) => r.id === value)?.name ?? "—")
      : typeof value === "boolean"
        ? value
          ? "Да"
          : "Нет"
        : (words[String(value)] ?? String(value ?? "—"));
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setBusy(true);
    setError("");
    try {
      await api("/data/" + kind, { revision, record: editing });
      await reload();
      setEditing(null);
      toast.success("Запись сохранена");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function archive(r: RecordData) {
    try {
      await api("/data/" + kind, {
        revision,
        record: { ...r, active: !r.active },
      });
      await reload();
      toast.success(r.active ? "Запись архивирована" : "Запись восстановлена");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
  return (
    <div className="flex flex-col gap-6">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ИСХОДНЫЕ ДАННЫЕ</p>
          <h1>{labels[kind]}</h1>
          <p className="subtitle">
            {kind === "rules"
              ? "Версионируемые нормативы и приоритеты. При пересечении обязательных правил действует более строгое."
              : "Добавляйте и уточняйте данные, которые используются при составлении расписания."}
          </p>
        </div>
        <Button
          onClick={() => {
            setError("");
            setEditing({ ...defaults(schema), id: crypto.randomUUID() });
          }}
        >
          <Plus data-icon="inline-start" />
          Добавить запись
        </Button>
      </div>
      <div className="toolbar">
        <div className="search-field">
          <Search aria-hidden="true" />
          <Input
            aria-label="Поиск по названию"
            placeholder="Найти по названию…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Badge variant="secondary">Всего: {data[kind]?.length ?? 0}</Badge>
      </div>
      {rows.length ? (
        <div className="surface">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Название</TableHead>
                {columns.map(([key, s]) => (
                  <TableHead key={key}>{s.title}</TableHead>
                ))}
                <TableHead>Статус</TableHead>
                <TableHead>
                  <span className="sr-only">Действия</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  {columns.map(([key]) => (
                    <TableCell key={key}>{display(key, r[key])}</TableCell>
                  ))}
                  <TableCell>
                    <Badge variant={r.active ? "secondary" : "outline"}>
                      {r.active ? "Активен" : "Архив"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Редактировать ${r.name}`}
                        onClick={() => {
                          setError("");
                          setEditing(structuredClone(r));
                        }}
                      >
                        <FilePenLine />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`${r.active ? "Архивировать" : "Восстановить"} ${r.name}`}
                        onClick={() => archive(r)}
                      >
                        <Archive />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <Empty className="surface">
          <EmptyHeader>
            <EmptyTitle>
              {search ? "Ничего не найдено" : "Здесь пока нет записей"}
            </EmptyTitle>
            <EmptyDescription>
              {search
                ? "Попробуйте другое название."
                : "Добавьте первую запись, чтобы включить её в расписание."}
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button
              variant="outline"
              onClick={() => {
                setError("");
                setEditing({ ...defaults(schema), id: crypto.randomUUID() });
              }}
            >
              Добавить запись
            </Button>
          </EmptyContent>
        </Empty>
      )}
      <Dialog
        open={!!editing}
        onOpenChange={(open) => {
          if (!open && !busy) setEditing(null);
        }}
      >
        <DialogContent className="record-dialog">
          <DialogHeader>
            <DialogTitle>
              {editing?.name || "Новая запись"} · {labels[kind]}
            </DialogTitle>
            <DialogDescription>
              Изменения проверяются на сервере перед сохранением.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={save} className="flex min-h-0 flex-col gap-5">
            <div className="dialog-scroll">
              {error ? (
                <Alert variant="destructive">
                  <AlertTitle>Проверьте данные</AlertTitle>
                  <AlertDescription className="whitespace-pre-line">
                    {error}
                  </AlertDescription>
                </Alert>
              ) : null}
              {editing ? (
                <SchemaForm
                  schema={schema}
                  value={editing}
                  onChange={setEditing}
                  data={data}
                />
              ) : null}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => setEditing(null)}
              >
                Отмена
              </Button>
              <Button disabled={busy}>
                {busy ? "Сохранение…" : "Сохранить"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
