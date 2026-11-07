import { Suspense } from "react";
import { Explorer } from "@/components/explorer/Explorer";

export default function HomePage() {
  return (
    <Suspense fallback={<div className="min-h-[100svh]" aria-hidden />}>
      <Explorer />
    </Suspense>
  );
}
