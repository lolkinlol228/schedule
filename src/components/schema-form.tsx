import { useId, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import {
  Field,
  FieldLabel,
  FieldGroup,
  FieldSet,
  FieldLegend,
  FieldDescription,
} from "@/components/ui/field";
import type { Schema, SchoolData, RecordData } from "@/types";
import { words, days } from "@/types";
import { BellsEditor } from "@/components/bells-editor";

const references: Record<string, string> = {
  class_id: "classes",
  course_id: "courses",
  subject_id: "subjects",
  group_id: "groups",
  teacher_id: "teachers",
  room_id: "rooms",
  base_room: "rooms",
  teacher_ids: "teachers",
  plan_ids: "plans",
  subjects: "subjects",
};
function TextList({
  id,
  name,
  value,
  onChange,
  numeric,
}: {
  id: string;
  name: string;
  value: any[];
  onChange: (v: any[]) => void;
  numeric: boolean;
}) {
  const [raw, setRaw] = useState(() => value.join(", "));
  return (
    <Input
      id={id}
      name={name}
      autoComplete="off"
      value={raw}
      placeholder={
        name === "tags" ? "Например: pc, projector, lab…" : undefined
      }
      onChange={(e) => {
        setRaw(e.target.value);
        onChange(
          e.target.value
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean)
            .map((x) => (numeric ? Number(x) : x)),
        );
      }}
    />
  );
}
function resolve(s: Schema, root: Schema): Schema {
  return s.$ref
    ? {
        ...root.$defs?.[s.$ref.split("/").pop()!],
        title: s.title ?? root.$defs?.[s.$ref.split("/").pop()!]?.title,
      }
    : s;
}
export function defaults(schema: Schema, root = schema): any {
  const s = resolve(schema, root);
  if (s.default !== undefined) return structuredClone(s.default);
  if (s.type === "object")
    return Object.fromEntries(
      Object.entries(s.properties ?? {})
        .filter(([key]) => key !== "id")
        .map(([key, value]) => [key, defaults(value, root)]),
    );
  if (s.type === "array") return [];
  if (s.type === "boolean") return false;
  if (s.type === "integer" || s.type === "number") return s.minimum ?? 0;
  return s.enum?.[0] ?? "";
}
type Props = {
  schema: Schema;
  value: any;
  onChange: (v: any) => void;
  data: SchoolData;
  root?: Schema;
  name?: string;
  parent?: any;
  required?: boolean;
};
export function SchemaForm({
  schema,
  value,
  onChange,
  data,
  root = schema,
  name = "",
  parent,
  required = false,
}: Props) {
  const id = useId();
  const s = resolve(schema, root);
  const title = s.title ?? name;
  if (name === "bells")
    return <BellsEditor value={value ?? []} onChange={onChange} />;
  // A soft rule is weighted by its priority, so a separate numeric value would be
  // inert; the form does not offer a field that changes nothing.
  if (name === "value" && parent?.kind === "soft") return null;
  if (s.type === "object")
    return (
      <FieldGroup>
        {Object.entries(s.properties ?? {})
          .filter(([key]) => key !== "id")
          .map(([key, property]) => (
            <SchemaForm
              key={key}
              schema={property}
              name={key}
              value={value?.[key]}
              onChange={(v) => onChange({ ...value, [key]: v })}
              data={data}
              root={root}
              parent={value}
              required={s.required?.includes(key)}
            />
          ))}
      </FieldGroup>
    );
  if (name === "availability")
    return (
      <FieldSet>
        <FieldLegend>{title}</FieldLegend>
        <FieldDescription>
          Каждая ячейка задаёт доступность на урок. Номера в интерфейсе
          начинаются с 1.
        </FieldDescription>
        <div className="availability-scroll">
          <table className="availability">
            <caption className="sr-only">Недельная доступность</caption>
            <thead>
              <tr>
                <th scope="col">Урок</th>
                {days.map((d) => (
                  <th scope="col" key={d}>
                    {d.slice(0, 2)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: data.settings.bells.length }, (_, slot) => (
                <tr key={slot}>
                  <th scope="row">
                    {slot + 1}
                    <br />
                    {data.settings.bells[slot].shift ?? 1} см. ·{" "}
                    {data.settings.bells[slot].start}
                  </th>
                  {days.map((day, d) => {
                    const current =
                      (value ?? []).find(
                        (a: any) => a.day === d && a.slot === slot,
                      )?.value ?? "possible";
                    return (
                      <td key={day}>
                        <NativeSelect
                          aria-label={`${day}, урок ${slot + 1}`}
                          value={current}
                          onChange={(e) =>
                            onChange([
                              ...(value ?? []).filter(
                                (a: any) => !(a.day === d && a.slot === slot),
                              ),
                              { day: d, slot, value: e.target.value },
                            ])
                          }
                        >
                          <NativeSelectOption value="possible">
                            Можно
                          </NativeSelectOption>
                          <NativeSelectOption value="unavailable">
                            Нельзя
                          </NativeSelectOption>
                          <NativeSelectOption value="undesirable">
                            Нежелат.
                          </NativeSelectOption>
                          <NativeSelectOption value="preferred">
                            Лучше
                          </NativeSelectOption>
                        </NativeSelect>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </FieldSet>
    );
  let ref = references[name];
  if (name === "resource_id")
    ref = parent?.scope === "school" ? "" : parent?.scope;
  if (s.type === "array") {
    const item = resolve(s.items ?? {}, root);
    const list: any[] = value ?? [];
    if (ref)
      return (
        <FieldSet>
          <FieldLegend variant="label">{title}</FieldLegend>
          <FieldDescription>
            Выберите нужные записи. Первый выбранный учитель — основной.
          </FieldDescription>
          <div className="choice-list">
            {(data[ref] ?? []).map((r: RecordData) => (
              <label key={r.id} className="choice">
                <input
                  type="checkbox"
                  checked={list.includes(r.id)}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...list, r.id]
                        : list.filter((x) => x !== r.id),
                    )
                  }
                />
                <span>
                  {r.name}
                  {!r.active ? " (архив)" : ""}
                </span>
              </label>
            ))}
          </div>
        </FieldSet>
      );
    if (name === "slots")
      return (
        <FieldSet>
          <FieldLegend variant="label">Уроки (пусто — весь день)</FieldLegend>
          <div className="flex flex-wrap gap-4">
            {Array.from({ length: data.settings.bells.length }, (_, i) => (
              <label className="choice" key={i}>
                <input
                  type="checkbox"
                  checked={list.includes(i)}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...list, i]
                        : list.filter((x) => x !== i),
                    )
                  }
                />
                {i + 1}
              </label>
            ))}
          </div>
        </FieldSet>
      );
    if (item.type !== "object")
      return (
        <Field>
          <FieldLabel htmlFor={id}>{title}</FieldLabel>
          <TextList
            id={id}
            name={name}
            value={list}
            onChange={onChange}
            numeric={item.type === "integer"}
          />
          <FieldDescription>Разделяйте значения запятыми.</FieldDescription>
        </Field>
      );
    return (
      <FieldSet>
        <FieldLegend>{title}</FieldLegend>
        <div className="flex flex-col gap-4">
          {list.map((v, i) => (
            <div className="nested-record" key={i}>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">
                  {title} · {i + 1}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={`Удалить: ${title}, ${i + 1}`}
                  onClick={() => onChange(list.filter((_, j) => j !== i))}
                >
                  <Trash2 />
                </Button>
              </div>
              <SchemaForm
                schema={item}
                value={v}
                onChange={(next) =>
                  onChange(list.map((x, j) => (j === i ? next : x)))
                }
                root={root}
                data={data}
              />
            </div>
          ))}
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => onChange([...list, defaults(item, root)])}
        >
          <Plus data-icon="inline-start" />
          Добавить: {title?.toLowerCase()}
        </Button>
      </FieldSet>
    );
  }
  if (s.type === "boolean")
    return (
      <Field orientation="horizontal">
        <input
          id={id}
          type="checkbox"
          checked={!!value}
          onChange={(e) => onChange(e.target.checked)}
        />
        <FieldLabel htmlFor={id}>{title}</FieldLabel>
      </Field>
    );
  if (ref || s.enum)
    return (
      <Field>
        <FieldLabel htmlFor={id}>{title}</FieldLabel>
        <NativeSelect
          id={id}
          value={value ?? ""}
          required={required}
          onChange={(e) => onChange(e.target.value)}
        >
          {ref ? (
            <>
              <NativeSelectOption value="">Выберите…</NativeSelectOption>
              {(data[ref] ?? []).map((r: RecordData) => (
                <NativeSelectOption key={r.id} value={r.id}>
                  {r.name}
                  {!r.active ? " (архив)" : ""}
                </NativeSelectOption>
              ))}
            </>
          ) : (
            s.enum?.map((v) => (
              <NativeSelectOption key={v} value={v}>
                {words[v] ?? v}
              </NativeSelectOption>
            ))
          )}
        </NativeSelect>
      </Field>
    );
  if (name === "method_day")
    return (
      <Field>
        <FieldLabel htmlFor={id}>Методический день</FieldLabel>
        <NativeSelect
          id={id}
          value={value ?? -1}
          onChange={(e) => onChange(Number(e.target.value))}
        >
          <NativeSelectOption value={-1}>Не задан</NativeSelectOption>
          {days.map((d, i) => (
            <NativeSelectOption key={d} value={i}>
              {d}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </Field>
    );
  return (
    <Field>
      <FieldLabel htmlFor={id}>{title}</FieldLabel>
      <Input
        id={id}
        name={name}
        autoComplete="off"
        required={required}
        type={
          s.format === "date"
            ? "date"
            : s.type === "integer" || s.type === "number"
              ? "number"
              : name === "start" || name === "end"
                ? "time"
                : "text"
        }
        min={s.minimum}
        max={s.maximum}
        minLength={s.minLength}
        maxLength={s.maxLength}
        value={value ?? ""}
        onChange={(e) =>
          onChange(
            s.type === "integer" || s.type === "number"
              ? e.target.value === ""
                ? ""
                : Number(e.target.value)
              : e.target.value,
          )
        }
      />
    </Field>
  );
}
