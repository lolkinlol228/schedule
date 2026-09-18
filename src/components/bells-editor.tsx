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
  FieldSet,
  FieldLegend,
  FieldDescription,
} from "@/components/ui/field";

type Bell = { shift?: number; start: string; end: string };
export function BellsEditor({
  value,
  onChange,
}: {
  value: Bell[];
  onChange: (value: Bell[]) => void;
}) {
  function change(index: number, patch: Partial<Bell>) {
    onChange(
      value.map((bell, i) => (i === index ? { ...bell, ...patch } : bell)),
    );
  }
  return (
    <FieldSet>
      <FieldLegend>Звонки</FieldLegend>
      <FieldDescription>
        От 5 до 8 уроков в каждой смене. Для двух смен по 5 уроков добавьте 10
        строк и укажите смену у каждой. Время должно идти по порядку. Смену
        класса задайте в справочнике «Классы».
      </FieldDescription>
      <div className="flex flex-col gap-3">
        {value.map((bell, i) => (
          <div key={i} className="bell-row">
            <span className="text-sm text-muted-foreground">{i + 1}</span>
            <Field>
              <FieldLabel htmlFor={`bell-shift-${i}`}>Смена</FieldLabel>
              <NativeSelect
                id={`bell-shift-${i}`}
                name={`bells.${i}.shift`}
                value={bell.shift ?? 1}
                onChange={(e) => change(i, { shift: Number(e.target.value) })}
              >
                <NativeSelectOption value={1}>1</NativeSelectOption>
                <NativeSelectOption value={2}>2</NativeSelectOption>
              </NativeSelect>
            </Field>
            <Field>
              <FieldLabel htmlFor={`bell-start-${i}`}>Начало</FieldLabel>
              <Input
                id={`bell-start-${i}`}
                name={`bells.${i}.start`}
                autoComplete="off"
                required
                type="time"
                value={bell.start}
                onChange={(e) => change(i, { start: e.target.value })}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor={`bell-end-${i}`}>Конец</FieldLabel>
              <Input
                id={`bell-end-${i}`}
                name={`bells.${i}.end`}
                autoComplete="off"
                required
                type="time"
                value={bell.end}
                onChange={(e) => change(i, { end: e.target.value })}
              />
            </Field>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={value.length <= 5}
              aria-label={`Удалить звонок ${i + 1}`}
              onClick={() => onChange(value.filter((_, j) => j !== i))}
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </div>
      <Button
        type="button"
        variant="outline"
        disabled={value.length >= 16}
        onClick={() =>
          onChange([
            ...value,
            { shift: value.at(-1)?.shift ?? 1, start: "", end: "" },
          ])
        }
      >
        <Plus data-icon="inline-start" />
        Добавить звонок
      </Button>
    </FieldSet>
  );
}
