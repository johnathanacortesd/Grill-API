# ======================================
# Motor de Análisis con IA (ai_analyzer.py)
# ======================================
import os
import re
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Callable, Set, Sequence, Union
from collections import Counter
import pandas as pd
from openai import OpenAI
from rapidfuzz import fuzz
from unidecode import unidecode

logger = logging.getLogger("ai_analyzer")

FORBIDDEN_TRAILING_WORDS = {
    "de", "del", "la", "el", "los", "las", "en", "para", "por", "con", "a", "al",
    "y", "o", "u", "e", "un", "una", "unos", "unas", "su", "sus", "sobre", "tras",
    "hacia", "desde", "sin", "que", "se"
}

STOPWORDS_ES = {
    "de", "del", "la", "el", "los", "las", "en", "para", "por", "con", "a", "al",
    "y", "o", "u", "e", "un", "una", "unos", "unas", "sobre", "tras", "este", "esta",
    "estos", "estas", "fue", "fueron", "era", "eran", "como", "mas", "pero", "sus",
    "que", "se", "ha", "han", "hay", "les", "nos", "son"
}

INSTITUTIONAL_PREFIXES = [
    "fundacion", "clinica", "hospital", "universidad", "instituto", "institucion",
    "colegio", "banco", "aerolinea", "empresa", "grupo", "corporacion", "alcaldia",
    "gobernacion", "ministerio", "centro", "complejo", "organizacion", "sociedad",
    "asociacion", "proyecto", "urbanizacion"
]

SUBTEMA_MIN_WORDS = 3
SUBTEMA_MAX_WORDS = 7
FACT_CONTEXT_MAX_CHARS = 700
TRAGEDY_GUARD_MAX_CHARS = 35
TEMA_TITLE_MAX_CHARS = 160
ALIAS_SPLIT_RE = re.compile(r"[,;\n]")

# 21 cubos cerrados (SPEC_TONO_TEMA). Nunca se emite "Otros".
DEFAULT_CUBOS = [
    "Educación Superior",
    "Estudiantes",
    "Sector Salud",
    "Gestión Institucional",
    "Gestión Tributaria",
    "Hitos y Aniversarios",
    "Gestión de Emergencias",
    "Infraestructura",
    "Seguridad Ciudadana",
    "Relaciones Gremiales",
    "Investigación y Ciencia",
    "Cultura y Deporte",
    "Medio Ambiente",
    "Economía y Empresa",
    "Gobierno y Política",
    "Responsabilidad Social",
    "Tecnología e Innovación",
    "Laboral y Empleo",
    "Legal y Regulatorio",
    "Comunidad y Territorio",
    "Comunicaciones y Medios",
]

FORBIDDEN_TEMA_NORMS = {
    "otros", "otro", "general", "varios", "miscelanea", "sin clasificar",
    "sin tema", "actualidad", "cobertura", "",
}

CUBO_KEYWORDS = {
    "Educación Superior": (
        "universidad", "pregrado", "posgrado", "academ", "carrera", "facultad",
        "rector", "beca", "docente", "matricul", "educacion superior",
    ),
    "Estudiantes": (
        "estudiante", "egresad", "alumno", "bienestar universitario",
    ),
    "Sector Salud": (
        "salud", "hospital", "clinica", "medico", "medicina", "paciente",
        "quirurg", "enfermedad", "eps", "achc",
    ),
    "Gestión Tributaria": (
        "aduan", "dian", "fiscal", "tributar", "impuesto", "arancel",
    ),
    "Hitos y Aniversarios": (
        "aniversario", "celebracion", "decadas", "homenaje", "reconocimiento",
    ),
    "Gestión de Emergencias": (
        "rescate", "bombero", "emergencia", "siniestro", "accidente", "desastre",
        "sismo", "terremoto", "inundacion",
    ),
    "Infraestructura": (
        "obra", "construccion", "via", "infraestructura", "puente", "sede",
        "campus", "edificio",
    ),
    "Seguridad Ciudadana": (
        "seguridad", "policia", "captura", "hurto", "delito", "fiscalia", "crimen",
    ),
    "Relaciones Gremiales": (
        "convenio", "acuerdo", "alianza", "gremio", "liderazgo",
    ),
    "Investigación y Ciencia": (
        "investigacion", "ciencia", "laboratorio", "cientific", "patente",
    ),
    "Cultura y Deporte": (
        "cultura", "deporte", "torneo", "campeon", "festival", "concierto",
    ),
    "Medio Ambiente": (
        "ambiente", "sostenib", "clima", "contamin", "recicl", "bosque",
    ),
    "Economía y Empresa": (
        "economia", "empresa", "mercado", "inversion", "pib",
    ),
    "Gobierno y Política": (
        "gobierno", "congreso", "alcalde", "ministro", "eleccion", "politica",
    ),
    "Responsabilidad Social": (
        "responsabilidad social", "rsc", "donacion", "voluntari",
        "comunidad vulnerable",
    ),
    "Tecnología e Innovación": (
        "tecnolog", "innovacion", "digital", "software", "inteligencia artificial",
    ),
    "Laboral y Empleo": (
        "laboral", "sindical", "desempleo", "nomina", "contrato de trabajo",
    ),
    "Legal y Regulatorio": (
        "demanda", "fallo", "tutela", "superintendencia", "regulacion", "norma",
    ),
    "Comunidad y Territorio": (
        "comunidad", "barrio", "territorio", "region", "municipio",
    ),
    "Comunicaciones y Medios": (
        "entrevista", "rueda de prensa", "comunicado", "periodist", "medios",
    ),
    "Gestión Institucional": (
        "institucion", "directivo", "gobernanza", "rectoria", "junta",
    ),
}

SPOKESPERSON_ROLES = (
    "rector", "rectora", "vicerrector", "vicerrectora", "presidente", "presidenta",
    "director", "directora", "gerente", "vocero", "vocera", "portavoz",
    "decano", "decana", "canciller", "secretario general", "secretaria general",
)

CONTRIBUTION_VERBS = (
    "aporta", "aportan", "aporto", "dona", "donan", "dono",
    "apoya", "apoyan", "apoyo", "respalda", "respaldan", "respaldo",
    "celebra", "celebran", "celebro", "inaugura", "inauguran", "inauguro",
    "lanza", "lanzan", "lanzo", "firma", "firman", "firmo",
    "impulsa", "impulsan", "impulso", "entrega", "entregan", "entrego",
    "ofrece", "ofrecen", "ofrecio", "otorga", "otorgan", "otorgo",
    "lidera", "lideran", "lidero", "financia", "financian", "financio",
    "abre", "abren", "abrio", "acompana", "acompanan", "acompanamos",
    "felicita", "felicitan", "felicito", "pone en marcha", "pusieron en marcha",
    "abren espacio", "rinde homenaje",
)

TRAGIC_MARKERS = (
    "fallec", "muert", "deceso", "victima", "tragedia", "sismo", "terremoto",
    "inundacion", "accidente", "obituario", "desastre", "catastrofe", "herido",
    "fatal", "luto",
)

DIRECTED_CRITICISM_MARKERS = (
    "denuncia", "queja", "demanda", "sancion", "investigacion por", "corrupcion",
    "negligen", "irregularidad", "fraude", "escandalo", "plagio",
    "cobros excesivos", "falla en el servicio", "mala practica", "senalan a",
    "acusan a", "responsabilizan",
)

LOCATIVE_MARKERS = (
    "en la sede", "en su sede", "cerca de la sede", "frente a la sede",
    "en el campus", "en las instalaciones", "en la sucursal", "predios de",
    "sede de", "sedes de", "ubicad", "en las inmediaciones",
)

ENTITY_MASK_TOKEN = "[ENTIDAD]"

def clean_text_strictly_no_links(text: str) -> str:
    """Elimina URLs (http, https, www), diccionarios y la palabra 'Link'."""
    if not text:
        return ""
    if isinstance(text, dict):
        val = text.get("value", "")
        text = str(val)

    s = str(text).strip()
    if s.lower() in ("nan", "none", "null", "link", "link nota", "ver nota"):
        return ""

    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"www\.\S+", "", s)
    s = re.sub(r"\b(?:http|https)://\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()

    if s.lower() in ("link", "link nota", ""):
        return ""
    return s

def normalize_text_for_matching(text: str) -> str:
    if not text:
        return ""
    t = unidecode(str(text).lower().strip())
    t = re.sub(r"^(?:imagenes|en imagenes|fotos|en fotos|video|en video|en vivo)\s*\|\s*", "", t)
    words = re.findall(r"\b[a-z0-9]+\b", t)
    
    stemmed = []
    for w in words:
        if w in STOPWORDS_ES or len(w) < 2:
            continue
        if w.endswith("ces") and len(w) > 4:
            w = w[:-3] + "z"
        elif w.endswith("es") and len(w) > 4:
            w = w[:-2]
        elif w.endswith("s") and not w.endswith("is") and len(w) > 3:
            w = w[:-1]
        stemmed.append(w)
        
    return " ".join(stemmed)

def get_content_words_set(text_norm: str) -> Set[str]:
    return {w for w in text_norm.split() if len(w) > 2 and w not in STOPWORDS_ES}

def get_lead_content_words(text_norm: str, n_words: int = 3) -> Tuple[str, ...]:
    words = [w for w in text_norm.split() if len(w) > 2 and w not in STOPWORDS_ES]
    return tuple(words[:n_words])

def extract_event_anchor(title_raw: str) -> str:
    if not title_raw:
        return ""
    parts = re.split(r"\s*[:|-]\s*", title_raw, 1)
    if len(parts) > 1 and len(parts[0].strip()) >= 10:
        return normalize_text_for_matching(parts[0])
    return ""

def parse_alias_list(aliases: Optional[Union[str, Sequence[str]]] = None) -> List[str]:
    """Parte alias por coma, punto y coma o salto de línea en cualquier sitio de parseo."""
    if aliases is None:
        return []
    if isinstance(aliases, str):
        parts = ALIAS_SPLIT_RE.split(aliases)
        return [p.strip() for p in parts if p.strip()]
    out: List[str] = []
    seen = set()
    for item in aliases:
        for part in ALIAS_SPLIT_RE.split(str(item)):
            cleaned = part.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                out.append(cleaned)
    return out


def _norm_label(text: str) -> str:
    return unidecode((text or "").strip().lower())


def split_text_units(text: str) -> List[str]:
    """Parte un campo (título o cuerpo) en unidades oracionales. Nunca mezcla campos."""
    if not text:
        return []
    chunks = [p.strip() for p in re.split(r"(?<=[.!?\n])\s+", str(text)) if p.strip()]
    units: List[str] = []
    for chunk in chunks:
        pieces = [p.strip() for p in re.split(r"\s*\|\s*", chunk) if p.strip()]
        units.extend(pieces or [chunk])
    return units


def mask_similar_entities(text: str, brand_regexes: List[str]) -> str:
    """Enmascara otras entidades institucionales parecidas antes de buscar la marca."""
    if not text:
        return ""
    prefix_alt = "|".join(re.escape(p) for p in INSTITUTIONAL_PREFIXES)
    # No cruzar conjunciones (Universidad X y Universidad Y) ni absorber la marca.
    pattern = (
        rf"\b(?:{prefix_alt})"
        rf"(?:\s+(?:de(?:l|\s+la)?))?"
        rf"(?:\s+(?!y\b|e\b|o\b)[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9][\w.\-]*){{1,4}}"
    )

    def _repl(match: re.Match) -> str:
        span = match.group(0)
        span_norm = unidecode(span.lower())
        if brand_regexes and any(re.search(rx, span_norm) for rx in brand_regexes):
            return span
        return ENTITY_MASK_TOKEN

    return re.sub(pattern, _repl, text, flags=re.IGNORECASE)


def sentence_mentions_brand(
    sentence: str,
    brand_regexes: List[str],
    brand: str = "",
    aliases: Optional[Sequence[str]] = None,
) -> bool:
    if not sentence:
        return False
    s_norm = unidecode(sentence.lower())
    if brand_regexes and any(re.search(rx, s_norm) for rx in brand_regexes):
        return True
    targets = parse_alias_list(aliases)
    if brand:
        targets = [brand] + targets
    for tgt in targets:
        tgt_norm = unidecode(tgt.lower().strip())
        if tgt_norm and re.search(rf"\b{re.escape(tgt_norm)}\b", s_norm):
            return True
        if tgt_norm:
            role_alt = "|".join(re.escape(r) for r in SPOKESPERSON_ROLES)
            if re.search(
                rf"\b(?:{role_alt})\b(?:\s+\w+){{0,4}}\s+(?:de\s+(?:la\s+)?)?{re.escape(tgt_norm)}\b",
                s_norm,
            ):
                return True
    return False


def _brand_units_from_field(
    field_text: str,
    brand_regexes: List[str],
    brand: str,
    aliases: List[str],
) -> List[str]:
    """Oraciones de UN campo que nombran marca/alias/voceros, tras enmascarar entidades ajenas."""
    clean = clean_text_strictly_no_links(field_text)
    if not clean:
        return []
    matched: List[str] = []
    for unit in split_text_units(clean):
        masked = mask_similar_entities(unit, brand_regexes)
        if sentence_mentions_brand(masked, brand_regexes, brand, aliases):
            if unit not in matched:
                matched.append(unit)
    if matched:
        return matched

    # Último recurso: ventana DENTRO del mismo campo (nunca concatenar con el otro).
    field_norm = unidecode(clean.lower())
    for rx in brand_regexes or []:
        for m in re.finditer(rx, field_norm):
            start = max(0, m.start() - 120)
            end = min(len(clean), m.end() + 150)
            snippet = clean_text_strictly_no_links(clean[start:end])
            masked_snip = mask_similar_entities(snippet, brand_regexes)
            if snippet and sentence_mentions_brand(masked_snip, brand_regexes, brand, aliases):
                if snippet not in matched:
                    matched.append(snippet)
            if len(matched) >= 2:
                return matched
        if matched:
            return matched
    return matched


def generate_brand_variants(brand: str, aliases: List[str]) -> List[str]:
    aliases = parse_alias_list(aliases)
    raw_inputs = [brand] + [a for a in aliases if a.strip()]
    variants_set = set()

    for item in raw_inputs:
        base = unidecode(item.lower().strip())
        if not base:
            continue
        variants_set.add(base)

        acronym_match = re.search(r"\(([a-z0-9]{2,6})\)", base)
        if acronym_match:
            acronym = acronym_match.group(1)
            variants_set.add(acronym)
            variants_set.add(r"\b" + r"\.?\s*".join(list(acronym)) + r"\.?\b")
            base = re.sub(r"\([a-z0-9]{2,6}\)", "", base).strip()
            variants_set.add(base)

        if len(base) <= 5 and base.isalpha():
            variants_set.add(r"\b" + r"\.?\s*".join(list(base)) + r"\.?\b")
            continue

        if "santa fe" in base:
            variants_set.add(base.replace("santa fe", "santafe"))
            variants_set.add("santa fe")
            variants_set.add("santafe")
            variants_set.add("clinica santa fe")
            variants_set.add("hospital santa fe")
            variants_set.add("fundacion santa fe")

        if "serena del mar" in base:
            variants_set.add("serena")
            variants_set.add("hospital serena")
            variants_set.add("hospital serena del mar")
            variants_set.add("clinica serena")
            variants_set.add("clinica serena del mar")

        for prefix in ["fundacion", "clinica", "hospital", "universidad", "instituto", "asociacion"]:
            if base.startswith(prefix + " "):
                core = base[len(prefix):].strip()
                if len(core) >= 4:
                    variants_set.add(core)
                    for alt_p in ["clinica", "hospital", "fundacion", "centro"]:
                        variants_set.add(f"{alt_p} {core}")

    sorted_variants = sorted(list(variants_set), key=lambda x: len(x), reverse=True)
    compiled_regexes = []
    for v in sorted_variants:
        if v.startswith(r"\b"):
            compiled_regexes.append(v)
        else:
            compiled_regexes.append(rf"\b{re.escape(v)}\b")
            
    return compiled_regexes

def extract_brand_context(
    resumen: str,
    titulo: str,
    brand_regexes: List[str],
    brand: str = "",
    aliases: Optional[Sequence[str]] = None,
) -> str:
    """Evidencia de marca: oraciones de título y cuerpo por separado que nombran la marca.

    Nunca concatena título+cuerpo antes de buscar. Sin mención → cadena vacía
    (el tono debe ser Neutro y no se pide tono al LLM).
    """
    alias_list = parse_alias_list(aliases)
    t_clean = clean_text_strictly_no_links(titulo)
    r_clean = clean_text_strictly_no_links(resumen)

    title_units = _brand_units_from_field(t_clean, brand_regexes, brand, alias_list)
    body_units = _brand_units_from_field(r_clean, brand_regexes, brand, alias_list)

    matched: List[str] = []
    for unit in title_units + body_units:
        if unit not in matched:
            matched.append(unit)

    if not matched:
        return ""

    return clean_text_strictly_no_links(" ".join(matched))[:800]


def build_fact_context(
    title: str,
    body: str,
    max_chars: int = FACT_CONTEXT_MAX_CHARS,
) -> str:
    """Contexto del hecho (BLOQUE B): titular + recorte de cuerpo, no evidencia de marca."""
    t = clean_text_strictly_no_links(title or "")
    b = clean_text_strictly_no_links(body or "")
    if t and b:
        joined = b if t.lower() in b.lower() else f"{t}. {b}".strip()
    else:
        joined = t or b
    return joined[:max_chars]


def has_brand_evidence(ctx: str) -> bool:
    return bool(ctx) and str(ctx).strip() not in ("", "-", "nan", "none")

def check_exact_byline_rule(text: str, brand: str, aliases: List[str]) -> bool:
    """
    REGLA LITERAL SOLICITADA:
    Si el texto contiene exactamente las frases de autoría indicadas:
    - 'Editora web y periodista egresada de [marca]'
    - 'Editor web y periodista egresado de [marca]'
    - 'Estudiante en formación [marca]'
    - 'Periodista egresado/a de [marca]'
    Se retorna True para asignar directamente Neutro, Estudiantes, Redacción de artículo.
    """
    if not text:
        return False
        
    t_norm = unidecode(str(text).lower())
    
    # Términos de búsqueda (marca y todos los alias, partidos por coma/;/salto)
    alias_list = parse_alias_list(aliases)
    targets = [unidecode(brand.lower().strip())] + [unidecode(a.lower().strip()) for a in alias_list if a.strip()]
    
    for tgt in targets:
        if not tgt:
            continue
        tgt_esc = re.escape(tgt)
        
        # 1. Editora web y periodista egresada de [marca]
        if re.search(rf"\beditora\s+web\s+y\s+periodista\s+egresada\s+(?:de\s+(?:la\s+)?)?{tgt_esc}\b", t_norm):
            return True
            
        # 2. Editor web y periodista egresado de [marca]
        if re.search(rf"\beditor\s+web\s+y\s+periodista\s+egresado\s+(?:de\s+(?:la\s+)?)?{tgt_esc}\b", t_norm):
            return True
            
        # 3. Estudiante en formación [marca] (con o sin 'de' / 'de la')
        if re.search(rf"\bestudiante\s+en\s+formacion\s+(?:de\s+(?:la\s+)?)?{tgt_esc}\b", t_norm):
            return True
            
        # 4. Periodista egresado/a de [marca] / Editor(a) egresado/a de [marca]
        if re.search(rf"\b(?:periodista|editor[a]?|redactor[a]?)\s+egresad[oa]\s+(?:de\s+(?:la\s+)?)?{tgt_esc}\b", t_norm):
            return True

    return False

def clean_subtema(text: str, brand: str, title_fallback: str) -> str:
    if not text:
        return _fallback_from_title(title_fallback)
        
    clean = re.sub(r'[,.;:!?¿¡"\'\(\)\[\]\{\}\-_/\\|]', ' ', str(text))
    words = [w for w in clean.split() if w]
    
    if len(words) > SUBTEMA_MAX_WORDS:
        words = words[:SUBTEMA_MAX_WORDS]
        
    while words and words[-1].lower() in FORBIDDEN_TRAILING_WORDS:
        words.pop()
        
    res = " ".join(words).strip()
    res_lower = res.lower()
    
    forbidden_starts = [
        "mencion de", "mencion a", "mencion en", "mencion del", "presencia de",
        "declaraciones de", "noticia sobre", "alusion a", "referencia a"
    ]
    for fs in forbidden_starts:
        if res_lower.startswith(fs):
            res = res[len(fs):].strip()
            break
            
    brand_words = set(re.findall(r"\b[a-z0-9]+\b", unidecode(brand.lower())))
    res_words = set(re.findall(r"\b[a-z0-9]+\b", unidecode(res.lower())))
    
    if not res or res_words.issubset(brand_words) or res_lower in ["universidad", "autonoma", "fundacion", "clinica", "hospital", "institucion", "asociacion"]:
        return _fallback_from_title(title_fallback)
        
    return res.capitalize()

def clean_tema(text: str) -> str:
    if not text:
        return "Gestión Institucional"
    clean = re.sub(r'[,.;:!?¿¡"\'\(\)\[\]\{\}\-_/\\|]', ' ', str(text)).strip()
    words = clean.split()[:4]
    res = " ".join(words).title()
    if res.lower() in ["otros", "otro", "general", "varios", "miscelanea", "sin clasificar", ""]:
        return "Gestión Institucional"
    return res

def ensure_different_tema_subtema(tema: str, subtema: str, ctx: str) -> str:
    t_clean = tema.strip().title()
    s_clean = subtema.strip().capitalize()
    
    if t_clean.lower() == s_clean.lower() or fuzz.ratio(t_clean.lower(), s_clean.lower()) >= 80:
        c_low = f"{s_clean} {ctx}".lower()
        if any(w in c_low for w in ["salud", "hospital", "clinica", "medico", "medicina", "paciente", "quirurg", "enfermedad", "achc"]):
            return "Sector Salud"
        if any(w in c_low for w in ["aduan", "dian", "fiscal", "tributar", "impuesto", "arancel"]):
            return "Gestión Tributaria"
        if any(w in c_low for w in ["universidad", "estudiante", "academ", "carrera", "educacion", "profesor", "beca", "uao", "feria", "inspirate"]):
            return "Educación Superior"
        if any(w in c_low for w in ["aniversario", "celebracion", "decadas", "anos", "reconocimiento", "homenaje"]):
            return "Hitos y Aniversarios"
        if any(w in c_low for w in ["rescate", "bombero", "emergencia", "siniestro", "accidente", "desastre"]):
            return "Gestión de Emergencias"
        if any(w in c_low for w in ["obra", "construccion", "via", "infraestructura", "puente", "sede"]):
            return "Infraestructura"
        if any(w in c_low for w in ["seguridad", "policia", "captura", "hurto", "delito", "fiscalia", "crimen"]):
            return "Seguridad Ciudadana"
        if any(w in c_low for w in ["convenio", "acuerdo", "alianza", "gremio", "liderazgo"]):
            return "Relaciones Gremiales"
        return "Gestión Institucional"
        
    return t_clean

def check_positive_institutional_override(ctx: str) -> bool:
    """Detecta de forma infalible acompañamiento, respaldo y felicitaciones."""
    c_low = unidecode(ctx.lower())
    positive_actions = [
        "celebra y respalda", "respalda el nombramiento", "respaldan el nombramiento",
        "acompanamos desde", "acompanamiento desde", "asesoria gratuita", "apoyo gratuito",
        "pusieron en marcha", "pone en marcha", "felicita a", "felicitamos a",
        "rinde homenaje", "reconocimiento destaca el compromiso", "abren espacio"
    ]
    has_positive = any(p in c_low for p in positive_actions)
    has_negative_allegation = any(n in c_low for n in ["denuncia penal", "sancion fiscal", "investigacion por corrupcion", "plagio"])
    return has_positive and not has_negative_allegation

def _fallback_from_title(title: str) -> str:
    if not title:
        return "Hecho Informativo"
    t = re.sub(r"^(?:imagenes|video|en fotos)\s*\|\s*", "", title, flags=re.IGNORECASE).strip()
    words = re.sub(r'[,.;:!?¿¡"\'\(\)\[\]\{\}\-_/\\|]', ' ', t).split()
    clean_words = words[:SUBTEMA_MAX_WORDS]
    while clean_words and clean_words[-1].lower() in FORBIDDEN_TRAILING_WORDS:
        clean_words.pop()
    return " ".join(clean_words).capitalize() if clean_words else "Hecho Informativo"


def validate_or_repair_subtema(
    text: str,
    brand: str,
    title_fallback: str,
    ctx: str = "",
) -> str:
    """Validador duro de 3–7 palabras; repara con título/contexto si hace falta."""
    cleaned = clean_subtema(text or "", brand, title_fallback)
    n = len(cleaned.split()) if cleaned else 0
    if SUBTEMA_MIN_WORDS <= n <= SUBTEMA_MAX_WORDS:
        return cleaned
    if n > SUBTEMA_MAX_WORDS:
        words = cleaned.split()[:SUBTEMA_MAX_WORDS]
        while words and words[-1].lower() in FORBIDDEN_TRAILING_WORDS:
            words.pop()
        cleaned = " ".join(words).capitalize() if words else cleaned
        n = len(cleaned.split())
        if SUBTEMA_MIN_WORDS <= n <= SUBTEMA_MAX_WORDS:
            return cleaned
    if n < SUBTEMA_MIN_WORDS:
        title_fb = _fallback_from_title(title_fallback)
        if title_fb and len(title_fb.split()) >= SUBTEMA_MIN_WORDS:
            return title_fb
        for source in (title_fallback, ctx):
            alt = clean_subtema(str(source or ""), brand, title_fallback)
            alt_n = len(alt.split()) if alt else 0
            if SUBTEMA_MIN_WORDS <= alt_n <= SUBTEMA_MAX_WORDS:
                return alt
        if title_fb and title_fb.strip() and title_fb != "Hecho Informativo":
            return title_fb
    return cleaned or _fallback_from_title(title_fallback)

# Strict same-fact clustering. Bias: two clusters for one fact (false negative)
# is better than one cluster for two facts (false positive).
# KEEP / tightened: near-identical titles; event-anchor equality PLUS extra
# distinctive overlap; high body similarity.
# REMOVED: 2-word lead-only match; title token_set >= 70 standalone;
# context token_set >= 63 standalone; context overlap of only 3 distinctive words;
# event-anchor equality without extra overlap. Brand evidence is not a fact signal.
CLUSTER_TITLE_CONTAINMENT_MIN_LEN = 20
CLUSTER_TITLE_PREFIX_LEN = 28
CLUSTER_TITLE_RATIO = 90
CLUSTER_TITLE_PARTIAL_RATIO = 94
CLUSTER_TITLE_PARTIAL_AND_RATIO = 82
CLUSTER_TITLE_TOKEN_SET = 92
CLUSTER_TITLE_TOKEN_SORT = 88
CLUSTER_BODY_MIN_LEN = 50
CLUSTER_BODY_TOKEN_SET = 90
CLUSTER_BODY_RATIO = 82
CLUSTER_BODY_DISTINCTIVE_OVERLAP = 4
CLUSTER_ANCHOR_EXTRA_OVERLAP = 2
CLUSTER_LEAD_EXTRA_OVERLAP = 1
CLUSTER_LEAD_SORT_MIN = 80
CLUSTER_TITLE_DISTINCTIVE_OVERLAP = 5
CLUSTER_TITLE_DISTINCTIVE_SORT = 85
CLUSTER_GENERIC_TOKENS = {
    "universidad", "instituto", "institucion", "clinica", "hospital", "fundacion",
    "colegio", "empresa", "grupo", "ciudad", "region",
}
CANON_SUBTEMA_NEAR_IDENTICAL = 90


def _distinctive_subset(words: Set[str], doc_freq: Counter, total_docs: int) -> Set[str]:
    """Filtra palabras que se repiten en gran parte del lote (nombre de marca,
    ciudad sede, evento recurrente) para que NO cuenten como señal de que dos
    noticias hablan del mismo hecho puntual. Sin esto, dos notas sobre hechos
    distintos que solo comparten la marca/ciudad/evento terminan fusionadas
    bajo el mismo subtema (sobre-agrupación)."""
    if total_docs <= 0 or not words:
        return set(words)
    cap = max(3, round(total_docs * 0.07))
    return {w for w in words if doc_freq.get(w, 0) <= cap}


def _is_generic_cluster_token(token: str, brand_regexes: List[str]) -> bool:
    if not token or token in CLUSTER_GENERIC_TOKENS or token in STOPWORDS_ES:
        return True
    if brand_regexes and any(re.search(rx, token) for rx in brand_regexes):
        return True
    return False


def _fact_overlap(a: Set[str], b: Set[str], brand_regexes: List[str]) -> Set[str]:
    return {
        w for w in (a & b)
        if len(w) > 3 and not _is_generic_cluster_token(w, brand_regexes)
    }


def subtema_has_fact_fidelity(
    subtema: str,
    title: str,
    body: str = "",
    brand: str = "",
) -> bool:
    """Palabras distintivas del subtema deben aparecer en el titular o el cuerpo del grupo."""
    sub_words = get_content_words_set(normalize_text_for_matching(subtema or ""))
    fact_words = get_content_words_set(
        normalize_text_for_matching(f"{title or ''} {body or ''}")
    )
    brand_words = get_content_words_set(normalize_text_for_matching(brand or ""))
    distinctive = {w for w in sub_words if len(w) > 3 and w not in brand_words}
    if not distinctive:
        return False
    need = max(1, (len(distinctive) + 1) // 2)
    return len(distinctive & fact_words) >= need


def _titles_are_near_identical(t_norm: str, rep_t: str) -> bool:
    if not t_norm or not rep_t:
        return False
    if t_norm == rep_t:
        return True
    min_len = min(len(t_norm), len(rep_t))
    if min_len >= CLUSTER_TITLE_CONTAINMENT_MIN_LEN and (t_norm in rep_t or rep_t in t_norm):
        return True
    if (
        min_len >= CLUSTER_TITLE_PREFIX_LEN
        and t_norm[:CLUSTER_TITLE_PREFIX_LEN] == rep_t[:CLUSTER_TITLE_PREFIX_LEN]
        and fuzz.ratio(t_norm, rep_t) >= CLUSTER_TITLE_PARTIAL_AND_RATIO
    ):
        return True
    if fuzz.ratio(t_norm, rep_t) >= CLUSTER_TITLE_RATIO:
        return True
    if (
        fuzz.partial_ratio(t_norm, rep_t) >= CLUSTER_TITLE_PARTIAL_RATIO
        and fuzz.ratio(t_norm, rep_t) >= CLUSTER_TITLE_PARTIAL_AND_RATIO
    ):
        return True
    if (
        fuzz.token_set_ratio(t_norm, rep_t) >= CLUSTER_TITLE_TOKEN_SET
        and fuzz.token_sort_ratio(t_norm, rep_t) >= CLUSTER_TITLE_TOKEN_SORT
    ):
        return True
    return False


def cluster_similar_rows(rows: List[dict], km: dict, brand_regexes: List[str]) -> Dict[int, int]:
    n = len(rows)
    cluster_map = {}
    clusters_rep = {}
    current_cluster = 0

    active_indices = [i for i in range(n) if not rows[i].get("is_duplicate")]

    # Features from title + body (the article fact). Brand evidence is not used
    # as a merge reason: after SPEC_TONO_TEMA it only contains marca snippets.
    features: Dict[int, dict] = {}
    title_doc_freq = Counter()
    body_doc_freq = Counter()
    for i in active_indices:
        t_raw = str(rows[i].get(km.get("titulo", "Título"), ""))
        r_raw = str(rows[i].get("Resumen - Aclaracion") or rows[i].get("resumen corto") or "")

        t_norm = normalize_text_for_matching(t_raw)
        c_words = get_content_words_set(t_norm)
        lead_words = get_lead_content_words(t_norm, n_words=3)
        anchor = extract_event_anchor(t_raw)
        r_norm = normalize_text_for_matching(r_raw[:350])
        body_words = get_content_words_set(r_norm)

        features[i] = {
            "title_norm": t_norm,
            "content_words": c_words,
            "lead_words": lead_words,
            "anchor": anchor,
            "body_norm": r_norm,
            "body_words": body_words,
        }
        for w in c_words:
            title_doc_freq[w] += 1
        for w in body_words:
            body_doc_freq[w] += 1

    total_docs = len(active_indices)
    sorted_indices = sorted(active_indices, key=lambda idx: features[idx]["title_norm"])

    for i in sorted_indices:
        f = features[i]
        t_norm = f["title_norm"]
        c_words = f["content_words"]
        lead_words = f["lead_words"]
        anchor = f["anchor"]
        r_norm = f["body_norm"]
        body_words = f["body_words"]
        distinctive_c_words = _distinctive_subset(c_words, title_doc_freq, total_docs)
        distinctive_body = _distinctive_subset(body_words, body_doc_freq, total_docs)

        assigned = False
        for cid, rep in clusters_rep.items():
            rep_t = rep["title_norm"]
            rep_words = rep["content_words"]
            rep_lead = rep["lead_words"]
            rep_anchor = rep["anchor"]
            rep_r = rep["body_norm"]
            rep_body_words = rep["body_words"]
            rep_distinctive = _distinctive_subset(rep_words, title_doc_freq, total_docs)
            title_overlap = _fact_overlap(distinctive_c_words, rep_distinctive, brand_regexes)

            if _titles_are_near_identical(t_norm, rep_t):
                cluster_map[i] = cid
                assigned = True
                break

            # 3-word lead only with extra distinctive overlap and high title sort.
            # 2-word lead-only match is intentionally not a merge reason.
            if (
                len(lead_words) >= 3
                and len(rep_lead) >= 3
                and lead_words == rep_lead
                and fuzz.token_sort_ratio(t_norm, rep_t) >= CLUSTER_LEAD_SORT_MIN
            ):
                extra = title_overlap - set(lead_words)
                if len(extra) >= CLUSTER_LEAD_EXTRA_OVERLAP:
                    cluster_map[i] = cid
                    assigned = True
                    break

            if anchor and rep_anchor and anchor == rep_anchor:
                extra = title_overlap - set(anchor.split())
                if len(extra) >= CLUSTER_ANCHOR_EXTRA_OVERLAP:
                    cluster_map[i] = cid
                    assigned = True
                    break

            if (
                len(title_overlap) >= CLUSTER_TITLE_DISTINCTIVE_OVERLAP
                and t_norm
                and rep_t
                and fuzz.token_sort_ratio(t_norm, rep_t) >= CLUSTER_TITLE_DISTINCTIVE_SORT
            ):
                cluster_map[i] = cid
                assigned = True
                break

            if r_norm and rep_r and len(r_norm) >= CLUSTER_BODY_MIN_LEN and len(rep_r) >= CLUSTER_BODY_MIN_LEN:
                body_overlap = _fact_overlap(
                    distinctive_body,
                    _distinctive_subset(rep_body_words, body_doc_freq, total_docs),
                    brand_regexes,
                )
                if (
                    len(body_overlap) >= CLUSTER_BODY_DISTINCTIVE_OVERLAP
                    and fuzz.token_set_ratio(r_norm, rep_r) >= CLUSTER_BODY_TOKEN_SET
                    and fuzz.ratio(r_norm, rep_r) >= CLUSTER_BODY_RATIO
                ):
                    cluster_map[i] = cid
                    assigned = True
                    break

        if not assigned:
            cluster_map[i] = current_cluster
            clusters_rep[current_cluster] = dict(f)
            current_cluster += 1

    return cluster_map

class _DSU:
    """Union-Find simple para fusionar clústers de forma transitiva y
    determinista (A~B y B~C implica A~B~C, sin importar el orden de
    comparación — el código anterior sobrescribía el mapeo par a par y podía
    dejar una fusión a medias según el orden de iteración)."""

    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def canonicalize_subtopics(
    cluster_results: Dict[int, Tuple[str, str, str]],
    cluster_contexts: Optional[Dict[int, str]] = None,
) -> Dict[int, Tuple[str, str, str]]:
    """Alinea el texto de subtema solo cuando las cadenas ya son casi idénticas.

    No une clústers por similitud laxa de evidencia de marca / contexto.
    Cada clúster conserva su (tono, tema, subtema) cuando los hechos difieren.
    `cluster_contexts` se acepta por compatibilidad y no dispara fusiones.
    """
    cids = list(cluster_results.keys())
    dsu = _DSU(cids)
    # cluster_contexts is accepted for call-site compatibility and is not a merge signal.

    norm_subs = {cid: normalize_text_for_matching(cluster_results[cid][2] or "") for cid in cids}

    for i in range(len(cids)):
        for j in range(i + 1, len(cids)):
            cid1, cid2 = cids[i], cids[j]
            if dsu.find(cid1) == dsu.find(cid2):
                continue
            n1, n2 = norm_subs[cid1], norm_subs[cid2]
            if not n1 or not n2:
                continue
            same_subtema_text = n1 == n2 or (
                fuzz.token_set_ratio(n1, n2) >= CANON_SUBTEMA_NEAR_IDENTICAL
                and fuzz.token_sort_ratio(n1, n2) >= CANON_SUBTEMA_NEAR_IDENTICAL
            )
            if same_subtema_text:
                dsu.union(cid1, cid2)

    groups: Dict[int, List[int]] = {}
    for cid in cids:
        groups.setdefault(dsu.find(cid), []).append(cid)

    final_results = {}
    for _, members in groups.items():
        sub_counts = Counter(cluster_results[m][2] for m in members if cluster_results[m][2])
        tema_counts = Counter(cluster_results[m][1] for m in members if cluster_results[m][1])
        if sub_counts:
            max_count = max(sub_counts.values())
            # Empate: se prefiere el subtema más específico (más palabras), y
            # como último criterio el orden alfabético, para que el resultado
            # sea determinista entre corridas.
            best_sub = min(
                (s for s, c in sub_counts.items() if c == max_count),
                key=lambda s: (-len(s.split()), s),
            )
        else:
            best_sub = ""
        best_tema = tema_counts.most_common(1)[0][0] if tema_counts else ""

        for m in members:
            tono, _, _ = cluster_results[m]
            final_results[m] = (tono, best_tema or cluster_results[m][1], best_sub or cluster_results[m][2])

    return final_results

def _labels_too_close(a: str, b: str) -> bool:
    if not a or not b:
        return False
    na = normalize_text_for_matching(a)
    nb = normalize_text_for_matching(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    return fuzz.ratio(na, nb) >= 80 or fuzz.token_set_ratio(na, nb) >= 85


def ensure_subtema_distinct_from_tema(
    tema: str,
    subtema: str,
    brand: str,
    title: str,
    ctx: str,
) -> str:
    """Si el subtema colisiona con un tema PKL, reusa el mismo limpiado específico (no recorta calidad a título)."""
    cleaned = validate_or_repair_subtema(subtema or "", brand, title, ctx)
    if cleaned and not _labels_too_close(tema, cleaned) and len(cleaned.split()) >= SUBTEMA_MIN_WORDS:
        return cleaned
    for candidate in (ctx, title):
        alt = validate_or_repair_subtema(str(candidate or ""), brand, title, ctx)
        if alt and not _labels_too_close(tema, alt) and len(alt.split()) >= SUBTEMA_MIN_WORDS:
            return alt
    return cleaned or subtema or _fallback_from_title(title)


def snap_to_cubo(label: str) -> Optional[str]:
    """Ajusta una etiqueta libre a la lista cerrada de 21 cubos. 'Otros' no es cubo."""
    n = _norm_label(label)
    if n in FORBIDDEN_TEMA_NORMS:
        return None
    for cubo in DEFAULT_CUBOS:
        if _norm_label(cubo) == n:
            return cubo
    best = None
    best_score = 0
    for cubo in DEFAULT_CUBOS:
        cn = _norm_label(cubo)
        score = fuzz.ratio(n, cn)
        if n and cn and (n in cn or cn in n) and min(len(n), len(cn)) >= 8:
            score = max(score, 86)
        if score > best_score:
            best_score = score
            best = cubo
    if best is not None and best_score >= 80:
        return best
    return None


def lexical_assign_tema(subtema: str, title: str) -> str:
    """Tema sin PKL: reglas léxicas sobre el subtema; el título solo si tiene ≤160 caracteres."""
    blob = unidecode((subtema or "").lower())
    if title and len(title) <= TEMA_TITLE_MAX_CHARS:
        blob = f"{blob} {unidecode(title.lower())}".strip()
    if not blob.strip():
        return "Gestión Institucional"

    scores = []
    for cubo in DEFAULT_CUBOS:
        hits = sum(1 for kw in CUBO_KEYWORDS.get(cubo, ()) if kw in blob)
        if hits:
            scores.append((hits, 0 if cubo == "Gestión Institucional" else 1, cubo))
    if not scores:
        return "Gestión Institucional"
    scores.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return scores[0][2]


def assign_closed_tema(
    llm_tema: Optional[str],
    subtema: str,
    title: str,
    ctx: str = "",
) -> str:
    """Nunca emite 'Otros'. Prefiere cubo del LLM si es válido; si no, léxico."""
    snapped = snap_to_cubo(llm_tema or "")
    if snapped:
        return snapped
    lexical = lexical_assign_tema(subtema, title)
    if lexical:
        return lexical
    ctx_guess = lexical_assign_tema(subtema, ctx[:TEMA_TITLE_MAX_CHARS] if ctx else "")
    return ctx_guess or "Gestión Institucional"


def _brand_is_contribution_subject(ctx: str, brand_regexes: List[str]) -> bool:
    if not ctx:
        return False
    for sent in split_text_units(ctx):
        s_norm = unidecode(sent.lower())
        brand_pos = None
        for rx in brand_regexes or []:
            m = re.search(rx, s_norm)
            if m and (brand_pos is None or m.start() < brand_pos):
                brand_pos = m.start()
        if brand_pos is None:
            continue
        for verb in CONTRIBUTION_VERBS:
            v = unidecode(verb.lower())
            idx = s_norm.find(v)
            if idx >= 0 and brand_pos < idx:
                return True
    return False


def _has_directed_criticism(ctx: str) -> bool:
    c_low = unidecode((ctx or "").lower())
    return any(m in c_low for m in DIRECTED_CRITICISM_MARKERS)


def _is_tragic_context(ctx: str) -> bool:
    c_low = unidecode((ctx or "").lower())
    return any(m in c_low for m in TRAGIC_MARKERS)


def _is_locative_only(ctx: str) -> bool:
    c_low = unidecode((ctx or "").lower())
    if not any(m in c_low for m in LOCATIVE_MARKERS):
        return False
    if _has_directed_criticism(ctx):
        return False
    if any(unidecode(v.lower()) in c_low for v in CONTRIBUTION_VERBS):
        return False
    agency = (
        "anuncio", "anuncia", "inaugur", "denunci", "sancion", "firmo", "firma",
        "lanzo", "lanza", "investiga",
    )
    if any(a in c_low for a in agency):
        return False
    return True


def apply_tone_guards(
    tono: str,
    brand_ctx: str,
    brand: str = "",
    aliases: Optional[Sequence[str]] = None,
    brand_regexes: Optional[List[str]] = None,
) -> str:
    """Guardas deterministas posteriores al LLM (SPEC_TONO_TEMA §2)."""
    if not has_brand_evidence(brand_ctx):
        return "Neutro"

    regexes = brand_regexes or generate_brand_variants(brand, parse_alias_list(aliases))
    current = tono if tono in ("Positivo", "Negativo", "Neutro") else "Neutro"

    if current == "Negativo":
        snippet = (brand_ctx or "").strip()
        if (
            len(snippet) <= TRAGEDY_GUARD_MAX_CHARS
            and _is_tragic_context(snippet)
            and not _has_directed_criticism(snippet)
        ):
            current = "Neutro"

    if _is_locative_only(brand_ctx) and not _has_directed_criticism(brand_ctx):
        current = "Neutro"

    if current == "Neutro" and _brand_is_contribution_subject(brand_ctx, regexes):
        current = "Positivo"

    if check_positive_institutional_override(brand_ctx):
        current = "Positivo"

    return current


def _call_openai_cluster(
    client: OpenAI,
    model: str,
    brand: str,
    aliases: List[str],
    brand_regexes: List[str],
    ctx: str,
    title_ref: str,
    request_tone: bool = True,
    request_theme: bool = True,
    pkl_theme: Optional[str] = None,
    fact_ctx: str = "",
) -> Tuple[str, str, str]:
    aliases = parse_alias_list(aliases)
    fact_for_subtema = (fact_ctx or "").strip() or (title_ref or "")
    # REGLA EXACTA DE AUTORÍA/EGRESADOS (SI ESTÁN LAS PALABRAS NO SE ANALIZA CON IA)
    search_scope = f"{title_ref} {ctx} {fact_for_subtema}"
    if check_exact_byline_rule(search_scope, brand, aliases):
        return "Neutro", "Estudiantes", "Redacción de artículo"

    ask_tone = bool(request_tone) and has_brand_evidence(ctx)
    cubos_list = "; ".join(DEFAULT_CUBOS)

    json_fields = []
    blocks = []
    if ask_tone:
        blocks.append(
            "BLOQUE A — TONO (únicamente evidencia de marca)\n"
            f'Decide "tono" SOLO con oraciones que nombran a "{brand}", sus alias o voceros. '
            'Valores: "Positivo", "Negativo" o "Neutro".\n'
            "PROHIBIDO usar el sentimiento del artículo completo, tragedias ajenas o hechos de otras entidades.\n"
            "Negativo exige crítica dirigida a la marca. Mención de sede/ubicación sin juicio → Neutro.\n"
            "Positivo: la marca es sujeto de aportes, respaldo, donación, alianza o inauguración."
        )
        json_fields.append('"tono": "..."')
    blocks.append(
        "BLOQUE B — SUBTEMA (únicamente el hecho específico)\n"
        'Decide "subtema" SOLO con el contexto del hecho (título + cuerpo), no con la evidencia de marca. '
        "Frase nominal coherente en español colombiano, OBLIGATORIO 3 a 7 palabras. "
        "Sin comas ni puntos. PROHIBIDO usar Mención, collage de keywords o recortar el titular. "
        "El subtema describe el hecho, no el tono ni el cubo temático. "
        "Las palabras distintivas del subtema deben aparecer en el titular o el cuerpo."
    )
    json_fields.append('"subtema": "..."')
    if request_theme:
        json_fields.append('"tema": "..."')
        blocks.append(
            "TEMA (lista cerrada de cubos; PROHIBIDO \"Otros\"): elige exactamente uno de: "
            f"{cubos_list}."
        )

    if request_theme:
        differ_rule = 'REGLA OBLIGATORIA: "tema" y "subtema" DEBEN SER DIFERENTES. tema ∈ cubos cerrados.'
    elif pkl_theme:
        differ_rule = (
            f'TEMA YA CLASIFICADO POR EL MODELO DEL CLIENTE: "{pkl_theme}". '
            "NO inventes otro tema ni lo copies como subtema. "
            "El subtema debe ser un hecho más específico y distinto a ese tema."
        )
    else:
        differ_rule = "El subtema debe describir el hecho concreto, no un dominio general."

    tone_examples = ""
    if ask_tone:
        tone_examples = """
EJEMPLOS DE TONO ASPECTUAL (solo marca):
- Caso 1: "Sismo en la región: Acompañamos desde la Universidad Autónoma de Occidente a las familias afectadas..."
  -> Tono: "Positivo" (la marca es sujeto de acompañamiento; la tragedia ajena no contagia).
- Caso 2: "Designación ministerial: La Universidad Autónoma de Occidente celebra y respalda el nombramiento..."
  -> Tono: "Positivo" (respaldo institucional de la marca).
- Caso 3: "UAO y DIAN abren espacio de asesoría gratuita en trámites aduaneros..."
  -> Tono: "Positivo" (alianza y beneficio).
- Caso 4: "Denuncian quejas por cobros excesivos en la UAO..."
  -> Tono: "Negativo" (crítica dirigida a la marca).
- Caso 5: "El sismo se sintió en la UAO." / "frente a la sede de la UAO"
  -> Tono: "Neutro" (tragedia corta sin crítica, o mención de sede).
- Caso 6: "Boletín general de cifras donde la entidad aporta un dato técnico..."
  -> Tono: "Neutro" (informativo sin juicio de valor).
"""

    alias_txt = ", ".join(aliases) if aliases else "Ninguno"
    prompt = f"""Analiza esta noticia para el cliente: "{brand}" (Alias: {alias_txt}).

Titular de referencia: "{title_ref}"
Evidencia de marca (BLOQUE A; vacía = no hay mención):
\"\"\"{ctx}\"\"\"

Contexto del hecho (BLOQUE B; título + cuerpo; el subtema se ancla aquí):
\"\"\"{fact_for_subtema}\"\"\"
{tone_examples}
Instrucciones (bloques independientes; no mezclar evidencia):
{chr(10).join(blocks)}

{differ_rule}

Responde estrictamente en JSON:
{{{", ".join(json_fields)}}}"""

    system_prompt = (
        "Auditor reputacional senior. El tono es ASPECTUAL: mide el impacto sobre la marca, "
        "alias o voceros, NUNCA el sentimiento del artículo completo. "
        "El BLOQUE A decide únicamente el tono (evidencia de marca). "
        "El BLOQUE B decide únicamente el subtema (contexto del hecho). "
        "No mezclar evidencia entre bloques. Sin mención de marca el tono es Neutro."
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=140
        )
        data = json.loads(resp.choices[0].message.content)

        if ask_tone:
            tono_raw = str(data.get("tono", "Neutro")).strip().capitalize()
            tono = tono_raw if tono_raw in ["Positivo", "Negativo", "Neutro"] else "Neutro"
        else:
            tono = "Neutro"

        tono = apply_tone_guards(tono, ctx, brand, aliases, brand_regexes)

        subtema = validate_or_repair_subtema(
            data.get("subtema", ""), brand, title_ref, fact_for_subtema
        )
        if not subtema_has_fact_fidelity(subtema, title_ref, fact_for_subtema, brand):
            subtema = validate_or_repair_subtema(
                _fallback_from_title(title_ref), brand, title_ref, fact_for_subtema
            )

        if request_theme:
            tema = assign_closed_tema(data.get("tema", ""), subtema, title_ref, fact_for_subtema)
            tema = ensure_different_tema_subtema(tema, subtema, fact_for_subtema)
            tema = assign_closed_tema(tema, subtema, title_ref, fact_for_subtema)
        else:
            tema = (pkl_theme or "").strip() or "Gestión Institucional"
            subtema = ensure_subtema_distinct_from_tema(
                tema, subtema, brand, title_ref, fact_for_subtema
            )
            subtema = validate_or_repair_subtema(subtema, brand, title_ref, fact_for_subtema)
            if not subtema_has_fact_fidelity(subtema, title_ref, fact_for_subtema, brand):
                subtema = validate_or_repair_subtema(
                    _fallback_from_title(title_ref), brand, title_ref, fact_for_subtema
                )

        return tono, tema, subtema
    except Exception as e:
        logger.error(f"Error en llamada OpenAI: {e}")
        sub_fb = validate_or_repair_subtema("", brand, title_ref, fact_for_subtema)
        if not subtema_has_fact_fidelity(sub_fb, title_ref, fact_for_subtema, brand):
            sub_fb = validate_or_repair_subtema(
                _fallback_from_title(title_ref), brand, title_ref, fact_for_subtema
            )
        if request_theme:
            tema_fb = assign_closed_tema("", sub_fb, title_ref, fact_for_subtema)
            tema_fb = ensure_different_tema_subtema(tema_fb, sub_fb, fact_for_subtema)
            tema_fb = assign_closed_tema(tema_fb, sub_fb, title_ref, fact_for_subtema)
        else:
            tema_fb = (pkl_theme or "").strip() or "Gestión Institucional"
            sub_fb = ensure_subtema_distinct_from_tema(
                tema_fb, sub_fb, brand, title_ref, fact_for_subtema
            )
            sub_fb = validate_or_repair_subtema(sub_fb, brand, title_ref, fact_for_subtema)
        tono_fb = apply_tone_guards("Neutro", ctx, brand, aliases, brand_regexes)
        return tono_fb, tema_fb, sub_fb

def enrich_rows_with_ai(
    rows: List[dict],
    km: dict,
    brand: str,
    aliases: List[str],
    api_key: str,
    model: str = "gpt-4.1-nano-2025-04-14",
    progress_callback: Optional[Callable[[int, str], None]] = None,
    tone_model=None,
    theme_model=None,
) -> List[dict]:
    from pkl_classifier import classification_plan, format_theme_label, map_tone_label, _safe_predict

    client = OpenAI(api_key=api_key)
    plan = classification_plan(True, tone_model, theme_model)

    aliases = parse_alias_list(aliases)
    brand_regexes = generate_brand_variants(brand, aliases)
    
    if progress_callback:
        progress_callback(71, "Extrayendo contexto de la marca y sus variantes para auditoría…")
    for row in rows:
        if row.get("is_duplicate"):
            row["Contexto analizado"] = "-"
        else:
            resumen_val = row.get("Resumen - Aclaracion") or row.get("resumen corto") or row.get("Resumen") or ""
            titulo_val = row.get(km.get("titulo", "Título")) or ""
            
            ctx = extract_brand_context(
                str(resumen_val),
                str(titulo_val),
                brand_regexes,
                brand=brand,
                aliases=aliases,
            )
            row["Contexto analizado"] = ctx

    if progress_callback:
        progress_callback(74, "Agrupando eventos y noticias similares (ordenamiento por titular)…")
    cluster_map = cluster_similar_rows(rows, km, brand_regexes)
    
    unique_clusters = sorted(set(cluster_map.values()))
    total_clusters = len(unique_clusters)
    
    cluster_to_sample_idx = {}
    for row_idx, cid in cluster_map.items():
        if cid not in cluster_to_sample_idx:
            cluster_to_sample_idx[cid] = row_idx
            
    cluster_results: Dict[int, Tuple[str, str, str]] = {}
    cluster_pkl: Dict[int, Tuple[Optional[str], Optional[str]]] = {}
    cluster_fact_ctx: Dict[int, str] = {}
    cluster_titles: Dict[int, str] = {}

    if progress_callback:
        progress_callback(77, f"Analizando {total_clusters} hechos únicos con {model}…")
        
    completed = 0
    with ThreadPoolExecutor(max_workers=14) as executor:
        future_to_cid = {}
        for cid, row_idx in cluster_to_sample_idx.items():
            ctx = rows[row_idx]["Contexto analizado"]
            t_ref = str(rows[row_idx].get(km.get("titulo", "Título"), ""))
            resumen_val = (
                rows[row_idx].get("Resumen - Aclaracion")
                or rows[row_idx].get("resumen corto")
                or rows[row_idx].get("Resumen")
                or ""
            )
            fact_ctx = build_fact_context(t_ref, str(resumen_val))
            cluster_fact_ctx[cid] = fact_ctx
            cluster_titles[cid] = t_ref
            pkl_tone = None
            pkl_theme = None
            if tone_model is not None:
                pkl_tone = map_tone_label(_safe_predict(tone_model, [ctx or ""], "tono")[0])
            if theme_model is not None:
                pkl_theme = format_theme_label(_safe_predict(theme_model, [ctx or ""], "tema")[0])
            cluster_pkl[cid] = (pkl_tone, pkl_theme)
            fut = executor.submit(
                _call_openai_cluster,
                client,
                model,
                brand,
                aliases,
                brand_regexes,
                ctx,
                t_ref,
                request_tone=plan["use_llm_tone"],
                request_theme=plan["use_llm_theme"],
                pkl_theme=pkl_theme,
                fact_ctx=fact_ctx,
            )
            future_to_cid[fut] = cid
            
        for fut in as_completed(future_to_cid):
            cid = future_to_cid[fut]
            tono, tema, subtema = fut.result()
            pkl_tone, pkl_theme = cluster_pkl.get(cid, (None, None))
            if pkl_tone:
                tono = pkl_tone
            if pkl_theme:
                tema = pkl_theme
                sample_idx = cluster_to_sample_idx[cid]
                subtema = ensure_subtema_distinct_from_tema(
                    tema,
                    subtema,
                    brand,
                    cluster_titles.get(cid) or str(rows[sample_idx].get(km.get("titulo", "Título"), "")),
                    cluster_fact_ctx.get(cid, ""),
                )
                if not subtema_has_fact_fidelity(
                    subtema,
                    cluster_titles.get(cid, ""),
                    cluster_fact_ctx.get(cid, ""),
                    brand,
                ):
                    subtema = validate_or_repair_subtema(
                        cluster_titles.get(cid, ""),
                        brand,
                        cluster_titles.get(cid, ""),
                        cluster_fact_ctx.get(cid, ""),
                    )
            cluster_results[cid] = (tono, tema, subtema)
            completed += 1
            if progress_callback and (completed % 15 == 0 or completed == total_clusters):
                pct = 77 + int((completed / total_clusters) * 16)
                progress_callback(pct, f"Analizando con IA… {completed}/{total_clusters} procesados")

    for cid, (tono, tema, subtema) in list(cluster_results.items()):
        group_title = cluster_titles.get(cid, "")
        group_fact = cluster_fact_ctx.get(cid, "")
        if not subtema_has_fact_fidelity(subtema, group_title, group_fact, brand):
            repaired = validate_or_repair_subtema(
                _fallback_from_title(group_title), brand, group_title, group_fact
            )
            cluster_results[cid] = (tono, tema, repaired)

    cluster_contexts = {
        cid: rows[row_idx].get("Contexto analizado", "")
        for cid, row_idx in cluster_to_sample_idx.items()
    }
    cluster_results = canonicalize_subtopics(cluster_results, cluster_contexts)

    for i, row in enumerate(rows):
        if row.get("is_duplicate"):
            row["Tono_IA"] = "Duplicada"
            row["Tema_IA"] = "-"
            row["Subtema_IA"] = "-"
            continue

        cid = cluster_map.get(i)
        if cid is not None and cid in cluster_results:
            tono, tema, subtema = cluster_results[cid]
        else:
            tono, tema, subtema = "Neutro", "Gestión Institucional", "Hecho Informativo"

        row_title = str(row.get(km.get("titulo", "Título"), ""))
        row_body = str(
            row.get("Resumen - Aclaracion")
            or row.get("resumen corto")
            or row.get("Resumen")
            or ""
        )
        row_fact = build_fact_context(row_title, row_body)

        # CHEQUEO DIRECTO POR FILA: ejes sin PKL siguen la regla de autoría; el subtema no se pierde.
        row_full_text = f"{row_title} {row.get('Contexto analizado', '')} {row_body}"
        if check_exact_byline_rule(row_full_text, brand, aliases):
            if tone_model is None:
                tono = "Neutro"
            if theme_model is None:
                tema = "Estudiantes"
            subtema = "Redacción de artículo"

        if theme_model is None:
            tema = ensure_different_tema_subtema(tema, subtema, row_fact)
            tema = assign_closed_tema(
                tema,
                subtema,
                row_title,
                row_fact,
            )
        else:
            subtema = ensure_subtema_distinct_from_tema(
                tema, subtema, brand, row_title, row_fact,
            )

        if subtema != "Redacción de artículo" and not subtema_has_fact_fidelity(
            subtema, row_title, row_body, brand
        ):
            # Repair from this group's / row's title, never from another cluster.
            subtema = validate_or_repair_subtema(
                _fallback_from_title(row_title), brand, row_title, row_fact
            )
        else:
            subtema = validate_or_repair_subtema(
                subtema,
                brand,
                row_title,
                row_fact,
            )

        row["Tono_IA"] = tono
        row["Tema_IA"] = tema
        row["Subtema_IA"] = subtema
            
    return rows
