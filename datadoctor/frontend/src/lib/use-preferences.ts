"use client";

import { useEffect, useState } from "react";
import { api, type SettingsResponse } from "./api";

let cache: Promise<SettingsResponse> | null = null;

/** Workspace preferences + system limits, fetched once per page load. */
export function useSettings(): SettingsResponse | null {
  const [data, setData] = useState<SettingsResponse | null>(null);
  useEffect(() => {
    cache ??= api.settings().catch((e) => {
      cache = null;
      throw e;
    });
    let alive = true;
    cache.then((d) => alive && setData(d)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);
  return data;
}
