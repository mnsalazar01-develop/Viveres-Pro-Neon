import psycopg2
from psycopg2.extras import execute_values
import pandas as pd

def sincronizar_desde_csv(ruta_csv, url_neon):
    # 1. Leer el archivo CSV
    try:
        df = pd.read_csv(ruta_csv)
        # Reemplazar valores Nulos/NaN de Pandas por None para que la BD los entienda como NULL
        df = df.astype(object).where(pd.notnull(df), None)
    except Exception as e:
        print(f"❌ Error al leer el archivo CSV: {e}")
        return False

    # 2. Mapear las columnas exactamente como están en tu archivo y tu BD
    # Asegúrate de que el orden de esta lista coincida con el INSERT de abajo
    columnas_validas = [
        "id_producto", "codigo_barras", "nombre", "marca", "tamano", "unidad", 
        "url_imagen", "id_cat", "id_subcat", "es_favorito", "alta_demanda", 
        "es_estrategico", "cod_verif", "id_catalogo", "id_marca", "id_segmento", "id_producto_mayor"
    ]
    
    # Convertimos el DataFrame a una lista de tuplas
    valores = list(df[columnas_validas].itertuples(index=False, name=None))
    
    # 3. Definir la consulta SQL con lógica UPSERT (ON CONFLICT)
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
    
    # 4. Conectar a Neon y ejecutar
    conn = None
    try:
        conn = psycopg2.connect(url_neon)
        cur = conn.cursor()
        
        # Envía todos los registros en un solo viaje de red masivo
        execute_values(cur, query, valores)
        conn.commit()
        
        print(f"🎉 Sincronización completada con éxito. Se procesaron {len(valores)} productos.")
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error en la base de datos durante la sincronización: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- EJEMPLO DE USO ---
# URL_NEON = "postgresql://usuario:contraseña@ep-xxxxx.neon.tech/neondb?sslmode=require"
# sincronizar_desde_csv("mis_nuevos_productos.csv", URL_NEON)
