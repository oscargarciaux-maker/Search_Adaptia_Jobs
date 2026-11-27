// Las vacantes de un cliente y un día en «Vacantes» (dividido de main.tsx): se piden solo en esa sección, la
// respuesta vieja no pisa a la nueva y, al llegar desde «Tomar vacantes», el foco va a «Copiar WhatsApp».
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
  const [results, setResults] = useState<Resultados | null>(null);
  const peticionResultados = useRef(0);
  // Contrato v48: al llegar desde «Tomar vacantes» del detalle, el foco queda en «Copiar WhatsApp».
  const enfocarWhatsApp = useRef(false);
  const botonWhatsApp = useRef<HTMLButtonElement>(null);
  const [focoWhatsApp, setFocoWhatsApp] = useState(0);
  const [loadingResults, setLoadingResults] = useState(false);
  const [errorResultados, setErrorResultados] = useState(false);
  async function cargarResultados() {
    const turno = ++peticionResultados.current;
    if (!sesion?.sesion) return;
    setLoadingResults(true);
    setResults(null);
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
        setResults(r);
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
        setLoadingResults(false);
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
