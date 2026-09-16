import streamlit as st
import psycopg2
from psycopg2.extras import execute_values
import pandas as pd

st.title("🔄 Sincronizador de Productos - Neon")

# 1. Obtener de forma segura la URL de conexión desde los Secrets
try:
    URL_NEON = st.secrets["NEON_URL"]
except KeyError:
    st.error("❌ No se encontró la variable 'NEON_URL' en los Secrets de Streamlit.")
    st.stop()

# Componente para subir el archivo CSV
archivo_subido = st.file_uploader("Sube tu archivo CSV con los nuevos productos", type=["csv"])

if archivo_subido is not None:
    try:
        # Leer el CSV subido en memoria
        df = pd.read_csv(archivo_subido)
        # Limpieza de datos: convertir NaN de Pandas a None para PostgreSQL (NULL)
        df = df.astype(object).where(pd.notnull(df), None)
        
        st.write("📋 **Vista previa de los datos a sincronizar:**")
        st.dataframe(df.head())
        
        # Mapeo estricto de columnas (deben coincidir con tu CSV y tu base de datos)
        columnas_validas = [
            "id_producto", "codigo_barras", "nombre", "marca", "tamano", "unidad", 
            "url_imagen", "id_cat", "id_subcat", "es_favorito", "alta_demanda", 
            "es_estrategico", "cod_verif", "id_catalogo", "id_marca", "id_segmento", "id_producto_mayor"
        ]
        
        # Filtrar y ordenar el dataframe solo con las columnas requeridas
        df_filtrado = df[columnas_validas]
        valores = list(df_filtrado.itertuples(index=False, name=None))
        
        # Botón para ejecutar la acción de sincronización
        if st.button("🚀 Iniciar Sincronización Masiva"):
            with st.spinner("Conectando a Neon y actualizando productos..."):
                
                # Consulta SQL con lógica UPSERT (Evita duplicados por id_producto)
                query = """
                    INSERT INTO public.productos (
                        id_producto, codigo_barras, nombre, marca, tamano, unidad, 
                        url_imagen, id_cat, id_subcat, es_favorito, alta_demanda, 
                        es_estrategico, cod_verif, id_catalogo, id_marca, id_segmento, id_producto_mayor
                    ) VALUES %s
                    ON CONFLICT (id_producto) 
                    DO UPDATE SET 
                        codigo_barras = EXCLUDED.codigo_barras,
                        nombre = EXCLUDED.nombre,
                        marca = EXCLUDED.marca,
                        tamano = EXCLUDED.tamano,
                        unidad = EXCLUDED.unidad,
                        url_imagen = EXCLUDED.url_imagen,
                        id_cat = EXCLUDED.id_cat,
                        id_subcat = EXCLUDED.id_subcat,
                        es_favorito = EXCLUDED.es_favorito,
                        alta_demanda = EXCLUDED.alta_demanda,
                        es_estrategico = EXCLUDED.es_estrategico,
                        cod_verif = EXCLUDED.cod_verif,
                        id_catalogo = EXCLUDED.id_catalogo,
                        id_marca = EXCLUDED.id_marca,
                        id_segmento = EXCLUDED.id_segmento,
                        id_producto_mayor = EXCLUDED.id_producto_mayor;
                """
                
                conn = None
                try:
                    conn = psycopg2.connect(URL_NEON)
                    cur = conn.cursor()
                    
                    # Inserción/Actualización masiva ultra rápida
                    execute_values(cur, query, valores)
                    conn.commit()
                    
                    st.success(f"🎉 ¡Sincronización exitosa! Se procesaron {len(valores)} productos de forma segura.")
                    
                except Exception as e:
                    if conn:
                        conn.rollback()
                    st.error(f"❌ Error en la base de datos durante la carga: {e}")
                finally:
                    if conn:
                        conn.close()
                        
    except Exception as error_csv:
        st.error(f"❌ Error al procesar el archivo CSV: {error_csv}")
