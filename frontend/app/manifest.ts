import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Black History Hub · Institution app",
    short_name: "BH Shelf",
    description: "For museums, archives and libraries: photograph a shelf, upload records, review and publish. Everything you add lands on the world.",
    start_url: "/app",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#edebe6",
    theme_color: "#f2612a",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
    ],
  };
}
