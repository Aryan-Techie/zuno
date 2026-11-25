/**
 * The four surfaces, as one quiet group of text links in the top bar rather
 * than a row of boxed buttons - the boxes are kept for things that toggle.
 */
const LINKS = [
  { href: "/", label: "Console" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/graph", label: "Graph" },
  { href: "/about", label: "Story" },
] as const;

export function NavLinks({ current }: { current: (typeof LINKS)[number]["href"] }) {
  return (
    <nav className="nav" aria-label="Pages">
      {LINKS.map((l) => (
        <a key={l.href} href={l.href} aria-current={l.href === current ? "page" : undefined}>
          {l.label}
        </a>
      ))}
    </nav>
  );
}
