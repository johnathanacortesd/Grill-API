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
import html

# ======================================
# Configuracion general
# ======================================
st.set_page_config(
    page_title="Análisis de Noticias · IA",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

OPENAI_MODEL_EMBEDDING     = "text-embedding-3-small"
OPENAI_MODEL_CLASIFICACION = "gpt-4.1-nano-2025-04-14"

CONCURRENT_REQUESTS          = 50
SIMILARITY_THRESHOLD_TONO    = 0.82
SIMILARITY_THRESHOLD_TITULOS = 0.93

UMBRAL_SUBTEMA = 0.78
UMBRAL_TEMA    = 0.72
NUM_TEMAS_MAX  = 15

UMBRAL_DEDUP_LABEL           = 0.78
UMBRAL_FUSION_SUBTEMAS       = 0.78
UMBRAL_FUSION_INTERGRUPO     = 0.84
MAX_ITER_FUSION              = 5

UMBRAL_MIN_PERTENENCIA_SUBTEMA = 0.60
UMBRAL_MIN_PERTENENCIA_TEMA    = 0.52

UMBRAL_COHERENCIA_ETIQUETA   = 0.35

MAX_GRUPO_ETIQUETA           = 40

SIM_MINIMA_AGRUPACION_SUBTEMA = 0.82
SIM_MINIMA_KEYWORDS_RARAS     = 0.78
SIM_MINIMA_FUSION_INTER       = 0.88

PRICE_INPUT_1M     = 0.10
PRICE_OUTPUT_1M    = 0.40
PRICE_EMBEDDING_1M = 0.02

if 'tokens_input'     not in st.session_state: st.session_state['tokens_input']     = 0
if 'tokens_output'    not in st.session_state: st.session_state['tokens_output']    = 0
if 'tokens_embedding' not in st.session_state: st.session_state['tokens_embedding'] = 0

STOPWORDS_ES = set("""
a ante bajo cabe con contra de desde durante en entre hacia hasta mediante
para por segun sin so sobre tras y o u e la el los las un una unos unas lo
al del se su sus le les mi mis tu tus nuestro nuestros vuestra vuestras este
esta estos estas ese esa esos esas aquel aquella aquellos aquellas que cual
cuales quien quienes cuyo cuya cuyos cuyas como cuando donde cual es son fue
fueron era eran sera seran seria serian he ha han habia habian hay hubo habra
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
    r"\b(calma|caos|urgente|hoy|ya|ahora|ayer|mañana|nuevo|nueva|"
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
    "turistica":"turística","turistico":"turístico","gastronomia":"gastronomía",
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
    "compania":"compañía","companias":"compañías","acompanamiento":"acompañamiento",
    "cana":"caña","canas":"cañas","banio":"baño","banios":"baños","bano":"baño","banos":"baños",
    "pena":"peña","penas":"peñas","penon":"peñón","senor":"señor","senora":"señora",
    "senores":"señores","senoras":"señoras","senal":"señal","senales":"señales",
    "senalizacion":"señalización","pequeno":"pequeño","pequena":"pequeña",
    "pequenos":"pequeños","pequenas":"peñas","sueno":"sueño","suenos":"sueños",
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
}

def corregir_tildes(texto: str) -> str:
    if not texto: return texto
    palabras = texto.split()
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
.app-header::after{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#f97316,#fb923c,#fdba74);}
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
.cluster-info{background:var(--accent-bg);border:1px solid var(--accent-bdr);border-radius:var(--r);padding:0.5rem 0.8rem;margin:0.4rem 0;font-family:'Roboto Mono',monospace;font-size:0.68rem;color:var(--text2);line-height:1.6;}
.cluster-info b{color:var(--accent2);font-size:0.72rem}
[data-testid="stProgressBar"]>div>div{background:linear-gradient(90deg,#f97316,#fb923c,#fdba74)!important;border-radius:100px!important;height:5px!important;}
[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:var(--r2)!important;box-shadow:var(--shadow-sm)!important;overflow:hidden!important;}
.success-banner{background:linear-gradient(135deg,#ecfdf5,#d1fae5);border:1px solid var(--green-bdr);border-left:4px solid var(--green);border-radius:var(--r2);padding:0.8rem 1.2rem;margin:0.5rem 0 0.8rem;display:flex;align-items:center;gap:0.8rem;}
.success-icon{width:34px;height:34px;background:linear-gradient(135deg,#059669,#047857);border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:1rem;flex-shrink:0;}
.success-title{font-family:'Google Sans',sans-serif;font-size:1rem;font-weight:700;color:#047857;margin-bottom:0.1rem}
.success-sub{font-size:0.8rem;color:var(--text2)}
.auth-wrap{max-width:380px;margin:8vh auto 0;text-align:center}
.auth-icon{width:60px;height:60px;background:linear-gradient(135deg,#f97316,#ea580c);border-radius:16px;display:inline-flex;align-items:center;justify-content:center;font-size:1.6rem;color:white;margin-bottom:1rem;box-shadow:0 4px 16px rgba(249,115,22,0.3);}
.auth-title{font-family:'Google Sans',sans-serif;font-size:1.5rem;font-weight:700;color:var(--text);margin-bottom:0.3rem}
.auth-sub{font-size:0.85rem;color:var(--text3);margin-bottom:2rem}
[data-testid="stStatus"]{background:var(--s1)!important;border:1px solid var(--border)!important;border-radius:var(--r2)!important;font-family:'Roboto Mono',monospace!important;font-size:0.8rem!important;}
[data-testid="stAlert"]{background:var(--s1)!important;border:1px solid var(--border)!important;border-radius:var(--r2)!important;color:var(--text2)!important;font-size:0.85rem!important;padding:0.6rem 0.8rem!important;}
.stButton>button,[data-testid="stDownloadButton"]>button{background:var(--s1)!important;border:1.5px solid var(--border)!important;color:var(--text)!important;border-radius:100px!important;font-family:'Google Sans',sans-serif!important;font-weight:500!important;font-size:0.88rem!important;transition:var(--transition)!important;padding:0.5rem 1.2rem!important;box-shadow:none!important;}
.stButton>button:hover,[data-testid="stDownloadButton"]>button:hover{border-color:var(--accent)!important;color:var(--accent2)!important;background:var(--accent-bg)!important;box-shadow:var(--shadow-sm)!important;transform:translateY(-1px)!important;}
.stButton>button[kind="primary"],[data-testid="stDownloadButton"]>button[kind="primary"]{background:var(--accent)!important;border:none!important;color:#fff!important;font-weight:500!important;font-size:0.92rem!important;padding:0.6rem 1.5rem!important;box-shadow:0 1px 3px rgba(249,115,22,0.3),0 4px 12px rgba(249,115,22,0.15)!important;letter-spacing:0.01em!important;}
.stButton>button[kind="primary"]:hover,[data-testid="stDownloadButton"]>button[kind="primary"]:hover{background:var(--accent2)!important;box-shadow:0 2px 6px rgba(234,88,12,0.35),0 8px 24px rgba(234,88,12,0.18)!important;transform:translateY(-1px)!important;color:#fff!important;}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{background:var(--s1)!important;border:1.5px solid var(--border)!important;color:var(--text)!important;border-radius:var(--r)!important;font-family:'Google Sans Text',sans-serif!important;font-size:0.9rem!important;padding:0.5rem 0.75rem!important;transition:var(--transition)!important;}
[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(249,115,22,0.12)!important;}
label[data-testid="stWidgetLabel"] p{font-family:'Google Sans',sans-serif!important;color:var(--text2)!important;font-size:0.82rem!important;font-weight:500!important;margin-bottom:0.15rem!important;}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--s2);border-radius:3px}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--accent)}
.footer{font-family:'Roboto Mono',monospace;font-size:0.6rem;color:var(--text4);text-align:center;padding:0.8rem 0 0.5rem;letter-spacing:0.04em;border-top:1px solid var(--s3);margin-top:1rem;}
.stElementContainer{margin-bottom:0!important}
[data-testid="stVerticalBlock"]>div{gap:0.3rem!important}
[data-testid="stHorizontalBlock"]>div{gap:0.4rem!important}
hr{border-color:var(--s3)!important;margin:0.5rem 0!important}
@media(max-width:768px){
    .metrics-grid{grid-template-columns:repeat(2,1fr)}
    .app-header{flex-direction:column;text-align:center;gap:0.5rem;padding:1rem}
}
</style>
""", unsafe_allow_html=True)


# ======================================
# Umbrales adaptativos
# ======================================
def _umbrales_adaptativos(n: int) -> dict:
    if n <= 5:
        return dict(subtema=0.93,tema=0.85,dedup_label=0.90,fusion_subtemas=0.92,
                    fusion_intergrupo=0.95,min_pertenencia_subtema=0.80,min_pertenencia_tema=0.75,
                    coherencia_etiqueta=0.50,sim_minima_agrupacion=0.93,sim_minima_keywords=0.93,
                    max_iter_fusion=1,num_temas_max=n,usar_paso2b=False,usar_fusion_iterativa=False)
    elif n <= 10:
        return dict(subtema=0.88,tema=0.80,dedup_label=0.85,fusion_subtemas=0.87,
                    fusion_intergrupo=0.91,min_pertenencia_subtema=0.72,min_pertenencia_tema=0.65,
                    coherencia_etiqueta=0.42,sim_minima_agrupacion=0.88,sim_minima_keywords=0.88,
                    max_iter_fusion=2,num_temas_max=min(n,5),usar_paso2b=False,usar_fusion_iterativa=False)
    elif n <= 20:
        return dict(subtema=0.83,tema=0.76,dedup_label=0.82,fusion_subtemas=0.82,
                    fusion_intergrupo=0.88,min_pertenencia_subtema=0.66,min_pertenencia_tema=0.58,
                    coherencia_etiqueta=0.38,sim_minima_agrupacion=0.84,sim_minima_keywords=0.84,
                    max_iter_fusion=3,num_temas_max=min(n//2,NUM_TEMAS_MAX),usar_paso2b=True,usar_fusion_iterativa=True)
    else:
        return dict(subtema=UMBRAL_SUBTEMA,tema=UMBRAL_TEMA,dedup_label=UMBRAL_DEDUP_LABEL,
                    fusion_subtemas=UMBRAL_FUSION_SUBTEMAS,fusion_intergrupo=UMBRAL_FUSION_INTERGRUPO,
                    min_pertenencia_subtema=UMBRAL_MIN_PERTENENCIA_SUBTEMA,min_pertenencia_tema=UMBRAL_MIN_PERTENENCIA_TEMA,
                    coherencia_etiqueta=UMBRAL_COHERENCIA_ETIQUETA,sim_minima_agrupacion=SIM_MINIMA_AGRUPACION_SUBTEMA,
                    sim_minima_keywords=SIM_MINIMA_KEYWORDS_RARAS,max_iter_fusion=MAX_ITER_FUSION,
                    num_temas_max=NUM_TEMAS_MAX,usar_paso2b=True,usar_fusion_iterativa=True)


# ======================================
# Caché Global de Embeddings
# ======================================
class EmbeddingCache:
    def __init__(self):
        self._cache: Dict[str, List[float]] = {}
        self._hits = 0
        self._misses = 0

    def _key(self, text):
        return hashlib.md5(text[:2000].encode('utf-8', errors='ignore')).hexdigest()

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
            if c is not None: results[i] = c
            else: missing.append(i)
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
# Utilidades generales
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
        try: return fn(*a, **kw)
        except Exception as e:
            if att == 2: raise e
            time.sleep(d); d *= 2

async def acall_with_retries(fn, *a, **kw):
    d = 1
    for att in range(3):
        try: return await fn(*a, **kw)
        except Exception as e:
            if att == 2: raise e
            await asyncio.sleep(d); d *= 2

def norm_key(text):
    if text is None: return ""
    return re.sub(r"[^a-z0-9]+", "", unidecode(str(text).strip().lower()))

def capitalizar_etiqueta(tema):
    if not tema or not tema.strip(): return "Sin tema"
    tema = tema.strip().lower()
    tema = corregir_tildes(tema)
    return tema[0].upper() + tema[1:]

def _frase_esta_completa(texto):
    if not texto or not texto.strip(): return False
    palabras = texto.strip().split()
    if not palabras: return False
    ultima = palabras[-1].lower().rstrip(".,;:!?")
    return unidecode(ultima) not in _TRAILING_INCOMPLETE and len(ultima) > 1

def _recortar_frase_completa(texto, max_palabras=7):
    if not texto: return "Sin tema"
    palabras = texto.strip().split()
    if len(palabras) > max_palabras: palabras = palabras[:max_palabras]
    while palabras and unidecode(palabras[-1].lower().rstrip(".,;:!?")) in _TRAILING_INCOMPLETE:
        palabras.pop()
    if not palabras: return texto.strip().split()[0] if texto.strip() else "Sin tema"
    return " ".join(palabras)

def limpiar_tema(tema):
    if not tema: return "Sin tema"
    tema = tema.strip().strip('"\'')
    for px in ["subtema:", "tema:", "categoría:", "categoria:", "category:"]:
        if tema.lower().startswith(px): tema = tema[len(px):].strip()
    tema = _recortar_frase_completa(tema, max_palabras=7)
    return capitalizar_etiqueta(tema) if tema else "Sin tema"

def limpiar_tema_geografico(tema, marca, aliases):
    if not tema: return "Sin tema"
    tl = unidecode(tema.lower())
    for n in [marca] + [a for a in aliases if a]:
        patron = r'\b' + re.escape(unidecode(n.strip().lower())) + r'\b'
        tl = re.sub(patron, '', tl)
    frases_eliminar = ["en colombia","de colombia","del pais","en el pais",
                       "territorio nacional","a nivel nacional","en todo el pais"]
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
    if not s: return ""
    s = unidecode(s.lower())
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(t for t in s.split() if t not in STOPWORDS_ES)

def _validar_estructura_subtema(etiqueta: str) -> bool:
    if not etiqueta or len(etiqueta.split()) < 2: return False
    if len(etiqueta.split()) > 7: return False
    if _PATRON_TITULAR.match(etiqueta): return False
    if _PATRON_ESTADO.search(etiqueta): return False
    palabras = etiqueta.split()
    if len(palabras) <= 4:
        nexos = {"de","del","para","sobre","en","con","por","ante","hacia",
                 "entre","sin","al","las","los","una","uno","que","como","y","o","a","e","u"}
        tiene_nexo = any(unidecode(p.lower().rstrip(".,;:!?")) in nexos for p in palabras[1:])
        if not tiene_nexo: return False
    return True

def normalize_title_for_comparison(title):
    if not isinstance(title, str): return ""
    tmp = re.split(r"\s*[:|-]\s*", title, 1)
    return re.sub(r"\W+", " ", tmp[0]).lower().strip()

def clean_title_for_output(title):
    return re.sub(r"\s*\|\s*[\w\s]+$", "", str(title)).strip()

def normalizar_tipo_medio(tipo_raw):
    if not isinstance(tipo_raw, str): return str(tipo_raw)
    t = unidecode(tipo_raw.strip().lower())
    return {
        "fm": "Radio", "am": "Radio", "radio": "Radio",
        "aire": "Televisión", "cable": "Televisión", "tv": "Televisión",
        "television": "Televisión", "televisión": "Televisión",
        "senal abierta": "Televisión", "señal abierta": "Televisión",
        "diario": "Prensa", "prensa": "Prensa",
        "revista": "Revistas", "revistas": "Revistas",
        "online": "Internet", "internet": "Internet",
        "digital": "Internet", "web": "Internet"
    }.get(t, str(tipo_raw).strip().title() or "Otro")

def texto_para_embedding(titulo, resumen, max_len=1800):
    t = str(titulo or "").strip()
    r = str(resumen or "").strip()
    return f"{t}. {t}. {t}. {r}"[:max_len]

def _validar_etiqueta_completa(etiqueta, titulos_grp=None, resumenes_grp=None, marca="", aliases=None, fallback_fn=None):
    if not etiqueta or etiqueta.strip().lower() in ("sin tema", "varios", "n/a"):
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
                + "\n".join(f"  · {t[:120]}" for t in titulos_grp[:4])
                + "\n\nREGLAS: frase nominal con preposición, terminar en sustantivo/adjetivo, "
                "tildes y ñ correctas, sin marcas ni ciudades.\n"
                'JSON: {"subtema":"..."}'
            )
            resp = call_with_retries(
                openai.ChatCompletion.create,
                model=OPENAI_MODEL_CLASIFICACION,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=80, temperature=0.1,
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
        except: pass
    if fallback_fn: return fallback_fn(titulos_grp or [])
    return capitalizar_etiqueta(recortada) if recortada and len(recortada.split()) >= 2 else "Cobertura informativa general"

def dedup_labels(etiquetas, umbral=UMBRAL_DEDUP_LABEL):
    unique = list(dict.fromkeys(etiquetas))
    if len(unique) <= 1: return etiquetas
    normed = [string_norm_label(u) for u in unique]
    n = len(unique)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[rb] = ra

    def _es_fusion_segura(s1, s2):
        antagonicos = [
            ({"aprobacion","apoyo","acuerdo"},{"rechazo","caida","desacuerdo","hundimiento"}),
            ({"aumento","crecimiento","alza","subida"},{"caida","reduccion","baja","disminucion"}),
            ({"apertura","inauguracion","inicio"},{"cierre","suspension","fin","clausura"}),
            ({"exito","logro","triunfo"},{"fracaso","derrota","problema"})
        ]
        t1 = set(s1.split()); t2 = set(s2.split())
        for pos_set, neg_set in antagonicos:
            if (t1 & pos_set and t2 & neg_set) or (t1 & neg_set and t2 & pos_set): return False
        return True

    for i in range(n):
        if not normed[i]: continue
        for j in range(i+1,n):
            if not normed[j] or find(i)==find(j): continue
            if SequenceMatcher(None,normed[i],normed[j]).ratio()>=umbral:
                if _es_fusion_segura(normed[i],normed[j]): union(i,j)

    for i in range(n):
        if not normed[i]: continue
        tokens_i = set(normed[i].split())
        if len(tokens_i)<2: continue
        for j in range(i+1,n):
            if not normed[j] or find(i)==find(j): continue
            tokens_j = set(normed[j].split())
            if len(tokens_j)<2: continue
            interseccion = tokens_i & tokens_j
            menor = min(len(tokens_i),len(tokens_j))
            if menor>0 and len(interseccion)/menor>=0.6:
                if _es_fusion_segura(normed[i],normed[j]): union(i,j)

    le = get_embeddings_batch(unique)
    vp = [(i,le[i]) for i in range(n) if le[i] is not None]
    if len(vp)>=2:
        vi, vv = zip(*vp)
        sm = cosine_similarity(np.array(vv))
        for pi in range(len(vi)):
            for pj in range(pi+1,len(vi)):
                if sm[pi][pj]>=umbral:
                    if find(vi[pi])!=find(vi[pj]):
                        if _es_fusion_segura(normed[vi[pi]],normed[vi[pj]]): union(vi[pi],vi[pj])

    freq = Counter(etiquetas)
    grupos = defaultdict(list)
    for i in range(n): grupos[find(i)].append(i)
    canon = {}
    for root, members in grupos.items():
        cands = [unique[m] for m in members]
        vc = [c for c in cands if c.lower() not in ("sin tema","varios") and _frase_esta_completa(c)]
        va = [c for c in cands if c.lower() not in ("sin tema","varios")]
        if vc: canon[root] = max(vc, key=lambda c:(freq[c],len(c)))
        elif va:
            best = max(va, key=lambda c:(freq[c],len(c)))
            r = _recortar_frase_completa(best)
            canon[root] = r if _frase_esta_completa(r) else best
        else: canon[root] = cands[0]
    lm = {unique[i]: canon[find(i)] for i in range(n)}
    return [capitalizar_etiqueta(lm.get(e,e)) for e in etiquetas]

def _fusionar_subtemas_semanticos(subtemas, textos_por_subtema, marca, aliases, umbral=UMBRAL_FUSION_SUBTEMAS):
    unique_subs = list(dict.fromkeys(subtemas))
    if len(unique_subs)<=1: return subtemas
    repr_texts = []
    for sub in unique_subs:
        txts = textos_por_subtema.get(sub,[])
        palabras = []
        for t in txts[:20]:
            for w in string_norm_label(str(t)).split():
                if len(w)>3: palabras.append(w)
        top_kw = " ".join(w for w,_ in Counter(palabras).most_common(10))
        repr_texts.append(f"{sub}. {sub}. {sub}. {top_kw}"[:600])
    emb_repr = get_embeddings_batch(repr_texts)
    valid = [(i,emb_repr[i]) for i in range(len(unique_subs)) if emb_repr[i] is not None]
    if len(valid)<2: return subtemas
    v_idx, v_emb = zip(*valid)
    sim = cosine_similarity(np.array(v_emb))
    n = len(v_idx)
    parent = list(range(n))

    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x

    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb: parent[rb]=ra

    for i in range(n):
        for j in range(i+1,n):
            if find(i)==find(j): continue
            if sim[i][j]>=umbral: union(i,j)

    grupos = defaultdict(list)
    for i in range(n): grupos[find(i)].append(v_idx[i])
    freq = Counter(subtemas)
    lm = {}
    for root, members in grupos.items():
        cands = [unique_subs[m] for m in members]
        if len(cands)==1: lm[cands[0]]=cands[0]; continue
        vc = [c for c in cands if c.lower() not in ("sin tema","varios") and _frase_esta_completa(c)]
        best = max(vc, key=lambda c:(freq.get(c,0),len(c))) if vc else max(cands, key=lambda c:(freq.get(c,0),len(c)))
        if len(cands)<=3:
            unified = _unificar_subtemas_llm(cands, textos_por_subtema, marca, aliases)
            if unified and _frase_esta_completa(unified): best = unified
        for c in cands: lm[c] = capitalizar_etiqueta(best)
    return [lm.get(s,s) for s in subtemas]

def _unificar_subtemas_llm(subtemas_a_unificar, textos_por_subtema, marca, aliases):
    subs_str = "\n".join(f"  · {s}" for s in subtemas_a_unificar)
    all_kw = []
    for sub in subtemas_a_unificar:
        for t in textos_por_subtema.get(sub,[])[:5]:
            for w in string_norm_label(str(t)).split():
                if len(w)>3: all_kw.append(w)
    kw_str = " · ".join(w for w,_ in Counter(all_kw).most_common(8))
    prompt = (
        f"Estos subtemas son variaciones del MISMO tema. "
        f"Genera UN subtema unificado (4-6 palabras) como frase nominal completa:\n\n"
        f"{subs_str}\n\nKeywords: {kw_str}\n\n"
        "REGLAS: frase coherente con preposición (de/del/para/sobre/en), "
        "sin marcas ni ciudades, tildes y ñ correctas.\n"
        'JSON: {"subtema":"..."}'
    )
    try:
        resp = call_with_retries(
            openai.ChatCompletion.create, model=OPENAI_MODEL_CLASIFICACION,
            messages=[{"role":"user","content":prompt}], max_tokens=60,
            temperature=0.05, response_format={"type":"json_object"}
        )
        u = resp.get('usage',{}) if isinstance(resp,dict) else getattr(resp,'usage',{})
        if u:
            st.session_state['tokens_input'] += (u.get('prompt_tokens') if isinstance(u,dict) else getattr(u,'prompt_tokens',0)) or 0
            st.session_state['tokens_output'] += (u.get('completion_tokens') if isinstance(u,dict) else getattr(u,'completion_tokens',0)) or 0
        raw = json.loads(resp.choices[0].message.content).get("subtema","")
        if raw: return limpiar_tema_geografico(limpiar_tema(raw), marca, aliases)
    except: pass
    return None

def get_embeddings_batch(textos, batch_size=100):
    if not textos: return []
    cache = get_embedding_cache()
    resultados, missing = cache.get_many(textos)
    if not missing: return resultados
    mt = [textos[i][:2000] if textos[i] else "" for i in missing]
    for i in range(0, len(mt), batch_size):
        batch = mt[i:i+batch_size]
        bidx = missing[i:i+batch_size]
        try:
            resp = call_with_retries(openai.Embedding.create, input=batch, model=OPENAI_MODEL_EMBEDDING)
            u = resp.get('usage',{}) if isinstance(resp,dict) else getattr(resp,'usage',{})
            if u:
                st.session_state['tokens_embedding'] += (u.get('total_tokens') if isinstance(u,dict) else getattr(u,'total_tokens',0)) or 0
            for j,d in enumerate(resp["data"]):
                oi = bidx[j]; emb = d["embedding"]
                resultados[oi] = emb; cache.put(textos[oi], emb)
        except:
            for j,t in enumerate(batch):
                oi = bidx[j]
                try:
                    r = openai.Embedding.create(input=[t], model=OPENAI_MODEL_EMBEDDING)
                    emb = r["data"][0]["embedding"]; resultados[oi]=emb; cache.put(textos[oi],emb)
                except: pass
    return resultados

class DSU:
    def __init__(self,n):
        self.p=list(range(n)); self.rank=[0]*n

    def find(self,i):
        path=[]
        while self.p[i]!=i: path.append(i); i=self.p[i]
        for node in path: self.p[node]=i
        return i

    def union(self,i,j):
        ri,rj=self.find(i),self.find(j)
        if ri==rj: return
        if self.rank[ri]<self.rank[rj]: ri,rj=rj,ri
        self.p[rj]=ri
        if self.rank[ri]==self.rank[rj]: self.rank[ri]+=1

    def grupos(self,n):
        c=defaultdict(list)
        for i in range(n): c[self.find(i)].append(i)
        return dict(c)

def agrupar_textos_similares(textos, umbral):
    if not textos: return {}
    embs = get_embeddings_batch(textos)
    valid = [(i,e) for i,e in enumerate(embs) if e is not None]
    if len(valid)<2: return {}
    idxs,M = zip(*valid)
    labels = AgglomerativeClustering(
        n_clusters=None,distance_threshold=1-umbral,metric="cosine",linkage="average"
    ).fit(np.array(M)).labels_
    g=defaultdict(list)
    for k,lbl in enumerate(labels): g[lbl].append(idxs[k])
    return dict(enumerate(g.values()))

def agrupar_por_titulo_similar(titulos):
    gid,grupos,used=0,{},set()
    norm=[normalize_title_for_comparison(t) for t in titulos]
    for i in range(len(norm)):
        if i in used or not norm[i]: continue
        grp=[i]; used.add(i)
        for j in range(i+1,len(norm)):
            if j in used or not norm[j]: continue
            if SequenceMatcher(None,norm[i],norm[j]).ratio()>=SIMILARITY_THRESHOLD_TITULOS:
                grp.append(j); used.add(j)
        if len(grp)>=2: grupos[gid]=grp; gid+=1
    return grupos

def seleccionar_representante(indices, textos):
    embs=get_embeddings_batch([textos[i] for i in indices])
    validos=[(indices[k],e) for k,e in enumerate(embs) if e is not None]
    if not validos: return indices[0],textos[indices[0]]
    idxs,M=zip(*validos)
    centro=np.mean(M,axis=0,keepdims=True)
    best=int(np.argmax(cosine_similarity(np.array(M),centro)))
    return idxs[best],textos[idxs[best]]


# ======================================
# TONO
# ======================================
class ClasificadorTono:
    def __init__(self, marca, aliases):
        self.marca = marca.strip()
        self.aliases = [a.strip() for a in (aliases or []) if a.strip()]
        self._all_names = [self.marca.lower()] + [a.lower() for a in self.aliases]

    def _menciona_marca(self, texto):
        t = unidecode(texto.lower())
        return any(m in t for m in self._all_names)

    async def _clasificar_llm(self, texto, sem):
        async with sem:
            if not self._menciona_marca(texto):
                return {"tono": "Neutro"}
            aliases_str = f" (también conocida como: {', '.join(self.aliases)})" if self.aliases else ""
            prompt = (
                f"Eres un experto analista en Relaciones Públicas y Gestión de Reputación. "
                f"Tu tarea es evaluar el impacto reputacional DIRECTO de la siguiente noticia sobre la marca '{self.marca}'{aliases_str}.\n\n"
                f"TEXTO A EVALUAR:\n{texto[:1600]}\n\n"
                f"REGLAS DE CLASIFICACIÓN ESTRICTAS:\n"
                f"🔴 NEGATIVO: La marca '{self.marca}' es CULPABLE o VÍCTIMA DIRECTA de algo malo.\n"
                f"🟢 POSITIVO: La marca '{self.marca}' LOGRA algo bueno.\n"
                f"⚪ NEUTRO: La marca se menciona SIN impacto a su imagen.\n\n"
                f'Responde ÚNICAMENTE con JSON: {{"tono": "Positivo|Negativo|Neutro"}}'
            )
            try:
                resp = await acall_with_retries(
                    openai.ChatCompletion.acreate, model=OPENAI_MODEL_CLASIFICACION,
                    messages=[{"role":"user","content":prompt}], max_tokens=40,
                    temperature=0.0, response_format={"type":"json_object"}
                )
                u = resp.get('usage',{}) if isinstance(resp,dict) else getattr(resp,'usage',{})
                if u:
                    st.session_state['tokens_input'] += (u.get('prompt_tokens') if isinstance(u,dict) else getattr(u,'prompt_tokens',0)) or 0
                    st.session_state['tokens_output'] += (u.get('completion_tokens') if isinstance(u,dict) else getattr(u,'completion_tokens',0)) or 0
                resultado = json.loads(resp.choices[0].message.content)
                tono = str(resultado.get("tono","Neutro")).strip().title()
                return {"tono": tono if tono in ("Positivo","Negativo","Neutro") else "Neutro"}
            except: return {"tono": "Neutro"}

    async def procesar_lote_async(self, textos, pbar, resumenes, titulos):
        n = len(textos); txts = textos.tolist()
        pbar.progress(0.05, "Agrupando noticias...")
        txts_emb = [texto_para_embedding(str(titulos.iloc[i]),str(resumenes.iloc[i])) for i in range(n)]
        dsu = DSU(n)
        for g in [agrupar_textos_similares(txts_emb,SIMILARITY_THRESHOLD_TONO),
                  agrupar_por_titulo_similar(titulos.tolist())]:
            for _,idxs in g.items():
                for j in idxs[1:]: dsu.union(idxs[0],j)
        grupos = dsu.grupos(n)
        reps = {cid: seleccionar_representante(idxs,txts)[1] for cid,idxs in grupos.items()}
        sem = asyncio.Semaphore(CONCURRENT_REQUESTS)
        cids = list(reps.keys())
        tasks = [self._clasificar_llm(reps[c],sem) for c in cids]
        rl = []
        for i,f in enumerate(asyncio.as_completed(tasks)):
            rl.append(await f)
            pbar.progress(0.1+0.85*(i+1)/len(tasks), f"Evaluando Reputación {i+1}/{len(tasks)}")
        rpg = {cids[i]:r for i,r in enumerate(rl)}
        final = [None]*n
        for cid,idxs in grupos.items():
            r = rpg.get(cid,{"tono":"Neutro"})
            for i in idxs: final[i]=r
        pbar.progress(1.0,"Tono completado")
        return final


# ======================================
# SUBTEMAS
# ======================================
class ClasificadorSubtema:
    def __init__(self, marca, aliases):
        self.marca = marca; self.aliases = aliases or []
        self._cache = {}; self._umbrales: dict = {}

    def _paso1(self, titulos, resumenes, dsu):
        def nt(t,n): return ' '.join(re.sub(r'[^a-z0-9\s]','',unidecode(str(t).lower())).split()[:n])
        bt,br=defaultdict(list),defaultdict(list)
        for i,(ti,re_) in enumerate(zip(titulos,resumenes)):
            a,b=nt(ti,40),nt(re_,15)
            if a: bt[hashlib.md5(a.encode()).hexdigest()].append(i)
            if b: br[hashlib.md5(b.encode()).hexdigest()].append(i)
        for bk in (bt,br):
            for idxs in bk.values():
                for j in idxs[1:]: dsu.union(idxs[0],j)

    def _paso2(self, titulos, dsu):
        norm=[normalize_title_for_comparison(t) for t in titulos]
        n=len(norm)
        for i in range(n):
            if not norm[i]: continue
            for j in range(i+1,n):
                if not norm[j] or dsu.find(i)==dsu.find(j): continue
                if SequenceMatcher(None,norm[i],norm[j]).ratio()>=SIMILARITY_THRESHOLD_TITULOS:
                    dsu.union(i,j)

    def _paso2b_keywords(self, titulos, dsu, ae):
        sim_min=self._umbrales.get('sim_minima_keywords',SIM_MINIMA_KEYWORDS_RARAS)
        stop={'el','la','los','las','un','una','unos','unas','de','del','al','en','con','por','para',
              'que','se','su','sus','es','son','fue','como','mas','pero','sin','sobre','entre','tras',
              'esta','este','esto','hay','ser','han','ha','ya','muy','otro','otra','otros','otras',
              'todo','toda','todos','todas','puede','desde','hasta','donde','cuando','quien','cual',
              'cada','nos','les','ante','bajo','nueva','nuevo','nuevos','nuevas','forma','hace','asi',
              'sera','segun','tiene','fueron','sido','hacer','dice','dijo','tambien'}
        titulo_words=[]
        for t in titulos:
            ws=set()
            for w in re.findall(r'[a-z]+',unidecode(str(t).lower())):
                if len(w)>=5 and w not in stop: ws.add(w)
            titulo_words.append(ws)
        word_freq=Counter()
        for ws in titulo_words:
            for w in ws: word_freq[w]+=1
        n=len(titulos)
        max_freq=max(2,int(n*0.03))
        rare_index=defaultdict(list)
        for i,ws in enumerate(titulo_words):
            for w in ws:
                if 2<=word_freq[w]<=max_freq: rare_index[w].append(i)
        for idxs in rare_index.values():
            for a in range(len(idxs)):
                for b in range(a+1,len(idxs)):
                    ia,ib=idxs[a],idxs[b]
                    if dsu.find(ia)==dsu.find(ib): continue
                    ea,eb=ae[ia],ae[ib]
                    if ea is None or eb is None: continue
                    sim=cosine_similarity(np.array(ea).reshape(1,-1),np.array(eb).reshape(1,-1))[0][0]
                    if sim>=sim_min: dsu.union(ia,ib)

    def _paso3(self, et, ae, dsu, pbar, ps):
        umbral_cluster=self._umbrales.get('subtema',UMBRAL_SUBTEMA)
        sim_min=self._umbrales.get('sim_minima_agrupacion',SIM_MINIMA_AGRUPACION_SUBTEMA)
        n=len(et)
        if n<2: return
        B=500
        if n<=B:
            pbar.progress(ps,"Clustering semántico...")
            ok=[(k,e) for k,e in enumerate(ae) if e is not None]
            if len(ok)<2: return
            io_,M=zip(*ok)
            sim_matrix=cosine_similarity(np.array(M))
            linkage='complete' if n<=10 else 'average'
            labels=AgglomerativeClustering(
                n_clusters=None,distance_threshold=1-umbral_cluster,
                metric='precomputed',linkage=linkage
            ).fit(1-sim_matrix).labels_
            g=defaultdict(list)
            for k,lbl in enumerate(labels): g[lbl].append(io_[k])
            for cl in g.values():
                if len(cl)<2: continue
                vecs=np.array([ae[i] for i in cl if ae[i] is not None])
                if len(vecs)<2: continue
                centroid=np.mean(vecs,axis=0)
                sims_al_centroid=cosine_similarity(vecs,centroid.reshape(1,-1)).flatten()
                todos_ok=all(s>=sim_min for s in sims_al_centroid)
                if todos_ok:
                    for j in cl[1:]: dsu.union(cl[0],j)
                else:
                    mejor_idx=int(np.argmax(sims_al_centroid))
                    repr_vec=np.array(ae[cl[mejor_idx]]).reshape(1,-1)
                    for k_local,i_global in enumerate(cl):
                        if ae[i_global] is None: continue
                        sim_vs_repr=cosine_similarity(np.array(ae[i_global]).reshape(1,-1),repr_vec)[0][0]
                        if sim_vs_repr>=sim_min: dsu.union(cl[mejor_idx],i_global)
            pbar.progress(ps+0.18,"Clustering completado")
            return
        tb=max(1,(n+B-1)//B)
        for bn_,bs in enumerate(range(0,n,B)):
            bi=list(range(bs,min(bs+B,n)))
            ok=[(idx,ae[idx]) for idx in bi if ae[idx] is not None]
            if len(ok)<2: continue
            io_,M=zip(*ok)
            sim_matrix=cosine_similarity(np.array(M))
            labels=AgglomerativeClustering(
                n_clusters=None,distance_threshold=1-umbral_cluster,
                metric='precomputed',linkage='average'
            ).fit(1-sim_matrix).labels_
            g=defaultdict(list)
            for k,lbl in enumerate(labels): g[lbl].append(io_[k])
            for cl in g.values():
                if len(cl)<2: continue
                vecs=np.array([ae[i] for i in cl if ae[i] is not None])
                if len(vecs)<2: continue
                centroid=np.mean(vecs,axis=0)
                sims=cosine_similarity(vecs,centroid.reshape(1,-1)).flatten()
                mejor_idx=int(np.argmax(sims))
                repr_vec=np.array(ae[cl[mejor_idx]]).reshape(1,-1)
                for k_local,i_global in enumerate(cl):
                    if ae[i_global] is None: continue
                    s=cosine_similarity(np.array(ae[i_global]).reshape(1,-1),repr_vec)[0][0]
                    if s>=sim_min: dsu.union(cl[mejor_idx],i_global)
            pbar.progress(ps+0.15*(bn_+1)/tb,f"Clustering {bn_+1}/{tb}...")
        pbar.progress(ps+0.16,"Unificando...")
        usar_fusion=self._umbrales.get('usar_fusion_iterativa',True)
        if usar_fusion: self._fusion(et,ae,dsu,pbar,ps+0.16)

    def _fusion(self, textos, ae, dsu, pbar, ps):
        n=len(textos)
        umbral_inter=self._umbrales.get('fusion_intergrupo',UMBRAL_FUSION_INTERGRUPO)
        max_iter=self._umbrales.get('max_iter_fusion',MAX_ITER_FUSION)
        sim_min=self._umbrales.get('sim_minima_agrupacion',SIM_MINIMA_AGRUPACION_SUBTEMA)
        for it in range(max_iter):
            grupos=dsu.grupos(n)
            if len(grupos)<2: break
            centroids,vg=[],[]
            for gid,idxs in grupos.items():
                vecs=[ae[i] for i in idxs[:50] if ae[i] is not None]
                if vecs: centroids.append(np.mean(vecs,axis=0)); vg.append(gid)
            if len(vg)<2: break
            sim=cosine_similarity(np.array(centroids))
            umbral_efectivo=max(umbral_inter,sim_min)
            pairs=sorted(
                [(sim[i][j],i,j) for i in range(len(vg)) for j in range(i+1,len(vg))
                 if sim[i][j]>=umbral_efectivo],reverse=True
            )
            fus=0
            for _,i,j in pairs:
                ri,rj=grupos[vg[i]][0],grupos[vg[j]][0]
                if dsu.find(ri)!=dsu.find(rj): dsu.union(ri,rj); fus+=1
            pbar.progress(min(ps+0.04*(it+1),0.52),f"Fusión {it+1}: {fus}")
            if fus==0: break

    def _extraer_keywords_titulos(self,titulos_grp,top_n=6):
        palabras=[]
        for t in titulos_grp[:10]:
            for w in string_norm_label(t).split():
                if len(w)>3: palabras.append(w)
        return [w for w,_ in Counter(palabras).most_common(top_n)]

    def _generar_etiqueta(self,textos_grp,titulos_grp,resumenes_grp,subtemas_existentes=None):
        tn=sorted(set(normalize_title_for_comparison(t) for t in titulos_grp if t))
        ck=hashlib.md5(("|".join(tn[:12])+f"#{len(titulos_grp)}").encode()).hexdigest()
        if ck in self._cache: return self._cache[ck]
        tm=list(dict.fromkeys(t[:130] for t in titulos_grp if t))[:6]
        rm=[str(r)[:200] for r in resumenes_grp[:3] if r and len(str(r))>20]
        kw_list=self._extraer_keywords_titulos(titulos_grp,top_n=8)
        palabras_res=[]
        for r in resumenes_grp[:5]:
            for w in string_norm_label(str(r)).split():
                if len(w)>4: palabras_res.append(w)
        kw_res=[w for w,_ in Counter(palabras_res).most_common(4)
                if w not in {unidecode(k.lower()) for k in kw_list}]
        kw=", ".join((kw_list+kw_res)[:10])
        ctx_resumenes=("\nRESÚMENES:\n"+"\n".join(f"  · {r}" for r in rm)) if rm else ""
        if len(kw_list)>=3:
            ejemplo_dinamico=(f"'{kw_list[0].title()} de {kw_list[1].title()}' o "
                              f"'{kw_list[0].title()} del {kw_list[2].title()}'")
        elif len(kw_list)>=2: ejemplo_dinamico=f"'{kw_list[0].title()} de {kw_list[1].title()}'"
        elif len(kw_list)==1: ejemplo_dinamico=f"'{kw_list[0].title()} en la región'"
        else: ejemplo_dinamico="'Proyecto de terminal de transportes'"
        lista_existentes=""
        if subtemas_existentes and len(subtemas_existentes)>0:
            lista_existentes=(
                "\n\nSUBTEMAS YA CREADOS:\n"+
                ", ".join(f"'{s}'" for s in subtemas_existentes[:15])+
                "\nREGLA: Si este grupo trata EXACTAMENTE del mismo tema, usa ese subtema."
            )
        prompt=(
            "Eres editor jefe de un periódico. "
            "Genera UN subtema periodístico (4-7 palabras) como FRASE NOMINAL para este grupo.\n\n"
            "TÍTULOS:\n"+"\n".join(f"  · {t}" for t in tm)
            +ctx_resumenes+f"\n\nPALABRAS CLAVE: {kw}"+lista_existentes
            +"\n\nREGLAS:\n"
            "  1. Frase nominal pura con preposición (de/del/para/sobre/en).\n"
            f"     CORRECTO: {ejemplo_dinamico}\n"
            "     INCORRECTO: 'Alcalde presenta proyecto', 'Gobernador anuncia inversión'\n"
            "  2. Sin marcas privadas. Tildes y ñ correctas.\n"
            'JSON: {"subtema":"..."}'
        )
        _VERBOS_FRASES=re.compile(
            r'\b(presenta|anuncia|lanza|inaugura|realiza|desarrolla|ejecuta|gestiona|'
            r'impulsa|promueve|lidera|encabeza|aprueba|firma|invierte|construye|'
            r'instala|entrega|recibe|solicita|destaca|señala|indica|afirma|propone)\b',
            re.IGNORECASE
        )
        def _tiene_verbo_conjugado(s): return bool(_VERBOS_FRASES.search(s))
        try:
            resp=call_with_retries(
                openai.ChatCompletion.create, model=OPENAI_MODEL_CLASIFICACION,
                messages=[{"role":"user","content":prompt}], max_tokens=60,
                temperature=0.0, response_format={"type":"json_object"}
            )
            u=resp.get('usage',{}) if isinstance(resp,dict) else getattr(resp,'usage',{})
            if u:
                st.session_state['tokens_input']+=(u.get('prompt_tokens') if isinstance(u,dict) else getattr(u,'prompt_tokens',0)) or 0
                st.session_state['tokens_output']+=(u.get('completion_tokens') if isinstance(u,dict) else getattr(u,'completion_tokens',0)) or 0
            raw=json.loads(resp.choices[0].message.content).get("subtema","Varios")
            et=limpiar_tema_geografico(limpiar_tema(raw),self.marca,self.aliases)
            if not et or et.strip().lower()=="sin tema":
                et=self._refinar(tm,kw,rm,forzar_preposicion=True)
            if _tiene_verbo_conjugado(et):
                et=self._refinar(tm,kw,rm,forzar_preposicion=True,prohibir_verbos=True)
            genericas={"gestión","gestion","actividades","acciones","noticias","información",
                       "informacion","eventos","varios","sin tema","actividad corporativa","gestion corporativa"}
            es_gen=string_norm_label(et) in {string_norm_label(g) for g in genericas}
            if es_gen or len(et.split())<3:
                et=self._refinar(tm,kw,rm,forzar_preposicion=True)
            if not _validar_estructura_subtema(et):
                et=self._refinar(tm,kw,rm,forzar_preposicion=True)
                if not _validar_estructura_subtema(et): et=self._fallback(titulos_grp)
            et=_validar_etiqueta_completa(et,titulos_grp=titulos_grp,resumenes_grp=resumenes_grp,
                                          marca=self.marca,aliases=self.aliases,fallback_fn=self._fallback)
        except: et=self._fallback(titulos_grp)
        et=capitalizar_etiqueta(et)
        self._cache[ck]=et
        return et

    def _refinar(self,titulos,kw,resumenes=None,forzar_preposicion=False,prohibir_verbos=False):
        ctx=("\nContexto: "+" | ".join(r[:100] for r in resumenes[:3])) if resumenes else ""
        kw_parts=[w.strip() for w in kw.split(",") if w.strip()]
        if len(kw_parts)>=2: ej_bueno=f"'{kw_parts[0].title()} de {kw_parts[1].title()}'"
        elif len(kw_parts)==1: ej_bueno=f"'{kw_parts[0].title()} en la región'"
        else: ej_bueno="'Proyecto de terminal de transportes'"
        instruccion_prep=("  OBLIGATORIO: usa preposición entre conceptos.\n") if forzar_preposicion else ""
        instruccion_verbo=("  PROHIBIDO: verbos conjugados. Solo frases nominales.\n") if prohibir_verbos else ""
        prompt=(
            "Genera UN subtema (4-7 palabras) como frase nominal sin verbo conjugado.\n\n"
            f"Títulos: {' | '.join(titulos[:5])}{ctx}\nKeywords: {kw}\n\n"
            f"{instruccion_prep}{instruccion_verbo}"
            f"CORRECTO: {ej_bueno}\nTildes y ñ correctas. Sin marcas.\n"
            'JSON: {"subtema":"..."}'
        )
        try:
            resp=call_with_retries(
                openai.ChatCompletion.create, model=OPENAI_MODEL_CLASIFICACION,
                messages=[{"role":"user","content":prompt}], max_tokens=60,
                temperature=0.2, response_format={"type":"json_object"}
            )
            raw=json.loads(resp.choices[0].message.content).get("subtema","Varios")
            et=limpiar_tema_geografico(limpiar_tema(raw),self.marca,self.aliases)
            if not _frase_esta_completa(et):
                et=_recortar_frase_completa(et)
                if not _frase_esta_completa(et): return self._fallback(titulos)
            return et
        except: return self._fallback([])

    def _fallback(self,titulos):
        if not titulos: return "Cobertura informativa general"
        palabras=[]
        for t in titulos[:5]:
            for w in string_norm_label(t).split():
                if len(w)>4: palabras.append(w)
        if palabras:
            top=[w for w,_ in Counter(palabras).most_common(3)]
            if len(top)>=2:
                frase=f"{top[0]} de {top[1]}"
                if _frase_esta_completa(frase): return capitalizar_etiqueta(frase)
                return capitalizar_etiqueta(f"{top[0]} {top[1]}")
            return capitalizar_etiqueta(top[0])
        return "Cobertura informativa general"

    def _consolidar_sinonimos_llm(self,subtemas_unicos):
        if len(subtemas_unicos)<=1: return {s:s for s in subtemas_unicos}
        prompt=(
            "Tienes estos subtemas periodísticos:\n"
            f"{', '.join(subtemas_unicos)}\n\n"
            "Encuentra SUBTEMAS SINÓNIMOS y unifícalos bajo el nombre más claro.\n"
            "Devuelve JSON donde cada clave es el subtema original y el valor el unificado.\n"
            'Ejemplo: {"Tendencias de consumo": "Tendencias de consumo", "Hábitos de compra": "Tendencias de consumo"}'
        )
        try:
            resp=call_with_retries(
                openai.ChatCompletion.create, model=OPENAI_MODEL_CLASIFICACION,
                messages=[{"role":"user","content":prompt}], max_tokens=1000,
                temperature=0.0, response_format={"type":"json_object"}
            )
            return json.loads(resp.choices[0].message.content)
        except: return {s:s for s in subtemas_unicos}

    def procesar_lote(self,col,pbar,res_puros,tit_puros):
        textos=col.tolist(); titulos=tit_puros.tolist(); resumenes=res_puros.tolist()
        n=len(textos)
        self._umbrales=_umbrales_adaptativos(n)
        u=self._umbrales
        st.caption(f"📐 Corpus: **{n}** noticias · Umbral subtema: **{u['subtema']}** · Sim mínima: **{u['sim_minima_agrupacion']}**")
        et=[texto_para_embedding(titulos[i],resumenes[i]) for i in range(n)]
        pbar.progress(0.05,"Fase 1 · Idénticas...")
        dsu=DSU(n); self._paso1(titulos,resumenes,dsu)
        pbar.progress(0.12,"Fase 2 · Títulos...")
        self._paso2(titulos,dsu)
        pbar.progress(0.18,"Embeddings...")
        ae=get_embeddings_batch(et)
        if u['usar_paso2b']:
            pbar.progress(0.15,"Fase 2b · Keywords raras...")
            self._paso2b_keywords(titulos,dsu,ae)
        pbar.progress(0.20,"Fase 3 · Clustering...")
        self._paso3(et,ae,dsu,pbar,0.20)
        gf=dsu.grupos(n); ng=len(gf)
        pbar.progress(0.55,f"Fase 4 · Etiquetando {ng} grupos...")
        mapa={}; sg=sorted(gf.items(),key=lambda x:-len(x[1])); subtemas_aprobados=[]
        for k,(lid,idxs) in enumerate(sg):
            if k%10==0: pbar.progress(0.55+0.25*(k/max(ng,1)),f"Etiquetando {k+1}/{ng}...")
            if len(idxs)>MAX_GRUPO_ETIQUETA:
                subgrupos=[idxs[i:i+MAX_GRUPO_ETIQUETA] for i in range(0,len(idxs),MAX_GRUPO_ETIQUETA)]
                for sg_ in subgrupos:
                    e=self._generar_etiqueta([textos[i] for i in sg_],[titulos[i] for i in sg_],
                                             [resumenes[i] for i in sg_],subtemas_existentes=subtemas_aprobados)
                    if e not in subtemas_aprobados: subtemas_aprobados.append(e)
                    for i in sg_: mapa[i]=e
            else:
                e=self._generar_etiqueta([textos[i] for i in idxs],[titulos[i] for i in idxs],
                                         [resumenes[i] for i in idxs],subtemas_existentes=subtemas_aprobados)
                if e not in subtemas_aprobados: subtemas_aprobados.append(e)
                for i in idxs: mapa[i]=e
        subtemas=[mapa.get(i,"Varios") for i in range(n)]
        pbar.progress(0.80,"Fase 4b · Coherencia...")
        umbral_coherencia=u['coherencia_etiqueta']
        subtemas_unicos=list(set(subtemas))
        embs_sub_lista=get_embeddings_batch(subtemas_unicos)
        emb_subtemas={sub:emb for sub,emb in zip(subtemas_unicos,embs_sub_lista) if emb is not None}
        for i in range(n):
            sub=subtemas[i]; emb_txt=ae[i]; emb_sub=emb_subtemas.get(sub)
            if emb_txt is None or emb_sub is None: continue
            sim=cosine_similarity(np.array(emb_txt).reshape(1,-1),np.array(emb_sub).reshape(1,-1))[0][0]
            if sim<umbral_coherencia:
                mejor_sub,mejor_sim=sub,sim
                for otro_sub,emb_otro in emb_subtemas.items():
                    if otro_sub==sub: continue
                    sim_otro=cosine_similarity(np.array(emb_txt).reshape(1,-1),np.array(emb_otro).reshape(1,-1))[0][0]
                    if sim_otro>mejor_sim: mejor_sim=sim_otro; mejor_sub=otro_sub
                if mejor_sub!=sub and mejor_sim>umbral_coherencia: subtemas[i]=mejor_sub
                else:
                    nueva=self._generar_etiqueta([textos[i]],[titulos[i]],[resumenes[i]],subtemas_existentes=subtemas_aprobados)
                    subtemas[i]=capitalizar_etiqueta(nueva)
                    if nueva not in subtemas_aprobados: subtemas_aprobados.append(nueva)
        pbar.progress(0.82,"Fase 5 · Dedup...")
        subtemas=dedup_labels(subtemas,u['dedup_label'])
        pbar.progress(0.86,"Fase 5b · Fusión semántica...")
        textos_por_sub=defaultdict(list)
        for i,s in enumerate(subtemas): textos_por_sub[s].append(textos[i])
        subtemas=_fusionar_subtemas_semanticos(subtemas,textos_por_sub,self.marca,self.aliases,u['fusion_subtemas'])
        pbar.progress(0.90,"Fase 6 · Consistencia...")
        subtemas=self._consistencia(subtemas,ae,pbar,u)
        indices_reclass=[i for i,s in enumerate(subtemas) if s=="_RECLASIFICAR"]
        if indices_reclass:
            pbar.progress(0.93,f"Fase 6b · Reclasificando...")
            for i in indices_reclass:
                et_ind=self._generar_etiqueta([textos[i]],[titulos[i]],[resumenes[i]],subtemas_existentes=subtemas_aprobados)
                subtemas[i]=capitalizar_etiqueta(et_ind)
                if et_ind not in subtemas_aprobados: subtemas_aprobados.append(et_ind)
        pbar.progress(0.93,"Fase 7 · Completitud...")
        subtemas=self._validar_completitud_final(subtemas,textos,titulos,resumenes)
        pbar.progress(0.97,"Fase 8 · Dedup final...")
        subtemas=dedup_labels(subtemas,u['dedup_label'])
        pbar.progress(0.99,"Consolidación sinónimos...")
        unicos_finales=list(dict.fromkeys(subtemas))
        if 1<len(unicos_finales)<=50:
            mapa_sinonimos=self._consolidar_sinonimos_llm(unicos_finales)
            subtemas=[mapa_sinonimos.get(s,s) for s in subtemas]
        subtemas=[capitalizar_etiqueta(s) for s in subtemas]
        nf=len(set(subtemas))
        pbar.progress(1.0,f"{nf} subtemas")
        st.info(f"Subtemas: **{nf}** · Grupos originales: **{ng}**")
        return subtemas

    def _validar_completitud_final(self,subtemas,textos,titulos,resumenes):
        por_subtema=defaultdict(list)
        for i,s in enumerate(subtemas): por_subtema[s].append(i)
        resultado=list(subtemas)
        for sub,idxs in por_subtema.items():
            if _frase_esta_completa(sub): continue
            recortada=_recortar_frase_completa(sub)
            if _frase_esta_completa(recortada) and len(recortada.split())>=2:
                for i in idxs: resultado[i]=capitalizar_etiqueta(recortada)
                continue
            tit_grp=[titulos[i] for i in idxs[:6]]; res_grp=[resumenes[i] for i in idxs[:3]]
            nueva=_validar_etiqueta_completa(sub,titulos_grp=tit_grp,resumenes_grp=res_grp,
                                             marca=self.marca,aliases=self.aliases,fallback_fn=self._fallback)
            for i in idxs: resultado[i]=capitalizar_etiqueta(nueva)
        return resultado

    def _consistencia(self,subtemas,ae,pbar,umbrales=None):
        min_sub=umbrales.get('min_pertenencia_subtema',UMBRAL_MIN_PERTENENCIA_SUBTEMA)
        ps=defaultdict(list)
        for i,s in enumerate(subtemas): ps[s].append(i)
        r=list(subtemas); centroids={}
        for sub,idxs in ps.items():
            vecs=[ae[i] for i in idxs if ae[i] is not None]
            if vecs: centroids[sub]=np.mean(vecs,axis=0)
        for sub in [s for s in centroids if len(ps[s])>=3]:
            idxs=ps[sub]
            if sub.lower() in ("sin tema","varios") or len(idxs)<3: continue
            vi=[(i,ae[i]) for i in idxs if ae[i] is not None]
            if len(vi)<3: continue
            v_i,v_v=zip(*vi); M=np.array(v_v)
            sims=cosine_similarity(M,centroids[sub].reshape(1,-1)).flatten()
            thr=max(0.60,np.mean(sims)-2*np.std(sims))
            for k,(oi,sv) in enumerate(zip(v_i,sims)):
                if sv>=thr: continue
                bs,bsim=sub,sv; emb=ae[oi]
                for os_,oc in centroids.items():
                    if os_==sub: continue
                    s2=cosine_similarity(np.array(emb).reshape(1,-1),oc.reshape(1,-1))[0][0]
                    if s2>bsim and s2>0.75: bsim=s2; bs=os_
                if bs!=sub: r[oi]=bs
                elif sv<min_sub: r[oi]="_RECLASIFICAR"
        return r


# ======================================
# TEMAS
# ======================================
def _construir_representacion_grupo(subtema, textos_grupo, max_textos=30):
    palabras=[]
    for t in textos_grupo[:max_textos]:
        for w in string_norm_label(str(t)).split():
            if len(w)>3: palabras.append(w)
    kw_str=" ".join(w for w,_ in Counter(palabras).most_common(12))
    return f"{subtema}. {subtema}. {kw_str}"[:500]

def _validar_estructura_tema(tema):
    if not tema or len(tema.split())<2: return False
    if len(tema.split())>4: return False
    if _PATRON_TITULAR.match(tema): return False
    if _PATRON_ESTADO.search(tema): return False
    return True

def _tema_es_igual_a_subtema(tema,subtemas_grupo):
    if not tema or not subtemas_grupo: return False
    tn=string_norm_label(tema)
    for sub in subtemas_grupo:
        sn=string_norm_label(sub)
        if not tn or not sn: continue
        if SequenceMatcher(None,tn,sn).ratio()>=0.80: return True
        if tn in sn or sn in tn: return True
    return False

def _generar_nombre_tema_llm(subtemas_grupo,textos_muestra,titulos_muestra):
    subs_list="\n".join(f"  · {s}" for s in subtemas_grupo[:8])
    palabras=[]
    for t in titulos_muestra[:15]:
        for w in string_norm_label(str(t)).split():
            if len(w)>3: palabras.append(w)
    kw=", ".join(w for w,_ in Counter(palabras).most_common(6))
    tit_muestra="\n".join(f"  · {t[:100]}" for t in list(dict.fromkeys(titulos_muestra))[:5])
    prompt=(
        "Crea UNA sección editorial (2-4 palabras) que agrupe estos subtemas.\n\n"
        "SUBTEMAS:\n"+subs_list+"\n\nTÍTULOS:\n"+tit_muestra+f"\n\nKEYWORDS: {kw}\n\n"
        "REGLAS: Sección de periódico (Política, Economía, Tecnología, Seguridad, Justicia...). "
        "Más GENERAL que los subtemas. 2-4 palabras. Tildes y ñ correctas.\n"
        "CORRECTO: 'Política', 'Gestión legislativa', 'Regulación financiera'\n"
        "INCORRECTO: 'Cinco congresistas', 'Nuevo acuerdo'\n"
        'JSON: {"tema":"..."}'
    )
    try:
        resp=call_with_retries(
            openai.ChatCompletion.create, model=OPENAI_MODEL_CLASIFICACION,
            messages=[{"role":"user","content":prompt}], max_tokens=40,
            temperature=0.05, response_format={"type":"json_object"}
        )
        raw=json.loads(resp.choices[0].message.content).get("tema","").strip().replace('"','').replace('.','')
        nombre=limpiar_tema(raw)
        if not _validar_estructura_tema(nombre): return None
        return nombre
    except: return None

def _regenerar_tema_diferente(subtemas_grupo,titulos_muestra,intento=0):
    subs_list=", ".join(subtemas_grupo[:8])
    prompt=(
        f"Subtemas: {subs_list}\n\n"
        "Genera UNA categoría GENERAL (2-3 palabras) diferente a los subtemas. "
        "Sección de periódico (Economía, Política, Tecnología, Infraestructura...). "
        "Tildes y ñ correctas.\n"
        'JSON: {"tema":"..."}'
    )
    try:
        resp=call_with_retries(
            openai.ChatCompletion.create, model=OPENAI_MODEL_CLASIFICACION,
            messages=[{"role":"user","content":prompt}], max_tokens=50,
            temperature=0.2+intento*0.1, response_format={"type":"json_object"}
        )
        return limpiar_tema(json.loads(resp.choices[0].message.content).get("tema","").strip().replace('"','').replace('.',''))
    except: return None

def consolidar_temas(subtemas, textos, pbar):
    n=len(textos); u=_umbrales_adaptativos(n)
    pbar.progress(0.05,"Preparando temas...")
    df=pd.DataFrame({'subtema':subtemas,'texto':textos})
    us=list(df['subtema'].unique())
    if len(us)<=1:
        pbar.progress(1.0,"Un tema")
        return [capitalizar_etiqueta(s) for s in subtemas]
    if n<=5 and len(us)==n:
        pbar.progress(1.0,"Corpus pequeño")
        st.info(f"Temas: **{n}** (corpus pequeño)")
        return [capitalizar_etiqueta(s) for s in subtemas]
    pbar.progress(0.10,"Representaciones...")
    textos_por_subtema=defaultdict(list)
    for i,sub in enumerate(subtemas): textos_por_subtema[sub].append(textos[i])
    repr_enriquecidas=[_construir_representacion_grupo(sub,textos_por_subtema[sub]) for sub in us]
    pbar.progress(0.20,"Embeddings...")
    emb_repr=get_embeddings_batch(repr_enriquecidas)
    emb_labels=get_embeddings_batch(us)
    ae=get_embeddings_batch(textos)
    centroids_contenido={}
    for sub in us:
        idxs=df.index[df['subtema']==sub].tolist()[:50]
        vecs=[ae[i] for i in idxs if ae[i] is not None]
        if vecs: centroids_contenido[sub]=np.mean(vecs,axis=0)
    pbar.progress(0.35,"Similitudes...")
    vs=[s for s in us if s in centroids_contenido]
    if len(vs)<2:
        pbar.progress(1.0,"Sin agrupación")
        return [capitalizar_etiqueta(s) for s in subtemas]
    idx_map={s:i for i,s in enumerate(us)}
    M_content=np.array([centroids_contenido[s] for s in vs])
    sim_content=cosine_similarity(M_content)
    has_repr=all(emb_repr[idx_map[s]] is not None for s in vs)
    has_label=all(emb_labels[idx_map[s]] is not None for s in vs)
    if has_repr and has_label:
        sim_combined=(0.50*sim_content+0.35*cosine_similarity(np.array([emb_repr[idx_map[s]] for s in vs]))+0.15*cosine_similarity(np.array([emb_labels[idx_map[s]] for s in vs])))
    elif has_repr:
        sim_combined=(0.60*sim_content+0.40*cosine_similarity(np.array([emb_repr[idx_map[s]] for s in vs])))
    else: sim_combined=sim_content
    pbar.progress(0.45,"Clustering temas...")
    dist_matrix=np.clip(1-sim_combined,0,2); np.fill_diagonal(dist_matrix,0)
    umbral_tema=u['tema']; num_temas_max=u['num_temas_max']
    linkage_temas='complete' if len(vs)<=6 else 'average'
    cl=AgglomerativeClustering(n_clusters=None,distance_threshold=1-umbral_tema,metric='precomputed',linkage=linkage_temas).fit(dist_matrix)
    if len(set(cl.labels_))>num_temas_max:
        cl=AgglomerativeClustering(n_clusters=num_temas_max,metric='precomputed',linkage=linkage_temas).fit(dist_matrix)
    clusters=defaultdict(list)
    for i,lbl in enumerate(cl.labels_): clusters[lbl].append(vs[i])
    uc=[s for s in us if s not in vs]
    mt={}; tc=len(clusters)
    pbar.progress(0.50,f"Nombres {tc} temas...")
    for k,(cid,subtemas_cluster) in enumerate(clusters.items()):
        pbar.progress(0.50+0.35*(k/max(tc,1)),f"Tema {k+1}/{tc}...")
        titulos_cluster=[]; textos_cluster=[]
        for sub in subtemas_cluster:
            for idx in df.index[df['subtema']==sub].tolist()[:10]:
                txt=str(textos[idx]); partes=txt.split('. ')
                if partes: titulos_cluster.append(partes[0][:120])
                textos_cluster.append(txt[:200])
        if len(subtemas_cluster)==1:
            nombre=_generar_nombre_tema_llm(subtemas_cluster,textos_cluster,titulos_cluster)
            if not nombre or _tema_es_igual_a_subtema(nombre,subtemas_cluster):
                nombre=_regenerar_tema_diferente(subtemas_cluster,titulos_cluster)
            if not nombre or _tema_es_igual_a_subtema(nombre,subtemas_cluster):
                p=subtemas_cluster[0].split()
                nombre=_recortar_frase_completa(" ".join(p),max_palabras=3) if len(p)>3 else subtemas_cluster[0]
        else:
            nombre=_generar_nombre_tema_llm(subtemas_cluster,textos_cluster,titulos_cluster)
            if not nombre or _tema_es_igual_a_subtema(nombre,subtemas_cluster):
                nombre=_regenerar_tema_diferente(subtemas_cluster,titulos_cluster)
            if not nombre or _tema_es_igual_a_subtema(nombre,subtemas_cluster):
                nombre=_regenerar_tema_diferente(subtemas_cluster,titulos_cluster,intento=1)
            if not nombre or _tema_es_igual_a_subtema(nombre,subtemas_cluster):
                all_words=[]
                for sub in subtemas_cluster:
                    for w in string_norm_label(sub).split():
                        if len(w)>3: all_words.append(w)
                nombre=capitalizar_etiqueta(" ".join(w for w,_ in Counter(all_words).most_common(2))) if all_words else subtemas_cluster[0]
        if not _frase_esta_completa(nombre):
            nombre=_recortar_frase_completa(nombre,max_palabras=4)
            if not _frase_esta_completa(nombre):
                freq=Counter(subtemas)
                nombre=_recortar_frase_completa(max(subtemas_cluster,key=lambda s:freq.get(s,0)),max_palabras=4)
        nombre=capitalizar_etiqueta(nombre)
        for sub in subtemas_cluster: mt[sub]=nombre
    for sub in uc: mt[sub]=capitalizar_etiqueta(sub)
    pbar.progress(0.87,"Validando pertenencia...")
    min_tema=u['min_pertenencia_tema']
    tf_inicial=[mt.get(sub,sub) for sub in subtemas]
    tema_agrupacion=defaultdict(list)
    for i,tema in enumerate(tf_inicial):
        if ae[i] is not None: tema_agrupacion[tema].append(ae[i])
    tema_centroids={t:np.mean(vecs,axis=0) for t,vecs in tema_agrupacion.items() if vecs}
    tf_validado=[]; n_forzadas=0
    for i,(sub,tema_asignado) in enumerate(zip(subtemas,tf_inicial)):
        emb=ae[i]
        if emb is not None and tema_asignado in tema_centroids:
            sim=cosine_similarity(np.array(emb).reshape(1,-1),tema_centroids[tema_asignado].reshape(1,-1))[0][0]
            if sim<min_tema:
                tf_validado.append(capitalizar_etiqueta(_recortar_frase_completa(sub,max_palabras=4)))
                n_forzadas+=1; continue
        tf_validado.append(capitalizar_etiqueta(tema_asignado))
    if n_forzadas: st.caption(f"ℹ️ {n_forzadas} noticias con baja pertenencia → tema propio asignado.")
    pbar.progress(0.88,"Dedup temas...")
    tf_validado=dedup_labels(tf_validado,u['dedup_label'])
    pbar.progress(0.90,"Fusionando temas solapados...")
    mapa_fusion=_fusionar_temas_contenidos(tf_validado)
    if mapa_fusion: tf_validado=[mapa_fusion.get(t,t) for t in tf_validado]
    pbar.progress(0.92,"Validando tema ≠ subtema...")
    tf_validado=_post_validar_tema_vs_subtema(tf_validado,subtemas)
    pbar.progress(0.95,"Completitud...")
    tf_validado=[capitalizar_etiqueta(_recortar_frase_completa(t) if not _frase_esta_completa(t) else t) for t in tf_validado]
    tf_validado=_unificar_tema_por_subtema(tf_validado,subtemas)
    st.info(f"Temas: **{len(set(tf_validado))}** (de {len(set(subtemas))} subtemas) · Máx: {num_temas_max}")
    pbar.progress(1.0,"Temas listos")
    return tf_validado

def _fusionar_temas_contenidos(temas):
    unique=list(dict.fromkeys(temas))
    if len(unique)<2: return {}
    normed={t:string_norm_label(t) for t in unique}
    mapa={}
    for i,ta in enumerate(unique):
        for tb in unique[i+1:]:
            na,nb=normed[ta],normed[tb]
            if not na or not nb: continue
            if (f" {na} " in f" {nb} ") or nb==na or nb.startswith(na+" ") or nb.endswith(" "+na):
                canon=tb if len(tb)>=len(ta) else ta
                mapa[ta if canon==tb else tb]=canon
            elif (f" {nb} " in f" {na} ") or na.startswith(nb+" ") or na.endswith(" "+nb):
                canon=ta if len(ta)>=len(tb) else tb
                mapa[tb if canon==ta else ta]=canon
    return mapa

def _post_validar_tema_vs_subtema(temas,subtemas):
    tema_a_subtemas=defaultdict(set)
    for t,s in zip(temas,subtemas): tema_a_subtemas[t].add(s)
    reemplazos={}
    for tema,subs in tema_a_subtemas.items():
        if len(subs)==1:
            sub_unico=list(subs)[0]
            tn=string_norm_label(tema); sn=string_norm_label(sub_unico)
            if tn and sn and SequenceMatcher(None,tn,sn).ratio()>=0.80:
                nuevo=_regenerar_tema_diferente([sub_unico],[])
                if nuevo and not _tema_es_igual_a_subtema(nuevo,[sub_unico]) and _frase_esta_completa(nuevo):
                    reemplazos[tema]=capitalizar_etiqueta(nuevo)
    return [reemplazos.get(t,t) for t in temas] if reemplazos else temas

def _unificar_tema_por_subtema(temas,subtemas):
    sub_to_temas=defaultdict(list)
    for t,s in zip(temas,subtemas): sub_to_temas[s].append(t)
    sub_to_best={sub:Counter(tema_list).most_common(1)[0][0] for sub,tema_list in sub_to_temas.items()}
    return [sub_to_best[s] for s in subtemas]


# ======================================
# Helpers HTML
# ======================================
def convert_html_entities(text):
    if not isinstance(text, str): return text
    text = html.unescape(text)
    def replace_hex_entity(match):
        try: return chr(int(match.group(1),16))
        except: return match.group(0)
    def replace_decimal_entity(match):
        try: return chr(int(match.group(1)))
        except: return match.group(0)
    text = re.sub(r'&#x([0-9A-Fa-f]+);', replace_hex_entity, text)
    text = re.sub(r'&#(\d+);', replace_decimal_entity, text)
    for bad, good in {'\u201c':'"','\u201d':'"','\u2018':"'",'\u2019':"'",'Â':'','â':'','€':'','™':''}.items():
        text = text.replace(bad, good)
    return text

def clean_text_field(text):
    if not isinstance(text, str): return text
    return convert_html_entities(text).strip()

def clean_cuerpo(text):
    if not isinstance(text, str) or text.strip()=='': return text
    text = convert_html_entities(text)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def corregir_texto_resumen(text):
    """Formatea el resumen para noticias gráficas (párrafos separados)."""
    if not isinstance(text, str) or not text.strip(): return text
    parrafos=[p.strip() for p in text.split('\n') if p.strip()]
    return '\n\n'.join(parrafos) if len(parrafos)>1 else text

def extract_link_from_cell(cell):
    if cell.hyperlink and cell.hyperlink.target:
        return cell.hyperlink.target
    return None


# ======================================
# Configuración (Regiones e Internet)
# ======================================
def load_config(config_file) -> tuple:
    """Carga region_map e internet_map desde Configuracion.xlsx subido."""
    config_sheets = pd.read_excel(config_file, sheet_name=None, engine='openpyxl')
    if 'Regiones' not in config_sheets or 'Internet' not in config_sheets:
        raise ValueError("El archivo de configuración debe tener hojas 'Regiones' e 'Internet'.")
    region_map = pd.Series(
        config_sheets['Regiones'].iloc[:,1].values,
        index=config_sheets['Regiones'].iloc[:,0].astype(str).str.lower().str.strip()
    ).to_dict()
    internet_map = pd.Series(
        config_sheets['Internet'].iloc[:,1].values,
        index=config_sheets['Internet'].iloc[:,0].astype(str).str.lower().str.strip()
    ).to_dict()
    return region_map, internet_map


# ======================================
# Procesamiento del dossier (nueva estructura)
# ======================================
def process_dossier_v2(dossier_file, region_map, internet_map):
    """
    Lee el dossier con la nueva estructura y retorna una lista de dicts
    con las columnas normalizadas listas para el pipeline de IA.

    Mapeo de columnas:
      NoticiaId            → ID Noticia
      Fecha                → Fecha
      Hora                 → Hora
      Medio                → Medio  (Internet: reemplazado por internet_map)
      Tipo de Medio        → Tipo de Medio (normalizado)
      Sección - Programa   → Sección - Programa
      Región               → generada desde region_map
      Título               → Titulo  ← columna de análisis
      Autor - Conductor    → Autor - Conductor
      Nro. Pagina          → Nro. Pagina
      Dimensioncm2         → Dimensión  (Gráfica) / Duración - Nro. Caracteres (AV → Dimensión)
      Duración - Nro. Char → Duración - Nro. Caracteres (Gráfica) / 0 (AV)
      CPE / Valor de Nota  → CPE
      Tier                 → Tier
      Audiencia            → Audiencia
      Tono                 → Tono (original del dossier)
      Tematica             → Tema (se sobreescribirá con IA)
      CuerpoEs             → Resumen - Aclaracion
      URL Nota AV          → Link Nota (AV, con .com.ar→.com.co)
      URL (Streaming)      → Link Nota (Gráfica)
      URL Nota             → Link (Streaming - Imagen) (Gráfica)
      Menciones / Empresa rel. → Menciones - Empresa  (expandido por ;)
    """
    wb = load_workbook(dossier_file)
    sheet = wb.active
    headers = [cell.value for cell in sheet[1] if cell.value is not None]

    raw_rows = []
    for row in sheet.iter_rows(min_row=2):
        if all(c.value is None for c in row): continue
        row_data = dict(zip(headers, [c.value for c in row[:len(headers)]]))
        # Extraer hipervínculos de columnas de links
        for lc in ['URL Nota AV','URL (Streaming - Imagen)','URL Nota','Link Nota AV']:
            if lc in headers:
                idx = headers.index(lc)
                if idx < len(row):
                    ext = extract_link_from_cell(row[idx])
                    if ext: row_data[lc] = ext
        raw_rows.append(row_data)

    rows_out = []
    for rd in raw_rows:
        tipo_raw = str(rd.get('Tipo de Medio','') or '')
        tipo = normalizar_tipo_medio(tipo_raw)
        is_av   = tipo in ('Radio','Televisión')
        is_graf = tipo in ('Prensa','Internet','Revistas')
        is_int  = tipo == 'Internet'

        medio_orig = str(rd.get('Medio','') or '').strip()
        medio = medio_orig
        if is_int:
            medio = internet_map.get(medio_orig.lower(), medio_orig)

        region = region_map.get(medio_orig.lower(), 'N/A')

        # Dimensión y Duración
        dim_raw  = rd.get('Dimensioncm2','') or ''
        dur_raw  = rd.get('Duración - Nro. Caracteres','') or ''
        if is_av:
            dimension = dur_raw   # AV: Dimensión ← Duración
            duracion  = 0         # AV: Duración ← 0
        else:
            dimension = dim_raw
            duracion  = dur_raw

        # CPE
        cpe_av    = rd.get('CPE','') or ''
        cpe_graf  = rd.get('Valor de Nota','') or ''
        cpe = cpe_av if is_av else (cpe_graf if is_graf else '')

        # Resumen
        cuerpo_raw = str(rd.get('CuerpoEs','') or '')
        cuerpo_limpio = clean_cuerpo(cuerpo_raw)
        resumen = cuerpo_limpio if is_av else corregir_texto_resumen(cuerpo_limpio)

        # Links
        url_nota_av  = str(rd.get('URL Nota AV', rd.get('Link Nota AV','')) or '').strip()
        url_streaming= str(rd.get('URL (Streaming - Imagen)','') or '').strip()
        url_nota     = str(rd.get('URL Nota','') or '').strip()

        link_nota_av_fixed = url_nota_av.replace('.com.ar','.com.co')
        if is_av:
            link_nota   = link_nota_av_fixed or None
            link_stream = None
        else:
            link_nota   = url_streaming or None
            link_stream = url_nota or None

        # Menciones
        if is_av:
            menciones_raw = str(rd.get('Menciones - Empresa','') or '')
        else:
            menciones_raw = str(rd.get('Empresa rel.', rd.get('Menciones - Empresa','')) or '')

        titulo_raw = clean_text_field(str(rd.get('Título','') or rd.get('Titulo','') or ''))
        autor_raw  = clean_text_field(str(rd.get('Autor - Conductor','') or ''))
        seccion_raw= clean_text_field(str(rd.get('Sección - Programa','') or ''))
        tono_orig  = clean_text_field(str(rd.get('Tono','') or ''))
        tema_orig  = clean_text_field(str(rd.get('Tematica','') or ''))

        # Fecha
        fecha_val = rd.get('Fecha','')
        try:
            if fecha_val:
                fecha_val = pd.to_datetime(fecha_val, dayfirst=True, errors='coerce')
        except: pass

        base = {
            'ID Noticia'                  : rd.get('NoticiaId',''),
            'Fecha'                       : fecha_val,
            'Hora'                        : rd.get('Hora',''),
            'Medio'                       : medio,
            'Tipo de Medio'               : tipo,
            'Sección - Programa'          : seccion_raw,
            'Región'                      : region,
            'Titulo'                      : titulo_raw,   # key interno para el pipeline
            'Autor - Conductor'           : autor_raw,
            'Nro. Pagina'                 : rd.get('Nro. Pagina',''),
            'Dimensión'                   : dimension,
            'Duración - Nro. Caracteres'  : duracion,
            'CPE'                         : cpe,
            'Tier'                        : rd.get('Tier',''),
            'Audiencia'                   : rd.get('Audiencia',''),
            'Tono'                        : tono_orig,
            '_Tema_orig'                  : tema_orig,    # guardamos para referencia
            'Resumen - Aclaracion'        : resumen,
            '_link_nota'                  : link_nota,
            '_link_stream'                : link_stream,
            'is_duplicate'                : False,
        }

        # Expansión por ; en Menciones
        menciones_lista = [m.strip() for m in menciones_raw.split(';') if m.strip()]
        if not menciones_lista: menciones_lista = ['']
        for m in menciones_lista:
            row_copy = dict(base)
            row_copy['Menciones - Empresa'] = m
            rows_out.append(row_copy)

    return rows_out


def detectar_duplicados_v2(rows):
    """
    Detección de duplicados adaptada a la nueva estructura.
    Usa Título + Medio + Tipo de Medio como señales.
    """
    seen_titulo: Dict[tuple, int] = {}
    for i, row in enumerate(rows):
        if row.get('is_duplicate'): continue
        tipo   = row.get('Tipo de Medio','')
        medio  = norm_key(row.get('Medio',''))
        titulo = normalize_title_for_comparison(row.get('Titulo',''))
        menciones = norm_key(row.get('Menciones - Empresa',''))

        # Internet: deduplicar por link
        if tipo == 'Internet':
            link = row.get('_link_nota') or ''
            if link and menciones:
                k = (_normalizar_url(link), menciones)
                if k in seen_titulo:
                    row['is_duplicate'] = True
                    row['ID duplicada'] = rows[seen_titulo[k]].get('ID Noticia','')
                    continue
                seen_titulo[k] = i

        # Radio/TV: deduplicar por medio + hora + menciones
        elif tipo in ('Radio','Televisión'):
            hora = str(row.get('Hora','') or '').strip()
            if medio and hora and menciones:
                k = (medio, hora, menciones)
                if k in seen_titulo:
                    row['is_duplicate'] = True
                    row['ID duplicada'] = rows[seen_titulo[k]].get('ID Noticia','')
                else:
                    seen_titulo[k] = i

        # Prensa/Revistas: deduplicar por título similar
        elif tipo in ('Prensa','Revistas') and titulo and menciones:
            k = (medio, menciones)
            if k not in seen_titulo:
                seen_titulo[k] = i
            else:
                prev_titulo = normalize_title_for_comparison(rows[seen_titulo[k]].get('Titulo',''))
                if titulo and prev_titulo and SequenceMatcher(None,titulo,prev_titulo).ratio()>=SIMILARITY_THRESHOLD_TITULOS:
                    row['is_duplicate'] = True
                    row['ID duplicada'] = rows[seen_titulo[k]].get('ID Noticia','')

    return rows

def _normalizar_url(url: str) -> str:
    if not url: return ""
    url = url.strip().lower()
    url = re.sub(r'^https?://','',url)
    url = re.sub(r'^www\.','',url)
    url = url.rstrip('/')
    return url


# ======================================
# Generación del Excel de salida
# ======================================
ORDER_SALIDA = [
    "ID Noticia", "Fecha", "Hora", "Medio", "Tipo de Medio", "Región",
    "Sección - Programa", "Titulo", "Autor - Conductor", "Nro. Pagina",
    "Dimensión", "Duración - Nro. Caracteres", "CPE", "Audiencia", "Tier",
    "Tono", "Tono IA", "Tema", "Subtema",
    "Link Nota", "Resumen - Aclaracion", "Link (Streaming - Imagen)",
    "Menciones - Empresa", "ID duplicada"
]

NUM_COLS = {"ID Noticia","Nro. Pagina","Dimensión","Duración - Nro. Caracteres","CPE","Tier","Audiencia"}

def generate_output_excel_v2(rows):
    wb = Workbook(); ws = wb.active; ws.title = "Resultado"
    ls = NamedStyle(name="HL", font=Font(color="0000FF", underline="single"))
    if "HL" not in wb.style_names: wb.add_named_style(ls)
    ws.append(ORDER_SALIDA)
    for row in rows:
        out = []; links = {}
        for ci, h in enumerate(ORDER_SALIDA, 1):
            if h == 'Link Nota':
                val = row.get('_link_nota')
            elif h == 'Link (Streaming - Imagen)':
                val = row.get('_link_stream')
            else:
                val = row.get(h)

            cv = None
            if h == 'Fecha' and val is not None and pd.notna(val):
                cv = val.to_pydatetime() if isinstance(val, pd.Timestamp) else val
            elif h in NUM_COLS:
                try: cv = float(val) if val is not None and str(val).strip()!='' else None
                except: cv = str(val) if val is not None else None
            elif isinstance(val, str) and val.startswith('http'):
                cv = 'Link'
                links[ci] = val
            elif val is not None and val != '':
                cv = str(val)
            out.append(cv)

        ws.append(out)
        for ci, url in links.items():
            cell = ws.cell(row=ws.max_row, column=ci)
            cell.hyperlink = url; cell.style = "HL"

    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


# ======================================
# Proceso principal async
# ======================================
async def run_full_process_async(dossier_file, config_file, bn, ba):
    st.session_state.update({'tokens_input':0,'tokens_output':0,'tokens_embedding':0})
    get_embedding_cache().clear()
    t0 = time.time()

    try:
        openai.api_key = st.secrets["OPENAI_API_KEY"]
        openai.aiosession.set(None)
    except:
        st.error("OPENAI_API_KEY no encontrado en secrets.")
        st.stop()

    # Paso 1: Configuración
    with st.status("Paso 1 · Cargando configuración", expanded=True) as s:
        try:
            region_map, internet_map = load_config(config_file)
            s.update(label=f"✓ Paso 1 · {len(region_map)} regiones, {len(internet_map)} medios internet", state="complete")
        except Exception as e:
            st.error(f"Error en Configuracion.xlsx: {e}")
            st.stop()

    # Paso 2: Procesamiento del dossier
    with st.status("Paso 2 · Procesando dossier", expanded=True) as s:
        rows = process_dossier_v2(dossier_file, region_map, internet_map)
        rows = detectar_duplicados_v2(rows)
        total = len(rows)
        dups  = sum(1 for r in rows if r.get('is_duplicate'))
        uniq  = total - dups
        s.update(label=f"✓ Paso 2 · {total} filas, {dups} duplicadas, {uniq} únicas", state="complete")

    # Marcar duplicadas con placeholders
    for row in rows:
        if row.get('is_duplicate'):
            row.update({'Tono IA':'Duplicada','Tema':'-','Subtema':'-'})

    # Solo procesar las únicas
    ta = [r for r in rows if not r.get('is_duplicate')]

    if ta:
        df = pd.DataFrame(ta)
        df['_txt'] = df.apply(
            lambda r: texto_para_embedding(str(r.get('Titulo','')), str(r.get('Resumen - Aclaracion',''))),
            axis=1
        )

        # Embeddings
        with st.status("Embeddings...", expanded=True) as s:
            _ = get_embeddings_batch(df['_txt'].tolist())
            s.update(label=f"✓ {get_embedding_cache().stats()}", state="complete")

        # Paso 3: Tono
        with st.status("Paso 3 · Tono (Reputación IA)", expanded=True) as s:
            pb = st.progress(0)
            res = await ClasificadorTono(bn, ba).procesar_lote_async(
                df['_txt'], pb, df['Resumen - Aclaracion'], df['Titulo']
            )
            df['Tono IA'] = [r['tono'] for r in res]
            s.update(label="✓ Paso 3 · Tono completado", state="complete")

        # Paso 4: Subtemas y Temas
        with st.status("Paso 4 · Clasificación (Subtema + Tema)", expanded=True) as s:
            pb = st.progress(0)
            subtemas = ClasificadorSubtema(bn, ba).procesar_lote(
                df['_txt'], pb, df['Resumen - Aclaracion'], df['Titulo']
            )
            temas = consolidar_temas(subtemas, df['_txt'].tolist(), pb)
            df['Subtema'] = subtemas
            df['Tema']    = temas
            s.update(label="✓ Paso 4 · Clasificación completada", state="complete")

        # Volcar resultados de vuelta a rows
        df_indexed = df.copy()
        df_indexed.index = [r for r in range(len(ta))]
        for i, row in enumerate(ta):
            orig_idx = rows.index(row)
            rows[orig_idx]['Tono IA'] = df.iloc[i]['Tono IA']
            rows[orig_idx]['Subtema'] = df.iloc[i]['Subtema']
            rows[orig_idx]['Tema']    = df.iloc[i]['Tema']

    gc.collect()

    ci = (st.session_state['tokens_input']     / 1e6) * PRICE_INPUT_1M
    co = (st.session_state['tokens_output']    / 1e6) * PRICE_OUTPUT_1M
    ce = (st.session_state['tokens_embedding'] / 1e6) * PRICE_EMBEDDING_1M

    with st.status("Paso 5 · Generando Excel", expanded=True) as s:
        st.session_state["output_data"]     = generate_output_excel_v2(rows)
        st.session_state["output_filename"] = f"Informe_IA_{bn.replace(' ','_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        st.session_state["processing_complete"] = True
        st.session_state.update({
            "brand_name": bn, "brand_aliases": ba,
            "total_rows": total, "unique_rows": uniq, "duplicates": dups,
            "process_duration": f"{time.time()-t0:.0f}s",
            "process_cost": f"${ci+co+ce:.4f} USD",
            "cache_stats": get_embedding_cache().stats()
        })
        s.update(label=f"✓ Completado · {get_embedding_cache().stats()}", state="complete")


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
            <div class="app-header-title">Análisis de Noticias</div>
            <div class="app-header-version">v19.0 · Nueva estructura de dossier · Tono, Tema y Subtema por IA</div>
        </div>
        <div class="app-header-badge">IA</div>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.get("processing_complete", False):
        # ── Configuración de marca ──────────────────────────────────────────
        st.markdown('<div class="sec-label">Configuración de marca</div>', unsafe_allow_html=True)
        cl, cr = st.columns([3,2])
        with cl:
            bn  = st.text_input("Marca principal", placeholder="Ej: Bancolombia", key="bn")
            bat = st.text_input("Alias (separados por ;)", placeholder="Ej: Grupo Bancolombia;Ban", key="ba")

        st.markdown('<div class="sec-label">Archivos</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📋 Dossier** — nueva estructura")
            f_dossier = st.file_uploader(
                "Dossier (.xlsx)", type=["xlsx"],
                label_visibility="collapsed", key="f_dossier"
            )
        with col2:
            st.markdown("**⚙️ Configuracion.xlsx** — hojas Regiones e Internet")
            f_config = st.file_uploader(
                "Configuracion.xlsx", type=["xlsx"],
                label_visibility="collapsed", key="f_config"
            )

        st.markdown(
            f'<div class="cluster-info">'
            f'<b>Parámetros</b> · Sub={UMBRAL_SUBTEMA} · Tema={UMBRAL_TEMA} · '
            f'Máx={NUM_TEMAS_MAX} · FusInter={UMBRAL_FUSION_INTERGRUPO} · '
            f'FusSem={UMBRAL_FUSION_SUBTEMAS} · Dedup={UMBRAL_DEDUP_LABEL} · '
            f'SimMin={SIM_MINIMA_AGRUPACION_SUBTEMA} (adaptativos según n)'
            f'</div>',
            unsafe_allow_html=True
        )

        if st.button("▶ Iniciar análisis", use_container_width=True, type="primary"):
            if not f_dossier or not f_config or not (bn or '').strip():
                st.error("Completa todos los campos: marca, dossier y configuración.")
            else:
                al = [a.strip() for a in bat.split(";") if a.strip()]
                asyncio.run(run_full_process_async(f_dossier, f_config, bn.strip(), al))
                st.rerun()
    else:
        # ── Resultados ──────────────────────────────────────────────────────
        total = st.session_state.total_rows
        uniq  = st.session_state.unique_rows
        dups  = st.session_state.duplicates
        dur   = st.session_state.process_duration
        cost  = st.session_state.get("process_cost","$0.00")

        st.markdown(
            '<div class="success-banner"><div class="success-icon">✓</div>'
            '<div><div class="success-title">Análisis completado</div>'
            '<div class="success-sub">Informe listo para descargar</div></div></div>',
            unsafe_allow_html=True
        )
        st.markdown(f"""
        <div class="metrics-grid">
          <div class="metric-card m-total"><div class="metric-val" style="color:var(--text)">{total}</div><div class="metric-lbl">Total</div></div>
          <div class="metric-card m-unique"><div class="metric-val" style="color:var(--green)">{uniq}</div><div class="metric-lbl">Únicas</div></div>
          <div class="metric-card m-dup"><div class="metric-val" style="color:var(--amber)">{dups}</div><div class="metric-lbl">Duplicados</div></div>
          <div class="metric-card m-time"><div class="metric-val" style="color:var(--blue)">{dur}</div><div class="metric-lbl">Tiempo</div></div>
          <div class="metric-card m-cost"><div class="metric-val" style="color:var(--accent)">{cost}</div><div class="metric-lbl">Costo</div></div>
        </div>""", unsafe_allow_html=True)

        if 'cache_stats' in st.session_state:
            st.caption(f"📊 {st.session_state['cache_stats']}")

        c1, c2 = st.columns(2)
        c1.download_button(
            "⬇ Descargar informe",
            data=st.session_state.output_data,
            file_name=st.session_state.output_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, type="primary"
        )
        if c2.button("Nuevo análisis", use_container_width=True):
            pwd = st.session_state.get("password_correct")
            st.session_state.clear()
            st.session_state.password_correct = pwd
            st.rerun()

    st.markdown(
        '<div class="footer">v19.0 · Análisis de Noticias con IA · Nueva estructura de dossier</div>',
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
