"use client";

import { ReactNode } from "react";
import { JobProvider } from "@/lib/jobContext";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <JobProvider>
      {children}
    </JobProvider>
  );
}


