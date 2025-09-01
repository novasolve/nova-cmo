import { Sidebar } from "@/components/Sidebar";
import { Inspector } from "@/components/Inspector";
import { JobProvider } from "@/lib/jobContext";

export default function ConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <JobProvider>
      <div className="h-screen w-screen grid grid-cols-[280px_1fr_360px] bg-gray-50">
        <aside className="border-r border-gray-200 bg-white p-4 overflow-y-auto">
          <Sidebar />
        </aside>
        <main className="flex flex-col bg-white">{children}</main>
        <aside className="border-l border-gray-200 bg-white p-4 overflow-y-auto">
          <Inspector />
        </aside>
      </div>
    </JobProvider>
  );
}
