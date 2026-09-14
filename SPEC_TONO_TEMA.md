# SPEC_TONO_TEMA — Tono aspectual, tema (cubos) y subtema

Versión 1.0 · Grill-API (`ai_analyzer.py`)

Este documento es la fuente de verdad para clasificar **tono**, **tema** y **subtema**. El tono mide el impacto reputacional **sobre la marca, sus alias y voceros**. No es el sentimiento del artículo entero.

---

## 1. Principio aspectual del tono

El tono es **aspectual**: se decide solo con oraciones que nombran a la marca, un alias o un vocero (rector, director, vocero, etc.).

| Situación | Tono |
|---|---|
| No hay mención de marca/alias/vocero | **Neutro**; no se pide tono al LLM |
| Crítica, queja, denuncia o sanción **dirigida** a la marca | **Negativo** |
| La marca es **sujeto** de un verbo de aporte (dona, respalda, inaugura, lanza, acompaña, …) | **Positivo** (solo se sube Neutro→Positivo; ver §2) |
| Tragedia, sismo o accidente **sin** crítica dirigida | **Neutro** |
| La marca aparece solo como sede, campus o ubicación | **Neutro** |
| Autoría / egresados (regla de byline) | **Neutro**, tema Estudiantes, subtema `Redacción de artículo` |

El LLM **no** debe contagiar el tono con el clima del titular ni con hechos de otras entidades.

---

## 2. Evidencia de marca vs contexto de hecho

### 2.1 Partición por campo

Título y cuerpo se parten **por oración por separado**. Está prohibido concatenar título+cuerpo **antes** de buscar la marca (esa concatenación era la hipótesis de contagio).

1. Limpiar cada campo (sin URLs).
2. Partir en unidades (`.`, `!`, `?`, salto de línea, `|`).
3. **Enmascarar** otras entidades institucionales parecidas (`Universidad X`, `Clínica Y`, …) que **no** sean la marca.
4. Conservar solo unidades que, ya enmascaradas, nombran marca, alias o vocero.
5. Unir esas unidades: ese texto es `Contexto analizado` (evidencia de marca).
6. Si no queda ninguna unidad → evidencia vacía → tono Neutro y se omite el BLOQUE A.

El **subtema** describe el hecho específico. El **tema** (sin PKL) se asigna con la lista cerrada de cubos y reglas léxicas sobre el subtema; el título solo entra si tiene **≤ 160 caracteres**.

### 2.2 Alias

En todos los sitios de parseo los alias se parten con:

```python
re.split(r'[,;\n]', ...)
```

---

## 3. Guardas deterministas posteriores al LLM (§2 operativo)

Se aplican **después** de la respuesta del modelo, sobre la evidencia de marca:

1. **Sin mención** → Neutro.
2. **Byline / egresados** (antes del LLM): Neutro + Estudiantes + `Redacción de artículo`.
3. **Negativo trágico corto**: si el tono LLM es Negativo, el snippet tiene **≤ 35 caracteres**, hay marca de tragedia y **no** hay crítica dirigida → Neutro.
4. **Sede/ubicación**: mención locativa sin agencia ni crítica → Neutro.
5. **Verbos de aporte**: si el tono quedó Neutro y la marca es sujeto de un verbo de contribución → **Positivo** (Neutro→Positivo únicamente).
6. **Override institucional útil** (`check_positive_institutional_override`): acompañamiento, respaldo, felicitación, alianza explícitos → Positivo.

Con PKL de tono, la etiqueta del modelo del cliente **sigue ganando** después de estas guardas. Con PKL de tema, el cubo del cliente **no se sustituye**.

---

## 4. Dual prompt (`_call_openai_cluster`)

El system prompt refuerza: tono aspectual; **BLOQUE A** decide solo el tono; **BLOQUE B** decide solo el subtema; no mezclar evidencia.

- **BLOQUE A — TONO**: únicamente evidencia de marca. Se omite si no hay mención (`request_tone` efectivo = false).
- **BLOQUE B — SUBTEMA**: hecho específico, 3 a 7 palabras, frase nominal. No es el cubo ni el tono.

Si se pide tema (no hay PKL de tema), el cubo debe salir de la lista cerrada. **PROHIBIDO "Otros"**.

---

## 5. Subtema

- Validador duro: **3 a 7 palabras**.
- Se reutilizan `clean_subtema` (recorte, stopwords finales, veto de “Mención de…”) y `canonicalize_subtopics` (unificación entre clústers).
- Si el LLM entrega menos de 3 o más de 7 palabras, `validate_or_repair_subtema` repara con título/contexto.
- El subtema no puede ser solo el nombre de la marca.

---

## 6. Tema — 21 cubos por defecto (sin PKL)

Lista cerrada. Nunca se emite `Otros`, `Otro`, `General`, `Varios`, `Sin clasificar` ni `Actualidad`. Si el LLM propone un cubo válido, se conserva; si no, reglas léxicas sobre el subtema (y el título solo si ≤ 160 caracteres). Por defecto: **Gestión Institucional**.

Con PKL de tema se mantiene el override actual del cliente.

### Cubos (21)

1. Educación Superior
2. Estudiantes
3. Sector Salud
4. Gestión Institucional
5. Gestión Tributaria
6. Hitos y Aniversarios
7. Gestión de Emergencias
8. Infraestructura
9. Seguridad Ciudadana
10. Relaciones Gremiales
11. Investigación y Ciencia
12. Cultura y Deporte
13. Medio Ambiente
14. Economía y Empresa
15. Gobierno y Política
16. Responsabilidad Social
17. Tecnología e Innovación
18. Laboral y Empleo
19. Legal y Regulatorio
20. Comunidad y Territorio
21. Comunicaciones y Medios

---

## 7. Invariantes de pipeline (no romper)

Se conservan:

- `cluster_similar_rows` / agrupación por hecho
- `canonicalize_subtopics`
- ruta PKL (`classification_plan`, override de tono/tema, subtema nunca por PKL)
- regla de byline / egresados
- `enrich_rows_with_ai`
- APIs de `pipeline.py` y `app.py`

---

## 8. Casos dorados

Ver `tests/casos_dorados.json`. Resumen:

| ID | Esperado | Por qué |
|---|---|---|
| `positivo_brand_actor` | Positivo | La marca es sujeto de aporte; la tragedia ajena no contagia |
| `negativo_directed_criticism` | Negativo | Queja/denuncia dirigida a la marca |
| `neutro_tragedy` | Neutro | Tragedia corta (≤35) sin crítica dirigida |
| `neutro_no_mention` | Neutro | Cero oraciones con marca; evidencia vacía |
| `neutro_sede_only` | Neutro | Solo ubicación/sede |
| `byline` | Neutro + Estudiantes + Redacción de artículo | Autoría / egresado |

---

## 9. Hipótesis verificada

El fallback histórico de `extract_brand_context` (concatenar título+cuerpo cuando no había match, y un prompt mixto de tono+hecho) **contagiaba** el tono con el sentimiento del artículo. Esta spec elimina ese fallback y separa los bloques del prompt.
