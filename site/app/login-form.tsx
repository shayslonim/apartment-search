"use client";

import { FormEvent, useState } from "react";

export function LoginForm() {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token: form.get("token") }),
    });
    setPending(false);
    if (response.ok) {
      window.location.reload();
      return;
    }
    setError("That access key is not valid.");
  }

  return (
    <main className="login-shell">
      <form className="login-panel" onSubmit={submit}>
        <p className="eyebrow">Apartment Search</p>
        <h1>Match inbox</h1>
        <label htmlFor="token">Access key</label>
        <input
          id="token"
          name="token"
          type="password"
          autoComplete="current-password"
          required
        />
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button className="primary-button" type="submit" disabled={pending}>
          {pending ? "Opening..." : "Open dashboard"}
        </button>
      </form>
    </main>
  );
}
