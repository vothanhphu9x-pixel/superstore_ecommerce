"use client";

import { createContext, ReactNode, useContext } from "react";

import type { StaffProfile } from "@/lib/api";

const StaffSessionContext = createContext<StaffProfile | null>(null);

type StaffSessionProviderProps = {
  profile: StaffProfile;
  children: ReactNode;
};

export function StaffSessionProvider({
  profile,
  children,
}: StaffSessionProviderProps) {
  return (
    <StaffSessionContext.Provider value={profile}>
      {children}
    </StaffSessionContext.Provider>
  );
}

export function useStaffSession(): StaffProfile {
  const profile = useContext(StaffSessionContext);

  if (!profile) {
    throw new Error("useStaffSession must be used inside StaffSessionProvider");
  }

  return profile;
}
