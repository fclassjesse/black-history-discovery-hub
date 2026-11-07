import { redirect } from "next/navigation";
import { localePath } from "@/lib/i18n-core";
import { getLocale } from "@/lib/i18n-server";

/** The explorer lives on the home page now; old /search links keep working (in either language). */
export default async function SearchRedirect({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, x));
    else if (v != null) sp.set(k, v);
  }
  const s = sp.toString();
  redirect(localePath(await getLocale(), s ? `/?${s}` : "/"));
}
