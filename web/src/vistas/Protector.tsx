import React from "react";

// Reunión del 14 nov: un fallo al pintar dejaba la pantalla en blanco y se perdía lo escrito. Ahora se muestra qué
// pasó; el borrador del cliente sigue en este navegador y se ofrece al volver a abrir el formulario.
export class Protector extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Fallo del panel:", error, info.componentStack);
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="fallo" role="alert">
        <h1>Algo falló al mostrar esta pantalla</h1>
        <p>
          Lo que estabas escribiendo de un cliente quedó guardado en este
          navegador: al abrir otra vez su formulario podrás recuperarlo.
        </p>
        <p className="fallo-detalle">Detalle: {this.state.error.message}</p>
        <button
          type="button"
          className="button primary"
          onClick={() => window.location.reload()}
        >
          Volver a cargar el panel
        </button>
      </main>
    );
  }
}
