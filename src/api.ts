let csrf = "";
export function setCsrf(token: string) {
  csrf = token;
}
export async function api<T = any>(
  path: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    credentials: "same-origin",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      "X-CSRF-Token": csrf,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth/"))
      window.dispatchEvent(new Event("session-expired"));
    const details = result.errors?.map((e: any) => e.message).join("; ");
    throw new Error(
      Array.isArray(result.detail)
        ? result.detail.join("\n")
        : details || result.detail || "Не удалось выполнить запрос",
    );
  }
  return result;
}
