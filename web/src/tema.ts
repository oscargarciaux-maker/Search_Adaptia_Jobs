// Paso 9 (15 nov): modo oscuro. Sin elección, sigue el modo del computador. El botón sol/luna lo fija y se recuerda en
// este navegador. `?tema=oscuro|claro` en la dirección manda (pensado para que Adaptia lo indique) y no se guarda.
export type Tema = "claro" | "oscuro";
const CLAVE = "tema";

function deLaDireccion(): Tema | "" {
  const t = new URLSearchParams(location.search).get("tema");
  return t === "oscuro" || t === "claro" ? t : "";
}

export function temaElegido(): Tema | "" {
  const url = deLaDireccion();
  if (url) return url;
  try {
    const t = localStorage.getItem(CLAVE);
    return t === "oscuro" || t === "claro" ? t : "";
  } catch {
    return "";
  }
}

export function delSistema(): Tema {
  try {
    return matchMedia("(prefers-color-scheme: dark)").matches
      ? "oscuro"
      : "claro";
  } catch {
    return "claro";
  }
}

export function aplicarTema(t: Tema | "") {
  if (t) document.documentElement.dataset.tema = t;
  else delete document.documentElement.dataset.tema;
}

export function guardarTema(t: Tema) {
  try {
    localStorage.setItem(CLAVE, t);
  } catch {
    // Sin almacenamiento (ventana privada): vale solo mientras la página siga abierta.
  }
  aplicarTema(t);
}

// Antes del primer dibujo, para que no parpadee en claro.
aplicarTema(temaElegido());
