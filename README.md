# 📰 Grill-API — Análisis de Noticias

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://grill-api.streamlit.app/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/johnathanacortesd/Grill-API)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Plataforma y API de Procesamiento y Análisis de Noticias en Tiempo Real impulsada por Streamlit y Procesamiento de Lenguaje Natural (NLP).**

---

## 🎨 Logotipo ASCII (Corregido)

```text
  ____ ____  ___ _     _        _    ____ ___ 
 / ___|  _ \|_ _| |   | |      / \  |  _ \_ _|
| |  _| |_) || || |   | |     / _ \ | |_) | | 
| |_| |  _ < | || |___| |___ / ___ \|  __/| | 
 \____|_| \_\___|_____|_____/_/   \_\_|  |___|

================================================
     [ ANÁLISIS DE NOTICIAS & NLP API ]
```

---

## 🌐 Demo En Vivo

Puedes probar la aplicación e interfaz interactiva directamente en Streamlit Cloud:

👉 **[👑 Abrir Grill-API en Streamlit](https://grill-api.streamlit.app/)** 🎈

---

## 🔑 Clave de Acceso y Uso (*API Key*)

Para poder realizar consultas, procesar feeds de noticias y utilizar todas las funciones de análisis dentro de la plataforma, **se requiere una clave de acceso (Key)**.

### ¿Cómo ingresar la clave?
1. **En la Web (Streamlit):** Ingresa tu clave en la barra lateral (*Sidebar*) de la aplicación en el campo titulado **`Ingresar Clave / API Key`**.
2. **En Desarrollo Local:** Define la clave en tu archivo `.env` antes de iniciar la aplicación:

```env
GRILL_API_KEY=tu_clave_de_acceso_aqui
```

> ⚠️ *Sin una clave válida, las llamadas a los servicios de extracción y procesamiento de noticias estarán restringidas.*

---

## 🚀 Descripción General

**Grill-API** es una herramienta desarrollada para la ingesta, filtrado, extracción de métricas, procesamiento de sentimiento y visualización interactiva de noticias procedentes de múltiples fuentes digitales.

Diseñada con **Python** y **Streamlit**, permite a periodistas, analistas de datos y desarrolladores examinar tendencias, palabras clave y polaridad de medios informativos de manera rápida e intuitiva.

---

## ✨ Características Principales

- 🔍 **Búsqueda y Filtrado de Noticias:** Filtrado por palabras clave, fechas, categoría y medio informativo.
- 📊 **Análisis de Sentimiento:** Clasificación de noticias en tono *Positivo*, *Neutro* o *Negativo*.
- 🏷️ **Extracción de Entidades & Palabras Clave:** Identificación de personajes, organizaciones y lugares clave.
- 🎈 **Interfaz Interactiva:** Visualizaciones con gráficos dinámicos integrados en Streamlit.
- ⚡ **API Rest/Endpoints Integrados:** Servicios listos para consultar datos estructurados en JSON.

---

## 🏗️ Arquitectura del Sistema (ASCII Diagram)

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
|  | Extractor / Scraper|  | Validador de Clave |  | Módulo NLP /      | |
|  | (Ingesta)         |  | (Auth API Key)     |  | Sentimientos      | |
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

## 🛠️ Tecnologías Utilizadas

- **Lenguaje:** Python 3.10+
- **Frontend / Dashboard:** [Streamlit](https://streamlit.io/) 🎈
- **Análisis de Datos:** Pandas, NumPy
- **Visualización:** Plotly / Altair
- **NLP / Ingesta:** NLTK / TextBlob / Requests

---

## ⚙️ Instalación y Configuración Local

### 1. Clonar el repositorio

```bash
git clone https://github.com/johnathanacortesd/Grill-API.git
cd Grill-API
```

### 2. Crear entorno virtual e instalar dependencias

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Linux/macOS:
source venv/bin/activate
# En Windows:
# venv\Scripts\activate

# Instalar librerías
pip install -r requirements.txt
```

### 3. Configurar la Clave de Uso

Crea un archivo `.env` en la raíz del proyecto:

```bash
GRILL_API_KEY=tu_clave_de_acceso_aqui
```

### 4. Ejecutar la App en Streamlit

```bash
streamlit run app.py
```

Accede desde tu navegador en: `http://localhost:8501`

---

## 🤝 Contribución

1. Haz un **Fork** de este proyecto.
2. Crea una rama para tus mejoras (`git checkout -b feature/NuevaMejora`).
3. Guarda tus cambios (`git commit -m 'Añade nueva funcionalidad'`).
4. Envía los cambios a tu repositorio (`git push origin feature/NuevaMejora`).
5. Abre un **Pull Request**.

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo `LICENSE` para más detalles.

---

<p align="center">
  Creado por <a href="https://github.com/johnathanacortesd">Johnathan A. Cortés D.</a> — Desplegado con 🎈 Streamlit
</p>
```
