import type { InputHTMLAttributes } from "react";

interface FormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
}

export function FormField({ id, label, ...inputProps }: FormFieldProps) {
  return (
    <div className="mb-4">
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-stone-700">
        {label}
      </label>
      <input
        id={id}
        className="w-full rounded-lg border border-stone-300 px-3 py-2 text-stone-900 focus:border-amber-600 focus:ring-2 focus:ring-amber-200 focus:outline-none"
        {...inputProps}
      />
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) {
    return null;
  }
  return (
    <p role="alert" className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
      {message}
    </p>
  );
}

export function SubmitButton({ busy, children }: { busy: boolean; children: string }) {
  return (
    <button
      type="submit"
      disabled={busy}
      className="w-full rounded-lg bg-amber-700 px-4 py-2.5 font-medium text-white hover:bg-amber-800 disabled:opacity-60"
    >
      {busy ? "Patientez…" : children}
    </button>
  );
}
