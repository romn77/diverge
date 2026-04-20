import { HomeDashboard } from "@/components/HomeDashboard";

interface WorkbenchHomePageProps {
  searchParams?: Promise<{ q?: string | string[] | undefined }>;
}

export default async function WorkbenchHomePage({
  searchParams,
}: WorkbenchHomePageProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const rawQuery = resolvedSearchParams?.q;
  const initialSearchQuery = Array.isArray(rawQuery) ? rawQuery[0] ?? "" : rawQuery ?? "";

  return <HomeDashboard initialSearchQuery={initialSearchQuery} />;
}
