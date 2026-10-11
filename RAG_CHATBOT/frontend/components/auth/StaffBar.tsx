"use client";

import { useState } from "react";

import { staffService } from "@/lib/api";
import { useStaffSession } from "./StaffSessionProvider";

export function StaffBar() {
  const profile = useStaffSession();
  const [loggingOut, setLoggingOut] = useState(false);

  async function logout() {
    setLoggingOut(true);

    try {
      await staffService.logout();
    } finally {
      window.location.assign("/login");
    }
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div>
          <p className="font-semibold text-slate-950">Internal Analytics</p>

          <p className="text-sm text-slate-500">
            {profile.name} · {profile.role}
          </p>
        </div>

        <button
          type="button"
          onClick={logout}
          disabled={loggingOut}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          {loggingOut ? "Signing out..." : "Sign out"}
        </button>
      </div>
    </header>
  );
}
