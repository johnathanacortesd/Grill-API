# Grill-API — News Analytics & NLP Platform

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://grill-api.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen.svg)]()

```text
  ____ ____  ___ _     _        _    ____ ___ 
 / ___|  _ \|_ _| |   | |      / \  |  _ \_ _|
| |  _| |_) || || |   | |     / _ \ | |_) | | 
| |_| |  _ < | || |___| |___ / ___ \|  __/| | 
 \____|_| \_\___|_____|_____/_/   \_\_|  |___|
```

**Grill-API** es un motor de procesamiento y visualización interactiva para el análisis de noticias generando un tono, tema y subtema. La plataforma ingiere información del admin Grill de GlobalNews Group, aplicando técnicas de Procesamiento de Lenguaje Natural (NLP) para evaluar el sentimiento, extraer entidades nombradas y detectar tendencias informativas de forma automatizada agrupando noticias similares en mismos temas y subtemas y enfocando el tono al impacto de la marca analizada y no al conjunto total de la noticia.

---

## 🌐 Dashboard y Acceso

La plataforma se encuentra desplegada y disponible para pruebas en vivo:

* **URL de Producción:** [https://grill-api.streamlit.app/](https://grill-api.streamlit.app/)

### 🔒 Autenticación

El acceso a la interfaz de producción está resguardado mediante autenticación.

1. Al ingresar a la URL del proyecto, la aplicación solicitará una **contraseña de acceso**.
2. Ingrese las credenciales en el campo de entrada ubicado en el módulo de autenticación (o menú lateral).
3. Una vez validada la contraseña, se desbloquearán los módulos de ingesta, análisis de métricas y gráficos en tiempo real.

> **Nota para evaluadores:** Solicite la contraseña de acceso directamente al mantenedor del proyecto ([@johnathanacortesd](https://github.com/johnathanacortesd)).

---

## 🚀 Funcionalidades

- **Ingesta Multi-fuente:** Captura y normalización de artículos desde RSS, sitios web y conectores de API.
- **Análisis de Sentimientos:** Clasificación automatizada de titulares y contenido en espectros positivo, neutro y negativo.
- **Extracción de Entidades y Palabras Clave:** Detección de organizaciones, personajes públicos y términos recurrentes.
- **Visualización Dinámica:** Cuadros de mando interactivos con filtros temporales, categoría y medio.
- **Estructuración de Datos:** Exportación y procesamiento estructurado listo para integración con otros sistemas.

---

## 🏗️ Arquitectura del Sistema

```text
+-----------------------------------------------------------------------+
|                         FUENTES DE NOTICIAS                           |
|            [ RSS Feeds ]     [ Web Portals ]     [ APIs ]             |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                              GRILL-API                                |
|  +-------------------+  +--------------------+  +-------------------+ |
|  | Extractor / Ingesta|  | Modulo de Auth     |  | Pipeline NLP /    | |
|  | (Data Collector)  |  | (Secrets & Session)|  | Sentiment Engine  | |
|  +-------------------+  +--------------------+  +-------------------+ |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                          INTERFAZ STREAMLIT                           |
|        [ Dashboard Web ]  <--->  https://grill-api.streamlit.app/     |
+-----------------------------------------------------------------------+
```

---

## 🛠️ Stack Tecnológico

- **Core Engine:** Python 3.10+
- **Frontend / Dashboard:** Streamlit
- **Procesamiento de Datos:** Pandas, NumPy
- **NLP & Analítica:** NLTK, TextBlob, SpaCy *(según módulo)*
- **Visualización:** Plotly, Altair
- **Infraestructura:** Streamlit Cloud Container Runtime

---

## ⚙️ Instalación y Ejecución Local

### Prerrequisitos

- Python 3.10 o superior
- `pip` y `virtualenv`

### 1. Clonar el repositorio

```bash
git clone https://github.com/johnathanacortesd/Grill-API.git
cd Grill-API
```

### 2. Configurar el entorno virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar en Linux/macOS
source venv/bin/activate

# Activar en Windows
# venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configuración de Secretos

Cree la carpeta `.streamlit` y el archivo `secrets.toml` dentro de la raíz del proyecto para definir la contraseña de acceso local:

```bash
mkdir -p .streamlit
cat <<EOF > .streamlit/secrets.toml
password = "tu_contrasena_local"
EOF
```

### 4. Ejecutar la aplicación

```bash
streamlit run app.py
```

La aplicación estará disponible en `http://localhost:8501`.

---

## ☁️ Despliegue en Producción

Para desplegar esta aplicación en **Streamlit Community Cloud**:

1. Vincule el repositorio `johnathanacortesd/Grill-API`.
2. Configure el archivo de inicio como `app.py`.
3. En la sección **Advanced Settings -> Secrets**, agregue la variable de entorno correspondiente a la contraseña:

```toml
password = "tu_contrasena_de_produccion"
```

---

## 📄 Licencia

Este proyecto está distribuido bajo la licencia **MIT**. Para más detalles, consulte el archivo [LICENSE](LICENSE).

---

**Mantenedor:** [Johnathan A. Cortés D.](https://github.com/johnathanacortesd)
```
