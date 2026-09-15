import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Editor de Campañas", layout="wide")
st.title("⚙️ Editor de Campañas y Configuración de Estados")

# --- OBTENER URL DE CONEXIÓN
try:
    URL_NEON = st.secrets["neon"]["url"]
except KeyError:
    st.error("❌ Error: Falta la variable ['neon']['url'] en los secrets.")
    st.stop()

# --- FUNCIONES DE BASE DE DATOS
def ejecutar_consulta(query, params=None):
    """Ejecuta consultas de lectura."""
    conn = None
    try:
        conn = psycopg2.connect(URL_NEON)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        return cur.fetchall()
    except Exception as e:
        st.error(f"❌ Error de lectura en Neon: {e}")
        return []
    finally:
        if conn:
            conn.close()

def ejecutar_update(query, params):
    """Ejecuta sentencias de actualización."""
    conn = None
    try:
        conn = psycopg2.connect(URL_NEON)
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Error al guardar datos en Neon: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- CARGAR CATÁLOGOS REQUERIDOS
@st.cache_data(ttl=5)
def cargar_campanas_y_supers():
    # Traemos las campañas tal cual están en la tabla
    campanas = ejecutar_consulta("SELECT * FROM public.campanas ORDER BY id_campana ASC;")
    df_c = pd.DataFrame(campanas) if campanas else pd.DataFrame(columns=[
        "id_campana", "id_super", "nombre_campana", "fecha_inicio", "fecha_fin", 
        "tipo_campana", "estado_campana", "mes", "estado_carga", "estado_maqueta"
    ])
    
    # Traemos supermercados para un mapeo local visual si es necesario
    supers = ejecutar_consulta("SELECT id_super, nombre_supermercado FROM public.supermercados;")
    df_s = pd.DataFrame(supers) if supers else pd.DataFrame(columns=["id_super", "nombre_supermercado"])
    
    return df_c, df_s

df_c, df_s = cargar_campanas_y_supers()

if df_c.empty:
    st.warning("⚠️ No se encontraron registros en la tabla de campañas.")
    st.stop()

# Diccionario para que el usuario identifique el ID del Supermercado al editar
with st.sidebar:
    st.markdown("### 🏪 Catálogo de Supermercados")
    if not df_s.empty:
        st.dataframe(df_s, use_container_width=True, hide_index=True)
    else:
        st.caption("No hay supermercados registrados.")

st.markdown("### 📝 Grilla de Campañas Modificable")
st.caption("Haz doble clic en cualquier celda para editar. Al finalizar, presiona el botón **Guardar Cambios** al final de la página.")

# --- CONFIGURACIÓN DE COLUMNAS PARA VALIDACIÓN (SCHEMA COMPLIANCE)
columnas_config = {
    "id_campana": st.column_config.NumberColumn(
        "ID Campaña", 
        disabled=True, # Deshabilitado porque es tu llave primaria de identificación
        format="%d"
    ),
    "id_super": st.column_config.NumberColumn(
        "ID Supermercado", 
        required=True,
        format="%d"
    ),
    "nombre_campana": st.column_config.TextColumn(
        "Nombre Campaña", 
        required=True
    ),
    "fecha_inicio": st.column_config.TextColumn("Fecha Inicio"),
    "fecha_fin": st.column_config.TextColumn("Fecha Fin"),
    "tipo_campana": st.column_config.TextColumn("Tipo Campaña"),
    "estado_campana": st.column_config.SelectboxColumn(
        "Estado Campaña",
        options=["Pre-Oferta", "Activa", "Cerrada"],
        required=True
    ),
    "mes": st.column_config.TextColumn("Mes"),
    "estado_carga": st.column_config.SelectboxColumn(
        "Estado Carga",
        options=["En espera", "Activa", "Cerrada"],
        required=False
    ),
    "estado_maqueta": st.column_config.SelectboxColumn(
        "Estado Maqueta",
        options=["En espera", "Activa", "Cerrada"],
        required=False
    )
}

# --- RENDERIZADO DEL EDITOR DE DATOS
# st.data_editor genera un diccionario con los registros modificados de forma automática
datos_editados = st.data_editor(
    df_c,
    column_config=columnas_config,
    use_container_width=True,
    hide_index=True,
    key="editor_campanas"
)

# --- PROCESAMIENTO DE CAMBIOS
# Buscamos si hay mutaciones en el estado del editor
cambios = st.session_state["editor_campanas"].get("edited_rows", {})

if cambios:
    st.warning(f"⚠️ Tienes {len(cambios)} fila(s) modificada(s) pendientes de guardar.")
    
    if st.button("💾 Guardar Cambios en Neon", type="primary"):
        exito_total = True
        
        # Iteramos únicamente sobre las filas del DataFrame original que sufrieron ediciones
        for indice_fila, campos_modificados in cambios.items():
            # Obtenemos los datos actuales de la fila mutada
            fila_original = df_c.iloc[int(indice_fila)]
            id_campana = int(fila_original["id_campana"])
            
            # Reconstruimos los valores finales mezclando el original con lo editado
            id_super = campos_modificados.get("id_super", fila_original["id_super"])
            nombre_campana = campos_modificados.get("nombre_campana", fila_original["nombre_campana"])
            fecha_inicio = campos_modificados.get("fecha_inicio", fila_original["fecha_inicio"])
            fecha_fin = campos_modificados.get("fecha_fin", fila_original["fecha_fin"])
            tipo_campana = campos_modificados.get("tipo_campana", fila_original["tipo_campana"])
            estado_campana = campos_modificados.get("estado_campana", fila_original["estado_campana"])
            mes = campos_modificados.get("mes", fila_original["mes"])
            estado_carga = campos_modificados.get("estado_carga", fila_original["estado_carga"])
            estado_maqueta = campos_modificados.get("estado_maqueta", fila_original["estado_maqueta"])
            
            # Consulta SQL dinámica parametrizada de actualización completa
            sql_update = """
                UPDATE public.campanas 
                SET 
                    id_super = %s, 
                    nombre_campana = %s, 
                    fecha_inicio = %s, 
                    fecha_fin = %s, 
                    tipo_campana = %s, 
                    estado_campana = %s, 
                    mes = %s, 
                    estado_carga = %s, 
                    estado_maqueta = %s
                WHERE id_campana = %s;
            """
            
            valores = (
                int(id_super) if pd.notna(id_super) else None,
                str(nombre_campana) if pd.notna(nombre_campana) else None,
                str(fecha_inicio) if pd.notna(fecha_inicio) else None,
                str(fecha_fin) if pd.notna(fecha_fin) else None,
                str(tipo_campana) if pd.notna(tipo_campana) else None,
                str(estado_campana) if pd.notna(estado_campana) else None,
                str(mes) if pd.notna(mes) else None,
                str(estado_carga) if pd.notna(estado_carga) else None,
                str(estado_maqueta) if pd.notna(estado_maqueta) else None,
                id_campana
            )
            
            # Ejecutamos la query por cada fila afectada
            if not ejecutar_update(sql_update, valores):
                exito_total = False
        
        if exito_total:
            st.success("🎉 ¡Todos los cambios han sido sincronizados en Neon con éxito!")
            # Limpiamos la caché de datos para forzar la recarga en el próximo ciclo
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("❌ Algunos cambios no se pudieron guardar. Revisa los errores superiores.")
else:
    st.info("💡 La grilla está sincronizada. Modifica cualquier celda para activar el guardado.")
