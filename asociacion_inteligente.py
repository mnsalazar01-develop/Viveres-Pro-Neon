import re
from difflib import SequenceMatcher
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import streamlit as st

# Cargar secretos de forma segura desde Streamlit Cloud
try:
    url_limpia = st.secrets["neon"]["url"]
    IMGBB_API_KEY = st.secrets["imgbb"]["api_key"]
    IMGBB_ALBUM_ID = st.secrets["imgbb"]["album_id"]
except KeyError as e:
    st.error(f"❌ Error: Falta configurar la variable {e} en los Secrets de Streamlit.")
    st.stop()

st.title("🔄 Vinculación Inteligente Avanzada por CSV (Neon)")
st.write("Sube tu archivo CSV o Excel. El sistema comparará usando Nombre, Marca, Tamaño y Unidad.")

# Componente para subir el archivo de manera interactiva
archivo_subido = st.file_uploader("Sube tu archivo CSV o Excel con los enlaces:", type=["csv", "xlsx"])

# Control interactivo para el umbral de confianza (Recomendado: 75% - 80%)
umbral_confianza = st.slider("⚙️ Ajustar umbral de confianza mínimo para asociar:", min_value=40, max_value=100, value=75, step=5)
umbral_decimal = umbral_confianza / 100.0

# Función mejorada para limpiar y normalizar texto
def limpiar_texto(texto):
    if not texto:
        return ""
    texto = str(texto).lower()
    # Quitar extensiones de imagen comunes
    texto = re.sub(r'\.(jpg|jpeg|png|webp|gif|bmp)', '', texto)
    # Reemplazar caracteres especiales por espacios
    texto = re.sub(r'[^a-z0-9áéíóúñ\s]', ' ', texto)
    return " ".join(texto.split())

# 1. ANALIZAR Y BUSCAR COINCIDENCIAS
if st.button("🔍 Analizar Archivo y Buscar Coincidencias"):
    if archivo_subido is None:
        st.warning("⚠️ Por favor, primero sube un archivo CSV o Excel.")
    else:
        try:
            # Leer el archivo dependiendo de su extensión
            if archivo_subido.name.endswith('.csv'):
                df_imagenes = pd.read_csv(archivo_subido)
            else:
                df_imagenes = pd.read_excel(archivo_subido)
            
            # Detectar automáticamente la columna que contiene los enlaces de ImgBB
            columna_url = None
            for col in df_imagenes.columns:
                if any(palabra in col.lower() for palabra in ["url", "link", "enlace", "href", "direct"]):
                    columna_url = col
                    break
            
            if not columna_url:
                columna_url = df_imagenes.columns[0]
                st.info(f"💡 No se detectó una columna con el nombre 'url'. Usando la primera columna: `{columna_url}`")

            # Extraer las URLs válidas
            texto_completo_urls = " ".join(df_imagenes[columna_url].dropna().astype(str).tolist())
            urls_imgbb = re.findall(r'https://(?:i\.)?ibb\.co/[^\s,\"\'>]+', texto_completo_urls)

            lista_imgbb = list()
            for url in urls_imgbb:
                url_limpia_enlace = url.strip().rstrip(',')
                nombre_archivo = url_limpia_enlace.split("/")[-1]
                
                lista_imgbb.append({
                    "url": url_limpia_enlace,
                    "nombre_limpio": limpiar_texto(nombre_archivo)
                })

            st.info(f"📦 Se procesaron **{len(lista_imgbb)}** enlaces de ImgBB desde el archivo.")

            if len(lista_imgbb) == 0:
                st.error("❌ No se encontraron enlaces válidos que apunten a ImgBB.")
            else:
                st.write("🔌 Conectando a Neon y descargando catálogo de productos...")
                conn = psycopg2.connect(url_limpia)
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                # Traemos nombre, marca, tamaño y unidad para armar la identidad completa
                cursor.execute("SELECT id_producto, nombre, marca, tamano, unidad FROM public.productos;")
                productos = cursor.fetchall()

                actualizaciones = list()
                
                for prod in productos:
                    # Construir la identidad completa del producto de forma robusta
                    componentes = [
                        str(prod["nombre"] or ""),
                        str(prod["marca"] or ""),
                        str(prod["tamano"] or ""),
                        str(prod["unidad"] or "")
                    ]
                    # Filtrar textos vacíos y unir con espacios
                    nombre_completo_prod = " ".join([c.strip() for c in componentes if c.strip()])
                    nombre_prod_limpio = limpiar_texto(nombre_completo_prod)
                    
                    # Obtener las palabras clave del nombre real para validación cruzada
                    palabras_producto = set(nombre_prod_limpio.split())
                    
                    mejor_similitud = 0.0
                    mejor_url = None
                    mejor_nombre_img = ""
                    
                    for img in lista_imgbb:
                        palabras_img = set(img["nombre_limpio"].split())
                        
                        # VALIDACIÓN CRUCIAL: Si no comparten al menos una palabra clave principal
                        # (por ejemplo, que la imagen contenga "cafe" si el producto es "cafe"), se descarta.
                        if not palabras_producto.intersection(palabras_img):
                            continue
                            
                        # Si pasa el filtro de palabras, medimos el parecido de la cadena completa
                        similitud = SequenceMatcher(None, nombre_prod_limpio, img["nombre_limpio"]).ratio()
                        
                        if similitud > mejor_similitud:
                            mejor_similitud = similitud
                            mejor_url = img["url"]
                            mejor_nombre_img = img["nombre_limpio"]
                            
                    # Aplicar el filtro dinámico seleccionado por el usuario en el Slider
                    if mejor_similitud >= umbral_decimal:
                        actualizaciones.append({
                            "id_producto": prod["id_producto"],
                            "producto_completo": nombre_completo_prod,
                            "imagen_detectada": mejor_nombre_img,
                            "url_nueva": mejor_url,
                            "confianza": mejor_similitud
                        })

                if not actualizaciones:
                    st.warning("⚠️ No se encontraron coincidencias con el umbral actual. Prueba bajando un poco el slider de confianza.")
                else:
                    df_resumen = pd.DataFrame(actualizaciones)
                    df_resumen["confianza_porcentaje"] = df_resumen["confianza"].apply(lambda x: f"{x * 100:.1f}%")
                    
                    st.write(f"### --- COINCIDENCIAS DETECTADAS (Umbral mínimo: {umbral_confianza}%) ---")
                    st.dataframe(df_resumen[["producto_completo", "imagen_detectada", "confianza_porcentaje"]])
                    
                    st.session_state["pendientes_actualizar"] = actualizaciones
                
                cursor.close()
                conn.close()

        except Exception as e:
            st.error(f"❌ Ocurrió un error al procesar el archivo: {e}")

# 2. APLICAR CAMBIOS EN LA BASE DE DATOS
if "pendientes_actualizar" in st.session_state and st.session_state["pendientes_actualizar"]:
    st.write("---")
    st.warning("⚠️ Confirmación: Al presionar el botón de abajo se guardarán definitivamente las nuevas URLs en Neon.")
    
    if st.button("💾 Guardar URLs en Base de Datos (Neon)"):
        try:
            conn = psycopg2.connect(url_limpia)
            cursor = conn.cursor()
            
            query_update = "UPDATE public.productos SET url_imagen = %s WHERE id_producto = %s;"
            
            for cambio in st.session_state["pendientes_actualizar"]:
                cursor.execute(query_update, (cambio["url_nueva"], cambio["id_producto"]))
                
            conn.commit()
            st.success(f"✅ ¡Éxito! Se vincularon {len(st.session_state['pendientes_actualizar'])} imágenes en tu base de datos de Neon.")
            
            st.session_state["pendientes_actualizar"] = list()
            cursor.close()
            conn.close()
        except Exception as e:
            st.error(f"❌ Error al guardar los datos en Neon: {e}")
