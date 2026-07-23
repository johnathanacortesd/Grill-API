# 📰 Grill-API — Análisis de Noticias

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://grill-api.streamlit.app/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/johnathanacortesd/Grill-API)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Plataforma y API de Procesamiento, Extracción y Análisis de Noticias en Tiempo Real impulsada por Streamlit y Procesamiento de Lenguaje Natural (NLP).**

---

## 🎨 Logotipo ASCII

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

Puedes acceder a la plataforma interactiva desplegada en Streamlit Cloud:

👉 **[👑 Abrir Grill-API en Streamlit](https://grill-api.streamlit.app/)** 🎈

---

## 🔐 Acceso a la App (Contraseña / Auth)

La aplicación web alojada en **[grill-api.streamlit.app](https://grill-api.streamlit.app/)** está **protegida por contraseña** para controlar el acceso y proteger los recursos de consulta.

```text
+-------------------------------------------------------------+
|                     📰 GRILL-API LOGIN                      |
|                                                             |
|   🔒 Acceso Restringido - Ingrese su Contraseña             |
|   Contraseña: [ ************ ]  [ 🔓 Ingresar ]             |
|                                                             |
+-------------------------------------------------------------+
```

### 🔑 ¿Cómo ingresar?
1. Entra al enlace [https://grill-api.streamlit.app/](https://grill-api.streamlit.app/).
2. Escribe la **contraseña de acceso** en el cuadro de texto del formulario inicial o barra lateral.
3. Haz clic en **Ingresar / Login** para desbloquear el panel de control de noticias.

> 📌 **Solicitud de Acceso:**  
> Si necesitas acceso a la demostración o una clave de prueba, ponte en contacto con el creador del repositorio: **[@johnathanacortesd](https://github.com/johnathanacortesd)**.

---

## 🚀 Descripción General

**Grill-API** es un sistema diseñado para centralizar la ingesta, filtrado, extracción de métricas, evaluación de sentimiento y visualización interactiva de noticias procedentes de diversas fuentes informativas.

Construida con **Python** y **Streamlit**, permite examinar tendencias, temas emergentes, palabras clave y polaridad de medios de comunicación de forma ágil y visual.

---

## ✨ Características Principales

- 🔍 **Búsqueda y Filtrado de Noticias:** Búsquedas por palabras clave, fechas y fuentes de medios.
- 📊 **Análisis de Sentimiento (NLP):** Clasificación de noticias en tono *Positivo*, *Neutro* o *Negativo*.
- 🏷️ **Extracción de Entidades:** Identificación de entidades clave, personajes y organizaciones.
- 🎈 **Dashboard Interactivo:** Gráficos dinámicos e indicadores métricos en Streamlit.
- ⚡ **API Rest / Ingesta:** Módulos listos para consultar y estructurar datos en formato JSON.

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
|  | Extractor / Scraper|  | Módulo de Auth     |  | Módulo NLP /      | |
|  | (Ingesta)         |  | (Contraseña / Auth)|  | Sentimientos      | |
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
- **Interfaz Web / Dashboard:** [Streamlit](https://streamlit.io/) 🎈
- **Análisis de Datos:** Pandas, NumPy
- **Visualización:** Plotly / Altair
- **Procesamiento de Lenguaje Natural (NLP):** NLTK / TextBlob / Requests

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

### 3. Configurar la Contraseña de Acceso (Secrets)

Para definir la contraseña en desarrollo local, crea un archivo `.streamlit/secrets.toml` en la raíz del proyecto:

```toml
# .streamlit/secrets.toml
password = "tu_contraseña_aqui"
```

*Si despliegas en **Streamlit Cloud**, añade esta variable dentro de la sección **Settings ➔ Secrets** de tu panel.*

### 4. Ejecutar la App

```bash
streamlit run app.py
```

Accede desde tu navegador en: `http://localhost:8501`

---

## 🤝 Contribución

1. Haz un **Fork** de este repositorio.
2. Crea una rama para tu característica (`git checkout -b feature/NuevaCaracteristica`).
3. Guarda tus cambios (`git commit -m 'Añade nueva funcionalidad'`).
4. Sube la rama (`git push origin feature/NuevaCaracteristica`).
5. Abre un **Pull Request**.

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Consulta el archivo `LICENSE` para más detalles.

---

<p align="center">
  Creado por <a href="https://github.com/johnathanacortesd">Johnathan A. Cortés D.</a> — Desplegado con 🎈 Streamlit
</p>
```
