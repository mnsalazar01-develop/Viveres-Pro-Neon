import streamlit as st
import requests
import base64
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from difflib import SequenceMatcher

# --- CONFIGURACIÓN DE LA INTERFAZ DE STREAMLIT ---
st.set_page_config(page_title="Asociador Pro V2", page_icon="📸", layout="centered")
st.title("📸 Administrador de Imágenes de Productos (Neon + ImgBB)")
st.write("Selecciona un producto y el sistema buscará o subirá su imagen de forma inteligente.")

# Cargar secretos de forma segura desde Streamlit Cloud
try:
    url_limpia = st.secrets["neon"]["url"]
    IMGBB_API_KEY = st.secrets["imgbb"]["api_key"]
    IMGBB_ALBUM_ID = st.secrets["imgbb"]["album_id"]
except KeyError as e:
    st.error(f"❌ Error: Falta configurar la variable {e} en los Secrets de Streamlit.")
    st.stop()

# --- FUNCIÓN PARA LIMPIAR TEXTO Y EVITAR FALSOS POSITIVOS ---
def limpiar_texto(texto):
    if not texto:
        return ""
    texto = str(texto).lower()
    texto = re.sub(r'\.(jpg|jpeg|png|webp|gif|bmp)', '', texto)
    texto = re.sub(r'[^a-z0-9áéíóúñ\s]', ' ', texto)
    return " ".join(texto.split())

# --- FUNCIÓN PARA TRAER LOS PRODUCTOS AL SELECTBOX ---
@st.cache_data(ttl=60)
def obtener_lista_productos():
    conn = None
    try:
        conn = psycopg2.connect(url_limpia)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id_producto, nombre, marca, tamano, unidad FROM public.productos WHERE nombre IS NOT NULL ORDER BY nombre ASC;")
        productos = cur.fetchall()
        return productos
    except Exception as e:
        st.error(f"❌ Error al cargar catálogo de productos: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- FUNCIÓN PARA OBTENER TODAS LAS IMÁGENES DEL ÁLBUM VÍA API ---
@st.cache_data(ttl=300)
def obtener_todas_las_imagenes_imgbb():
    """Conecta a la API de ImgBB y extrae el listado completo de imágenes del álbum."""
    url_api = f"https://imgbb.com{IMGBB_ALBUM_ID}"
    parametros = {"key": IMGBB_API_KEY}
    try:
        respuesta = requests.get(url_api, params=parametros)
        resultado = respuesta.json()
        if resultado.get("status") == 200 and "data" in resultado:
            return resultado["data"].get("images", [])
        return []
    except:
        return []

# --- FUNCIÓN PARA SUBIR A IMGBB ---
def subir_imagen_a_album(imagen_bytes, nombre_producto):
    url_api = "https://imgbb.com"
    try:
        imagen_base64 = base64.b64encode(imagen_bytes).decode('utf-8')
        datos = {
            "key": IMGBB_API_KEY,
            "image": imagen_base64,
            "album_id": IMGBB_ALBUM_ID,
            "name": f"prod_{nombre_producto.replace(' ', '_').lower()}"
        }
        respuesta = requests.post(url_api, data=datos)
        resultado = respuesta.json()
        if resultado.get("status") == 200:
            return resultado["data"]["url"]
        else:
            st.error(f"❌ Error ImgBB: {resultado.get('error', {}).get('message')}")
            return None
    except Exception as e:
        st.error(f"❌ Error al procesar la subida: {e}")
        return None

# --- FUNCIÓN PARA GUARDAR EN NEON ---
def guardar_url_en_neon(id_producto, url_foto):
    id_parametro = str(id_producto)
    if not id_parametro.strip():
        st.error("❌ El ID de producto proporcionado está vacío.")
        return False

    query_update = """
        UPDATE public.productos 
        SET url_imagen = %s 
        WHERE id_producto = %s;
    """
    conn = None
    try:
        conn = psycopg2.connect(url_limpia)
        cur = conn.cursor()
        cur.execute(query_update, (str(url_foto).strip(), id_parametro))
        filas_afectadas = cur.rowcount
        
        if filas_afectadas == 0:
            st.warning(f"⚠️ No se encontró ningún producto con el ID exacto: '{id_parametro}'.")
            conn.rollback()
            return False
            
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Fallo crítico al escribir en Neon: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# --- FLUJO PRINCIPAL DEL PROGRAMA ---
catalogo = obtener_lista_productos()

if not catalogo:
    st.warning("⚠️ No se encontraron productos en la tabla 'productos' o la base de datos está vacía.")
else:
    # 1. Buscador de productos con identidad completa
    producto_seleccionado = st.selectbox(
        "1. Selecciona el Producto:",
        options=catalogo,
        format_func=lambda prod: f"{prod['nombre'] or ''} {prod['marca'] or ''} {prod['tamano'] or ''} {prod['unidad'] or ''}".strip()
    )
    
    id_prod = producto_seleccionado['id_producto']
    
    # Construcción de la identidad completa para la comparación inteligente
    componentes = [
        str(producto_seleccionado["nombre"] or ""),
        str(producto_seleccionado["marca"] or ""),
        str(producto_seleccionado["tamano"] or ""),
        str(producto_seleccionado["unidad"] or "")
    ]
    identidad_completa = " ".join([c.strip() for c in componentes if c.strip()])
    nombre_prod_limpio = limpiar_texto(identidad_completa)
    palabras_producto = set(nombre_prod_limpio.split())

    st.write("---")

    # 2. Selector de modalidad
    opcion_metodo = st.radio(
        "2. Selecciona el método para la imagen:",
        options=["Subir imagen desde la computadora", "Asociar a imagen existente en el álbum"]
    )

    st.write("---")

    # === MODALIDAD 1: SUBIR DESDE DISCO ===
    if opcion_metodo == "Subir imagen desde la computadora":
        archivo_imagen = st.file_uploader("Selecciona o arrastra la imagen del producto", type=["jpg", "jpeg", "png", "webp"])
        
        if archivo_imagen is not None:
            st.session_state["bytes_archivo_subido"] = archivo_imagen.getvalue()
            st.session_state["nombre_archivo_subido"] = archivo_imagen.name
        else:
            if "bytes_archivo_subido" in st.session_state:
                del st.session_state["bytes_archivo_subido"]
                del st.session_state["nombre_archivo_subido"]

        if "bytes_archivo_subido" in st.session_state:
            st.success(f"📸 Archivo cargado en memoria: {st.session_state['nombre_archivo_subido']}")
            
            if st.button("🚀 Subir e Inyectar en Neon", type="primary", use_container_width=True):
                with st.spinner("Procesando subida..."):
                    bytes_de_la_foto = st.session_state["bytes_archivo_subido"]
                    url_foto = subir_imagen_a_album(bytes_de_la_foto, identidad_completa)
                    
                    if url_foto:
                        if guardar_url_en_neon(id_prod, url_foto):
                            st.success(f"¡Éxito! Foto subida y asociada a '{identidad_completa}' correctamente. 🎉")
                            st.balloons()
                            del st.session_state["bytes_archivo_subido"]
                            st.rerun()
        else:
            st.info("💡 Sube una imagen desde tu PC para habilitar el botón de guardado.")

    # === MODALIDAD 2: ESCANEO AUTOMÁTICO DE ÁLBUM ===
    elif opcion_metodo == "Asociar a imagen existente en el álbum":
        st.write("🔍 **Buscador Inteligente Anti-Errores** (Evita cruzar café con carne molida)")
        
        umbral_confianza = st.slider("Ajustar nivel de precisión mínimo (%)", min_value=50, max_value=100, value=75, step=5)
        umbral_decimal = umbral_confianza / 100.0

        if st.button("🔍 Buscar coincidencia en el álbum entero", type="primary", use_container_width=True):
            with st.spinner("Escaneando el álbum remoto de ImgBB..."):
                imagenes_album = obtener_todas_las_imagenes_imgbb()
                
                if not imagenes_album:
                    st.error("❌ No se pudieron leer las imágenes automáticamente desde el álbum de ImgBB (verifica si el álbum es privado).")
                    st.info("💡 Como alternativa segura, puedes introducir el enlace directo abajo:")
                else:
                    mejor_similitud = 0.0
                    mejor_url = None
                    mejor_nombre_img = ""

                    for img in imagenes_album:
                        nombre_img_remota = limpiar_texto(img.get("title", "") or img.get("filename", ""))
                        palabras_img = set(nombre_img_remota.split())

                        # FILTRO CRUCIAL: Deben compartir al menos una palabra clave de identidad para evitar café vs carne
                        if not palabras_producto.intersection(palabras_img):
                            continue

                        similitud = SequenceMatcher(None, nombre_prod_limpio, nombre_img_remota).ratio()
                        if similitud > mejor_similitud:
                            mejor_similitud = similitud
                            mejor_url = img.get("url")
                            mejor_nombre_img = img.get("title") or img.get("filename")

                    # Validar si pasa el filtro configurado por el usuario
                    if mejor_similitud >= umbral_decimal and mejor_url:
                        st.session_state["url_detectada"] = mejor_url
                        st.session_state["nombre_img_detectada"] = mejor_nombre_img
                        st.session_state["similitud_detectada"] = mejor_similitud
                    else:
                        st.warning(f"⚠️ No se encontró ninguna imagen en el álbum que coincida con '{identidad_completa}' bajo un umbral del {umbral_confianza}%.")
                        if "url_detectada" in st.session_state:
                            del st.session_state["url_detectada"]

        # Mostrar resultados y botón de guardado fuera del bloque del botón de búsqueda para persistencia
        if "url_detectada" in st.session_state:
            st.write("---")
            st.success(f"🎯 ¡Coincidencia encontrada con el **{st.session_state['similitud_detectada']*100:.1f}%** de confianza!")
            st.write(f"**Producto:** `{identidad_completa}`")
            st.write(f"**Imagen en ImgBB:** `{st.session_state['nombre_img_detectada']}`")
            st.image(st.session_state["url_detectada"], caption="Imagen detectada en tu álbum", width=250)

            if st.button("💾 Confirmar y Guardar esta Asociación en Neon", use_container_width=True):
                with st.spinner("Guardando en Neon..."):
                    if guardar_url_en_neon(id_prod, st.session_state["url_detectada"]):
                        st.success("🎉 ¡Guardado exitosamente en la base de datos!")
                        del st.session_state["url_detectada"]
                        st.rerun()

        # Entrada manual de respaldo siempre visible si falla el escaneo automático
        st.write("---")
        st.write("📌 **Alternativa manual:**")
        url_manual = st.text_input("Pega la URL de la imagen aquí si prefieres hacerlo manualmente:", placeholder="https://ibb.co...")
        if url_manual:
            if st.button("🔗 Forzar asociación manual", use_container_width=True):
                with st.spinner("Guardando enlace manual..."):
                    if guardar_url_en_neon(id_prod, url_manual.strip()):
                        st.success("✅ Vinculado manualmente con éxito.")
                        st.rerun()
