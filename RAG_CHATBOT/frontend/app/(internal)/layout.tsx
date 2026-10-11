import { ReactNode } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { StaffBar } from "@/components/auth/StaffBar";
import { StaffSessionProvider } from "@/components/auth/StaffSessionProvider";
import type { StaffProfile } from "@/lib/api";
import { internalFetch } from "@/lib/server/internalApi";

async function loadStaffProfile(): Promise<StaffProfile | null> {
  const cookieStore = await cookies();

  const response = await internalFetch("/api/staff/me", {
    headers: {
      cookie: cookieStore.toString(),
    },
  });

  if (response.status === 401 || response.status === 403) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Staff authentication service returned ${response.status}`);
  }

  return response.json() as Promise<StaffProfile>;
}

export default async function InternalLayout({
  children,
}: {
  children: ReactNode;
}) {
  const profile = await loadStaffProfile();

  if (!profile) {
    redirect("/login?next=/dashboard");
  }

  return (
    <StaffSessionProvider profile={profile}>
      <div className="min-h-screen bg-slate-50">
        <StaffBar />
        {children}
      </div>
    </StaffSessionProvider>
  );
}
