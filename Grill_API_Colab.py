# %% [markdown]
# # Grill-API — alternativa Colab
#
# Use este script cuando [grill-api.streamlit.app](https://grill-api.streamlit.app/)
# se quede en **Etiquetando 1/N**. Suba un `.xlsx`, indique marca + alias,
# y descargue el resultado con `Contexto analizado`, `Tono IA`, `Tema`,
# `Subtema` y `Grupo noticia`.
#
# **Modelo:** `gpt-4.1-nano-2025-04-14` por defecto.
# **No use** `gpt-5-nano-2025-08-07` en esta pila: subtemas tipo «X de Y»,
# tono todo Neutro, y TTFT de decenas de segundos. Solo vale la pena con
# `reasoning_effort=minimal` y un A/B real; no como default mientras el
# etiquetado esté bloqueado.
#
# **Clave OpenAI (cualquiera de las dos):**
# 1. Colab → 🔑 Secrets → `OPENAI_API_KEY` (recomendado: `userdata.get`).
# 2. Si `userdata` no está, pegue la clave en el recuadro de la UI.
#
# En Colab: *Runtime → Run all*. Debe estar el repo (o al menos `app.py`)
# en el cwd. En local: `python Grill_API_Colab.py`.

# %%
import sys
import subprocess

_PKGS = [
    "pandas>=2.1,<3",
    "openpyxl>=3.1,<4",
    "openai==0.28.0",
    "scikit-learn>=1.3,<2",
    "unidecode>=1.3,<2",
    "joblib>=1.3,<2",
    "numpy",
    "xgboost==2.0.3",
    "gradio>=4.44,<6",
]
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "-q", *_PKGS],
    stdout=subprocess.DEVNULL,
)

# %%
import io
import os
from pathlib import Path
from unittest.mock import MagicMock

import gradio as gr
import openai
import pandas as pd


def _leer_openai_key():
    env = os.environ.get("OPENAI_API_KEY", "").strip()
    if env:
        return env
    try:
        from google.colab import userdata  # type: ignore
        k = (userdata.get("OPENAI_API_KEY") or "").strip()
        if k:
            os.environ["OPENAI_API_KEY"] = k
            return k
    except Exception:
        pass
    return ""


class _Session(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


if "streamlit" not in sys.modules:
    st = MagicMock()
    st.session_state = _Session()
    st.secrets = {}
    st.set_page_config = lambda **_k: None
    st.cache_data = lambda **_k: (lambda f: f)
    sys.modules["streamlit"] = st

os.environ.setdefault("OPENAI_CLASIF_MODEL", "gpt-4.1-nano-2025-04-14")

ROOT = Path(__file__).resolve().parent if "__file__" in dir() else Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app  # noqa: E402

app.refrescar_modelo_clasificacion()


def _bytes_de_archivo(file_obj):
    if file_obj is None:
        return None
    if isinstance(file_obj, (bytes, bytearray)):
        return bytes(file_obj)
    if hasattr(file_obj, "read"):
        data = file_obj.read()
        try:
            file_obj.seek(0)
        except Exception:
            pass
        return data
    if isinstance(file_obj, dict):
        path = file_obj.get("path") or file_obj.get("name")
        return Path(path).read_bytes() if path else None
    path = getattr(file_obj, "name", None) or str(file_obj)
    return Path(path).read_bytes()


def _leer_xlsx(file_obj):
    data = _bytes_de_archivo(file_obj)
    if not data:
        raise gr.Error("Suba un Excel .xlsx")
    return pd.read_excel(io.BytesIO(data))


def _col(df, candidatos, fallback=0):
    return df.columns[app._default_text_column_index(list(df.columns), candidatos, fallback)]


class _PBar:
    def progress(self, frac, text=""):
        print(f"{int((frac or 0) * 100)}% {text}".strip(), flush=True)


def correr_clasificacion(
    xlsx, marca, aliases_txt, pkl_tema, pkl_tono, api_key_manual, usar_llm,
):
    key = (api_key_manual or "").strip() or _leer_openai_key()
    if usar_llm and not key:
        raise gr.Error(
            "Falta OPENAI_API_KEY. En Colab: Secrets → OPENAI_API_KEY, "
            "o péguela en el recuadro."
        )
    if key:
        openai.api_key = key
        os.environ["OPENAI_API_KEY"] = key

    app.st.session_state["tokens_input"] = 0
    app.st.session_state["tokens_output"] = 0
    app.st.session_state["tokens_embedding"] = 0
    app.refrescar_modelo_clasificacion()

    df = _leer_xlsx(xlsx)
    tc = _col(df, ["Título", "Titulo", "Titular", "Headline"], 0)
    sc = _col(
        df,
        ["Resumen - Aclaración", "Resumen - Aclaracion", "Resumen", "CuerpoEs",
         "Cuerpo", "Descripción", "Descripcion"],
        1 if len(df.columns) > 1 else 0,
    )
    cc = None
    for c in df.columns:
        if app._normalizar_mencion(c) in {"cuerpo completo", "cuerpo", "cuerpocompleto"}:
            cc = c
            break
    marca = (marca or "").strip()
    if not marca:
        raise gr.Error("Indique la marca principal.")
    aliases = [a.strip() for a in str(aliases_txt or "").split(";") if a.strip()]
    cuerpos = df[cc].fillna("").tolist() if cc else None

    tema_buf = tono_buf = None
    raw_tema = _bytes_de_archivo(pkl_tema)
    if raw_tema:
        tema_buf = io.BytesIO(raw_tema)
    raw_tono = _bytes_de_archivo(pkl_tono)
    if raw_tono:
        tono_buf = io.BytesIO(raw_tono)

    out = app.clasificar_noticias_core(
        df[tc].fillna("").tolist(),
        df[sc].fillna("").tolist(),
        marca,
        aliases,
        cuerpos=cuerpos,
        pkl_tono=tono_buf,
        pkl_tema=tema_buf,
        usar_llm=bool(usar_llm),
        pbar=_PBar(),
    )
    extra = [c for c in ("Contexto analizado", "Tono IA", "Tema", "Subtema", "Grupo noticia") if c in out.columns]
    merged = df.copy()
    for c in extra:
        merged[c] = out[c].tolist()
    dest = Path("/tmp") / f"grill_clasificacion_{app._safe_filename_part(marca)}.xlsx"
    with pd.ExcelWriter(dest, engine="openpyxl") as w:
        merged.to_excel(w, index=False, sheet_name="Clasificacion")
    aviso = (
        f"Modelo `{app.OPENAI_MODEL_CLASIFICACION}`. "
        + (app.advertencia_modelo_clasificacion() or "")
        + f" Filas: {len(merged)}."
    )
    return merged.head(12), str(dest), aviso


CSS = """
.gradio-container {background:#0d0d0d !important; color:#f4f4f4 !important;}
#grill-title h1 {color:#ff6b00 !important; letter-spacing:.04em;}
"""

with gr.Blocks(
    title="Grill-API · Colab",
    css=CSS,
    theme=gr.themes.Base(primary_hue="orange", neutral_hue="slate").set(
        body_background_fill="#0d0d0d",
        body_text_color="#f4f4f4",
        button_primary_background_fill="#ff6b00",
        button_primary_text_color="#0d0d0d",
    ),
) as demo:
    gr.Markdown(
        "# Grill-API\nClasificación de noticias (Colombia): **contexto · tono · tema · subtema**",
        elem_id="grill-title",
    )
    gr.Markdown(
        "Fallback cuando Streamlit Cloud se queda en *Etiquetando 1/N*. "
        "Misma lógica que `app.py` (`clasificar_noticias_core`). "
        f"Default: **{app.MODELO_CLASIF_DEFAULT}** — no gpt-5-nano."
    )
    with gr.Row():
        xlsx = gr.File(label="Dossier .xlsx", file_types=[".xlsx"])
        pkl_tema = gr.File(label="PKL de temas (opcional)", file_types=[".pkl"])
        pkl_tono = gr.File(label="PKL de tono (opcional)", file_types=[".pkl"])
    with gr.Row():
        marca = gr.Textbox(label="Marca principal", placeholder="Ej. Fenavi")
        aliases = gr.Textbox(label="Alias (separados por ;)", placeholder="Ej. Federación Nacional de Avicultores")
    api_key_manual = gr.Textbox(
        label="OPENAI_API_KEY (si no está en Colab Secrets)",
        type="password",
        placeholder="sk-…  — déjelo vacío si ya configuró userdata / env",
    )
    usar_llm = gr.Checkbox(value=True, label="Usar API OpenAI (desmarque para heurística local, sin tono IA)")
    btn = gr.Button("Clasificar", variant="primary")
    preview = gr.Dataframe(label="Vista previa")
    descarga = gr.File(label="Descargar xlsx")
    status = gr.Markdown()
    btn.click(
        fn=correr_clasificacion,
        inputs=[xlsx, marca, aliases, pkl_tema, pkl_tono, api_key_manual, usar_llm],
        outputs=[preview, descarga, status],
    )

if __name__ == "__main__":
    try:
        from google.colab import output as _colab_output  # type: ignore  # noqa: F401
        in_colab = True
    except Exception:
        in_colab = False
    demo.queue().launch(share=in_colab, debug=False, inline=in_colab)
