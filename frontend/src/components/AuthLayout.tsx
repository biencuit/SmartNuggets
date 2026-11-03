import type { ReactNode } from "react";

/** Mise en page des écrans de connexion et d'inscription (pensée d'abord pour le mobile). */
export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <p className="mb-6 text-center text-2xl font-bold text-amber-800">SmartNuggets</p>
        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-stone-200">
          <h1 className="mb-6 text-xl font-semibold text-stone-900">{title}</h1>
          {children}
        </section>
      </div>
    </main>
  );
}
