# Contrato de datos v26: salario mínimo en cualquier moneda

**Fecha:** 15 de noviembre de 2026. **Amplía:** [v22](CONTRATO_DATOS_v22.md), en lo que toca a la restricción
«salario mínimo». **No cambia:** las columnas de `ofertas`, el CSV ni la configuración del panel. No hay SQL nuevo.

## Por qué

Con v22, la restricción `salario_minimo` del perfil solo comparaba si el aviso decía el salario **en la misma moneda**.
Un perfil con «mínimo 1000 USD al mes» no comparaba con un aviso de «999 EUR al mes»: la vacante nunca se descartaba,
pero tampoco se descartaba una de «300 EUR al mes». Oscar pidió que se usen equivalencias entre monedas.

## Regla

1. Del aviso se lee lo de siempre (`contrato.salario`): monto máximo, o el único si solo hay uno, su moneda (solo si el
   aviso la dice: un «$» solo no basta) y su periodo.
2. Si la moneda del aviso es distinta de la del perfil, el monto se convierte con la tabla `datos/tasas_cambio.yaml`
   (tasas frente al dólar, con su fecha). Después se pasa a mensual como en v22 (año = 12 meses; por hora solo se
   compara con por hora).
3. **Margen del 10 %.** Se descarta solo si la equivalencia queda **más de un 10 % por debajo** del mínimo del perfil.
   Así, los redondeos y la variación diaria de las tasas no descartan. Ejemplo: mínimo 1000 USD y aviso de 999 EUR
   (unos 1100 USD): no se descarta. Mínimo 1000 USD y aviso de 700 EUR (unos 770 USD): se descarta.
4. **Nunca se descarta sin evidencia clara.** No se convierte (y la vacante sigue, como en v22) cuando:
   - la moneda del aviso o la del perfil no está en la tabla;
   - es una moneda de alta inflación (`inestables` de la tabla: ARS y VES);
   - la tabla tiene más de 120 días: con tasas viejas no se descarta (`python -m buscador.tasas` dice si está vigente).
5. Con la misma moneda también se aplica el margen del 10 %, para que la regla sea igual en todos los casos.

## Perfiles muy móviles

`puede_trabajar_en` admite hasta **60** países (antes 30, v23), igual que «También se mudaría a…». Así cabe, por ejemplo,
una persona que se mueve entre Emiratos y cualquier país de Europa. El importador de clientes acepta regiones en esas
listas («Europa», «UE», «LATAM», «LATAM y España», «Norteamérica», «Toda América»), que se convierten en sus países.

## Tabla de tasas

`datos/tasas_cambio.yaml`:

```yaml
fecha: "2026-11-15"        # día de las tasas
fuente: "open.er-api.com"  # fuente pública sin clave
base: USD
tasas: {EUR: 0.906, COP: 3285.26, ...}   # unidades de cada moneda por 1 USD
inestables: [ARS, VES]
```

Se actualiza con `python -m buscador.tasas --actualizar` (una vez al mes basta) o editándola a mano. No necesita
cuenta ni clave. Si la fuente no responde, la tabla anterior se conserva.

## Pruebas

En `pruebas/panel/test_control.py`:
- 999 EUR frente a 1000 USD no descarta;
- 700 EUR frente a 1000 USD descarta;
- 1050 USD frente a 1100 USD no descarta (margen);
- ARS no descarta;
- tabla vencida no descarta;
- COP mensual frente a USD;
- por hora frente a mensual no compara.
