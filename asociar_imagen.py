import streamlit as st
import requests
import base64
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from difflib import SequenceMatcher
import pandas as pd  # <--- ¡ESTA ES LA LÍNEA QUE FALTA AGREGAR!

# --- CONFIGURACIÓN DE LA INTERFAZ DE STREAMLIT ---
st.set_page_config(page_title="Asociador Pro V2", page_icon="📸", layout="wide") # Layout ancho para la grilla
st.title("📸 Administrador de Imágenes de Productos (Neon + ImgBB)")
st.write("Selecciona un producto individual o procesa imágenes de forma masiva con validación visual.")

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

# --- FUNCIÓN PARA SUBIR A IMGBB ---
def subir_imagen_a_album(imagen_bytes, nombre_producto):
    url_api = "https://imgbb.com"
    try:
        # Sanitizar el nombre para que no lleve espacios problemáticos en el envío de archivos
        nombre_limpio_api = f"prod_{nombre_producto.replace(' ', '_').lower()}"
        
        # Parámetros obligatorios en la URL/Data string
        payload = {
            "key": IMGBB_API_KEY,
            "album_id": IMGBB_ALBUM_ID,
            "name": nombre_limpio_api
        }
        
        # Enviamos el archivo de forma binaria nativa (multipart/form-data)
        # Esto es mucho más ligero y reduce errores de procesamiento en ImgBB
        files = {
            "image": (f"{nombre_limpio_api}.png", imagen_bytes, "image/png")
        }
        
        respuesta = requests.post(url_api, data=payload, files=files)
        
        # Validar si el servidor respondió con un código de error HTTP
        if respuesta.status_code != 200:
            st.error(f"❌ Error de red ImgBB (Código {respuesta.status_code}): El servidor rechazó la solicitud.")
            return None
            
        resultado = respuesta.json()
        if resultado.get("status") == 200:
            return resultado["data"]["url"]
        else:
            st.error(f"❌ Error ImgBB: {resultado.get('error', {}).get('message')}")
            return None
    except requests.exceptions.JSONDecodeError:
        st.error("❌ Fallo en ImgBB: La API devolvió una respuesta vacía o un código HTML inválido en lugar de JSON. Inténtalo de nuevo en unos segundos.")
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
    # Selector de modalidad global
    opcion_metodo = st.radio(
        "⚙️ Selecciona el método de trabajo:",
        options=["Subir imagen individual desde la computadora", "Carga masiva desde la computadora con Grilla de Validación"],
        horizontal=True
    )

    st.write("---")

    # === MODALIDAD 1: INDIVIDUAL ===
    if opcion_metodo == "Subir imagen individual desde la computadora":
        # Buscador de productos con identidad completa
        producto_seleccionado = st.selectbox(
            "1. Selecciona el Producto:",
            options=catalogo,
            format_func=lambda prod: f"{prod['nombre'] or ''} {prod['marca'] or ''} {prod['tamano'] or ''} {prod['unidad'] or ''}".strip()
        )
        
        id_prod = producto_seleccionado['id_producto']
        
        componentes = [
            str(producto_seleccionado["nombre"] or ""),
            str(producto_seleccionado["marca"] or ""),
            str(producto_seleccionado["tamano"] or ""),
            str(producto_seleccionado["unidad"] or "")
        ]
        identidad_completa = " ".join([c.strip() for c in componentes if c.strip()])

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

    # === MODALIDAD 2: CARGA MASIVA LOCAL CON GRILLA INTERACTIVA (CORREGIDA SIN ARROW ERROR) ===
    elif opcion_metodo == "Carga masiva desde la computadora con Grilla de Validación":
        st.write("🚀 **Buscador Inteligente con Grilla Masiva** (Evita cruzar café con carne molida)")
        st.info("💡 Arrastra aquí todas las fotos de tus productos juntas. El sistema buscará a qué producto corresponden y armará una grilla visual con sus checks.")

        archivos_locales = st.file_uploader(
            "Selecciona o arrastra múltiples imágenes de productos de tu PC:", 
            type=["jpg", "jpeg", "png", "webp"], 
            accept_multiple_files=True
        )

        umbral_confianza = st.slider("Ajustar nivel de precisión mínimo (%)", min_value=40, max_value=100, value=75, step=5)
        umbral_decimal = umbral_confianza / 100.0

        if archivos_locales:
            coincidencias_calculadas = []
            
            with st.spinner("Analizando nombres de archivos locales y buscando coincidencias..."):
                for archivo in archivos_locales:
                    nombre_archivo_limpio = limpiar_texto(archivo.name)
                    palabras_img = set(nombre_archivo_limpio.split())
                    
                    mejor_similitud = 0.0
                    producto_asociado = None
                    
                    # Comparar de forma inteligente contra todo el catálogo cargado en memoria
                    for prod in catalogo:
                        componentes = [
                            str(prod["nombre"] or ""),
                            str(prod["marca"] or ""),
                            str(prod["tamano"] or ""),
                            str(prod["unidad"] or "")
                        ]
                        id_completa_prod = " ".join([c.strip() for c in componentes if c.strip()])
                        prod_limpio = limpiar_texto(id_completa_prod)
                        palabras_producto = set(prod_limpio.split())
                        
                        # FILTRO CRUCIAL: Evitar café vs carne molida
                        if not palabras_producto.intersection(palabras_img):
                            continue
                            
                        similitud = SequenceMatcher(None, prod_limpio, nombre_archivo_limpio).ratio()
                        if similitud > mejor_similitud:
                            mejor_similitud = similitud
                            producto_asociado = prod
                    
                    # Si supera el umbral, lo empaquetamos temporalmente para la grilla
                    if mejor_similitud >= umbral_decimal and producto_asociado:
                        componentes_asoc = [
                            str(producto_asociado["nombre"] or ""),
                            str(producto_asociado["marca"] or ""),
                            str(producto_asociado["tamano"] or ""),
                            str(producto_asociado["unidad"] or "")
                        ]
                        nombre_final_prod = " ".join([c.strip() for c in componentes_asoc if c.strip()])
                        
                        coincidencias_calculadas.append({
                            "id_producto": producto_asociado["id_producto"],
                            "Producto sugerido en Neon": nombre_final_prod,
                            "Archivo Local": archivo.name,
                            "Porcentaje Confianza": f"{mejor_similitud * 100:.1f}%",
                            "Validar": True,  # Marcado por defecto para agilizar tu flujo
                            "_file_object": archivo  # Guardamos el puntero al archivo para subirlo después
                        })

            # Renderizado de la grilla interactiva si hay resultados
            if coincidencias_calculadas:
                st.write("---")
                st.subheader(f"📋 Grilla de Verificación Masiva ({len(coincidencias_calculadas)} coincidencias listas)")
                st.write("Revisa la lista. Si detectas un error, simplemente **desmarca la casilla** en la columna ¿Es correcto?.")

                # CREACIÓN COMPATIBLE CON PYARROW: Creamos un DataFrame excluyendo el objeto de archivo crudo
                columnas_visibles = [
                    {k: v for k, v in item.items() if k != "_file_object"} 
                    for item in coincidencias_calculadas
                ]
                df_grilla = pd.DataFrame(columnas_visibles)

                # Mostramos la tabla editable al usuario
                grilla_editada = st.data_editor(
                    df_grilla,
                    column_config={
                        "Producto sugerido en Neon": st.column_config.TextColumn("Producto en Base de Datos", width="large", disabled=True),
                        "Archivo Local": st.column_config.TextColumn("Nombre del Archivo Local", width="medium", disabled=True),
                        "Porcentaje Confianza": st.column_config.TextColumn("Confianza", disabled=True),
                        "Validar": st.column_config.CheckboxColumn("¿Es correcto?", help="Mantén marcado para subir a ImgBB y guardar en Neon"),
                        "id_producto": None  # Ocultar columna técnica id
                    },
                    disabled=["Producto sugerido en Neon", "Archivo Local", "Porcentaje Confianza"],
                    hide_index=True,
                    use_container_width=True
                )

                st.write("---")
                st.warning("⚠️ Al presionar el botón, el sistema subirá de manera automática las imágenes aprobadas a ImgBB y las inyectará en Neon.")

                if st.button("🔥 Procesar y Guardar Cambios Aprobados", type="primary", use_container_width=True):
                    # Filtrar qué filas dejó el usuario con el check en True
                    filas_aprobadas_indices = grilla_editada[grilla_editada["Validar"] == True].index.tolist()

                    if not filas_aprobadas_indices:
                        st.warning("⚠️ No seleccionaste ninguna fila para procesar.")
                    else:
                        progreso = st.progress(0)
                        exitos = 0

                        for i, idx in enumerate(filas_aprobadas_indices):
                            # Rescatamos el objeto de archivo original a través de la lista original usando el índice
                            datos_origen = coincidencias_calculadas[idx]
                            archivo_original = datos_origen["_file_object"]
                            id_producto_neon = datos_origen["id_producto"]
                            nombre_para_url = datos_origen["Producto sugerido en Neon"]

                            st.write(f"🔄 Subiendo `{archivo_original.name}` a ImgBB e inyectando en Neon...")

                            # 1. Subir los bytes a internet vía la API
                            url_imgbb = subir_imagen_a_album(archivo_original.getvalue(), nombre_para_url)

                            # 2. Si se generó el enlace, lo guardamos en la fila de la base de datos
                            if url_imgbb:
                                if guardar_url_en_neon(id_producto_neon, url_imgbb):
                                    exitos += 1

                            progreso.progress((i + 1) / len(filas_aprobadas_indices))

                        st.success(f"🎉 ¡Inyección masiva completada! Se guardaron con éxito **{exitos}** de **{len(filas_aprobadas_indices)}** productos en Neon.")
                        st.balloons()
                        st.rerun()
            else:
                st.warning("⚠️ No se encontraron productos coincidentes para los nombres de estas fotos bajo el umbral de confianza actual.")

