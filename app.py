# ======================================
# Importaciones
# ======================================
import streamlit as st
import pandas as pd
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, NamedStyle, Alignment
from collections import defaultdict, Counter
from difflib import SequenceMatcher
from copy import deepcopy
import datetime
import io
import openai
import re
import time
from unidecode import unidecode
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering
import json
import asyncio
import hashlib
from typing import List, Dict, Tuple, Optional, Any
import joblib
import gc
import requests
import os
import zipfile
import xml.etree.ElementTree as ET
import html
from pathlib import Path

# ======================================
# Configuración general
# ======================================
st.set_page_config(
    page_title="Análisis de Noticias · API - Realizado por Johnathan Cortés",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

OPENAI_MODEL_EMBEDDING     = "text-embedding-3-small"
OPENAI_MODEL_CLASIFICACION = "gpt-4.1-nano-2025-04-14"

CONCURRENT_REQUESTS          = 50
SIMILARITY_THRESHOLD_TONO    = 0.96  
SIMILARITY_THRESHOLD_TITULOS = 0.94

# ── Umbrales base (corpus grande ≥ 20 noticias) ──────────────────────────────
UMBRAL_SUBTEMA = 0.78
UMBRAL_TEMA    = 0.72
NUM_TEMAS_MAX  = 15

UMBRAL_DEDUP_LABEL           = 0.86
UMBRAL_FUSION_SUBTEMAS       = 0.88
UMBRAL_FUSION_INTERGRUPO     = 0.90
MAX_ITER_FUSION              = 3

UMBRAL_MIN_PERTENENCIA_SUBTEMA = 0.60
UMBRAL_MIN_PERTENENCIA_TEMA    = 0.52

UMBRAL_COHERENCIA_ETIQUETA   = 0.35

MAX_GRUPO_ETIQUETA           = 40

# ── Umbrales mínimos de similitud REAL para agrupar ──────────────────────────
SIM_MINIMA_AGRUPACION_SUBTEMA = 0.90
SIM_MINIMA_KEYWORDS_RARAS     = 0.86
SIM_MINIMA_FUSION_INTER       = 0.90

# ── Consistencia ultra-precisa entre republicaciones / coberturas casi idénticas ─────────────
UMBRAL_SIM_TITULO_CONSIST = 0.90   
UMBRAL_SIM_CUERPO_CONSIST = 0.88   
UMBRAL_EMB_TITULO_CONSIST = 0.935  
UMBRAL_EMB_CUERPO_CONSIST = 0.915  
UMBRAL_PREF_TITULO_CONSIST = 0.93  
MIN_LEN_CUERPO_CONSIST    = 50     
MIN_PALABRAS_PREF_TITULO  = 6      

# ── Unificación post-etiqueta (subtemas levemente distintos del mismo hecho) ─
UMBRAL_FUSION_ETIQUETA_POST   = 0.90   
UMBRAL_FUSION_CONTENIDO_POST  = 0.905  
UMBRAL_OVERLAP_POST           = 0.28   
UMBRAL_NEAR_DUP_CONTENT       = 0.93   

PRICE_INPUT_1M     = 0.10
PRICE_OUTPUT_1M    = 0.40
PRICE_EMBEDDING_1M = 0.02

if 'tokens_input' not in st.session_state: st.session_state['tokens_input']     = 0
if 'tokens_output' not in st.session_state: st.session_state['tokens_output']    = 0
if 'tokens_embedding' not in st.session_state: st.session_state['tokens_embedding'] = 0

STOPWORDS_ES = set("""
a ante bajo cabe con contra de desde durante en entre hacia hasta mediante
para por segun sin so sobre tras y o u e la el los las un una unos unas lo
al del se su sus le les mi mis tu tus nuestro nuestros vuestra vuestras este
esta estos estas ese esa esos esas aquel aquella aquellos aquellas que cual
cuales quien quienes cuyo cuya cuyos cuyas como cuando donde cual es son fue
fueron era eran sera seran seria serian he ha han habia han hay hubo habra
habria estoy esta estan estaba estaban estamos estan estar estare estaria
estuvieron estarian estuvo asi ya mas menos tan tanto cada muy todo toda todos
todas ser haber hacer tener poder deber ir dar ver saber querer llegar pasar
encontrar creer decir poner salir volver seguir llevar sentir cambiar
""".split())

_TRAILING_INCOMPLETE = {
    "de","del","la","el","los","las","un","una","unos","unas","al","su","sus",
    "en","con","sin","por","para","sobre","ante","bajo","contra","desde",
    "entre","hacia","hasta","mediante","tras","y","o","u","e","lo","que","se",
    "como","donde","cuando","cual","cuyo","cuya","cuyos","cuyas",
    "este","esta","estos","estas","ese","esa","esos","esas",
    "aquel","aquella","aquellos","aquellas","cada","todo","toda","todos","todas",
    "otro","otra","otros","otras","nuevo","nueva","nuevos","nuevas",
    "gran","grandes","mayor","mayores","menor","menores","mejor","mejores",
    "peor","peores","primer","primera","segundo","segunda","tercer","tercera",
    "más","mas","muy","tan","tanto","tanta","tantos","tantas",
    "mi","mis","tu","tus","nuestro","nuestra","nuestros","nuestras",
    "a","ha","he","ser","estar","haber","hacer","tener","poder","deber",
    "ir","dar","ver","saber","querer","llegar","pasar","decir","poner",
}

_PATRON_TITULAR = re.compile(
    r"^(nuevo|nueva|anuncia|lanza|presenta|inaugura|llega|abre|inicia|"
    r"logra|alcanza|supera|confirma|destaca|revela|señala|advierte|"
    r"lanzamiento|anuncio|apertura|inicio|presentacion|presentación)\b",
    re.IGNORECASE
)
_PATRON_ESTADO = re.compile(
    r"\b(calma|caos|urgente|hoy|ya|ahora|yesterday|mañana|nuevo|nueva|"
    r"gran|grande|importante|especial|exclusivo)\s*$",
    re.IGNORECASE
)

_TILDE_MAP = {
    "regulacion":"regulación","regulaciones":"regulaciones","innovacion":"innovación",
    "innovaciones":"innovaciones","tecnologia":"tecnología","tecnologias":"tecnologías",
    "tecnologica":"tecnológica","tecnologico":"tecnológico","educacion":"educación",
    "gestion":"gestión","administracion":"administración","informacion":"información",
    "comunicacion":"comunicación","comunicaciones":"comunicaciones","operacion":"operación",
    "operaciones":"operaciones","inversion":"inversión","inversiones":"inversiones",
    "expansion":"expansión","adquisicion":"adquisición","adquisiciones":"adquisiciones",
    "fusion":"fusión","fusiones":"fusiones","transicion":"transición",
    "transformacion":"transformación","digitalizacion":"digitalización",
    "automatizacion":"automatización","modernizacion":"modernización",
    "optimizacion":"optimización","implementacion":"implementación","evaluacion":"evaluación",
    "planificacion":"planificación","organizacion":"organización","atencion":"atención",
    "produccion":"producción","construccion":"construcción","distribucion":"distribución",
    "exportacion":"exportación","importacion":"importación","comercializacion":"comercialización",
    "negociacion":"negociación","negociaciones":"negociaciones","participacion":"participación",
    "colaboracion":"colaboración","asociacion":"asociación","integracion":"integración",
    "relacion":"relación","relaciones":"relaciones","situacion":"situación",
    "condicion":"condición","condiciones":"condiciones","solucion":"solución",
    "soluciones":"soluciones","prevencion":"prevención","proteccion":"protección",
    "fiscalizacion":"fiscalización","sancion":"sanción","sanciones":"sanciones",
    "investigacion":"investigación","investigaciones":"investigaciones","accion":"acción",
    "acciones":"acciones","direccion":"dirección","decision":"decisión",
    "decisiones":"decisiones","eleccion":"elección","elecciones":"elecciones",
    "votacion":"votación","aprobacion":"aprobación","legislacion":"legislación",
    "reclamacion":"reclamación","reclamaciones":"reclamaciones","obligacion":"obligación",
    "obligaciones":"obligaciones","inflacion":"inflación","tributacion":"tributación",
    "financiera":"financiera","financiero":"financiero","economica":"económica",
    "economico":"económico","economia":"economía","credito":"crédito",
    "creditos":"créditos","prestamo":"préstamo","prestamos":"préstamos",
    "interes":"interés","comision":"comisión","comisiones":"comisiones",
    "politica":"política","politicas":"políticas","politico":"político",
    "publica":"pública","publico":"público","estrategia":"estrategia",
    "estrategica":"estratégica","estrategico":"estratégico","logistica":"logística",
    "analisis":"análisis","diagnostico":"diagnóstico","indice":"índice",
    "vehiculo":"vehículo","vehiculos":"vehículos","electrico":"eléctrico",
    "electrica":"eléctrica","energia":"energía","energetica":"energética",
    "petroleo":"petróleo","mineria":"minería","agricola":"agrícola",
    "biologica":"biológica","ecologica":"ecológica","inclusion":"inclusión",
    "exclusion":"exclusión","pension":"pensión","pensiones":"pensiones",
    "jubilacion":"jubilación","compensacion":"compensación","remuneracion":"remuneración",
    "contratacion":"contratación","capacitacion":"capacitación","formacion":"formación",
    "certificacion":"certificación","habilitacion":"habilitación","autorizacion":"autorización",
    "concesion":"concesión","licitacion":"licitación","migracion":"migración",
    "poblacion":"población","recaudacion":"recaudación","asignacion":"asignación",
    "corporacion":"corporación","fundacion":"fundación","institucion":"institución",
    "instituciones":"instituciones","region":"región","unico":"único","unica":"única",
    "ultimo":"último","ultima":"última","proximo":"próximo","basico":"básico",
    "basica":"básica","historico":"histórico","historica":"histórica",
    "medico":"médico","medica":"médica","farmaceutica":"farmacéutica",
    "clinica":"clínica","numero":"número","telefono":"teléfono","telefonia":"telefonía",
    "movil":"móvil","moviles":"móviles","codigo":"código","informatica":"informática",
    "electronica":"electrónica","robotica":"robótica","ciberseguridad":"ciberseguridad",
    "trafico":"tráfico","transito":"tránsito","aereo":"aéreo","maritimo":"marítimo",
    "turistica":"turística","turistico":"turístico","gastronomia":"gastrónomía",
    "academica":"académica","academico":"académico","pedagogica":"pedagógica",
    "cientifica":"científica","cientifico":"científico","juridica":"jurídica",
    "juridico":"jurídico","constitucion":"constitución","resolucion":"resolución",
    "notificacion":"notificación","programacion":"programación","actualizacion":"actualización",
    "verificacion":"verificación","validacion":"validación","liquidacion":"liquidación",
    "facturacion":"facturación","evasion":"evasión","corrupcion":"corrupción",
    "deforestacion":"deforestación","contaminacion":"contaminación","conservacion":"conservación",
    "restauracion":"restauración","rehabilitacion":"rehabilitación","renovacion":"renovación",
    "ampliacion":"ampliación","inauguracion":"inauguración","celebracion":"celebración",
    "clasificacion":"clasificación","eliminacion":"eliminación","motivacion":"motivación",
    "satisfaccion":"satisfacción","reputacion":"reputación","disposicion":"disposición",
}

_ENIE_MAP = {
    "desempeno":"desempeño","desempenos":"desempeños","empeno":"empeño","empenos":"empeños",
    "ensenanza":"enseñanza","ensenanzas":"enseñanzas","diseno":"diseño","disenos":"diseños",
    "disenador":"diseñador","disenadora":"diseñadora","disenadores":"diseñadores",
    "nino":"niño","nina":"niña","ninos":"niños","ninas":"niñas","ninez":"niñez",
    "ano":"año","anos":"años","danio":"daño","danios":"daños","dano":"daño","danos":"daños",
    "danino":"dañino","danina":"dañina","montana":"montaña","montanas":"montañas",
    "espana":"España","espanol":"español","espanola":"española","espanoles":"españoles",
    "companero":"compañero","companera":"compañera","companeros":"compañeros","companeras":"compañeras",
    "compania":"compañía","companias":"compañías","acompanamiento":"acompanamiento",
    "cana":"caña","canas":"cañas","banio":"baño","banios":"baños","bano":"baño","banos":"baños",
    "pena":"peña","penas":"peñas","penon":"peñón","senor":"señor","senora":"señora",
    "senores":"señores","senoras":"señoras","senal":"señal","senales":"señales",
    "senalizacion":"señalización","pequeno":"pequeño","pequena":"pequeña",
    "pequenos":"pequeños","pequenas":"pequeñas","sueno":"sueño","suenos":"sueños",
    "dueno":"dueño","duena":"dueña","duenos":"dueños","duenas":"dueñas",
    "otono":"otoño","punio":"puño","punios":"puños","puno":"puño",
    "canon":"cañón","canones":"cañones","manana":"mañana","mananas":"mañanas",
    "cabana":"cabaña","cabanas":"cabañas","banera":"bañera","vinedo":"viñedo",
    "vinedos":"viñedos","rebano":"rebaño","rebanos":"rebaños","extrano":"extraño",
    "extrana":"extraña","extranos":"extraños","extranas":"extrañas",
    "enganio":"engaño","engano":"engaño","enganos":"engaños","tamanio":"tamaño",
    "tamano":"tamaño","tamanos":"tamaños","muneca":"muñeca","munecas":"muñecas",
    "cunado":"cuñado","cunada":"cuñada","cunados":"cuñados","albanil":"albañil",
    "albaniles":"albañiles","narino":"Nariño","quindio":"Quindío",
    "ibanez":"Ibáñez","nunez":"Núñez","munoz":"Muñoz","ordonez":"Ordóñez",
    "yanez":"Yáñez","castaneda":"Castañeda","penalosa":"Peñalosa",
    "vineta":"viñeta","vinetas":"viñetas","banado":"bañado","banada":"bañada",
    "rinon":"riñón","rinones":"riñones","panial":"pañal","paniales":"pañales",
    "panal":"pañal","panales":"pañales","arana":"araña","aranas":"arañas",
    "pestana":"pestaña","pestanas":"pestañas","guino":"guiño","guinos":"guiños",
    "munequera":"muñequera","lenador":"leñador","lenadores":"leñadores",
    "resena":"reseña","resenas":"reseñas","panuelo":"pañuelo","panuelos":"pañuelos",
    "companerismo":"compañerismo","desengano":"desengaño","lenio":"leño","leno":"leño",
}

def corregir_tildes(texto: str) -> str:
    if not texto: return texto
    palabras = str(texto).split()
    resultado = []
    for p in palabras:
        low = p.lower()
        if low in _TILDE_MAP:
            c = _TILDE_MAP[low]
            if p[0].isupper() and not c[0].isupper(): c = c[0].upper() + c[1:]
            resultado.append(c)
        elif low in _ENIE_MAP:
            c = _ENIE_MAP[low]
            if p[0].isupper() and not c[0].isupper(): c = c[0].upper() + c[1:]
            resultado.append(c)
        else:
            resultado.append(p)
    return " ".join(resultado)


# ======================================
# CSS
# ======================================
def load_custom_css():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Google+Sans+Text:wght@400;500;700&family=Roboto+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
:root {
    --bg:#f8f9fa;--s1:#ffffff;--s2:#f1f3f4;--s3:#e8eaed;
    --border:#dadce0;--border2:#bdc1c6;--border-focus:#f97316;
    --text:#202124;--text2:#3c4043;--text3:#5f6368;--text4:#9aa0a6;
    --accent:#f97316;--accent2:#ea580c;--accent3:#c2410c;
    --accent-bg:#fff7ed;--accent-bg2:#ffedd5;--accent-bdr:#fed7aa;
    --green:#059669;--green2:#047857;--green-bg:#ecfdf5;--green-bdr:#a7f3d0;
    --red:#dc2626;--amber:#d97706;--blue:#1a73e8;
    --r:8px;--r2:12px;--r3:16px;--r4:20px;
    --shadow-sm:0 1px 2px rgba(60,64,67,0.1),0 1px 3px rgba(60,64,67,0.08);
    --shadow-md:0 1px 3px rgba(60,64,67,0.12),0 4px 8px rgba(60,64,67,0.08);
    --shadow-lg:0 2px 6px rgba(60,64,67,0.1),0 8px 24px rgba(60,64,67,0.1);
    --transition:all 0.2s cubic-bezier(0.4,0,0.2,1);
}
html,body,[data-testid="stApp"]{
    background:var(--bg)!important;color:var(--text)!important;
    font-family:'Google Sans Text','Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    font-size:14px;-webkit-font-smoothing:antialiased;letter-spacing:0.01em;
}
#MainMenu,footer,header{visibility:hidden}.stDeployButton{display:none}
.block-container{padding-top:1rem!important;padding-bottom:0!important}
[data-testid="stAppViewBlockContainer"]{padding-top:1rem!important}
.app-header{background:var(--s1);border:1px solid var(--border);border-radius:var(--r3);padding:1rem 1.5rem;margin-bottom:1rem;display:flex;align-items:center;gap:1rem;box-shadow:var(--shadow-sm);position:relative;overflow:hidden;}
.app-header-icon{width:40px;height:40px;background:linear-gradient(135deg,#f97316,#ea580c);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;color:white;flex-shrink:0;box-shadow:0 2px 8px rgba(249,115,22,0.3);}
.app-header-text{flex:1}
.app-header-title{font-family:'Google Sans',sans-serif;font-size:1.25rem;font-weight:700;color:var(--text);letter-spacing:-0.01em;line-height:1.3}
.app-header-version{font-family:'Roboto Mono',monospace;font-size:0.65rem;color:var(--text3);letter-spacing:0.03em;margin-top:0.15rem}
.app-header-badge{background:var(--accent-bg);border:1px solid var(--accent-bdr);color:var(--accent2);font-family:'Roboto Mono',monospace;font-size:0.6rem;font-weight:500;padding:0.25rem 0.75rem;border-radius:100px;letter-spacing:0.04em;text-transform:uppercase;white-space:nowrap;}
[data-testid="stTabs"] [data-testid="stTabsList"]{background:var(--s1)!important;border:1px solid var(--border)!important;border-radius:var(--r2)!important;padding:4px!important;gap:4px!important;box-shadow:var(--shadow-sm)!important;margin-bottom:0.75rem!important;}
[data-testid="stTabs"] button[data-baseweb="tab"]{font-family:'Google Sans',sans-serif!important;font-size:0.88rem!important;font-weight:500!important;color:var(--text2)!important;border-radius:var(--r)!important;padding:0.45rem 1.2rem!important;border:none!important;background:transparent!important;transition:var(--transition)!important;}
[data-testid="stTabs"] button[data-baseweb="tab"]:hover{background:var(--s2)!important;color:var(--text)!important}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]{background:var(--accent-bg)!important;color:var(--accent2)!important;border:1px solid var(--accent-bdr)!important;font-weight:700!important;}
.metrics-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:0.6rem;margin:0.8rem 0}
.metric-card{background:var(--s1);border:1px solid var(--border);border-radius:var(--r2);padding:0.8rem 0.6rem;text-align:center;transition:var(--transition);box-shadow:var(--shadow-sm);position:relative;overflow:hidden;}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:var(--r2) var(--r2) 0 0}
.metric-card.m-total::before{background:linear-gradient(90deg,#5f6368,#9aa0a6)}
.metric-card.m-unique::before{background:linear-gradient(90deg,#059669,#34d399)}
.metric-card.m-dup::before{background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.metric-card.m-time::before{background:linear-gradient(90deg,#1a73e8,#4285f4)}
.metric-card.m-cost::before{background:linear-gradient(90deg,#f97316,#fb923c)}
.metric-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}
.metric-val{font-family:'Google Sans',sans-serif;font-size:1.5rem;font-weight:700;line-height:1;margin-bottom:0.3rem;letter-spacing:-0.01em}
.metric-lbl{font-family:'Roboto Mono',monospace;font-size:0.62rem;color:var(--text3);text-transform:uppercase;letter-spacing:0.08em;font-weight:500}
[data-testid="stForm"]{background:var(--s1)!important;border:1px solid var(--border)!important;border-radius:var(--r3)!important;padding:1.2rem 1.5rem!important;box-shadow:var(--shadow-md)!important;}
.sec-label{font-family:'Google Sans',sans-serif;font-size:0.72rem;font-weight:700;color:var(--text2);letter-spacing:0.08em;text-transform:uppercase;padding-bottom:0.3rem;border-bottom:2px solid var(--s3);margin:0.8rem 0 0.5rem;display:flex;align-items:center;gap:0.5rem;}
.sec-label::before{content:'';display:inline-block;width:3px;height:12px;background:linear-gradient(180deg,#f97316,#ea580c);border-radius:2px}
.upload-zone{display:grid;grid-template-columns:repeat(3,1fr);gap:0.6rem;margin:0.3rem 0}
.upload-zone-card{background:var(--s1);border:1.5px dashed var(--border);border-radius:var(--r2);padding:0.6rem 0.8rem;display:flex;align-items:center;gap:0.6rem;transition:var(--transition);}
.upload-zone-card:hover{border-color:var(--accent);border-style:solid;transform:translateY(-1px);box-shadow:var(--shadow-md)}
.upload-zone-icon{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1rem;flex-shrink:0;}
.upload-zone-icon.uz-dossier{background:#fff7ed;color:#f97316}
.upload-zone-icon.uz-region{background:#ecfdf5;color:#059669}
.upload-zone-icon.uz-internet{background:#eff6ff;color:#1a73e8}
.upload-zone-text{flex:1;min-width:0}
.upload-zone-title{font-family:'Google Sans',sans-serif;font-size:0.82rem;font-weight:700;color:var(--text);line-height:1.2}
.upload-zone-desc{font-size:0.7rem;color:var(--text3);line-height:1.3}
[data-testid="stFileUploader"]{background:var(--s1)!important;border:1.5px dashed var(--border)!important;border-radius:var(--r)!important;padding:0.4rem 0.6rem!important;transition:var(--transition)!important;min-height:auto!important;}
[data-testid="stFileUploader"]:hover{border-color:var(--accent)!important;border-style:solid!important;background:var(--accent-bg)!important;}
[data-testid="stFileUploader"] section{padding:0.2rem!important}
[data-testid="stFileUploader"] section>div{font-size:0.78rem!important;color:var(--text2)!important}
[data-testid="stFileUploader"] section small{font-size:0.7rem!important;color:var(--text3)!important}
[data-testid="stFileUploader"] button{background:var(--accent-bg)!important;border:1px solid var(--accent-bdr)!important;color:var(--accent2)!important;font-weight:500!important;font-size:0.75rem!important;border-radius:100px!important;padding:0.25rem 0.8rem!important;font-family:'Google Sans',sans-serif!important;transition:var(--transition)!important;}
[data-testid="stFileUploader"] button:hover{background:var(--accent)!important;color:white!important;border-color:var(--accent)!important}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{background:var(--s1)!important;border:1.5px solid var(--border)!important;color:var(--text)!important;border-radius:var(--r)!important;font-family:'Google Sans Text',sans-serif!important;font-size:0.9rem!important;padding:0.5rem 0.75rem!important;transition:var(--transition)!important;}
[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(249,115,22,0.12)!important;}
[data-testid="stTextInput"] input::placeholder,[data-testid="stTextArea"] textarea::placeholder{color:var(--text4)!important;font-size:0.85rem!important;}
label[data-testid="stWidgetLabel"] p{font-family:'Google Sans',sans-serif!important;color:var(--text2)!important;font-size:0.82rem!important;font-weight:500!important;margin-bottom:0.15rem!important;}
.stButton>button,[data-testid="stDownloadButton"]>button{background:var(--s1)!important;border:1.5px solid var(--border)!important;color:var(--text)!important;border-radius:100px!important;font-family:'Google Sans',sans-serif!important;font-weight:500!important;font-size:0.88rem!important;transition:var(--transition)!important;padding:0.5rem 1.2rem!important;box-shadow:none!important;}
.stButton>button:hover,[data-testid="stDownloadButton"]>button:hover{border-color:var(--accent)!important;color:var(--accent2)!important;background:var(--accent-bg)!important;box-shadow:var(--shadow-sm)!important;transform:translateY(-1px)!important;}
.stButton>button[kind="primary"],[data-testid="stDownloadButton"]>button[kind="primary"]{background:var(--accent)!important;border:none!important;color:#fff!important;font-weight:500!important;font-size:0.92rem!important;padding:0.6rem 1.5rem!important;box-shadow:0 1px 3px rgba(249,115,22,0.3),0 4px 12px rgba(249,115,22,0.15)!important;letter-spacing:0.01em!important;}
.stButton>button[kind="primary"]:hover,[data-testid="stDownloadButton"]>button[kind="primary"]:hover{background:var(--accent2)!important;box-shadow:0 2px 6px rgba(234,88,12,0.35),0 8px 24px rgba(234,88,12,0.18)!important;transform:translateY(-1px)!important;color:#fff!important;}
[data-testid="stRadio"] label{font-family:'Google Sans Text',sans-serif!important;color:var(--text)!important;font-size:0.88rem!important;font-weight:400!important;}
[data-testid="stRadio"]{margin-bottom:0!important}
[data-testid="stRadio"]>div{gap:0!important}
[data-testid="stStatus"]{background:var(--s1)!important;border:1px solid var(--border)!important;border-radius:var(--r2)!important;font-family:'Roboto Mono',monospace!important;font-size:0.8rem!important;}
[data-testid="stAlert"]{background:var(--s1)!important;border:1px solid var(--border)!important;border-radius:var(--r2)!important;color:var(--text2)!important;font-size:0.85rem!important;padding:0.6rem 0.8rem!important;}
.success-banner{background:linear-gradient(135deg,#ecfdf5,#d1fae5);border:1px solid var(--green-bdr);border-left:4px solid var(--green);border-radius:var(--r2);padding:0.8rem 1.2rem;margin:0.5rem 0 0.8rem;display:flex;align-items:center;gap:0.8rem;}
.success-icon{width:34px;height:34px;background:linear-gradient(135deg,#059669,#047857);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:1rem;flex-shrink:0;}
.success-title{font-family:'Google Sans',sans-serif;font-size:1rem;font-weight:700;color:#047857;margin-bottom:0.1rem}
.success-sub{font-size:0.8rem;color:var(--text2)}
.auth-wrap{max-width:380px;margin:8vh auto 0;text-align:center}
.auth-icon{width:60px;height:60px;background:linear-gradient(135deg,#f97316,#ea580c);border-radius:16px;display:inline-flex;align-items:center;justify-content:center;font-size:1.6rem;color:white;margin-bottom:1rem;box-shadow:0 4px 16px rgba(249,115,22,0.3);}
.auth-title{font-family:'Google Sans',sans-serif;font-size:1.5rem;font-weight:700;color:var(--text);margin-bottom:0.3rem}
.auth-sub{font-size:0.85rem;color:var(--text3);margin-bottom:2rem}
.cluster-info{background:var(--accent-bg);border:1px solid var(--accent-bdr);border-radius:var(--r);padding:0.5rem 0.8rem;margin:0.4rem 0;font-family:'Roboto Mono',monospace;font-size:0.68rem;color:var(--text2);line-height:1.6;}
.cluster-info b{color:var(--accent2);font-size:0.72rem}
.config-badge{display:inline-flex;align-items:center;gap:0.4rem;background:var(--s2);border:1px solid var(--border);border-radius:100px;padding:0.2rem 0.7rem;font-family:'Roboto Mono',monospace;font-size:0.62rem;color:var(--text3);margin-bottom:0.6rem;}
[data-testid="stProgressBar"]>div>div{background:linear-gradient(90deg,#f97316,#fb923c,#fdba74)!important;border-radius:100px!important;height:5px!important;}
[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:var(--r2)!important;box-shadow:var(--shadow-sm)!important;overflow:hidden!important;}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--s2);border-radius:3px}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--accent)}
.footer{font-family:'Roboto Mono',monospace;font-size:0.6rem;color:var(--text4);text-align:center;padding:0.8rem 0 0.5rem;letter-spacing:0.04em;border-top:1px solid var(--s3);margin-top:1rem;}
.stElementContainer{margin-bottom:0!important}
[data-testid="stVerticalBlock"]>div{gap:0.3rem!important}
[data-testid="stHorizontalBlock"]>div{gap:0.4rem!important}
hr{border-color:var(--s3)!important;margin:0.5rem 0!important}
[data-testid="stSelectbox"]>div>div{font-family:'Google Sans Text',sans-serif!important;font-size:0.88rem!important;color:var(--text)!important;}
@media(max-width:768px){
    .metrics-grid{grid-template-columns:repeat(2,1fr)}
    .upload-zone{grid-template-columns:1fr}
    .app-header{flex-direction:column;text-align:center;gap:0.5rem;padding:1rem}
}
</style>
""", unsafe_allow_html=True)


# ======================================
# Umbrales adaptativos según tamaño del corpus
# ======================================
def _umbrales_adaptativos(n: int) -> dict:
    if n <= 5:
        return dict(
            subtema=0.93,
            tema=0.85,
            dedup_label=0.90,
            fusion_subtemas=0.92,
            fusion_intergrupo=0.95,
            min_pertenencia_subtema=0.80,
            min_pertenencia_tema=0.75,
            coherencia_etiqueta=0.50,
            sim_minima_agrupacion=0.93,
            sim_minima_keywords=0.93,
            max_iter_fusion=1,
            num_temas_max=n,
            usar_paso2b=False,
            usar_fusion_iterativa=False,
        )
    elif n <= 10:
        return dict(
            subtema=0.90,
            tema=0.84,
            dedup_label=0.88,
            fusion_subtemas=0.90,
            fusion_intergrupo=0.93,
            min_pertenencia_subtema=0.72,
            min_pertenencia_tema=0.65,
            coherencia_etiqueta=0.42,
            sim_minima_agrupacion=0.90,
            sim_minima_keywords=0.90,
            max_iter_fusion=2,
            num_temas_max=min(n, 5),
            usar_paso2b=False,
            usar_fusion_iterativa=False,
        )
    elif n <= 20:
        return dict(
            subtema=0.87,
            tema=0.82,
            dedup_label=0.86,
            fusion_subtemas=0.88,
            fusion_intergrupo=0.91,
            min_pertenencia_subtema=0.66,
            min_pertenencia_tema=0.58,
            coherencia_etiqueta=0.38,
            sim_minima_agrupacion=0.87,
            sim_minima_keywords=0.87,
            max_iter_fusion=3,
            num_temas_max=min(n // 2, NUM_TEMAS_MAX),
            usar_paso2b=True,
            usar_fusion_iterativa=True,
        )
    else:
        return dict(
            subtema=UMBRAL_SUBTEMA,
            tema=UMBRAL_TEMA,
            dedup_label=UMBRAL_DEDUP_LABEL,
            fusion_subtemas=UMBRAL_FUSION_SUBTEMAS,
            fusion_intergrupo=UMBRAL_FUSION_INTERGRUPO,
            min_pertenencia_subtema=UMBRAL_MIN_PERTENENCIA_SUBTEMA,
            min_pertenencia_tema=UMBRAL_MIN_PERTENENCIA_TEMA,
            coherencia_etiqueta=UMBRAL_COHERENCIA_ETIQUETA,
            sim_minima_agrupacion=SIM_MINIMA_AGRUPACION_SUBTEMA,
            sim_minima_keywords=SIM_MINIMA_KEYWORDS_RARAS,
            max_iter_fusion=MAX_ITER_FUSION,
            num_temas_max=NUM_TEMAS_MAX,
            usar_paso2b=True,
            usar_fusion_iterativa=True,
        )


# ======================================
# Funciones Auxiliares
# ======================================
def safe_str(val) -> str:
    """Convierte de manera segura cualquier variable, previniendo fallos en pandas series por np.nan / None"""
    if val is None:
        return ""
    if pd.isna(val):
        return ""
    return str(val).strip()


# ======================================
# Caché Global de Embeddings
# ======================================
class EmbeddingCache:
    def __init__(self):
        self._cache: Dict[str, List[float]] = {}
        self._hits = 0
        self._misses = 0

    def _key(self, text):
        s_text = safe_str(text)
        return hashlib.md5(s_text[:2000].encode('utf-8', errors='ignore')).hexdigest()

    def get(self, text):
        k = self._key(text)
        if k in self._cache:
            self._hits += 1
            return self._cache[k]
        self._misses += 1
        return None

    def put(self, text, emb):
        self._cache[self._key(text)] = emb

    def get_many(self, textos):
        results = [None] * len(textos)
        missing = []
        for i, t in enumerate(textos):
            c = self.get(t)
            if c is not None:
                results[i] = c
            else:
                missing.append(i)
        return results, missing

    def stats(self):
        total = self._hits + self._misses
        rate = (self._hits / total * 100) if total > 0 else 0
        return f"Cache: {self._hits} hits, {self._misses} misses ({rate:.0f}%)"

    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0

if '_emb_cache' not in st.session_state:
    st.session_state['_emb_cache'] = EmbeddingCache()

def get_embedding_cache():
    return st.session_state['_emb_cache']

# ======================================
# Configuración vía Google Sheets (CSV público)
# ======================================
CONFIG_CACHE_TTL = 300

@st.cache_data(ttl=CONFIG_CACHE_TTL, show_spinner=False)
def _fetch_map_from_csv(csv_url: str) -> dict:
    df = pd.read_csv(csv_url, header=None, dtype=str)
    df = df.dropna(how="all")
    mapping = pd.Series(
        df.iloc[:, 1].values,
        index=df.iloc[:, 0].astype(str).str.lower().str.strip()
    ).to_dict()
    mapping = {k: v for k, v in mapping.items() if k not in ("nan", "")}
    return mapping

def load_config_from_sheets():
    regiones_url = st.secrets.get("REGIONES_CSV_URL")
    internet_url = st.secrets.get("INTERNET_CSV_URL")

    if not regiones_url or not internet_url:
        st.error(
            "❌ Faltan las URLs de configuración. Agrega REGIONES_CSV_URL e "
            "INTERNET_CSV_URL en los Secrets de la app."
        )
        st.stop()

    try:
        region_map = _fetch_map_from_csv(regiones_url)
        internet_map = _fetch_map_from_csv(internet_url)
    except Exception as e:
        st.error(f"❌ No se pudo leer la configuración desde Google Sheets: {e}")
        st.stop()

    return region_map, internet_map

def refresh_config_cache():
    _fetch_map_from_csv.clear()


# ======================================
# Mas utilidades
# ======================================

def check_password():
    if st.session_state.get("password_correct", False):
        return True
    st.markdown("""
    <div class="auth-wrap">
        <div class="auth-icon">◈</div>
        <div class="auth-title">Sistema de Análisis</div>
        <div class="auth-sub">Ingresa tus credenciales para continuar</div>
    </div>""", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("pw"):
            pw = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
            if st.form_submit_button("Ingresar", use_container_width=True, type="primary"):
                if pw == st.secrets.get("APP_PASSWORD", "INVALID"):
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
    return False

def call_with_retries(fn, *a, **kw):
    d = 1
    for att in range(3):
        try:
            return fn(*a, **kw)
        except Exception as e:
            if att == 2: raise e
            time.sleep(d)
            d *= 2

async def acall_with_retries(fn, *a, **kw):
    d = 1
    for att in range(3):
        try:
            return await fn(*a, **kw)
        except Exception as e:
            if att == 2: raise e
            await asyncio.sleep(d)
            d *= 2

def norm_key(text):
    text = safe_str(text)
    if not text: return ""
    return re.sub(r"[^a-z0-9]+", "", unidecode(text.lower()))

def capitalizar_etiqueta(tema):
    tema = safe_str(tema)
    if not tema: return "Sin tema"
    tema = tema.lower()
    tema = corregir_tildes(tema)
    return tema[0].upper() + tema[1:]

def _frase_esta_completa(texto):
    texto = safe_str(texto)
    if not texto: return False
    palabras = texto.split()
    if not palabras: return False
    ultima = palabras[-1].lower().rstrip(".,;:!?")
    return unidecode(ultima) not in _TRAILING_INCOMPLETE and len(ultima) > 1

def _recortar_frase_completa(texto, max_palabras=7):
    texto = safe_str(texto)
    if not texto: return "Sin tema"
    palabras = texto.split()
    if len(palabras) > max_palabras: palabras = palabras[:max_palabras]
    while palabras and unidecode(palabras[-1].lower().rstrip(".,;:!?")) in _TRAILING_INCOMPLETE:
        palabras.pop()
    if not palabras: return texto.split()[0] if texto else "Sin tema"
    return " ".join(palabras)

def limpiar_tema(tema):
    tema = safe_str(tema).strip('"\'')
    if not tema: return "Sin tema"
    for px in ["subtema:", "tema:", "categoría:", "categoria:", "category:"]:
        if tema.lower().startswith(px): tema = tema[len(px):].strip()
    tema = _recortar_frase_completa(tema, max_palabras=7)
    return capitalizar_etiqueta(tema) if tema else "Sin tema"

def limpiar_tema_geografico(tema, marca, aliases):
    tema = safe_str(tema)
    if not tema: return "Sin tema"
    tl = unidecode(tema.lower())
    for n in [marca] + [a for a in aliases if a]:
        patron = r'\b' + re.escape(unidecode(safe_str(n).lower())) + r'\b'
        tl = re.sub(patron, '', tl)
    frases_eliminar = [
        "en colombia", "de colombia", "del pais", "en el pais",
        "territorio nacional", "a nivel nacional", "en todo el pais",
    ]
    for frase in frases_eliminar:
        tl = re.sub(r'\b' + re.escape(frase) + r'\b', '', tl)
    tl = re.sub(r'\s+', ' ', tl).strip()
    if not tl: return "Sin tema"
    tokens_orig = tema.split()
    tokens_norm = unidecode(tema.lower()).split()
    norm_disponibles = tl.split()
    resultado_tokens = []
    for orig, norm in zip(tokens_orig, tokens_norm):
        if norm_disponibles and norm == norm_disponibles[0]:
            resultado_tokens.append(orig)
            norm_disponibles.pop(0)
    resultado = " ".join(resultado_tokens).strip()
    resultado = corregir_tildes(resultado) if resultado else ""
    return limpiar_tema(resultado) if resultado.strip() else "Sin tema"

def string_norm_label(s):
    s = safe_str(s)
    if not s: return ""
    s = unidecode(s.lower())
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(t for t in s.split() if t not in STOPWORDS_ES)

_ACCIONES_OPUESTAS = [
    ({"aprobacion", "aprueba", "apoyo", "acuerdo", "aval", "respaldo"}, {"rechazo", "rechaza", "desacuerdo", "oposicion", "critica"}),
    ({"aumento", "crecimiento", "alza", "subida", "incremento"}, {"caida", "reduccion", "baja", "disminucion", "descenso"}),
    ({"apertura", "inauguracion", "inicio", "lanzamiento", "estreno"}, {"cierre", "suspension", "fin", "clausura", "cancelacion"}),
    ({"exito", "logro", "triunfo", "premio", "reconocimiento"}, {"fracaso", "derrota", "problema", "crisis", "sancion"}),
    ({"demanda", "denuncia", "investigacion", "sancion", "multa"}, {"absolucion", "archivo", "exoneracion", "acuerdo"}),
]

_TOKENS_DEBILES_AGRUPACION = STOPWORDS_ES | {
    "noticia", "noticias", "informe", "informacion", "comunicado", "anuncio",
    "colombia", "pais", "nacional", "regional", "local", "sector", "sectores",
    "empresa", "empresas", "entidad", "entidades", "autoridad", "autoridades",
    "gobierno", "alcaldia", "gobernacion", "ministerio", "nuevo", "nueva",
    "nuevos", "nuevas", "plan", "programa", "proyecto", "iniciativa",
    "actividad", "actividades", "gestion", "tema", "caso", "casos",
}

def _tokens_distintivos(texto: str, min_len: int = 4) -> set:
    norm = string_norm_label(texto)
    return {
        t for t in norm.split()
        if len(t) >= min_len and t not in _TOKENS_DEBILES_AGRUPACION and not t.isdigit()
    }

def _overlap_distintivo(a: str, b: str) -> float:
    ta, tb = _tokens_distintivos(a), _tokens_distintivos(b)
    if not ta or not tb: return 0.0
    return len(ta & tb) / max(1, min(len(ta), len(tb)))

def _hay_conflicto_accion(a: str, b: str) -> bool:
    ta, tb = _tokens_distintivos(a, min_len=3), _tokens_distintivos(b, min_len=3)
    for grupo_a, grupo_b in _ACCIONES_OPUESTAS:
        if (ta & grupo_a and tb & grupo_b) or (ta & grupo_b and tb & grupo_a):
            return True
    return False

def _etiquetas_compatibles(a: str, b: str, min_overlap: float = 0.45) -> bool:
    na, nb = string_norm_label(a), string_norm_label(b)
    if not na or not nb: return False
    if _hay_conflicto_accion(na, nb): return False
    if SequenceMatcher(None, na, nb).ratio() >= 0.90: return True
    return _overlap_distintivo(na, nb) >= min_overlap

def _grupos_contenido_compatibles(
    textos_a: list,
    textos_b: list,
    etiqueta_a: str = "",
    etiqueta_b: str = "",
    min_sim: float = 0.88,
    min_overlap: float = 0.20,
) -> bool:
    muestra_a = [safe_str(t) for t in textos_a[:20] if safe_str(t)]
    muestra_b = [safe_str(t) for t in textos_b[:20] if safe_str(t)]
    if not muestra_a or not muestra_b: return False
    texto_a = " ".join(muestra_a)[:2500]
    texto_b = " ".join(muestra_b)[:2500]
    if _hay_conflicto_accion(f"{etiqueta_a} {texto_a}", f"{etiqueta_b} {texto_b}"):
        return False
    overlap = _overlap_distintivo(f"{etiqueta_a} {texto_a}", f"{etiqueta_b} {texto_b}")
    labels_muy_cercanas = _etiquetas_compatibles(etiqueta_a, etiqueta_b, min_overlap=0.55)
    if overlap < min_overlap and not labels_muy_cercanas:
        return False
    embs = get_embeddings_batch([texto_a, texto_b])
    if len(embs) < 2 or embs[0] is None or embs[1] is None:
        return labels_muy_cercanas and overlap >= min_overlap
    sim = cosine_similarity(
        np.array(embs[0]).reshape(1, -1),
        np.array(embs[1]).reshape(1, -1)
    )[0][0]
    return sim >= min_sim

def _validar_estructura_subtema(etiqueta: str) -> bool:
    etiqueta = safe_str(etiqueta)
    if not etiqueta or len(etiqueta.split()) < 2: return False
    if len(etiqueta.split()) > 7: return False
    if _PATRON_TITULAR.match(etiqueta): return False
    if _PATRON_ESTADO.search(etiqueta): return False
    palabras = etiqueta.split()
    if len(palabras) <= 4:
        nexos = {
            "de","del","para","sobre","en","con","por","ante","hacia",
            "entre","sin","al","las","los","una","uno","que","como",
            "y","o","a","e","u",
        }
        tiene_nexo = any(unidecode(p.lower().rstrip(".,;:!?")) in nexos for p in palabras[1:])
        if not tiene_nexo: return False
    return True

def extract_link(cell):
    if hasattr(cell, "hyperlink") and cell.hyperlink:
        return {"value": "Link", "url": cell.hyperlink.target}
    if isinstance(cell.value, str) and "=HYPERLINK" in cell.value:
        m = re.search(r'=HYPERLINK\("([^"]+)"', cell.value)
        if m: return {"value": "Link", "url": m.group(1)}
    return {"value": cell.value, "url": None}

def extract_link_from_cell(cell):
    if cell.hyperlink and cell.hyperlink.target:
        return cell.hyperlink.target
    return None

def convert_html_entities(text):
    text = safe_str(text)
    if not text: return ""
    text = html.unescape(text)
    html_entities = {
        '&#xF3;': 'ó', '&#xE1;': 'á', '&#xE9;': 'é', '&#xED;': 'í',
        '&#xFA;': 'ú', '&#xF1;': 'ñ', '&#xDC;': 'Ü', '&#xFC;': 'ü',
        '&#xC1;': 'Á', '&#xC9;': 'É', '&#xCD;': 'Í', '&#xD3;': 'Ó',
        '&#xDA;': 'Ú', '&#xD1;': 'Ñ', '&#xC7;': 'Ç', '&#xE7;': 'ç',
    }
    for entity, char in html_entities.items():
        text = text.replace(entity, char)

    def replace_hex_entity(match):
        try:
            return chr(int(match.group(1), 16))
        except Exception:
            return match.group(0)

    def replace_decimal_entity(match):
        try:
            return chr(int(match.group(1)))
        except Exception:
            return match.group(0)

    text = re.sub(r'&#x([0-9A-Fa-f]+);', replace_hex_entity, text)
    text = re.sub(r'&#(\d+);', replace_decimal_entity, text)

    for bad, good in {'\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
                      'Â': '', 'â': '', '€': '', '™': ''}.items():
        text = text.replace(bad, good)
    return text

def clean_text(text):
    text = safe_str(text)
    if not text: return ""
    return convert_html_entities(text)

def clean_cuerpo(text):
    text = safe_str(text)
    if not text: return ""
    text = convert_html_entities(text)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


# ======================================
# NORMALIZACIÓN DE TÍTULOS
# ======================================
def normalize_title_for_comparison(title):
    s_title = safe_str(title)
    if not s_title: return ""
    cleaned = re.sub(r"\s+[\|–—-]\s+[^\|–—-]+$", "", s_title).strip()

    if ":" in cleaned:
        parts = cleaned.split(":", 1)
        prefix = parts[0].strip()
        suffix = parts[1].strip()
        if len(suffix) >= 10 and len(prefix.split()) <= 4:
            cleaned = suffix

    cleaned = unidecode(cleaned.lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _prefijo_titulo_significativo(title_norm: str, max_words: int = 10) -> str:
    if not title_norm: return ""
    stop = STOPWORDS_ES | {"dice", "dijo", "tras", "luego", "segun", "según"}
    words = [w for w in title_norm.split() if len(w) >= 3 and w not in stop]
    if len(words) < MIN_PALABRAS_PREF_TITULO:
        words = title_norm.split()
    return " ".join(words[:max_words])


def clean_title_for_output(title):
    s_title = safe_str(title)
    if not s_title: return ""
    return re.sub(r"\s*\|\s*[\w\s]+$", "", s_title).strip()

def corregir_texto(text):
    stext = safe_str(text)
    if not stext: return ""
    stext = re.sub(r"(<br>|\[\.\.\.\]|\s+)", " ", stext).strip()
    m = re.search(r"[A-ZÁÉÍÓÚÑ]", stext)
    if m: stext = stext[m.start():]
    if stext and not stext.endswith("..."): stext = stext.rstrip(".") + "..."
    return stext

def normalizar_tipo_medio(tipo_raw):
    t_str = safe_str(tipo_raw)
    if not t_str: return ""
    t = unidecode(t_str.lower())
    return {
        'online': 'Internet', 'internet': 'Internet',
        'diario': 'Prensa',
        'am': 'Radio', 'fm': 'Radio', 'radio': 'Radio',
        'aire': 'Televisión', 'cable': 'Televisión', 'tv': 'Televisión',
        'television': 'Televisión', 'televisión': 'Televisión',
        'revista': 'Revistas', 'revistas': 'Revistas',
    }.get(t, t_str.title() or "Otro")

def parse_numeric(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (int, float)):
        if isinstance(val, float) and val.is_integer():
            return int(val)
        return val
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    if 'e' in s.lower():
        s = s.replace(',', '.')
    else:
        if ',' in s and '.' in s:
            if s.rfind('.') < s.rfind(','):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            parts = s.split(',')
            if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3 and not s.lower().startswith('0,')):
                s = s.replace(',', '')
            else:
                s = s.replace(',', '.')
        elif '.' in s:
            parts = s.split('.')
            if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3 and not s.lower().startswith('0.')):
                s = s.replace('.', '')
    try:
        f_val = float(s)
        if f_val.is_integer():
            return int(f_val)
        return f_val
    except ValueError:
        return None

def texto_para_embedding(titulo, resumen, max_len=1800):
    t = safe_str(titulo)
    r = safe_str(resumen)
    return f"{t}. {t}. {t}. {r}"[:max_len]

def _normalizar_mencion(texto: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", unidecode(safe_str(texto).lower()))).strip()

def _coincide_nombre_completo(texto: str, nombre: str) -> bool:
    nombre = _normalizar_mencion(nombre)
    if len(nombre) < 3:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(nombre)}(?![a-z0-9])", texto))

def _validar_etiqueta_completa(etiqueta, titulos_grp=None, resumenes_grp=None, marca="", aliases=None, fallback_fn=None):
    etiqueta = safe_str(etiqueta)
    if not etiqueta or etiqueta.lower() in ("sin tema", "varios", "n/a"):
        if fallback_fn: return fallback_fn(titulos_grp or [])
        return "Cobertura informativa general"
    if _frase_esta_completa(etiqueta): return etiqueta
    recortada = _recortar_frase_completa(etiqueta, max_palabras=7)
    if _frase_esta_completa(recortada) and len(recortada.split()) >= 2:
        return capitalizar_etiqueta(recortada)
    if titulos_grp and len(titulos_grp) > 0:
        try:
            prompt = (
                f"La frase '{etiqueta}' está incompleta o es genérica. "
                f"Genera una frase temática COMPLETA en español de 4-6 palabras "
                f"con preposición (de/del/para/sobre/en):\n\n"
                + "\n".join(f"  · {safe_str(t)[:120]}" for t in titulos_grp[:4])
                + "\n\nREGLAS: frase nominal con preposición, terminar en sustantivo/adjetivo, "
                "tildes y ñ correctas, sin marcas ni ciudades.\n"
                'JSON: {"subtema":"..."}'
            )
            resp = call_with_retries(
                openai.ChatCompletion.create,
                model=OPENAI_MODEL_CLASIFICACION,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=80,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            u = resp.get('usage', {}) if isinstance(resp, dict) else getattr(resp, 'usage', {})
            if u:
                st.session_state['tokens_input'] += (u.get('prompt_tokens') if isinstance(u, dict) else getattr(u, 'prompt_tokens', 0)) or 0
                st.session_state['tokens_output'] += (u.get('completion_tokens') if isinstance(u, dict) else getattr(u, 'completion_tokens', 0)) or 0
            raw = json.loads(resp.choices[0].message.content).get("subtema", "")
            if raw:
                cleaned = limpiar_tema_geografico(limpiar_tema(raw), marca, aliases or [])
                if _frase_esta_completa(cleaned) and len(cleaned.split()) >= 2:
                    return capitalizar_etiqueta(cleaned)
        except:
            pass
    if fallback_fn: return fallback_fn(titulos_grp or [])
    return capitalizar_etiqueta(recortada) if recortada and len(recortada.split()) >= 2 else "Cobertura informativa general"

def dedup_labels(etiquetas, umbral=UMBRAL_DEDUP_LABEL):
    unique = list(dict.fromkeys(etiquetas))
    if len(unique) <= 1:
        return etiquetas
    normed = [string_norm_label(u) for u in unique]
    n = len(unique)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    def _es_fusion_segura(s1, s2):
        return _etiquetas_compatibles(s1, s2, min_overlap=0.45)

    for i in range(n):
        if not normed[i]: continue
        for j in range(i + 1, n):
            if not normed[j] or find(i) == find(j): continue
            if SequenceMatcher(None, normed[i], normed[j]).ratio() >= max(umbral, 0.88):
                if _es_fusion_segura(normed[i], normed[j]):
                    union(i, j)

    for i in range(n):
        if not normed[i]: continue
        tokens_i = set(normed[i].split())
        if len(tokens_i) < 2: continue
        for j in range(i + 1, n):
            if not normed[j] or find(i) == find(j): continue
            tokens_j = set(normed[j].split())
            if len(tokens_j) < 2: continue
            interseccion = tokens_i & tokens_j
            menor = min(len(tokens_i), len(tokens_j))
            if menor > 0 and len(interseccion) / menor >= 0.78:
                if _es_fusion_segura(normed[i], normed[j]):
                    union(i, j)

    le = get_embeddings_batch(unique)
    vp = [(i, le[i]) for i in range(n) if le[i] is not None]
    if len(vp) >= 2:
        vi, vv = zip(*vp)
        sm = cosine_similarity(np.array(vv))
        for pi in range(len(vi)):
            for pj in range(pi + 1, len(vi)):
                if sm[pi][pj] >= max(umbral, 0.90):
                    if find(vi[pi]) != find(vi[pj]):
                        if _es_fusion_segura(normed[vi[pi]], normed[vi[pj]]):
                            union(vi[pi], vi[pj])

    freq = Counter(etiquetas)
    grupos = defaultdict(list)
    for i in range(n):
        grupos[find(i)].append(i)
    canon = {}
    for root, members in grupos.items():
        cands = [unique[m] for m in members]
        vc = [c for c in cands if safe_str(c).lower() not in ("sin tema", "varios") and _frase_esta_completa(c)]
        va = [c for c in cands if safe_str(c).lower() not in ("sin tema", "varios")]
        if vc:
            canon[root] = max(vc, key=lambda c: (freq[c], len(c)))
        elif va:
            best = max(va, key=lambda c: (freq[c], len(c)))
            r = _recortar_frase_completa(best)
            canon[root] = r if _frase_esta_completa(r) else best
        else:
            canon[root] = cands[0]
    lm = {unique[i]: canon[find(i)] for i in range(n)}
    return [capitalizar_etiqueta(lm.get(e, e)) for e in etiquetas]

def _fusionar_subtemas_semanticos(subtemas, textos_por_subtema, marca, aliases, umbral=UMBRAL_FUSION_SUBTEMAS):
    unique_subs = list(dict.fromkeys(subtemas))
    if len(unique_subs) <= 1: return subtemas
    repr_texts = []
    for sub in unique_subs:
        txts = textos_por_subtema.get(sub, [])
        palabras = []
        for t in txts[:20]:
            for w in string_norm_label(t).split():
                if len(w) > 3: palabras.append(w)
        top_kw = " ".join(w for w, _ in Counter(palabras).most_common(10))
        repr_texts.append(f"{sub}. {sub}. {sub}. {top_kw}"[:600])
    emb_repr = get_embeddings_batch(repr_texts)
    valid = [(i, emb_repr[i]) for i in range(len(unique_subs)) if emb_repr[i] is not None]
    if len(valid) < 2: return subtemas
    v_idx, v_emb = zip(*valid)
    sim = cosine_similarity(np.array(v_emb))
    n = len(v_idx)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j): continue
            sub_i, sub_j = unique_subs[v_idx[i]], unique_subs[v_idx[j]]
            if sim[i][j] >= max(umbral, 0.88) and _grupos_contenido_compatibles(
                textos_por_subtema.get(sub_i, []),
                textos_por_subtema.get(sub_j, []),
                sub_i,
                sub_j,
                min_sim=max(umbral, 0.88),
                min_overlap=0.22,
            ):
                union(i, j)

    grupos = defaultdict(list)
    for i in range(n): grupos[find(i)].append(v_idx[i])
    freq = Counter(subtemas)
    lm = {}
    for root, members in grupos.items():
        cands = [unique_subs[m] for m in members]
        if len(cands) == 1:
            lm[cands[0]] = cands[0]
            continue
        vc = [c for c in cands if safe_str(c).lower() not in ("sin tema", "varios") and _frase_esta_completa(c)]
        best = max(vc, key=lambda c: (freq.get(c, 0), len(c))) if vc else max(cands, key=lambda c: (freq.get(c, 0), len(c)))
        if len(cands) <= 3:
            unified = _unificar_subtemas_llm(cands, textos_por_subtema, marca, aliases)
            if unified and _frase_esta_completa(unified): best = unified
        for c in cands: lm[c] = capitalizar_etiqueta(best)
    return [lm.get(s, s) for s in subtemas]

def _unificar_subtemas_llm(subtemas_a_unificar, textos_por_subtema, marca, aliases):
    subs_str = "\n".join(f"  · {s}" for s in subtemas_a_unificar)
    all_kw = []
    for sub in subtemas_a_unificar:
        for t in textos_por_subtema.get(sub, [])[:5]:
            for w in string_norm_label(t).split():
                if len(w) > 3: all_kw.append(w)
    kw_str = " · ".join(w for w, _ in Counter(all_kw).most_common(8))
    prompt = (
        f"Estos subtemas son variaciones del MISMO tema. "
        f"Genera UN subtema unificado (4-6 palabras) como frase nominal completa:\n\n"
        f"{subs_str}\n\nKeywords: {kw_str}\n\n"
        "REGLAS: frase coherente con preposición, sin marcas ni ciudades, tildes y ñ correctas.\n"
        'JSON: {"subtema":"..."}'
    )
    try:
        resp = call_with_retries(
            openai.ChatCompletion.create,
            model=OPENAI_MODEL_CLASIFICACION,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.05,
            response_format={"type": "json_object"}
        )
        u = resp.get('usage', {}) if isinstance(resp, dict) else getattr(resp, 'usage', {})
        if u:
            st.session_state['tokens_input'] += (u.get('prompt_tokens') if isinstance(u, dict) else getattr(u, 'prompt_tokens', 0)) or 0
            st.session_state['tokens_output'] += (u.get('completion_tokens') if isinstance(u, dict) else getattr(u, 'completion_tokens', 0)) or 0
        raw = json.loads(resp.choices[0].message.content).get("subtema", "")
        if raw: return limpiar_tema_geografico(limpiar_tema(raw), marca, aliases)
    except:
        pass
    return None

def get_embeddings_batch(textos, batch_size=100):
    if not textos: return []
    # Usar safe_str para protegerse de floats nan
    textos_str = [safe_str(t) for t in textos]
    cache = get_embedding_cache()
    resultados, missing = cache.get_many(textos_str)
    if not missing: return resultados
    mt = [textos_str[i][:2000] for i in missing]
    for i in range(0, len(mt), batch_size):
        batch = mt[i:i + batch_size]
        bidx = missing[i:i + batch_size]
        try:
            resp = call_with_retries(openai.Embedding.create, input=batch, model=OPENAI_MODEL_EMBEDDING)
            u = resp.get('usage', {}) if isinstance(resp, dict) else getattr(resp, 'usage', {})
            if u:
                st.session_state['tokens_embedding'] += (u.get('total_tokens') if isinstance(u, dict) else getattr(u, 'total_tokens', 0)) or 0
            for j, d in enumerate(resp["data"]):
                oi = bidx[j]
                emb = d["embedding"]
                resultados[oi] = emb
                cache.put(textos_str[oi], emb)
        except Exception:
            for j, t in enumerate(batch):
                oi = bidx[j]
                try:
                    r = openai.Embedding.create(input=[t], model=OPENAI_MODEL_EMBEDDING)
                    emb = r["data"][0]["embedding"]
                    resultados[oi] = emb
                    cache.put(textos_str[oi], emb)
                except Exception:
                    pass
    return resultados

class DSU:
    def __init__(self, n):
        self.p = list(range(n))
        self.rank = [0] * n

    def find(self, i):
        path = []
        while self.p[i] != i:
            path.append(i)
            i = self.p[i]
        for node in path: self.p[node] = i
        return i

    def union(self, i, j):
        ri, rj = self.find(i), self.find(j)
        if ri == rj: return
        if self.rank[ri] < self.rank[rj]: ri, rj = rj, ri
        self.p[rj] = ri
        if self.rank[ri] == self.rank[rj]: self.rank[ri] += 1

    def grupos(self, n):
        c = defaultdict(list)
        for i in range(n): c[self.find(i)].append(i)
        return dict(c)

def agrupar_textos_similares(textos, umbral):
    if not textos: return {}
    embs = get_embeddings_batch(textos)
    valid = [(i, e) for i, e in enumerate(embs) if e is not None]
    if len(valid) < 2: return {}
    idxs, M = zip(*valid)
    labels = AgglomerativeClustering(
        n_clusters=None, distance_threshold=1 - umbral, metric="cosine", linkage="average"
    ).fit(np.array(M)).labels_
    g = defaultdict(list)
    for k, lbl in enumerate(labels): g[lbl].append(idxs[k])
    return dict(enumerate(g.values()))

def agrupar_por_titulo_similar(titulos):
    gid, grupos, used = 0, {}, set()
    norm = [normalize_title_for_comparison(t) for t in titulos]
    for i in range(len(norm)):
        if i in used or not norm[i]: continue
        grp = [i]
        used.add(i)
        for j in range(i + 1, len(norm)):
            if j in used or not norm[j]: continue
            if SequenceMatcher(None, norm[i], norm[j]).ratio() >= SIMILARITY_THRESHOLD_TITULOS:
                grp.append(j)
                used.add(j)
        if len(grp) >= 2:
            grupos[gid] = list(set(grp))
            gid += 1
    return grupos

def seleccionar_representante(indices, textos):
    embs = get_embeddings_batch([textos[i] for i in indices])
    validos = [(indices[k], e) for k, e in enumerate(embs) if e is not None]
    if not validos: return indices[0], textos[indices[0]]
    idxs, M = zip(*validos)
    centro = np.mean(M, axis=0, keepdims=True)
    best = int(np.argmax(cosine_similarity(np.array(M), centro)))
    return idxs[best], textos[idxs[best]]


# ==========================================================================================
# MOTOR DE CONSISTENCIA ULTRA-PRECISA (Título y/o CuerpoEs)
# ==========================================================================================
def _normalizar_cuerpo_para_comparacion(texto, max_chars=700):
    t_str = safe_str(texto)
    if not t_str: return ""
    t = unidecode(t_str.lower())
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'https?://\S+', ' ', t)
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:max_chars]


def _sim_texto(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _son_misma_noticia_signals(
    tit_i, tit_j, cue_i, cue_j,
    emb_t_i=None, emb_t_j=None,
    emb_c_i=None, emb_c_j=None,
    pref_i="", pref_j="",
):
    if tit_i and tit_j and _hay_conflicto_accion(tit_i, tit_j):
        return False
    if cue_i and cue_j and len(cue_i) >= MIN_LEN_CUERPO_CONSIST and len(cue_j) >= MIN_LEN_CUERPO_CONSIST:
        if _hay_conflicto_accion(cue_i, cue_j):
            return False

    # 1) Título literal
    sim_tit = _sim_texto(tit_i, tit_j) if tit_i and tit_j else 0.0
    if sim_tit >= UMBRAL_SIM_TITULO_CONSIST:
        return True

    # 2) Prefijo de título
    if pref_i and pref_j and len(pref_i.split()) >= MIN_PALABRAS_PREF_TITULO:
        sim_pref = _sim_texto(pref_i, pref_j)
        if sim_pref >= UMBRAL_PREF_TITULO_CONSIST:
            ov = _overlap_distintivo(tit_i, tit_j)
            if ov >= 0.35 or sim_tit >= 0.82:
                return True
            if sim_pref >= 0.97 and len(pref_i.split()) >= 8:
                return True

    # 3) Cuerpo literal
    if cue_i and cue_j and len(cue_i) >= MIN_LEN_CUERPO_CONSIST and len(cue_j) >= MIN_LEN_CUERPO_CONSIST:
        sim_cue = _sim_texto(cue_i, cue_j)
        if sim_cue >= UMBRAL_SIM_CUERPO_CONSIST:
            return True
        if sim_cue >= 0.84 and sim_tit >= 0.75 and _overlap_distintivo(tit_i, tit_j) >= 0.30:
            return True

    # 4) Embedding solo título
    if emb_t_i is not None and emb_t_j is not None and tit_i and tit_j:
        sim_et = cosine_similarity(
            np.array(emb_t_i).reshape(1, -1),
            np.array(emb_t_j).reshape(1, -1)
        )[0][0]
        if sim_et >= UMBRAL_EMB_TITULO_CONSIST and _overlap_distintivo(tit_i, tit_j) >= 0.25:
            return True
        if sim_et >= 0.92 and pref_i and pref_j and _sim_texto(pref_i, pref_j) >= 0.88:
            return True

    # 5) Embedding solo cuerpo
    if emb_c_i is not None and emb_c_j is not None and cue_i and cue_j:
        if len(cue_i) >= MIN_LEN_CUERPO_CONSIST and len(cue_j) >= MIN_LEN_CUERPO_CONSIST:
            sim_ec = cosine_similarity(
                np.array(emb_c_i).reshape(1, -1),
                np.array(emb_c_j).reshape(1, -1)
            )[0][0]
            if sim_ec >= UMBRAL_EMB_CUERPO_CONSIST and _overlap_distintivo(cue_i, cue_j) >= 0.22:
                return True
            if sim_ec >= 0.90 and sim_tit >= 0.70:
                return True

    return False


def construir_grupos_consistencia(titulos, resumenes, pbar=None, ps=0.0):
    n = len(titulos)
    dsu = DSU(n)
    if n < 2:
        return dsu.grupos(n)

    titulos_safe = [safe_str(t) for t in titulos]
    resumenes_safe = [safe_str(r) for r in resumenes]

    titulos_norm = [normalize_title_for_comparison(t) for t in titulos_safe]
    cuerpos_norm = [_normalizar_cuerpo_para_comparacion(r) for r in resumenes_safe]
    prefijos = [_prefijo_titulo_significativo(t) for t in titulos_norm]

    stop_local = STOPWORDS_ES | {"dice", "dijo", "informo", "segun", "segun", "tras", "luego"}

    if pbar: pbar.progress(ps, "Consistencia · títulos literales / prefijos...")
    bt = defaultdict(list)
    bp = defaultdict(list)
    for i, tn in enumerate(titulos_norm):
        if len(tn) >= 10:
            bt[tn[:50]].append(i)
        pref = prefijos[i]
        if pref and len(pref.split()) >= 4:
            bp[" ".join(pref.split()[:5])].append(i)

    for bucket in list(bt.values()) + list(bp.values()):
        if len(bucket) > 80:
            continue
        for a in range(len(bucket)):
            for b in range(a + 1, len(bucket)):
                i, j = bucket[a], bucket[b]
                if dsu.find(i) == dsu.find(j):
                    continue
                if _son_misma_noticia_signals(
                    titulos_norm[i], titulos_norm[j],
                    cuerpos_norm[i], cuerpos_norm[j],
                    pref_i=prefijos[i], pref_j=prefijos[j],
                ):
                    dsu.union(i, j)

    if pbar: pbar.progress(min(ps + 0.01, 1.0), "Consistencia · cuerpos literales...")
    bc = defaultdict(list)
    for i, cn in enumerate(cuerpos_norm):
        if len(cn) >= MIN_LEN_CUERPO_CONSIST:
            bc[cn[:70]].append(i)
    for idxs in bc.values():
        if len(idxs) > 80:
            continue
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                if dsu.find(i) == dsu.find(j):
                    continue
                if _son_misma_noticia_signals(
                    titulos_norm[i], titulos_norm[j],
                    cuerpos_norm[i], cuerpos_norm[j],
                    pref_i=prefijos[i], pref_j=prefijos[j],
                ):
                    dsu.union(i, j)

    if pbar: pbar.progress(min(ps + 0.02, 1.0), "Consistencia · embeddings de título...")
    emb_titulos = get_embeddings_batch(titulos_safe)
    palabras_idx_t = defaultdict(list)
    for i, tn in enumerate(titulos_norm):
        vistos = set()
        for w in tn.split():
            if len(w) >= 5 and w not in stop_local and w not in vistos:
                palabras_idx_t[w].append(i)
                vistos.add(w)
    candidatos_t = set()
    for idxs in palabras_idx_t.values():
        if 2 <= len(idxs) <= 50:
            for a in range(len(idxs)):
                for b in range(a + 1, len(idxs)):
                    i, j = idxs[a], idxs[b]
                    if dsu.find(i) != dsu.find(j):
                        candidatos_t.add((min(i, j), max(i, j)))
    for i, j in candidatos_t:
        if dsu.find(i) == dsu.find(j):
            continue
        if _son_misma_noticia_signals(
            titulos_norm[i], titulos_norm[j],
            cuerpos_norm[i], cuerpos_norm[j],
            emb_t_i=emb_titulos[i], emb_t_j=emb_titulos[j],
            pref_i=prefijos[i], pref_j=prefijos[j],
        ):
            dsu.union(i, j)

    if pbar: pbar.progress(min(ps + 0.03, 1.0), "Consistencia · embeddings de cuerpo...")
    idx_cuerpo_validos = [i for i, c in enumerate(cuerpos_norm) if len(c) >= MIN_LEN_CUERPO_CONSIST]
    emb_cuerpos = {}
    if len(idx_cuerpo_validos) >= 2:
        textos_cuerpo = [resumenes_safe[i][:1200] for i in idx_cuerpo_validos]
        emb_cuerpos_sub = get_embeddings_batch(textos_cuerpo)
        emb_cuerpos = {idx_cuerpo_validos[k]: emb_cuerpos_sub[k] for k in range(len(idx_cuerpo_validos))}
        palabras_idx_c = defaultdict(list)
        for i in idx_cuerpo_validos:
            vistos = set()
            for w in cuerpos_norm[i].split():
                if len(w) >= 6 and w not in stop_local and w not in vistos:
                    palabras_idx_c[w].append(i)
                    vistos.add(w)
        candidatos_c = set()
        for idxs in palabras_idx_c.values():
            if 2 <= len(idxs) <= 50:
                for a in range(len(idxs)):
                    for b in range(a + 1, len(idxs)):
                        i, j = idxs[a], idxs[b]
                        if dsu.find(i) != dsu.find(j):
                            candidatos_c.add((min(i, j), max(i, j)))
        for i, j in candidatos_c:
            if dsu.find(i) == dsu.find(j):
                continue
            if _son_misma_noticia_signals(
                titulos_norm[i], titulos_norm[j],
                cuerpos_norm[i], cuerpos_norm[j],
                emb_t_i=emb_titulos[i], emb_t_j=emb_titulos[j],
                emb_c_i=emb_cuerpos.get(i), emb_c_j=emb_cuerpos.get(j),
                pref_i=prefijos[i], pref_j=prefijos[j],
            ):
                dsu.union(i, j)

    if pbar: pbar.progress(min(ps + 0.04, 1.0), "Grupos de consistencia listos")
    return dsu.grupos(n)


def _votar_valor_mayoritario(valores, embeddings=None, textos=None):
    limpios = [v for v in valores if safe_str(v) and safe_str(v).lower() not in ("n/a", "-", "nan", "none")]
    if not limpios:
        return None
    conteo = Counter(limpios)
    max_freq = max(conteo.values())
    empatados = [v for v, c in conteo.items() if c == max_freq]
    if len(empatados) == 1:
        return empatados[0]
    if embeddings is not None:
        vecs = [e for e in embeddings if e is not None]
        if len(vecs) >= 2:
            centro = np.mean(np.array(vecs), axis=0, keepdims=True)
            mejor_val, mejor_sim = empatados[0], -1.0
            for idx, val in enumerate(valores):
                if val in empatados and idx < len(embeddings) and embeddings[idx] is not None:
                    sim = cosine_similarity(np.array(embeddings[idx]).reshape(1, -1), centro)[0][0]
                    if sim > mejor_sim:
                        mejor_sim = sim
                        mejor_val = val
            return mejor_val
    return max(empatados, key=lambda x: (len(safe_str(x).split()), len(safe_str(x))))


def aplicar_consistencia_intergrupo(df, km_tono, km_tema, km_subtema, km_titulo, km_resumen, pbar=None):
    n = len(df)
    if n < 2:
        return df

    df = df.reset_index(drop=True)
    titulos = [safe_str(t) for t in (df[km_titulo].tolist() if km_titulo in df.columns else [""] * n)]
    resumenes = [safe_str(r) for r in (df[km_resumen].tolist() if km_resumen in df.columns else [""] * n)]

    if pbar: pbar.progress(0.0, "Detectando republicaciones / coberturas casi idénticas...")
    grupos = construir_grupos_consistencia(titulos, resumenes, pbar, ps=0.0)

    emb_combinado = get_embeddings_batch([texto_para_embedding(titulos[i], resumenes[i]) for i in range(n)])

    tonos = df[km_tono].tolist() if km_tono in df.columns else [None] * n
    temas = df[km_tema].tolist() if km_tema in df.columns else [None] * n
    subtemas = df[km_subtema].tolist() if km_subtema in df.columns else [None] * n

    grupos_multiples = {gid: idxs for gid, idxs in grupos.items() if len(idxs) >= 2}
    total_g = len(grupos_multiples)
    unificados = 0
    for k, (gid, idxs) in enumerate(grupos_multiples.items()):
        if pbar and total_g:
            pbar.progress(min(0.05 + 0.85 * (k / total_g), 0.90), f"Unificando republicaciones {k + 1}/{total_g}...")

        embs_grupo = [emb_combinado[i] for i in idxs]

        if km_tono in df.columns:
            tono_final = _votar_valor_mayoritario([tonos[i] for i in idxs], embs_grupo)
            if tono_final is not None:
                for i in idxs: tonos[i] = tono_final

        if km_subtema in df.columns:
            subtema_final = _votar_valor_mayoritario([subtemas[i] for i in idxs], embs_grupo)
            if subtema_final is not None:
                for i in idxs: subtemas[i] = subtema_final

        if km_tema in df.columns:
            tema_final = _votar_valor_mayoritario([temas[i] for i in idxs], embs_grupo)
            if tema_final is not None:
                for i in idxs: temas[i] = tema_final

        unificados += len(idxs)

    if km_tono in df.columns: df[km_tono] = tonos
    if km_tema in df.columns: df[km_tema] = temas
    if km_subtema in df.columns: df[km_subtema] = subtemas

    if pbar: pbar.progress(0.92, "Republicaciones unificadas")
    if total_g:
        st.caption(
            f"🔗 Consistencia republicaciones: **{total_g}** grupos "
            f"(**{unificados}** noticias) → Tono/Tema/Subtema unificados."
        )
    return df


# ==========================================================================================
# UNIFICACIÓN POST-ETIQUETA: subtemas levemente distintos
# ==========================================================================================
def _repr_grupo_para_fusion(etiqueta, textos, titulos, max_n=25):
    muestra_t = [safe_str(t) for t in titulos[:12] if safe_str(t)]
    muestra_x = [safe_str(t) for t in textos[:max_n] if safe_str(t)]
    palabras = []
    for t in muestra_t + muestra_x[:10]:
        for w in string_norm_label(t).split():
            if len(w) > 3:
                palabras.append(w)
    kw = " ".join(w for w, _ in Counter(palabras).most_common(12))
    return f"{etiqueta}. {etiqueta}. {' | '.join(muestra_t[:6])}. {kw}"[:900]


def unificar_subtemas_similares_post(
    df,
    km_subtema,
    km_tema,
    km_tono,
    km_titulo,
    km_resumen,
    marca="",
    aliases=None,
    pbar=None,
):
    n = len(df)
    if n < 2 or km_subtema not in df.columns:
        return df

    df = df.reset_index(drop=True)
    titulos = [safe_str(t) for t in (df[km_titulo].tolist() if km_titulo in df.columns else [""] * n)]
    resumenes = [safe_str(r) for r in (df[km_resumen].tolist() if km_resumen in df.columns else [""] * n)]
    subtemas = [capitalizar_etiqueta(s) if pd.notna(s) else "Sin tema" for s in df[km_subtema].tolist()]
    temas = df[km_tema].tolist() if km_tema in df.columns else ["Sin tema"] * n
    tonos = df[km_tono].tolist() if km_tono in df.columns else [None] * n

    textos_emb = [texto_para_embedding(titulos[i], resumenes[i]) for i in range(n)]
    if pbar: pbar.progress(0.05, "Post-unificación · embeddings de contenido...")
    emb_txt = get_embeddings_batch(textos_emb)

    # Near-duplicates de CONTENIDO
    if pbar: pbar.progress(0.15, "Post-unificación · near-duplicates de contenido...")
    dsu = DSU(n)
    stop_local = STOPWORDS_ES | {"dice", "dijo", "informo", "segun"}
    idx_kw = defaultdict(list)
    for i, t in enumerate(titulos):
        tn = normalize_title_for_comparison(t)
        vistos = set()
        for w in tn.split():
            if len(w) >= 5 and w not in stop_local and w not in vistos:
                idx_kw[w].append(i)
                vistos.add(w)
        sn = string_norm_label(subtemas[i])
        for w in sn.split():
            if len(w) >= 5:
                idx_kw[f"sub::{w}"].append(i)

    candidatos = set()
    for idxs in idx_kw.values():
        if 2 <= len(idxs) <= 40:
            for a in range(len(idxs)):
                for b in range(a + 1, len(idxs)):
                    i, j = idxs[a], idxs[b]
                    candidatos.add((min(i, j), max(i, j)))

    for i, j in candidatos:
        if dsu.find(i) == dsu.find(j):
            continue
        if emb_txt[i] is None or emb_txt[j] is None:
            continue
        if _hay_conflicto_accion(textos_emb[i], textos_emb[j]):
            continue
        sim = cosine_similarity(
            np.array(emb_txt[i]).reshape(1, -1),
            np.array(emb_txt[j]).reshape(1, -1)
        )[0][0]
        if sim < UMBRAL_NEAR_DUP_CONTENT:
            continue
        ov = _overlap_distintivo(textos_emb[i], textos_emb[j])
        labels_ok = _etiquetas_compatibles(subtemas[i], subtemas[j], min_overlap=0.40)
        tit_sim = _sim_texto(normalize_title_for_comparison(titulos[i]), normalize_title_for_comparison(titulos[j]))
        if ov >= 0.30 or labels_ok or tit_sim >= 0.88 or sim >= 0.96:
            dsu.union(i, j)

    for idxs in dsu.grupos(n).values():
        if len(idxs) < 2:
            continue
        embs_g = [emb_txt[i] for i in idxs]
        sub_final = _votar_valor_mayoritario([subtemas[i] for i in idxs], embs_g)
        tema_final = _votar_valor_mayoritario([temas[i] for i in idxs], embs_g) if km_tema in df.columns else None
        tono_final = _votar_valor_mayoritario([tonos[i] for i in idxs], embs_g) if km_tono in df.columns else None
        for i in idxs:
            if sub_final:
                subtemas[i] = capitalizar_etiqueta(sub_final)
            if tema_final is not None:
                temas[i] = tema_final
            if tono_final is not None:
                tonos[i] = tono_final

    # Fusión de ETIQUETAS de subtema similares con contenido compatible
    if pbar: pbar.progress(0.45, "Post-unificación · fusión de subtemas afines...")
    textos_por_sub = defaultdict(list)
    titulos_por_sub = defaultdict(list)
    idxs_por_sub = defaultdict(list)
    for i, s in enumerate(subtemas):
        textos_por_sub[s].append(textos_emb[i])
        titulos_por_sub[s].append(titulos[i])
        idxs_por_sub[s].append(i)

    unique_subs = list(idxs_por_sub.keys())
    if len(unique_subs) >= 2:
        reprs = [
            _repr_grupo_para_fusion(s, textos_por_sub[s], titulos_por_sub[s])
            for s in unique_subs
        ]
        emb_repr = get_embeddings_batch(reprs)
        emb_lab = get_embeddings_batch(unique_subs)

        m = len(unique_subs)
        parent = list(range(m))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        valid = [(i, emb_repr[i]) for i in range(m) if emb_repr[i] is not None]
        if len(valid) >= 2:
            vi, vv = zip(*valid)
            sm = cosine_similarity(np.array(vv))
            pos = {vi[k]: k for k in range(len(vi))}
            for a in range(m):
                for b in range(a + 1, m):
                    if find(a) == find(b):
                        continue
                    sa, sb = unique_subs[a], unique_subs[b]
                    if _hay_conflicto_accion(sa, sb):
                        continue

                    na, nb = string_norm_label(sa), string_norm_label(sb)
                    sim_txt = SequenceMatcher(None, na, nb).ratio() if na and nb else 0.0
                    sim_lab = 0.0
                    if emb_lab[a] is not None and emb_lab[b] is not None:
                        sim_lab = cosine_similarity(
                            np.array(emb_lab[a]).reshape(1, -1),
                            np.array(emb_lab[b]).reshape(1, -1)
                        )[0][0]
                    sim_repr = 0.0
                    if a in pos and b in pos:
                        sim_repr = sm[pos[a]][pos[b]]

                    etiquetas_cercanas = (
                        sim_txt >= UMBRAL_FUSION_ETIQUETA_POST
                        or sim_lab >= UMBRAL_FUSION_ETIQUETA_POST
                        or (sim_txt >= 0.82 and sim_lab >= 0.88)
                        or _etiquetas_compatibles(sa, sb, min_overlap=0.55)
                    )
                    contenido_cercano = sim_repr >= UMBRAL_FUSION_CONTENIDO_POST

                    if not (etiquetas_cercanas and contenido_cercano):
                        if not (sim_txt >= 0.94 or sim_lab >= 0.95):
                            continue
                        if sim_repr < 0.88:
                            continue

                    if not _grupos_contenido_compatibles(
                        textos_por_sub[sa],
                        textos_por_sub[sb],
                        sa,
                        sb,
                        min_sim=max(UMBRAL_FUSION_CONTENIDO_POST - 0.02, 0.88),
                        min_overlap=UMBRAL_OVERLAP_POST,
                    ):
                        continue
                    union(a, b)

        freq = Counter(subtemas)
        grupos_lab = defaultdict(list)
        for i in range(m):
            grupos_lab[find(i)].append(i)
        mapa = {}
        for members in grupos_lab.values():
            cands = [unique_subs[i] for i in members]
            if len(cands) == 1:
                mapa[cands[0]] = cands[0]
                continue
            vc = [c for c in cands if safe_str(c).lower() not in ("sin tema", "varios") and _frase_esta_completa(c)]
            best = max(vc or cands, key=lambda c: (freq.get(c, 0), len(c.split()), len(c)))
            if 2 <= len(cands) <= 4:
                textos_map = {c: textos_por_sub.get(c, []) for c in cands}
                unified = _unificar_subtemas_llm(cands, textos_map, marca, aliases or [])
                if unified and _frase_esta_completa(unified) and _validar_estructura_subtema(unified):
                    best = unified
            best = capitalizar_etiqueta(best)
            for c in cands:
                mapa[c] = best

        subtemas = [mapa.get(s, s) for s in subtemas]

    if pbar: pbar.progress(0.75, "Post-unificación · dedup final y temas...")
    subtemas = dedup_labels(subtemas, max(UMBRAL_DEDUP_LABEL, 0.86))
    subtemas = [capitalizar_etiqueta(s) for s in subtemas]

    if km_tema in df.columns:
        sub_to_temas = defaultdict(list)
        for s, t in zip(subtemas, temas):
            if t and safe_str(t) and safe_str(t).lower() not in ("n/a", "-", "nan"):
                sub_to_temas[s].append(t)
        sub_to_best_tema = {}
        for s, tlist in sub_to_temas.items():
            sub_to_best_tema[s] = Counter(tlist).most_common(1)[0][0]
        temas = [sub_to_best_tema.get(s, t) for s, t in zip(subtemas, temas)]

    if pbar: pbar.progress(0.88, "Post-unificación · refuerzo consistencia...")
    grupos2 = construir_grupos_consistencia(titulos, resumenes, pbar=None, ps=0.0)
    for idxs in grupos2.values():
        if len(idxs) < 2:
            continue
        embs_g = [emb_txt[i] for i in idxs]
        sf = _votar_valor_mayoritario([subtemas[i] for i in idxs], embs_g)
        tf = _votar_valor_mayoritario([temas[i] for i in idxs], embs_g) if km_tema in df.columns else None
        nf = _votar_valor_mayoritario([tonos[i] for i in idxs], embs_g) if km_tono in df.columns else None
        for i in idxs:
            if sf: subtemas[i] = capitalizar_etiqueta(sf)
            if tf is not None: temas[i] = tf
            if nf is not None: tonos[i] = nf

    if km_tema in df.columns:
        sub_to_temas = defaultdict(list)
        for s, t in zip(subtemas, temas):
            if t and safe_str(t) and safe_str(t).lower() not in ("n/a", "-", "nan"):
                sub_to_temas[s].append(t)
        sub_to_best_tema = {s: Counter(tlist).most_common(1)[0][0] for s, tlist in sub_to_temas.items() if tlist}
        temas = [sub_to_best_tema.get(s, t) for s, t in zip(subtemas, temas)]

    df[km_subtema] = subtemas
    if km_tema in df.columns:
        df[km_tema] = temas
    if km_tono in df.columns:
        df[km_tono] = tonos

    n_subs = len(set(subtemas))
    n_temas = len(set(safe_str(t) for t in temas))
    if pbar: pbar.progress(1.0, f"Post-unificación lista · {n_subs} subtemas / {n_temas} temas")
    st.caption(f"🎯 Post-unificación: **{n_subs}** subtemas · **{n_temas}** temas.")
    return df


# ======================================
# TONO (Sistema Reputacional)
# ======================================
class ClasificadorTono:
    def __init__(self, marca, aliases):
        self.marca = safe_str(marca)
        self.aliases = [safe_str(a) for a in (aliases or []) if safe_str(a)]
        self._all_names = [self.marca] + self.aliases

    def _menciona_marca(self, texto):
        t = _normalizar_mencion(texto)
        return any(_coincide_nombre_completo(t, nombre) for nombre in self._all_names)

    async def _clasificar_llm(self, texto, sem):
        texto = safe_str(texto)
        async with sem:
            if not self._menciona_marca(texto):
                return {"tono": "Neutro"}

            aliases_str = f" (también conocida como: {', '.join(self.aliases)})" if self.aliases else ""
            prompt = (
                f"Eres un experto analista en Relaciones Públicas y Gestión de Reputación. "
                f"Tu tarea es evaluar el impacto reputacional DIRECTO de la siguiente noticia sobre la marca '{self.marca}'{aliases_str}.\n\n"
                f"TEXTO A EVALUAR:\n{texto[:1600]}\n\n"
                f"REGLAS DE CLASIFICACIÓN ESTRICTAS:\n"
                f"🔴 NEGATIVO: un hecho perjudica, cuestiona o expone directamente a '{self.marca}'.\n"
                f"🟢 POSITIVO: el hecho acredita directamente un logro, mejora o aporte verificable de '{self.marca}'.\n"
                f"⚪ NEUTRO: La marca se menciona SIN impacto a su imagen.\n\n"
                f'Responde ÚNICAMENTE con JSON en este formato: {{"tono": "Positivo|Negativo|Neutro"}}'
            )

            try:
                resp = await acall_with_retries(
                    openai.ChatCompletion.acreate,
                    model=OPENAI_MODEL_CLASIFICACION,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=40,
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )

                u = resp.get('usage', {}) if isinstance(resp, dict) else getattr(resp, 'usage', {})
                if u:
                    st.session_state['tokens_input'] += (u.get('prompt_tokens') if isinstance(u, dict) else getattr(u, 'prompt_tokens', 0)) or 0
                    st.session_state['tokens_output'] += (u.get('completion_tokens') if isinstance(u, dict) else getattr(u, 'completion_tokens', 0)) or 0

                resultado = json.loads(resp.choices[0].message.content)
                tono = safe_str(resultado.get("tono", "Neutro")).title()

                return {"tono": tono if tono in ("Positivo", "Negativo", "Neutro") else "Neutro"}
            except Exception:
                return {"tono": "Neutro"}

    async def procesar_lote_async(self, textos, pbar, resumenes, titulos):
        n = len(textos)
        txts = [safe_str(t) for t in textos.tolist()]
        tit_list = [safe_str(t) for t in titulos.tolist()]
        res_list = [safe_str(r) for r in resumenes.tolist()]
        
        pbar.progress(0.05, "Agrupando noticias para análisis de tono...")

        txts_emb = [texto_para_embedding(tit_list[i], res_list[i]) for i in range(n)]
        dsu = DSU(n)

        embs = get_embeddings_batch(txts_emb)

        candidatos = agrupar_textos_similares(txts_emb, SIMILARITY_THRESHOLD_TONO)
        candidatos.update({len(candidatos) + k: v for k, v in agrupar_por_titulo_similar(tit_list).items()})
        for idxs in candidatos.values():
            for pos, i in enumerate(idxs):
                for j in idxs[pos + 1:]:
                    ti, tj = normalize_title_for_comparison(tit_list[i]), normalize_title_for_comparison(tit_list[j])
                    titulo_casi_igual = SequenceMatcher(None, ti, tj).ratio() >= 0.94
                    pref_i, pref_j = _prefijo_titulo_significativo(ti), _prefijo_titulo_significativo(tj)
                    pref_casi_igual = pref_i and pref_j and SequenceMatcher(None, pref_i, pref_j).ratio() >= 0.95
                    contenido_casi_igual = (
                        embs[i] is not None and embs[j] is not None
                        and cosine_similarity(np.array(embs[i]).reshape(1, -1), np.array(embs[j]).reshape(1, -1))[0][0] >= SIMILARITY_THRESHOLD_TONO
                        and _overlap_distintivo(txts_emb[i], txts_emb[j]) >= 0.40
                    )
                    if (titulo_casi_igual or pref_casi_igual or contenido_casi_igual) and not _hay_conflicto_accion(txts_emb[i], txts_emb[j]):
                        dsu.union(i, j)

        pbar.progress(0.08, "Tono · detectando republicaciones...")
        grupos_cons = construir_grupos_consistencia(tit_list, res_list, pbar=None)
        for idxs in grupos_cons.values():
            if len(idxs) < 2:
                continue
            for k in range(1, len(idxs)):
                dsu.union(idxs[0], idxs[k])

        grupos = dsu.grupos(n)
        reps = {cid: seleccionar_representante(idxs, txts)[1] for cid, idxs in grupos.items()}

        sem = asyncio.Semaphore(CONCURRENT_REQUESTS)
        cids = list(reps.keys())

        async def _clasificar_con_cid(cid):
            return cid, await self._clasificar_llm(reps[cid], sem)

        tasks = [_clasificar_con_cid(c) for c in cids]
        rpg = {}

        for i, f in enumerate(asyncio.as_completed(tasks)):
            cid, r = await f
            rpg[cid] = r
            pbar.progress(0.1 + 0.85 * (i + 1) / max(len(tasks), 1), f"Evaluando Reputación {i + 1}/{len(tasks)}")

        final = [None] * n

        for cid, idxs in grupos.items():
            r = rpg.get(cid, {"tono": "Neutro"})
            for i in idxs:
                final[i] = r

        pbar.progress(1.0, "Análisis de Tono completado")
        return final

def analizar_tono_con_pkl(textos, pkl_file):
    try:
        pipeline = joblib.load(pkl_file)
        TM = {1: "Positivo", "1": "Positivo", 0: "Neutro", "0": "Neutro", -1: "Negativo", "-1": "Negativo"}
        return [{"tono": TM.get(p, safe_str(p).title())} for p in pipeline.predict(textos)]
    except Exception as e:
        st.error(f"Error pkl: {e}")
        return None

def analizar_temas_con_pkl(textos, pkl_file):
    try:
        pipeline = joblib.load(pkl_file)
        predicciones = pipeline.predict(textos)
        return [safe_str(p) for p in predicciones]
    except Exception as e:
        st.error(f"Error pkl temas: {e}")
        return None

# ======================================
# SUBTEMAS
# ======================================
class ClasificadorSubtema:
    def __init__(self, marca, aliases):
        self.marca = marca
        self.aliases = aliases or []
        self._cache = {}
        self._umbrales: dict = {}

    def _paso1(self, titulos, resumenes, dsu):
        def nt(t, n):
            return ' '.join(re.sub(r'[^a-z0-9\s]', '', unidecode(safe_str(t).lower())).split()[:n])
        bt, br = defaultdict(list), defaultdict(list)
        for i, (ti, re_) in enumerate(zip(titulos, resumenes)):
            a, b = nt(ti, 40), nt(re_, 15)
            if a: bt[hashlib.md5(a.encode()).hexdigest()].append(i)
            b = nt(re_, 120)
            if len(b.split()) >= 25: br[hashlib.md5(b.encode()).hexdigest()].append(i)
        for bk in (bt, br):
            for idxs in bk.values():
                for j in idxs[1:]: dsu.union(idxs[0], j)

    def _paso2(self, titulos, dsu):
        norm = [normalize_title_for_comparison(t) for t in titulos]
        prefs = [_prefijo_titulo_significativo(t) for t in norm]
        n = len(norm)
        for i in range(n):
            if not norm[i]: continue
            for j in range(i + 1, n):
                if not norm[j] or dsu.find(i) == dsu.find(j): continue
                ratio = SequenceMatcher(None, norm[i], norm[j]).ratio()
                pref_ratio = SequenceMatcher(None, prefs[i], prefs[j]).ratio() if prefs[i] and prefs[j] else 0.0
                comparte_asunto = _overlap_distintivo(norm[i], norm[j]) >= 0.38
                if ((ratio >= SIMILARITY_THRESHOLD_TITULOS and comparte_asunto)
                        or (pref_ratio >= 0.95 and comparte_asunto and len(prefs[i].split()) >= MIN_PALABRAS_PREF_TITULO)
                    ) and not _hay_conflicto_accion(norm[i], norm[j]):
                    dsu.union(i, j)

    def _paso2b_keywords(self, titulos, dsu, ae):
        sim_min = self._umbrales.get('sim_minima_keywords', SIM_MINIMA_KEYWORDS_RARAS)
        stop = STOPWORDS_ES
        titulo_words = []
        for t in titulos:
            ws = set()
            for w in re.findall(r'[a-z]+', unidecode(safe_str(t).lower())):
                if len(w) >= 5 and w not in stop: ws.add(w)
            titulo_words.append(ws)
        word_freq = Counter()
        for ws in titulo_words:
            for w in ws: word_freq[w] += 1
        n = len(titulos)
        max_freq = max(2, int(n * 0.03))
        rare_index = defaultdict(list)
        for i, ws in enumerate(titulo_words):
            for w in ws:
                if 2 <= word_freq[w] <= max_freq: rare_index[w].append(i)
        for idxs in rare_index.values():
            for a in range(len(idxs)):
                for b in range(a + 1, len(idxs)):
                    ia, ib = idxs[a], idxs[b]
                    if dsu.find(ia) == dsu.find(ib): continue
                    ea, eb = ae[ia], ae[ib]
                    if ea is None or eb is None: continue
                    sim = cosine_similarity(
                        np.array(ea).reshape(1, -1),
                        np.array(eb).reshape(1, -1)
                    )[0][0]
                    if sim >= sim_min and not _hay_conflicto_accion(safe_str(titulos[ia]), safe_str(titulos[ib])):
                        dsu.union(ia, ib)

    def _paso2c_consistencia(self, titulos, resumenes, dsu):
        grupos = construir_grupos_consistencia(titulos, resumenes, pbar=None)
        for idxs in grupos.values():
            if len(idxs) < 2:
                continue
            for k in range(1, len(idxs)):
                dsu.union(idxs[0], idxs[k])

    def _paso3(self, et, ae, dsu, pbar, ps):
        umbral_cluster = max(self._umbrales.get('subtema', UMBRAL_SUBTEMA), 0.82)
        sim_min = max(self._umbrales.get('sim_minima_agrupacion', SIM_MINIMA_AGRUPACION_SUBTEMA), 0.90)
        n = len(et)
        if n < 2: return

        def _puede_unir(i, j):
            if _hay_conflicto_accion(et[i], et[j]):
                return False
            if _overlap_distintivo(et[i], et[j]) >= 0.30:
                return True
            return SequenceMatcher(
                None,
                normalize_title_for_comparison(et[i]),
                normalize_title_for_comparison(et[j])
            ).ratio() >= 0.94

        B = 500
        if n <= B:
            pbar.progress(ps, "Clustering semántico...")
            ok = [(k, e) for k, e in enumerate(ae) if e is not None]
            if len(ok) < 2: return
            io_, M = zip(*ok)
            sim_matrix = cosine_similarity(np.array(M))
            linkage = 'complete' if n <= 10 else 'average'
            labels = AgglomerativeClustering(
                n_clusters=None, distance_threshold=1 - umbral_cluster,
                metric='precomputed', linkage=linkage
            ).fit(1 - sim_matrix).labels_
            g = defaultdict(list)
            for k, lbl in enumerate(labels): g[lbl].append(io_[k])
            for cl in g.values():
                if len(cl) < 2: continue
                vecs = np.array([ae[i] for i in cl if ae[i] is not None])
                if len(vecs) < 2: continue
                centroid = np.mean(vecs, axis=0)
                sims_al_centroid = cosine_similarity(vecs, centroid.reshape(1, -1)).flatten()
                todos_ok = all(s >= sim_min for s in sims_al_centroid)
                if todos_ok:
                    for j in cl[1:]:
                        if _puede_unir(cl[0], j):
                            dsu.union(cl[0], j)
                else:
                    mejor_idx = int(np.argmax(sims_al_centroid))
                    repr_vec = np.array(ae[cl[mejor_idx]]).reshape(1, -1)
                    for k_local, i_global in enumerate(cl):
                        if ae[i_global] is None: continue
                        sim_vs_repr = cosine_similarity(
                            np.array(ae[i_global]).reshape(1, -1), repr_vec
                        )[0][0]
                        if sim_vs_repr >= sim_min and _puede_unir(cl[mejor_idx], i_global):
                            dsu.union(cl[mejor_idx], i_global)
            pbar.progress(ps + 0.18, "Clustering completado")
            return

        tb = max(1, (n + B - 1) // B)
        for bn_, bs in enumerate(range(0, n, B)):
            bi = list(range(bs, min(bs + B, n)))
            ok = [(idx, ae[idx]) for idx in bi if ae[idx] is not None]
            if len(ok) < 2: continue
            io_, M = zip(*ok)
            sim_matrix = cosine_similarity(np.array(M))
            labels = AgglomerativeClustering(
                n_clusters=None, distance_threshold=1 - umbral_cluster,
                metric='precomputed', linkage='average'
            ).fit(1 - sim_matrix).labels_
            g = defaultdict(list)
            for k, lbl in enumerate(labels): g[lbl].append(io_[k])
            for cl in g.values():
                if len(cl) < 2: continue
                vecs = np.array([ae[i] for i in cl if ae[i] is not None])
                if len(vecs) < 2: continue
                centroid = np.mean(vecs, axis=0)
                sims = cosine_similarity(vecs, centroid.reshape(1, -1)).flatten()
                mejor_idx = int(np.argmax(sims))
                repr_vec = np.array(ae[cl[mejor_idx]]).reshape(1, -1)
                for k_local, i_global in enumerate(cl):
                    if ae[i_global] is None: continue
                    s = cosine_similarity(np.array(ae[i_global]).reshape(1, -1), repr_vec)[0][0]
                    if s >= sim_min and _puede_unir(cl[mejor_idx], i_global):
                        dsu.union(cl[mejor_idx], i_global)
            pbar.progress(ps + 0.15 * (bn_ + 1) / tb, f"Clustering {bn_ + 1}/{tb}...")

        pbar.progress(ps + 0.16, "Unificando...")
        usar_fusion = self._umbrales.get('usar_fusion_iterativa', True)
        if usar_fusion: self._fusion(et, ae, dsu, pbar, ps + 0.16)

    def _fusion(self, textos, ae, dsu, pbar, ps):
        n = len(textos)
        umbral_inter = self._umbrales.get('fusion_intergrupo', UMBRAL_FUSION_INTERGRUPO)
        max_iter = self._umbrales.get('max_iter_fusion', MAX_ITER_FUSION)
        sim_min = self._umbrales.get('sim_minima_agrupacion', SIM_MINIMA_AGRUPACION_SUBTEMA)
        for it in range(max_iter):
            grupos = dsu.grupos(n)
            if len(grupos) < 2: break
            centroids, vg = [], []
            for gid, idxs in grupos.items():
                vecs = [ae[i] for i in idxs[:50] if ae[i] is not None]
                if vecs:
                    centroids.append(np.mean(vecs, axis=0))
                    vg.append(gid)
            if len(vg) < 2: break
            sim = cosine_similarity(np.array(centroids))
            umbral_efectivo = max(umbral_inter, sim_min)
            pairs = sorted(
                [(sim[i][j], i, j) for i in range(len(vg)) for j in range(i + 1, len(vg))
                 if sim[i][j] >= umbral_efectivo], reverse=True
            )
            fus = 0
            for _, i, j in pairs:
                ri, rj = grupos[vg[i]][0], grupos[vg[j]][0]
                if dsu.find(ri) != dsu.find(rj):
                    textos_i = [textos[k] for k in grupos[vg[i]][:20]]
                    textos_j = [textos[k] for k in grupos[vg[j]][:20]]
                    if _grupos_contenido_compatibles(
                        textos_i,
                        textos_j,
                        "",
                        "",
                        min_sim=umbral_efectivo,
                        min_overlap=0.16,
                    ):
                        dsu.union(ri, rj)
                        fus += 1
            pbar.progress(min(ps + 0.04 * (it + 1), 0.52), f"Fusión {it + 1}: {fus}")
            if fus == 0: break

    def _extraer_keywords_titulos(self, titulos_grp: list, top_n: int = 6) -> list:
        palabras = []
        for t in titulos_grp[:10]:
            for w in string_norm_label(t).split():
                if len(w) > 3: palabras.append(w)
        return [w for w, _ in Counter(palabras).most_common(top_n)]

    def _generar_etiqueta(self, textos_grp, titulos_grp, resumenes_grp, subtemas_existentes=None):
        tn = sorted(set(normalize_title_for_comparison(t) for t in titulos_grp if t))
        existentes_key = "|".join(sorted(string_norm_label(s) for s in (subtemas_existentes or []))[:20])
        ck = hashlib.md5(("|".join(tn[:12]) + f"#{len(titulos_grp)}#{existentes_key}").encode()).hexdigest()
        if ck in self._cache: return self._cache[ck]

        tm = list(dict.fromkeys(safe_str(t)[:130] for t in titulos_grp if safe_str(t)))[:6]
        rm = [safe_str(r)[:200] for r in resumenes_grp[:3] if safe_str(r) and len(safe_str(r)) > 20]

        kw_list = self._extraer_keywords_titulos(titulos_grp, top_n=8)
        palabras_res = []
        for r in resumenes_grp[:5]:
            for w in string_norm_label(r).split():
                if len(w) > 4: palabras_res.append(w)
        kw_res = [w for w, _ in Counter(palabras_res).most_common(4)
                  if w not in {unidecode(k.lower()) for k in kw_list}]
        kw_todos = kw_list + kw_res
        kw = ", ".join(kw_todos[:10])

        ctx_resumenes = (
            "\nRESÚMENES (para contexto):\n"
            + "\n".join(f"  · {r}" for r in rm)
        ) if rm else ""

        if len(kw_list) >= 3:
            ejemplo_dinamico = f"'{kw_list[0].title()} de {kw_list[1].title()}'"
        else:
            ejemplo_dinamico = "'Proyecto de terminal de transportes'"

        lista_existentes = ""
        if subtemas_existentes and len(subtemas_existentes) > 0:
            lista_existentes = (
                "\n\nSUBTEMAS YA CREADOS (REUTILIZA SI ES EL MISMO ASUNTO):\n" +
                ", ".join(f"'{s}'" for s in subtemas_existentes[:20]) +
                "\nREGLA CRÍTICA: Si este grupo trata del MISMO hecho/asunto que uno ya creado, RESPONDE EXACTAMENTE con ese subtema."
            )

        prompt = (
            "Eres editor jefe. "
            "Genera UN subtema periodístico (4-7 palabras) que sea una FRASE NOMINAL "
            "para este grupo de noticias.\n\n"
            "TÍTULOS:\n" + "\n".join(f"  · {t}" for t in tm)
            + ctx_resumenes
            + f"\n\nPALABRAS CLAVE: {kw}"
            + lista_existentes
            + "\n\nREGLAS OBLIGATORIAS:\n"
            "  1. FRASE NOMINAL PURA: empieza con sustantivo, usa preposición.\n"
            f"     CORRECTO: {ejemplo_dinamico}\n"
            "  2. USA preposiciones (de, del, para, sobre, en, por) para conectar conceptos.\n"
            "  3. Tildes y ñ correctas.\n\n"
            'JSON: {"subtema":"..."}'
        )

        try:
            resp = call_with_retries(
                openai.ChatCompletion.create,
                model=OPENAI_MODEL_CLASIFICACION,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            u = resp.get('usage', {}) if isinstance(resp, dict) else getattr(resp, 'usage', {})
            if u:
                st.session_state['tokens_input'] += (u.get('prompt_tokens') if isinstance(u, dict) else getattr(u, 'prompt_tokens', 0)) or 0
                st.session_state['tokens_output'] += (u.get('completion_tokens') if isinstance(u, dict) else getattr(u, 'completion_tokens', 0)) or 0

            raw = json.loads(resp.choices[0].message.content).get("subtema", "Varios")
            et = limpiar_tema_geografico(limpiar_tema(raw), self.marca, self.aliases)

            if subtemas_existentes:
                et_norm = string_norm_label(et)
                mejor_exist, mejor_r = None, 0.0
                for ex in subtemas_existentes:
                    r = SequenceMatcher(None, et_norm, string_norm_label(ex)).ratio()
                    if r > mejor_r:
                        mejor_r, mejor_exist = r, ex
                if mejor_exist and mejor_r >= 0.88:
                    et = mejor_exist

            et = _validar_etiqueta_completa(
                et, titulos_grp=titulos_grp, resumenes_grp=resumenes_grp,
                marca=self.marca, aliases=self.aliases, fallback_fn=self._fallback
            )
        except Exception:
            et = self._fallback(titulos_grp)

        et = capitalizar_etiqueta(et)
        self._cache[ck] = et
        return et

    def _fallback(self, titulos):
        if not titulos: return "Cobertura de información relevante"
        palabras = []
        for t in titulos[:5]:
            for w in string_norm_label(t).split():
                if len(w) > 4: palabras.append(w)
        if palabras:
            top = [w for w, _ in Counter(palabras).most_common(3)]
            if len(top) >= 2:
                frase = f"{top[0]} de {top[1]}"
                if _frase_esta_completa(frase): return capitalizar_etiqueta(frase)
                return capitalizar_etiqueta(f"Asuntos de {top[0]} y {top[1]}")
            return capitalizar_etiqueta(f"Asuntos relacionados con {top[0]}")
        return "Cobertura de información relevante"

    def _consolidar_sinonimos_llm(self, subtemas_unicos):
        if len(subtemas_unicos) <= 1:
            return {s: s for s in subtemas_unicos}

        prompt = (
            "Eres un analista de datos. Tienes la siguiente lista de subtemas periodísticos:\n"
            f"{', '.join(subtemas_unicos)}\n\n"
            "Tu tarea es encontrar SUBTEMAS SINÓNIMOS o variaciones leves del MISMO asunto y unificarlos.\n"
            'Devuelve JSON: {"subtema_original": "subtema_unificado"}'
        )
        try:
            resp = call_with_retries(
                openai.ChatCompletion.create,
                model=OPENAI_MODEL_CLASIFICACION,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            return json.loads(resp.choices[0].message.content)
        except Exception:
            return {s: s for s in subtemas_unicos}

    def procesar_lote(self, col, pbar, res_puros, tit_puros):
        textos    = [safe_str(t) for t in col.tolist()]
        titulos   = [safe_str(t) for t in tit_puros.tolist()]
        resumenes = [safe_str(r) for r in res_puros.tolist()]
        n = len(textos)

        self._umbrales = _umbrales_adaptativos(n)
        u = self._umbrales

        et = [texto_para_embedding(titulos[i], resumenes[i]) for i in range(n)]

        pbar.progress(0.04, "Fase 1 · Idénticas...")
        dsu = DSU(n)
        self._paso1(titulos, resumenes, dsu)

        pbar.progress(0.08, "Fase 1b · Consistencia título/cuerpo...")
        self._paso2c_consistencia(titulos, resumenes, dsu)

        pbar.progress(0.12, "Fase 2 · Títulos / prefijos...")
        self._paso2(titulos, dsu)

        pbar.progress(0.18, "Embeddings...")
        ae = get_embeddings_batch(et)

        if u['usar_paso2b']:
            pbar.progress(0.20, "Fase 2b · Keywords raras...")
            self._paso2b_keywords(titulos, dsu, ae)

        pbar.progress(0.22, "Fase 3 · Clustering...")
        self._paso3(et, ae, dsu, pbar, 0.22)

        gf = dsu.grupos(n)
        ng = len(gf)
        pbar.progress(0.55, f"Fase 4 · Etiquetando {ng} grupos...")
        mapa = {}
        sg = sorted(gf.items(), key=lambda x: -len(x[1]))
        subtemas_aprobados = []
        textos_por_subtema_aprobado = defaultdict(list)

        def _generar_etiqueta_segura(idxs):
            textos_grp = [textos[i] for i in idxs]
            titulos_grp = [titulos[i] for i in idxs]
            resumenes_grp = [resumenes[i] for i in idxs]
            etiqueta = self._generar_etiqueta(
                textos_grp,
                titulos_grp,
                resumenes_grp,
                subtemas_existentes=subtemas_aprobados
            )
            if etiqueta not in subtemas_aprobados:
                subtemas_aprobados.append(etiqueta)
            textos_por_subtema_aprobado[etiqueta].extend(textos_grp[:MAX_GRUPO_ETIQUETA])
            return etiqueta

        for k, (lid, idxs) in enumerate(sg):
            if k % 10 == 0: pbar.progress(0.55 + 0.25 * (k / max(ng, 1)), f"Etiquetando {k + 1}/{ng}...")

            if len(idxs) > MAX_GRUPO_ETIQUETA:
                subgrupos = [idxs[i:i + MAX_GRUPO_ETIQUETA] for i in range(0, len(idxs), MAX_GRUPO_ETIQUETA)]
                for sg_ in subgrupos:
                    e = _generar_etiqueta_segura(sg_)
                    for i in sg_: mapa[i] = e
            else:
                e = _generar_etiqueta_segura(idxs)
                for i in idxs: mapa[i] = e

        subtemas = [mapa.get(i, "Varios") for i in range(n)]

        pbar.progress(0.82, "Fase 5 · Dedup...")
        subtemas = dedup_labels(subtemas, u['dedup_label'])

        pbar.progress(0.86, "Fase 5b · Fusión semántica...")
        textos_por_sub = defaultdict(list)
        for i, s in enumerate(subtemas): textos_por_sub[s].append(textos[i])
        subtemas = _fusionar_subtemas_semanticos(subtemas, textos_por_sub, self.marca, self.aliases, u['fusion_subtemas'])

        pbar.progress(0.97, "Fase 8 · Dedup final...")
        subtemas = dedup_labels(subtemas, u['dedup_label'])

        subtemas = [capitalizar_etiqueta(s) for s in subtemas]
        pbar.progress(1.0, "Subtemas procesados")
        return subtemas

# ======================================
# TEMAS
# ======================================
def _construir_representacion_grupo(subtema, textos_grupo, max_textos=30):
    palabras = []
    for t in textos_grupo[:max_textos]:
        for w in string_norm_label(t).split():
            if len(w) > 3: palabras.append(w)
    kw_str = " ".join(w for w, _ in Counter(palabras).most_common(12))
    return f"{subtema}. {subtema}. {kw_str}"[:500]

def _generar_nombre_tema_llm(subtemas_grupo, textos_muestra, titulos_muestra):
    subs_list = "\n".join(f"  · {s}" for s in subtemas_grupo[:8])
    prompt = (
        "Crea UN tema editorial preciso (2-5 palabras) que agrupe estos subtemas.\n\n"
        "SUBTEMAS:\n" + subs_list + "\n\n"
        'JSON: {"tema":"..."}'
    )
    try:
        resp = call_with_retries(
            openai.ChatCompletion.create,
            model=OPENAI_MODEL_CLASIFICACION,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=40,
            temperature=0.05,
            response_format={"type": "json_object"}
        )
        raw = json.loads(resp.choices[0].message.content).get("tema", "").strip()
        return capitalizar_etiqueta(raw)
    except Exception:
        return None

def consolidar_temas(subtemas, textos, pbar):
    n = len(textos)
    u = _umbrales_adaptativos(n)
    df = pd.DataFrame({'subtema': subtemas, 'texto': textos})
    us = list(df['subtema'].unique())
    if len(us) <= 1:
        return [capitalizar_etiqueta(s) for s in subtemas]

    textos_por_subtema = defaultdict(list)
    for i, sub in enumerate(subtemas): textos_por_subtema[sub].append(textos[i])
    repr_enriquecidas = [_construir_representacion_grupo(sub, textos_por_subtema[sub]) for sub in us]
    
    emb_repr = get_embeddings_batch(repr_enriquecidas)
    ae = get_embeddings_batch(textos)
    centroids_contenido = {}
    for sub in us:
        idxs = df.index[df['subtema'] == sub].tolist()[:50]
        vecs = [ae[i] for i in idxs if ae[i] is not None]
        if vecs: centroids_contenido[sub] = np.mean(vecs, axis=0)

    vs = [s for s in us if s in centroids_contenido]
    if len(vs) < 2:
        return [capitalizar_etiqueta(s) for s in subtemas]

    M_content = np.array([centroids_contenido[s] for s in vs])
    sim_combined = cosine_similarity(M_content)

    dist_matrix = np.clip(1 - sim_combined, 0, 2)
    np.fill_diagonal(dist_matrix, 0)
    cl = AgglomerativeClustering(
        n_clusters=None, distance_threshold=1 - u['tema'],
        metric='precomputed', linkage='average'
    ).fit(dist_matrix)

    clusters = defaultdict(list)
    for i, lbl in enumerate(cl.labels_): clusters[lbl].append(vs[i])

    mt = {}
    for cid, subtemas_cluster in clusters.items():
        if len(subtemas_cluster) == 1:
            nombre = subtemas_cluster[0]
        else:
            nombre = _generar_nombre_tema_llm(subtemas_cluster, [], []) or subtemas_cluster[0]
        for sub in subtemas_cluster: mt[sub] = capitalizar_etiqueta(nombre)

    tf_final = [mt.get(s, s) for s in subtemas]
    pbar.progress(1.0, "Temas listos")
    return tf_final

def _unificar_tema_por_subtema(temas, subtemas):
    sub_to_temas = defaultdict(list)
    for t, s in zip(temas, subtemas): sub_to_temas[s].append(t)
    sub_to_best = {sub: Counter(tlist).most_common(1)[0][0] for sub, tlist in sub_to_temas.items()}
    return [sub_to_best[s] for s in subtemas]


# ======================================
# Duplicados y Excel
# ======================================
def _normalizar_url(url: str) -> str:
    if not url: return ""
    url = safe_str(url).lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip('/')
    return url

def detectar_duplicados_avanzado(rows, km):
    processed = deepcopy(rows)
    seen_url, seen_bcast = {}, {}
    seen_streaming: Dict[tuple, int] = {}
    tb = defaultdict(list)

    for i, row in enumerate(processed):
        if row.get("is_duplicate"): continue

        tipo    = normalizar_tipo_medio(row.get(km["tipodemedio"], ""))
        mencion = norm_key(row.get(km["menciones"], ""))
        medio   = norm_key(row.get(km["medio"], ""))

        streaming_url_raw = row.get(km["link_streaming"])
        if isinstance(streaming_url_raw, dict):
            streaming_url_raw = streaming_url_raw.get("url")

        if streaming_url_raw and mencion:
            streaming_url_norm = _normalizar_url(streaming_url_raw)
            if streaming_url_norm:
                sk = (streaming_url_norm, mencion)
                if sk in seen_streaming:
                    row["is_duplicate"] = True
                    row[km["idduplicada"]] = processed[seen_streaming[sk]].get(km["idnoticia"], "")
                    continue
                seen_streaming[sk] = i

        if tipo == "Internet":
            li = row.get(km["link_nota"])
            url = li.get("url") if isinstance(li, dict) else li
            if url and mencion:
                url_norm = _normalizar_url(url)
                k = (url_norm, mencion)
                if k in seen_url:
                    row["is_duplicate"] = True
                    row[km["idduplicada"]] = processed[seen_url[k]].get(km["idnoticia"], "")
                    continue
                seen_url[k] = i
            if medio and mencion:
                tb[(medio, mencion)].append(i)

        elif tipo in ("Radio", "Televisión"):
            hora = safe_str(row.get(km["hora"], ""))
            if mencion and medio and hora:
                k = (mencion, medio, hora)
                if k in seen_bcast:
                    row["is_duplicate"] = True
                    row[km["idduplicada"]] = processed[seen_bcast[k]].get(km["idnoticia"], "")
                else:
                    seen_bcast[k] = i

    for idxs in tb.values():
        if len(idxs) < 2: continue
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                a, b = idxs[i], idxs[j]
                if processed[a].get("is_duplicate") or processed[b].get("is_duplicate"): continue
                ta  = normalize_title_for_comparison(processed[a].get(km["titulo"]))
                tb_ = normalize_title_for_comparison(processed[b].get(km["titulo"]))
                if ta and tb_ and SequenceMatcher(None, ta, tb_).ratio() >= SIMILARITY_THRESHOLD_TITULOS:
                    if len(ta) < len(tb_):
                        processed[a]["is_duplicate"] = True
                        processed[a][km["idduplicada"]]  = processed[b].get(km["idnoticia"], "")
                    else:
                        processed[b]["is_duplicate"] = True
                        processed[b][km["idduplicada"]]  = processed[a].get(km["idnoticia"], "")

    return processed

def read_and_normalize_dossier(sheet, region_map, internet_map):
    headers = [cell.value for cell in sheet[1] if cell.value is not None]
    rows = []
    for row in sheet.iter_rows(min_row=2):
        if all(c.value is None for c in row):
            continue
        row_data = {}
        for i, h in enumerate(headers):
            if i < len(row):
                cell = row[i]
                val = cell.value
                url = cell.hyperlink.target if (cell.hyperlink and cell.hyperlink.target) else None
                if url:
                    row_data[h] = {"value": val or "Link", "url": url}
                else:
                    row_data[h] = val
        rows.append(row_data)

    df = pd.DataFrame(rows)

    tipo_medio_map = {
        'online': 'Internet', 'internet': 'Internet',
        'diario': 'Prensa', 'am': 'Radio', 'fm': 'Radio',
        'aire': 'Televisión', 'cable': 'Televisión', 'revista': 'Revistas'
    }

    if 'Tipo de Medio' in df.columns:
        df['Tipo de Medio'] = (
            df['Tipo de Medio'].astype(str).str.lower().str.strip()
            .map(tipo_medio_map)
            .fillna(df['Tipo de Medio'].astype(str).str.strip())
        )
    else:
        df['Tipo de Medio'] = 'Otro'

    is_av = df['Tipo de Medio'].isin(['Radio', 'Televisión'])
    is_grafica = df['Tipo de Medio'].isin(['Prensa', 'Internet', 'Revistas'])
    is_internet = df['Tipo de Medio'] == 'Internet'

    if 'Medio' in df.columns:
        raw_medios_clean = df['Medio'].astype(str).str.lower().str.strip()
        df['Región'] = raw_medios_clean.map(region_map).fillna("N/A")
    else:
        df['Medio'] = 'N/A'
        df['Región'] = 'N/A'

    if 'Medio' in df.columns:
        df.loc[is_internet, 'Medio'] = (
            df.loc[is_internet, 'Medio']
            .astype(str).str.lower().str.strip()
            .map(internet_map)
            .fillna(df.loc[is_internet, 'Medio'])
        )

    df['ID Noticia'] = df.get('NoticiaId', df.get('ID Noticia', pd.Series(dtype=str)))
    df['Fecha'] = pd.to_datetime(df.get('Fecha', pd.Series(dtype=str)), dayfirst=True, errors='coerce').dt.normalize()
    df['Hora'] = df.get('Hora', pd.Series(dtype=str))
    df['Sección - Programa'] = df.get('Sección - Programa', pd.Series(dtype=str)).apply(clean_text)

    titulo_col = 'Título' if 'Título' in df.columns else 'Titulo'
    df['Título'] = df.get(titulo_col, pd.Series(dtype=str)).apply(clean_text)
    df['Autor - Conductor'] = df.get('Autor - Conductor', pd.Series(dtype=str)).apply(clean_text)

    cuerpo_col = 'CuerpoEs' if 'CuerpoEs' in df.columns else 'Resumen - Aclaracion'
    df['Resumen - Aclaracion'] = df.get(cuerpo_col, pd.Series([''] * len(df))).apply(clean_cuerpo)

    url_nota_av = df.get('URL Nota AV', df.get('Link Nota AV', pd.Series([''] * len(df))))
    url_streaming = df.get('URL (Streaming - Imagen)', pd.Series([''] * len(df)))

    link_nota_final = []
    for val_av, val_str, is_av_row in zip(url_nota_av, url_streaming, is_av):
        if is_av_row:
            if isinstance(val_av, dict):
                url_t = val_av.get("url", "")
                link_nota_final.append({"value": "Link", "url": url_t.replace(".com.ar", ".com.co") if url_t else None})
            else:
                url_t = safe_str(val_av)
                link_nota_final.append({"value": "Link", "url": url_t.replace(".com.ar", ".com.co") if url_t else None})
        else:
            if isinstance(val_str, dict):
                link_nota_final.append(val_str)
            else:
                link_nota_final.append({"value": "Link", "url": val_str if val_str else None})

    df['Link Nota'] = link_nota_final

    menciones_av = df.get('Menciones - Empresa', pd.Series([''] * len(df))).fillna('').apply(clean_text)
    menciones_grafica = df.get('Empresa rel.', pd.Series([''] * len(df))).fillna('').apply(clean_text)
    df['Menciones - Empresa'] = np.where(is_av, menciones_av, np.where(is_grafica, menciones_grafica, menciones_av))

    return df

def generate_output_excel(rows, km):
    wb = Workbook()
    ws = wb.active
    ws.title = "Resultado"
    ORDER = [
        "ID Noticia", "Fecha", "Hora", "Medio", "Tipo de Medio",
        "Sección - Programa", "Región", "Título", "Autor - Conductor",
        "Nro. Pagina", "Dimensión", "Duración - Nro. Caracteres",
        "CPE", "Tier", "Audiencia", "Tono", "Tono IA", "Tema", "Subtema",
        "Link Nota", "Resumen - Aclaracion", "Link (Streaming - Imagen)", "Menciones - Empresa",
        "ID duplicada"
    ]
    NUM = {"ID Noticia", "Nro. Pagina", "Dimensión", "Duración - Nro. Caracteres", "CPE", "Tier", "Audiencia"}
    ws.append(ORDER)

    font_hyperlink = Font(color="000000", underline=None)
    align_left = Alignment(horizontal='left')
    font_header = Font(bold=True)

    for i, col_name in enumerate(ORDER, start=1):
        cell = ws.cell(row=1, column=i)
        cell.font = font_header

    for row in rows:
        tk = km.get("titulo")
        if tk and tk in row: row[tk] = clean_title_for_output(row.get(tk))
        rk = km.get("resumen")
        if rk and rk in row: row[rk] = corregir_texto(row.get(rk))

        out, links = [], {}
        for ci, h in enumerate(ORDER, start=1):
            val = row.get(h)
            cv = None

            if h == 'Fecha' and pd.notna(val):
                if isinstance(val, pd.Timestamp):
                    cv = val.to_pydatetime()
                elif isinstance(val, (datetime.datetime, datetime.date)):
                    cv = val
                else:
                    cv = safe_str(val) if val is not None else None
            elif h in NUM:
                cv = parse_numeric(val)
            elif isinstance(val, dict) and "url" in val:
                cv = val.get("value", "Link")
                if val.get("url"): links[ci] = val["url"]
            elif val is not None:
                if isinstance(val, str) and val.startswith("http"):
                    cv = "Link"
                    links[ci] = val
                else:
                    cv = safe_str(val)
            out.append(cv)
        ws.append(out)

        current_row = ws.max_row
        for ci, url in links.items():
            cell = ws.cell(row=current_row, column=ci)
            cell.hyperlink = url
            cell.font = font_hyperlink
            cell.alignment = align_left

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ======================================
# Proceso principal Async
# ======================================
async def run_full_process_async(df_file, bn, ba, tpkl, epkl, mode, xlsx_bytes=None, cliente="", voceros="", enable_scraping=False):
    st.session_state.update({'tokens_input': 0, 'tokens_output': 0, 'tokens_embedding': 0})
    get_embedding_cache().clear()
    t0 = time.time()

    if "API" in mode:
        try:
            openai.api_key=st.secrets["OPENAI_API_KEY"]
            openai.aiosession.set(None)
        except Exception:
            st.error("OPENAI_API_KEY no encontrado.")
            st.stop()

    with st.status("Paso 1 · Carga de Configuración y Dossier", expanded=True) as s:
        region_map, internet_map = load_config_from_sheets()

        wb_in = load_workbook(df_file, data_only=True)
        df_normalized = read_and_normalize_dossier(wb_in.active, region_map, internet_map)

        rows_expanded = []
        for idx, row_series in df_normalized.iterrows():
            menciones = [m.strip() for m in safe_str(row_series['Menciones - Empresa']).split(';') if m.strip()]
            if not menciones:
                row_dict = row_series.to_dict()
                row_dict['Menciones - Empresa'] = ""
                row_dict['original_index'] = idx
                row_dict['expanded_index'] = len(rows_expanded)
                row_dict['is_duplicate'] = False
                rows_expanded.append(row_dict)
            else:
                for m in menciones:
                    row_dict = row_series.to_dict()
                    row_dict['Menciones - Empresa'] = m
                    row_dict['original_index'] = idx
                    row_dict['expanded_index'] = len(rows_expanded)
                    row_dict['is_duplicate'] = False
                    rows_expanded.append(row_dict)

        km = {
            "idnoticia": "ID Noticia",
            "fecha": "Fecha",
            "hora": "Hora",
            "medio": "Medio",
            "tipodemedio": "Tipo de Medio",
            "seccion_programa": "Sección - Programa",
            "region": "Región",
            "titulo": "Título",
            "autor_conductor": "Autor - Conductor",
            "nro_pagina": "Nro. Pagina",
            "dimension": "Dimensión",
            "duracion_caracteres": "Duración - Nro. Caracteres",
            "cpe": "CPE",
            "tier": "Tier",
            "audiencia": "Audiencia",
            "tono": "Tono",
            "tonoiai": "Tono IA",
            "tema": "Tema",
            "subtema": "Subtema",
            "link_nota": "Link Nota",
            "resumen": "Resumen - Aclaracion",
            "link_streaming": "Link (Streaming - Imagen)",
            "menciones": "Menciones - Empresa",
            "idduplicada": "ID duplicada"
        }

        rows = detectar_duplicados_avanzado(rows_expanded, km)
        for row in rows:
            if row["is_duplicate"]:
                row["Tono IA"] = "Duplicada"
                row["Tema"] = "-"
                row["Subtema"] = "-"

        s.update(label="✓ Paso 1 completado", state="complete")

    ta = [r for r in rows if not r.get("is_duplicate")]

    if ta:
        df = pd.DataFrame(ta)
        df["_txt"] = df.apply(
            lambda r: texto_para_embedding(r.get(km["titulo"], ""), r.get(km["resumen"], "")),
            axis=1
        )
        with st.status("Embeddings...", expanded=True) as s:
            _ = get_embeddings_batch(df["_txt"].tolist())
            s.update(label=f"✓ {get_embedding_cache().stats()}", state="complete")

        with st.status("Paso 3 · Tono (Reputación)", expanded=True) as s:
            pb = st.progress(0)
            if "PKL" in mode and tpkl:
                res = analizar_tono_con_pkl(df["_txt"].tolist(), tpkl)
                if res is None: st.stop()
            elif "API" in mode:
                res = await ClasificadorTono(bn, ba).procesar_lote_async(
                    df["_txt"], pb, df[km["resumen"]], df[km["titulo"]]
                )
            else:
                res = [{"tono": "N/A"}] * len(ta)
            df[km["tonoiai"]] = [r["tono"] for r in res]
            s.update(label="✓ Paso 3 · Tono (Reputación)", state="complete")

        with st.status("Paso 4 · Clasificación", expanded=True) as s:
            pb = st.progress(0)
            subtemas = ClasificadorSubtema(bn, ba).procesar_lote(
                df["_txt"], pb, df[km["resumen"]], df[km["titulo"]]
            )
            temas = consolidar_temas(subtemas, df["_txt"].tolist(), pb)
            df[km["subtema"]] = subtemas
            df[km["tema"]] = temas
            s.update(label="✓ Paso 4 · Clasificación", state="complete")

        with st.status("Paso 4b · Consistencia republicaciones (Título/CuerpoEs)", expanded=True) as s:
            pb = st.progress(0)
            df = aplicar_consistencia_intergrupo(
                df,
                km_tono=km["tonoiai"], km_tema=km["tema"], km_subtema=km["subtema"],
                km_titulo=km["titulo"], km_resumen=km["resumen"],
                pbar=pb
            )
            s.update(label="✓ Paso 4b · Consistencia completada", state="complete")

        with st.status("Paso 4c · Unificación de subtemas similares", expanded=True) as s:
            pb = st.progress(0)
            df = unificar_subtemas_similares_post(
                df,
                km_subtema=km["subtema"],
                km_tema=km["tema"],
                km_tono=km["tonoiai"],
                km_titulo=km["titulo"],
                km_resumen=km["resumen"],
                marca=bn,
                aliases=ba,
                pbar=pb,
            )
            s.update(label="✓ Paso 4c · Subtemas unificados", state="complete")

        rm2 = df.set_index("expanded_index").to_dict("index")
        for idx, row in enumerate(rows):
            if not row.get("is_duplicate"):
                row.update(rm2.get(row.get("expanded_index"), {}))

    gc.collect()
    ci = (st.session_state['tokens_input']     / 1e6) * PRICE_INPUT_1M
    co = (st.session_state['tokens_output']    / 1e6) * PRICE_OUTPUT_1M
    ce = (st.session_state['tokens_embedding'] / 1e6) * PRICE_EMBEDDING_1M

    with st.status("Paso 5 · Informe", expanded=True) as s:
        st.session_state["output_data"]     = generate_output_excel(rows, km)
        st.session_state["output_filename"] = f"Informe_IA_{bn.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        st.session_state["processing_complete"] = True
        st.session_state.update({
            "brand_name": bn, "brand_aliases": ba,
            "total_rows": len(rows), "unique_rows": len(ta), "duplicates": len(rows) - len(ta),
            "process_duration": f"{time.time() - t0:.0f}s",
            "process_cost": f"${ci + co + ce:.4f} USD",
            "cache_stats": get_embedding_cache().stats()
        })
        s.update(label=f"✓ Completado · {get_embedding_cache().stats()}", state="complete")

async def run_quick_async(df, tc, sc, bn, al):
    st.session_state.update({'tokens_input': 0, 'tokens_output': 0, 'tokens_embedding': 0})
    get_embedding_cache().clear()
    df['_txt'] = df.apply(lambda r: texto_para_embedding(r.get(tc, ""), r.get(sc, "")), axis=1)
    
    _ = get_embeddings_batch(df['_txt'].tolist())
    pb = st.progress(0)
    res = await ClasificadorTono(bn, al).procesar_lote_async(df["_txt"], pb, df[sc], df[tc])
    df['Tono IA'] = [r["tono"] for r in res]
    
    subtemas = ClasificadorSubtema(bn, al).procesar_lote(df["_txt"], pb, df[sc], df[tc])
    df['Subtema'] = subtemas
    temas = consolidar_temas(subtemas, df["_txt"].tolist(), pb)
    df['Tema'] = temas
    
    df = aplicar_consistencia_intergrupo(
        df, km_tono='Tono IA', km_tema='Tema', km_subtema='Subtema',
        km_titulo=tc, km_resumen=sc, pbar=pb
    )
    df = unificar_subtemas_similares_post(
        df, km_subtema='Subtema', km_tema='Tema', km_tono='Tono IA',
        km_titulo=tc, km_resumen=sc, marca=bn, aliases=al, pbar=pb
    )
    df.drop(columns=['_txt'], inplace=True)
    return df

def gen_quick_excel(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df.to_excel(w, index=False, sheet_name='Analisis')
    return buf.getvalue()

def render_quick_tab():
    st.markdown('<div class="sec-label">Análisis rápido</div>', unsafe_allow_html=True)
    if 'quick_result' in st.session_state:
        st.dataframe(st.session_state.quick_result.head(10), use_container_width=True)
        st.download_button(
            "Descargar",
            data=gen_quick_excel(st.session_state.quick_result),
            file_name="Analisis_Rapido_IA.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )
        return
    if 'quick_df' not in st.session_state:
        f = st.file_uploader("Excel", type=["xlsx"], label_visibility="collapsed", key="qu")
        if f:
            try:
                st.session_state.quick_df   = pd.read_excel(f)
                st.session_state.quick_name = f.name
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        with st.form("qf"):
            cols = st.session_state.quick_df.columns.tolist()
            tc = st.selectbox("Col. título", cols, 0)
            sc = st.selectbox("Col. resumen", cols, 1 if len(cols) > 1 else 0)
            bn  = st.text_input("Marca", placeholder="Ej: Bancolombia")
            bat = st.text_input("Alias (;)", placeholder="Ej: Grupo Bancolombia;Ban")
            if st.form_submit_button("Analizar", use_container_width=True, type="primary"):
                al = [a.strip() for a in bat.split(";") if a.strip()]
                st.session_state.quick_result = asyncio.run(
                    run_quick_async(st.session_state.quick_df.copy(), tc, sc, bn, al)
                )
                st.rerun()


# ======================================
# Main
# ======================================
def main():
    load_custom_css()
    if not check_password(): return

    st.markdown("""
    <div class="app-header">
        <div class="app-header-icon">◈</div>
        <div class="app-header-text">
            <div class="app-header-title">Análisis de Noticias - API</div>
            <div class="app-header-version">v18.5 · Ultra-consistencia Título/CuerpoEs + Unificación Estricta · Johnathan Cortés</div>
        </div>
        <div class="app-header-badge">IA</div>
    </div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Análisis Completo", "Análisis Rápido"])

    with tab1:
        if not st.session_state.get("processing_complete", False):
            cl, cr = st.columns([3, 2])
            with cl:
                bn  = st.text_input("Marca principal", placeholder="Ej: Bancolombia", key="bn")
                bat = st.text_input("Alias (separados por ;)", placeholder="Ej: Grupo Bancolombia;Ban", key="ba")
            with cr:
                mode = st.radio(
                    "Modo de análisis",
                    ["API de OpenAI", "Híbrido (PKL + API)", "Solo Modelos PKL"],
                    index=0, key="mode"
                )

            tpkl, epkl = None, None

            with st.form("main_form"):
                f1 = st.file_uploader("Dossier", type=["xlsx"], label_visibility="collapsed", key="f1")

                if st.form_submit_button("▶ Iniciar análisis", use_container_width=True, type="primary"):
                    if not all([f1, bn.strip()]):
                        st.error("Completa todos los campos.")
                    else:
                        al = [a.strip() for a in bat.split(";") if a.strip()]
                        cur_mode = st.session_state.get("mode", "API de OpenAI")
                        asyncio.run(run_full_process_async(f1, bn, al, tpkl, epkl, cur_mode))
                        st.rerun()
        else:
            st.download_button(
                "⬇ Descargar informe",
                data=st.session_state.output_data,
                file_name=st.session_state.output_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
            if st.button("Nuevo análisis", use_container_width=True):
                pwd = st.session_state.get("password_correct")
                st.session_state.clear()
                st.session_state.password_correct = pwd
                st.rerun()

    with tab2:
        render_quick_tab()

if __name__ == "__main__":
    main()
