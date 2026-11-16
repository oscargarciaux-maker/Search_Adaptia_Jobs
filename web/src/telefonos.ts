// Contrato v35: código telefónico de cada país (ITU E.164) para elegirlo en una lista y escribir solo el número.
// Cuando varios países comparten código (+1, +7, +44…), el primero de la lista es el que se muestra al leer un número
// ya guardado; el operador puede cambiarlo. El número se sigue guardando como «+código número».
const TABLA =
  "US:1 CA:1 DO:1 PR:1 JM:1 TT:1 BS:1 BB:1 AG:1 DM:1 GD:1 KN:1 LC:1 VC:1 " +
  "RU:7 KZ:7 EG:20 ZA:27 GR:30 NL:31 BE:32 FR:33 ES:34 HU:36 IT:39 VA:39 RO:40 CH:41 AT:43 GB:44 " +
  "DK:45 SE:46 NO:47 PL:48 DE:49 PE:51 MX:52 CU:53 AR:54 BR:55 CL:56 CO:57 VE:58 MY:60 AU:61 " +
  "ID:62 PH:63 NZ:64 SG:65 TH:66 JP:81 KR:82 VN:84 CN:86 TR:90 IN:91 PK:92 AF:93 LK:94 MM:95 " +
  "IR:98 SS:211 MA:212 DZ:213 TN:216 LY:218 GM:220 SN:221 MR:222 ML:223 GN:224 CI:225 BF:226 " +
  "NE:227 TG:228 BJ:229 MU:230 LR:231 SL:232 GH:233 NG:234 TD:235 CF:236 CM:237 CV:238 ST:239 " +
  "GQ:240 GA:241 CG:242 CD:243 AO:244 GW:245 SC:248 SD:249 RW:250 ET:251 SO:252 DJ:253 KE:254 " +
  "TZ:255 UG:256 BI:257 MZ:258 ZM:260 MG:261 ZW:263 NA:264 MW:265 LS:266 BW:267 SZ:268 KM:269 " +
  "ER:291 AW:297 FO:298 GL:299 GI:350 PT:351 LU:352 IE:353 IS:354 AL:355 MT:356 CY:357 FI:358 " +
  "BG:359 LT:370 LV:371 EE:372 MD:373 AM:374 BY:375 AD:376 MC:377 SM:378 UA:380 RS:381 ME:382 " +
  "XK:383 HR:385 SI:386 BA:387 MK:389 CZ:420 SK:421 LI:423 BZ:501 GT:502 SV:503 HN:504 NI:505 " +
  "CR:506 PA:507 HT:509 BO:591 GY:592 EC:593 PY:595 SR:597 UY:598 CW:599 TL:670 BN:673 NR:674 " +
  "PG:675 TO:676 SB:677 VU:678 FJ:679 PW:680 WS:685 KI:686 FM:691 MH:692 KP:850 HK:852 MO:853 " +
  "KH:855 LA:856 BD:880 TW:886 MV:960 LB:961 JO:962 SY:963 IQ:964 KW:965 SA:966 YE:967 OM:968 " +
  "PS:970 AE:971 IL:972 BH:973 QA:974 BT:975 MN:976 NP:977 TJ:992 TM:993 AZ:994 GE:995 KG:996 " +
  "UZ:998";

export const CODIGOS: { pais: string; codigo: string }[] = TABLA.split(" ")
  .filter(Boolean)
  .map((x) => {
    const [pais, codigo] = x.split(":");
    return { pais, codigo };
  });

// Primero los países donde viven la mayoría de los clientes (LATAM y España), después el resto.
export const FRECUENTES = [
  "CO",
  "MX",
  "AR",
  "CL",
  "PE",
  "EC",
  "VE",
  "UY",
  "PY",
  "BO",
  "CR",
  "PA",
  "GT",
  "SV",
  "HN",
  "NI",
  "DO",
  "CU",
  "PR",
  "ES",
  "US",
];

export function codigoDe(pais: string) {
  return CODIGOS.find((c) => c.pais === pais)?.codigo || "";
}

// «+57 300 123 4567» → { pais: "CO", numero: "300 123 4567" }. Sin «+» o sin código reconocido, el país queda vacío.
export function separarTelefono(telefono: string, preferido = "") {
  const t = (telefono || "").trim();
  if (!t.startsWith("+")) return { pais: preferido, numero: t };
  const digitos = t.replace(/\D/g, "");
  if (preferido && digitos.startsWith(codigoDe(preferido)))
    return {
      pais: preferido,
      numero: quitarCodigo(t, codigoDe(preferido)),
    };
  // En +1 el código de área dice el país en los casos más comunes de la región.
  const area = digitos.slice(1, 4);
  const nanp = ["809", "829", "849"].includes(area)
    ? "DO"
    : ["787", "939"].includes(area)
      ? "PR"
      : "";
  if (digitos.startsWith("1") && nanp)
    return { pais: nanp, numero: quitarCodigo(t, "1") };
  for (const largo of [3, 2, 1]) {
    const c = CODIGOS.find((x) => x.codigo === digitos.slice(0, largo));
    if (c) return { pais: c.pais, numero: quitarCodigo(t, c.codigo) };
  }
  return { pais: "", numero: t };
}

function quitarCodigo(telefono: string, codigo: string) {
  let resto = telefono.trim().slice(1);
  for (const d of codigo) resto = resto.slice(resto.indexOf(d) + 1);
  return resto.trim();
}

// El número se guarda siempre con el código delante; si alguien pega el número completo con «+», se respeta.
export function unirTelefono(pais: string, numero: string) {
  const n = numero.trim();
  if (!n) return "";
  if (n.startsWith("+") || !pais) return n;
  return "+" + codigoDe(pais) + " " + n;
}
