// Las vacantes de un cliente y un día en «Vacantes»: se piden solo en esa sección, la
// respuesta vieja no pisa a la nueva y, al llegar desde «Tomar vacantes», el foco va a «Copiar WhatsApp».
// P-12.10: al volver a la sección con el mismo cliente y día se sigue viendo la lista anterior hasta que llega la
// nueva (antes se borraba y quedaba «Consultando vacantes…» mientras el servidor calculaba).
import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Resultados, Sesion } from "./types";

export function useResultados(
  sesion: Sesion | null,
  selectedClient: string,
  resultDate: string,
  tab: string,
  notify: (s: string, error?: boolean) => void,
) {
  // La última lista recibida y de qué cliente y día es: solo se muestra si es la del cliente y día elegidos.
  const [guardada, setGuardada] = useState<{
    clave: string;
    datos: Resultados;
  } | null>(null);
  const peticionResultados = useRef(0);
  // Contrato v48: al llegar desde «Tomar vacantes» del detalle, el foco queda en «Copiar WhatsApp».
  const enfocarWhatsApp = useRef(false);
  const botonWhatsApp = useRef<HTMLButtonElement>(null);
  const [focoWhatsApp, setFocoWhatsApp] = useState(0);
  const [consultando, setConsultando] = useState(false);
  const [errorResultados, setErrorResultados] = useState(false);
  const clave = selectedClient + "|" + resultDate;
  const results = guardada?.clave === clave ? guardada.datos : null;
  async function cargarResultados() {
    const turno = ++peticionResultados.current;
    if (!sesion?.sesion) return;
    setConsultando(true);
    setErrorResultados(false);
    try {
      const r = await api<Resultados>(
        "/resultados?" +
          new URLSearchParams({
            ...(selectedClient ? { cliente_id: selectedClient } : {}),
            ...(resultDate ? { fecha: resultDate } : {}),
          }),
      );
      if (turno === peticionResultados.current) {
        setGuardada({ clave, datos: r });
        // Contrato v48: al llegar desde «Tomar vacantes», el foco va a «Copiar WhatsApp» con los datos de ese día.
        if (enfocarWhatsApp.current) setFocoWhatsApp((n) => n + 1);
      }
    } catch (e) {
      if (turno === peticionResultados.current) {
        setErrorResultados(true);
        notify((e as Error).message, true);
      }
    } finally {
      if (turno === peticionResultados.current) {
        setConsultando(false);
        enfocarWhatsApp.current = false;
      }
    }
  }
  // Contrato v46 (velocidad): las vacantes solo se piden en su pestaña; antes, entrar por #mensajes también las pedía.
  const enVacantes = tab === "Vacantes";
  useEffect(() => {
    if (enVacantes) cargarResultados();
  }, [selectedClient, resultDate, sesion?.sesion, enVacantes]);
  useEffect(() => {
    if (focoWhatsApp) botonWhatsApp.current?.focus();
  }, [focoWhatsApp]);
  // «Consultando vacantes…» solo cuando no hay una lista de ese cliente y día que mostrar mientras tanto.
  const loadingResults = consultando && !results;
  // Contrato v48: el servidor dice si es de un día anterior y cuántas se pueden copiar.
  const diaResultados = (results?.ejecucion?.fecha || "").slice(0, 10);
  const diaAnterior = Boolean(results?.dia_anterior);
  const paraCopiar = results?.para_copiar ?? results?.listas ?? 0;
  return {
    results,
    enfocarWhatsApp,
    botonWhatsApp,
    loadingResults,
    errorResultados,
    cargarResultados,
    diaResultados,
    diaAnterior,
    paraCopiar,
  };
}
