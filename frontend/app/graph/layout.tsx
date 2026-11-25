import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Zuno Graph",
};

export default function GraphLayout({ children }: { children: React.ReactNode }) {
  return children;
}
