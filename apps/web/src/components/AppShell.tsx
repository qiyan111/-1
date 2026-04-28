import type { PropsWithChildren } from "react";

import { routes } from "../app/routes";

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <p className="app-shell__brand">流式分析平台</p>
        <nav className="app-shell__nav" aria-label="主导航">
          {routes.map((route, index) => (
            <a
              className={
                index === 0
                  ? "app-shell__nav-item app-shell__nav-item--active"
                  : "app-shell__nav-item"
              }
              href={route.path}
              key={route.path}
            >
              {route.label}
            </a>
          ))}
        </nav>
      </aside>
      <main className="app-shell__main">{children}</main>
    </div>
  );
}

