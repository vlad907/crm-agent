const WORKSPACE_STORAGE_KEY = "crm.workspace_id";
const USER_STORAGE_KEY = "crm.user_id";

const ENV_WORKSPACE_ID = (process.env.NEXT_PUBLIC_WORKSPACE_ID ?? "").trim();
const ENV_USER_ID = (process.env.NEXT_PUBLIC_USER_ID ?? "").trim();

export const IDENTITY_UPDATED_EVENT = "crm:identity-updated";

function getLocalStorageValue(key: string): string {
  if (typeof window === "undefined") {
    return "";
  }

  try {
    return (window.localStorage.getItem(key) ?? "").trim();
  } catch {
    return "";
  }
}

function setLocalStorageValue(key: string, value: string): void {
  if (typeof window === "undefined") {
    return;
  }

  const normalized = value.trim();
  try {
    if (normalized) {
      window.localStorage.setItem(key, normalized);
    } else {
      window.localStorage.removeItem(key);
    }
    window.dispatchEvent(new Event(IDENTITY_UPDATED_EVENT));
  } catch {
    // ignore localStorage errors in dev
  }
}

export function getWorkspaceId(): string {
  const stored = getLocalStorageValue(WORKSPACE_STORAGE_KEY);
  return stored || ENV_WORKSPACE_ID;
}

export function getUserId(): string {
  const stored = getLocalStorageValue(USER_STORAGE_KEY);
  return stored || ENV_USER_ID;
}

export function setWorkspaceId(id: string): void {
  setLocalStorageValue(WORKSPACE_STORAGE_KEY, id);
}

export function setUserId(id: string): void {
  setLocalStorageValue(USER_STORAGE_KEY, id);
}
