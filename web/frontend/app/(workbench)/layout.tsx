import type { ReactNode } from "react";
import { WorkbenchProvider } from "@/components/WorkbenchProvider";
import { WorkbenchShell } from "@/components/WorkbenchShell";

export default function WorkbenchLayout({ children }: { children: ReactNode }) {
  return (
    <WorkbenchProvider>
      <WorkbenchShell>{children}</WorkbenchShell>
    </WorkbenchProvider>
  );
}
