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

st.title("🔄 Vinculación Inteligente mediante CSV (Neon)")
st.write("Sube el archivo CSV o Excel exportado con los enlaces de ImgBB para cruzarlos con tu base de datos.")

# Componente para subir el archivo de manera interactiva
archivo_subido = st.file_uploader("Sube tu archivo CSV o Excel con los enlaces:", type=["csv", "xlsx"])

# Función para limpiar texto y facilitar la comparación
def limpiar_texto(texto):
    if not texto:
        return ""
    texto = str(texto).lower()
    texto = re.sub(r'\.(jpg|jpeg|png|webp|gif|bmp)', '', texto)
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
            
            # Intentar detectar automáticamente la columna que contiene los enlaces de ImgBB
            columna_url = None
            for col in df_imagenes.columns:
                if any(palabra in col.lower() for palabra in ["url", "link", "enlace", "href", "direct"]):
                    columna_url = col
                    break
            
            # Si no encuentra un nombre obvio, toma la primera columna del archivo
            if not columna_url:
                columna_url = df_imagenes.columns[0]
                st.info(f"💡 No se detectó una columna con el nombre 'url'. Usando la primera columna: `{columna_url}`")

            # Convertir las celdas de la columna seleccionada a texto plano para extraer las URLs
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

            st.info(f"📦 Se procesaron **{len(lista_imgbb)}** enlaces de ImgBB desde el archivo `{archivo_subido.name}`.")

            if len(lista_imgbb) == 0:
                st.error("❌ No se encontraron enlaces válidos que apunten a ImgBB en la columna seleccionada.")
            else:
                st.write("🔌 Conectando a la base de datos de Neon...")
                conn = psycopg2.connect(url_limpia)
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                
                cursor.execute("SELECT id_producto, nombre FROM public.productos;")
                productos = cursor.fetchall()

                actualizaciones = list()
                
                for prod in productos:
                    nombre_prod_limpio = limpiar_texto(prod["nombre"])
                    mejor_similitud = 0.0
                    mejor_url = None
                    mejor_nombre_img = ""
                    
                    for img in lista_imgbb:
                        similitud = SequenceMatcher(None, nombre_prod_limpio, img["nombre_limpio"]).ratio()
                        
                        if similitud > mejor_similitud:
                            mejor_similitud = similitud
                            mejor_url = img["url"]
                            mejor_nombre_img = img["nombre_limpio"]
                            
                    # Si el parecido es igual o mayor al 60%
                    if mejor_similitud >= 0.60:
                        actualizaciones.append({
                            "id_producto": prod["id_producto"],
                            "nombre": prod["nombre"],
                            "imagen_detectada": mejor_nombre_img,
                            "url_nueva": mejor_url,
                            "confianza": mejor_similitud
                        })

                if not actualizaciones:
                    st.warning("⚠️ No se encontraron coincidencias automáticas. Prueba a renombrar los archivos del CSV con palabras clave similares a tus productos.")
                else:
                    df_resumen = pd.DataFrame(actualizaciones)
                    df_resumen["confianza_porcentaje"] = df_resumen["confianza"].apply(lambda x: f"{x * 100:.1f}%")
                    
                    st.write("### --- RESUMEN DE COINCIDENCIAS DETECTADAS ---")
                    st.dataframe(df_resumen[["nombre", "imagen_detectada", "confianza_porcentaje"]])
                    
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
