import { api, ApiError, type User } from "./api.ts";

export const session = $state<{ user: User | null; loaded: boolean }>({
  user: null,
  loaded: false,
});

/** Who is this device? The first visit makes a new person; there's no login on the home network. */
export async function loadSession() {
  try {
    session.user = await api<User>("/auth/me");
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 401)) throw e;
    session.user = await api<User>("/auth/device", { method: "POST" });
  } finally {
    session.loaded = true;
  }
}
