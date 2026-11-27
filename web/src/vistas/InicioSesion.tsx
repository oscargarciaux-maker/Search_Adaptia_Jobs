// Inicio de sesión del panel.
import { ArrowRight, Loader2, ShieldCheck } from "lucide-react";
import { api } from "../api";

export function InicioSesion({
  email,
  setEmail,
  password,
  setPassword,
  busy,
  setBusy,
  error,
  setError,
  cargar,
}: {
  email: string;
  setEmail: (s: string) => void;
  password: string;
  setPassword: (s: string) => void;
  busy: boolean;
  setBusy: (v: boolean) => void;
  error: string;
  setError: (s: string) => void;
  cargar: () => Promise<void>;
}) {
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand">
          <span className="brand-icon">a</span>adaptia
          <span className="brand-dot">.</span>
        </div>
        {/* Sesión de prueba (17 nov): un solo recorrido de lectura, marca → título → campos → botón. */}
        <h1>Inicia sesión</h1>
        <p>Las vacantes correctas para cada persona.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              await api("/auth/login", {
                method: "POST",
                body: JSON.stringify({ email, password }),
              });
              setPassword("");
              await cargar();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="field">
            <label htmlFor="email">Correo electrónico</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Contraseña</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <button className="button primary full" disabled={busy}>
            {busy ? (
              <Loader2 className="spin" size={18} />
            ) : (
              <ArrowRight size={18} />
            )}
            Iniciar sesión
          </button>
        </form>
        <div className="secure-note">
          <ShieldCheck size={15} />
          Solo entran las personas autorizadas.
        </div>
      </div>
    </div>
  );
}
