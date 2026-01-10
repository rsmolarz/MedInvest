"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = { href: string; label: string };

const NAV: NavItem[] = [
  { href: "/admin/verification", label: "Verification" },
  { href: "/admin/analytics", label: "Analytics" },
  { href: "/admin/analytics/cohorts", label: "Cohorts" },
  { href: "/admin/reports", label: "Reports" },
];

export default function AdminNav() {
  const pathname = usePathname();

  return (
    <nav className="w-full">
      <div className="px-4 pt-6 pb-2 text-xs font-semibold uppercase tracking-wide opacity-70">Admin</div>
      <ul className="px-2 pb-6">
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <li key={item.href} className="px-2">
              <Link
                href={item.href}
                className={`block rounded-xl px-3 py-2 text-sm ${
                  active ? "bg-white/10 font-semibold" : "opacity-85 hover:bg-white/5"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
