Sistema de Análisis de Noticias e Inteligencia Reputacional por IA

Aplicación Web en Streamlit diseñada para el procesamiento automático, clustering temático jerárquico y evaluación reputacional (tono) de noticias corporativas mediante modelos de Inteligencia Artificial de OpenAI (gpt-4.1-nano y text-embedding-3-small).

💡 Características Principales

Normalización e Ingestión Flexible: Lee archivos Excel (.xlsx), estandariza campos de fecha, medios, enlaces, valores de PR y alcance.

Mapeo Dinámico vía Google Sheets: Obtiene de forma remota los mapeos de medios a regiones y medios online directamente desde URLs públicas de Google Sheets en formato CSV.

Clustering Temático Adaptativo (Subtemas): Combina embeddings vectoriales, DSU (Disjoint Set Union), clustering jerárquico aglomerativo y etiquetado inductivo por LLM para generar frases nominales representativas.

Macro Temas: Agrupa automáticamente decenas de subtemas en 5-15 grandes macro-categorías informativas.

Evaluación Reputacional de Tono con Concurrencia: Clasificación de impacto corporativo (Positivo, Neutro, Negativo) mediante prompts especializados en PR y ejecución asíncrona concurrente.

Reportes Descargables en Excel: Genera libros formateados profesionalmente con hojas resumen de Tabla General, Resumen por Tema, y métricas numéricas ajustadas.

🛠️ Requisitos Previos

Python 3.10+ instalado.

Cuenta de OpenAI con API Key válida.

Hojas de cálculo en Google Sheets (opcional para mapeos dinámicos) publicadas como CSV.

⚙️ Configuración del Entorno local y Secrets

Crea un directorio .streamlit/ en la raíz del proyecto y agrega el archivo secrets.toml:

APP_PASSWORD = "TuContraseñaSegura"
OPENAI_API_KEY = "sk-proj-..."

# URLs de publicación en web desde Google Sheets (opcionales)
REGIONES_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-xxx/pub?gid=0&single=true&output=csv"
INTERNET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-xxx/pub?gid=123456&single=true&output=csv"


Configurar Google Sheets para Mapeos de Medios:

En Google Sheets, crea una pestaña para Regiones (Columna A: Medio, Columna B: Región) y otra para Internet (Columna A: Nombre fuente, Columna B: Nombre normalizado).

Ve a Archivo > Compartir > Publicar en la web.

Selecciona la hoja correspondiente y exporta en formato CSV.

Copia el enlace generado en REGIONES_CSV_URL y INTERNET_CSV_URL.

🚀 Instalación y Ejecución

Clonar el repositorio o descargar el código:

git clone <URL_DEL_REPOSiTORIO>
cd analisis-noticias


Instalar dependencias:

pip install -r requirements.txt


Ejecutar la aplicación:

streamlit run app.py


📊 Estructura del Archivo Excel de Entrada (Dossier)

El sistema detecta automáticamente columnas que contengan palabras clave como:

Título / Titular: Texto principal de la noticia.

Resumen / Cuerpo / Descripción: Contenido o extracto.

Medio: Nombre del periódico, emisora o portal.

Tipo de Medio: Prensa, Radio, Televisión, Internet, etc.

Valor / Costo: Valor comercial ($).

Alcance / Audiencia: Número de personas impactadas.

Enlace / URL: Enlace a la publicación original.
