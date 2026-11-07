import { headers } from "next/headers";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";
import { DEFAULT_LOCALE, LOCALE_HEADER, makeT, type Locale, type Messages, type Translator } from "@/lib/i18n-core";

export function getMessages(locale: Locale): Messages {
  return (locale === "fr" ? fr : en) as Messages;
}

/** The locale `proxy.ts` resolved for this request (header set on every page request). */
export async function getLocale(): Promise<Locale> {
  const h = await headers();
  return h.get(LOCALE_HEADER) === "fr" ? "fr" : DEFAULT_LOCALE;
}

/** Server-component translator: `const { t, locale } = await getT();` */
export async function getT(): Promise<Translator> {
  const locale = await getLocale();
  return makeT(getMessages(locale), locale);
}
