import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Dashboard de Campañas (Neon)", layout="wide")
st.title("📊 Dashboard de Control de Campañas (Neon)")

# --- CONEXIÓN A NEON
try:
    # 💡 Se cambia la sección de secretos para apuntar a la URL de conexión de Neon
    URL_NEON = st.secrets["neon"]["url"]
except KeyError:
    st.error("❌ Error: Falta la variable ['neon']['url'] en los secrets de '.streamlit/secrets.toml'.")
    st.stop()

# --- FUNCIÓN CORE DE EXTRACCIÓN SQL
def ejecutar_consulta_neon(query):
    """Ejecuta sentencias SQL en Neon administrando de forma segura la conexión."""
    conn = None
    try:
        conn = psycopg2.connect(URL_NEON)
        # Usamos RealDictCursor para heredar los datos como una lista de diccionarios planos
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query)
        return cur.fetchall()
    except Exception as e:
        st.error(f"❌ Fallo crítico en motor relacional Neon: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- CARGA DE DATOS SIN LIMITACIONES DE API REST
@st.cache_data(ttl=30)
def cargar_datos_seguros():
    try:
        # 1. Traer campañas directo desde PostgreSQL
        res_campanas = ejecutar_consulta_neon("SELECT * FROM public.campanas;")
        df_c = pd.DataFrame(res_campanas) if res_campanas else pd.DataFrame()
        
        # 🚀 REEMPLAZO DEL BYPASS: Neon no requiere bucles iterativos para saltar paginación.
        # Una sola consulta SQL limpia extrae la base completa de ofertas de forma eficiente.
        res_ofertas = ejecutar_consulta_neon("SELECT id_oferta, id_campana, numero_pagina FROM public.ofertas;")
        df_o = pd.DataFrame(res_ofertas) if res_ofertas else pd.DataFrame()
        
        # 3. Traer supermercados
        try:
            res_supers = ejecutar_consulta_neon("SELECT id_super, nombre_supermercado FROM public.supermercados;")
            df_s = pd.DataFrame(res_supers) if res_supers else pd.DataFrame()
        except Exception:
            df_s = pd.DataFrame(columns=["id_super", "nombre_supermercado"])
            
        if df_c.empty:
            return pd.DataFrame(), pd.DataFrame()
            
        if df_o.empty:
            df_o = pd.DataFrame(columns=["id_oferta", "id_campana", "numero_pagina"])
            
        # --- BLINDAJE DE CRUCE ORIGINAL (Uso interno strings)
        df_c_copia = df_c.copy()
        df_o_copia = df_o.copy()
        
        df_c_copia["id_campana_str"] = df_c_copia["id_campana"].astype(str).str.strip()
        df_o_copia["id_campana_str"] = df_o_copia["id_campana"].astype(str).str.strip()
        
        # Mapear nombres de supermercados localmente
        if not df_s.empty:
            df_s["id_super"] = df_s["id_super"].astype(int)
            dic_supers = dict(zip(df_s["id_super"], df_s["nombre_supermercado"]))
            df_c_copia["supermercado"] = df_c_copia["id_super"].map(dic_supers).fillna("No asignado")
        else:
            df_c_copia["supermercado"] = "No asignado"
            
        return df_c_copia, df_o_copia
        
    except Exception as e:
        st.error(f"❌ Error crítico al extraer los datos: {e}")
        return pd.DataFrame(), pd.DataFrame()

# Llamada a la carga de datos
df_campanas, df_ofertas = cargar_datos_seguros()

# ==============================================================================
# PROCESAMIENTO VISUAL Y RENDERIZADO UI (PRESERVADO IDÉNTICO)
# ==============================================================================
if df_campanas.empty:
    st.warning("⚠️ No se encontraron campañas registradas en la base de datos de Neon.")
    st.stop()

df_campanas["mes"] = df_campanas["mes"].fillna("Sin Mes Asignado")

# Conteo de intersecciones mediante las llaves string normalizadas
df_dashboard = df_campanas.copy()
if not df_ofertas.empty:
    ofertas_sin_pagina = df_ofertas[df_ofertas["numero_pagina"].isna() | (df_ofertas["numero_pagina"].astype(str).str.strip() == "")]
    
    conteo_total = df_ofertas.groupby("id_campana_str").size().to_dict()
    conteo_null = ofertas_sin_pagina.groupby("id_campana_str").size().to_dict()
    
    df_dashboard["cant_ofertas"] = df_dashboard["id_campana_str"].map(conteo_total).fillna(0).astype(int)
    df_dashboard["cant_null"] = df_dashboard["id_campana_str"].map(conteo_null).fillna(0).astype(int)
else:
    df_dashboard["cant_ofertas"] = 0
    df_dashboard["cant_null"] = 0

# Restauración de tipos para ordenamiento en las grillas de Streamlit
df_dashboard["id_campana"] = df_dashboard["id_campana"].astype(int)
df_dashboard["cant_ofertas"] = df_dashboard["cant_ofertas"].astype(int)
df_dashboard["cant_null"] = df_dashboard["cant_null"].astype(int)

# Segmentación por estados de maquetación
df_por_cargar = df_dashboard[df_dashboard["cant_ofertas"] == 0].copy()
df_pendiente_maquetacion = df_dashboard[df_dashboard["cant_null"] > 0].copy()

# Renderizado de Tarjetas KPI superiores
kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.metric("📋 Total Campañas", len(df_dashboard))
with kpi2:
    st.metric("⚠️ Por Cargar Ofertas", len(df_por_cargar), help=f"Total registros en la tabla ofertas: {len(df_ofertas)}")
with kpi3:
    st.metric("🎨 Con Ofertas sin Maquetar", len(df_pendiente_maquetacion))

st.divider()

# Navegación estructural por pestañas
tab1, tab2, tab3, tab4 = st.tabs([
    "📂 Campañas por Cargar Ofertas",
    "📌 Campañas pendientes de maquetación",
    "📦 Inventario General",
    "📊 Distribución Mensual"
])

with tab1:
    if not df_por_cargar.empty:
        st.subheader("📂 Campañas sin ningún registro en la tabla ofertas")
        st.dataframe(
            df_por_cargar[["id_campana", "nombre_campana", "supermercado", "mes", "fecha_inicio", "estado_campana"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("✅ ¡Al día! Todas las campañas tienen registros en la tabla de ofertas.")

with tab2:
    st.subheader("📌 Conteo de ofertas sin maquetación por campaña")
    if not df_pendiente_maquetacion.empty:
        st.dataframe(
            df_pendiente_maquetacion[["id_campana", "nombre_campana", "supermercado", "mes", "fecha_inicio", "cant_ofertas", "cant_null"]].rename(
                columns={"cant_ofertas": "Total Ofertas Cargadas", "cant_null": "Ofertas Sin Maquetación (numero_pagina NULL)"}
            ),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("✅ ¡Excelente! No existen ofertas pendientes de asignación de página.")

with tab3:
    st.subheader("📦 Inventario General de Campañas y Ofertas")
    filtro_buscar = st.text_input("🔍 Filtrar campaña por nombre:", "")
    df_vista = df_dashboard.copy()
    if filtro_buscar:
        df_vista = df_vista[df_vista["nombre_campana"].str.contains(filtro_buscar, case=False)]
    
    st.dataframe(
        df_vista[["id_campana", "nombre_campana", "supermercado", "mes", "fecha_inicio", "fecha_fin", "estado_campana", "cant_ofertas"]].rename(
            columns={"cant_ofertas": "Cantidad Ofertas"}
        ),
        use_container_width=True,
        hide_index=True
    )

with tab4:
    st.subheader("📊 Cantidad de Campañas por Supermercado por Mes")
    if not df_dashboard.empty:
        matriz_distribucion = pd.crosstab(
            index=df_dashboard["supermercado"],
            columns=df_dashboard["mes"],
            values=df_dashboard["id_campana"],
            aggfunc="count"
        ).fillna(0).astype(int)
        
        st.dataframe(matriz_distribucion, use_container_width=True)
        st.bar_chart(matriz_distribucion)
