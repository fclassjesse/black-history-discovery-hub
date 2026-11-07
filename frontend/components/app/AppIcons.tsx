import type { SVGProps } from "react";

const base = { width: 24, height: 24, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2.2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const HomeIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="M3 11.5 12 4l9 7.5" /><path d="M5.5 10v9.5h13V10" /><path d="M10 19.5v-5h4v5" /></svg>;
export const ReviewIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="M5 4.5h14v15H5z" /><path d="M8.5 9.5h7M8.5 13h7M8.5 16.5h4" /></svg>;
export const CameraIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="M4 8.5h3l1.5-2.5h7L17 8.5h3v10H4z" /><circle cx="12" cy="13.2" r="3.2" /></svg>;
export const UploadIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="M12 16V5" /><path d="m7.5 9.5 4.5-4.5 4.5 4.5" /><path d="M4.5 16.5v3h15v-3" /></svg>;
export const PersonIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><circle cx="12" cy="8.5" r="3.6" /><path d="M4.5 20c.8-3.9 3.7-6 7.5-6s6.7 2.1 7.5 6" /></svg>;
export const ChevronIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="m9 6 6 6-6 6" /></svg>;
export const FileIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="M6.5 3.5h7l4 4v13h-11z" /><path d="M13.5 3.5v4h4" /></svg>;
export const PenIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="m4.5 19.5 4-1 10-10-3-3-10 10z" /><path d="m13.5 7.5 3 3" /></svg>;
export const CheckIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>;
export const CrossIcon = (p: SVGProps<SVGSVGElement>) => <svg {...base} {...p}><path d="m6 6 12 12M18 6 6 18" /></svg>;
