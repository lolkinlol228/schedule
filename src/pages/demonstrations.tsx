import { useEffect, useState } from "react";
import { api } from "@/api";
import { labels, type SchoolData } from "@/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
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
import { Input } from "@/components/ui/input";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

type Scenario = {
  id: string;
  title: string;
  description: string;
  observe: string;
  counts: Record<string, number>;
  students: number;
  hours: number;
};
export default function Demonstrations({
  data,
  revision,
  reload,
  go,
}: {
  data: SchoolData;
  revision: number;
  reload: () => Promise<void>;
  go: (page: string) => void;
}) {
  const [items, setItems] = useState<Scenario[]>([]);
  const [selected, setSelected] = useState(data._demo?.scenario ?? "balanced");
  const [seed, setSeed] = useState(42);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    api<Scenario[]>("/demo/scenarios")
      .then((rows) => {
        if (live) setItems(rows);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, []);
  const scenario = items.find((item) => item.id === selected);
  async function open() {
    setBusy(true);
    setError("");
    try {
      await api("/demo/workspace", { revision, scenario: selected, seed });
      await reload();
      go("overview");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="eyebrow">УЧЕБНОЕ ПРОСТРАНСТВО</p>
        <h1>Демонстрации</h1>
        <p className="subtitle">
          Выберите условия школы. Расписание будет рассчитано заново после
          запуска генерации.
        </p>
      </div>
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Сценарий школы</CardTitle>
          <CardDescription>
            В каждом наборе заполнены все справочники, включая темы, подгруппы,
            периоды и примеры исключений. Все данные вымышленные и доступны для
            редактирования.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {items.length ? (
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="demo-scenario">Ситуация</FieldLabel>
                <NativeSelect
                  id="demo-scenario"
                  value={selected}
                  disabled={busy}
                  onChange={(e) => {
                    setSelected(e.target.value);
                    setConfirmed(false);
                  }}
                >
                  {items.map((item) => (
                    <NativeSelectOption key={item.id} value={item.id}>
                      {item.title}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </Field>
              {scenario ? (
                <>
                  <p>{scenario.description}</p>
                  <p className="text-sm text-muted-foreground">
                    {scenario.observe}
                  </p>
                  <dl className="demo-counts">
                    <div>
                      <dt>Учеников</dt>
                      <dd>{scenario.students}</dd>
                    </div>
                    {Object.entries(scenario.counts).map(([key, count]) => (
                      <div key={key}>
                        <dt>{labels[key] ?? key}</dt>
                        <dd>{count}</dd>
                      </div>
                    ))}
                    <div>
                      <dt>Часов по плану</dt>
                      <dd>{scenario.hours}</dd>
                    </div>
                  </dl>
                </>
              ) : null}
              <Field>
                <FieldLabel htmlFor="demo-seed">
                  Вариант исходных данных
                </FieldLabel>
                <Input
                  id="demo-seed"
                  type="number"
                  min={0}
                  max={2147483647}
                  required
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value))}
                />
                <FieldDescription>
                  Измените число, чтобы поменять назначения учителей. Масштаб и
                  дефицит задаёт выбранная ситуация. После загрузки можно
                  изменить любые справочники.
                </FieldDescription>
              </Field>
              <Field orientation="horizontal">
                <input
                  id="demo-confirm"
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                <FieldLabel htmlFor="demo-confirm">
                  {data._demo
                    ? "Начать новый сценарий. Текущие правки демонстрации не переносятся."
                    : "Перейти в демонстрационный режим. Рабочие данные школы сохранятся для возврата."}
                </FieldLabel>
              </Field>
            </FieldGroup>
          ) : (
            <Skeleton className="h-32 w-full" />
          )}
          {error ? (
            <Alert variant="destructive">
              <AlertTitle>Не удалось открыть сценарий</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
        <CardFooter>
          <Button
            disabled={
              busy ||
              !confirmed ||
              !scenario ||
              !Number.isInteger(seed) ||
              seed < 0 ||
              seed > 2147483647
            }
            aria-busy={busy}
            onClick={open}
          >
            {busy ? "Подготовка данных…" : "Открыть сценарий"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
