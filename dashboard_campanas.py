import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Dashboard de Campañas (Neon)", layout="wide")

# --- CONEXIÓN A NEON
try:
    URL_NEON = st.secrets["neon"]["url"]
except KeyError:
    st.error("❌ Error: Falta la variable ['neon']['url'] en los secrets de '.streamlit/secrets.toml'.")
    st.stop()

# --- FUNCIONES DE BASE DE DATOS INTERNAS
def ejecutar_consulta_neon(query, params=None):
    """Ejecuta sentencias SQL de lectura administrando de forma segura la conexión."""
    conn = None
    try:
        conn = psycopg2.connect(URL_NEON)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        return cur.fetchall()
    except Exception as e:
        st.error(f"❌ Fallo crítico en motor relacional Neon: {e}")
        return None
    finally:
        if conn:
            conn.close()

def ejecutar_update_neon(query, params):
    """Ejecuta sentencias SQL de actualización (UPDATE) de forma segura."""
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

# --- CARGA DE DATOS CENTRALIZADA Y CONTROLADA
@st.cache_data(ttl=30)
def cargar_datos_seguros():
    try:
        # 1. Traer campañas directo desde PostgreSQL
        res_campanas = ejecutar_consulta_neon("SELECT * FROM public.campanas ORDER BY id_campana ASC;")
        df_c = pd.DataFrame(res_campanas) if res_campanas else pd.DataFrame()
        
        # 2. Traer ofertas completas (Sin límites de API REST de Supabase)
        res_ofertas = ejecutar_consulta_neon("SELECT id_oferta, id_campana, numero_pagina FROM public.ofertas;")
        df_o = pd.DataFrame(res_ofertas) if res_ofertas else pd.DataFrame()
        
        # 3. Traer supermercados
        try:
            res_supers = ejecutar_consulta_neon("SELECT id_super, nombre_supermercado FROM public.supermercados;")
            df_s = pd.DataFrame(res_supers) if res_supers else pd.DataFrame()
        except Exception:
            df_s = pd.DataFrame(columns=["id_super", "nombre_supermercado"])
            
        if df_c.empty:
            return pd.DataFrame(), pd.DataFrame(), df_s
            
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
            
        return df_c_copia, df_o_copia, df_s
        
    except Exception as e:
        st.error(f"❌ Error crítico al extraer los datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# Llamada global de datos
df_campanas, df_ofertas, df_supermercados = cargar_datos_seguros()

# --- MENÚ DE NAVEGACIÓN EN LA BARRA LATERAL
with st.sidebar:
    st.title("🧭 Panel de Control")
    opcion_menu = st.radio(
        "Selecciona una vista:",
        ["📈 Dashboard de Control", "⚙️ Editor de Campañas"]
    )

# ==============================================================================
# MÓDULO 1: DASHBOARD DE CONTROL (CÓDIGO ORIGINAL CONSERVADO)
# ==============================================================================
if opcion_menu == "📈 Dashboard de Control":
    st.title("📊 Dashboard de Control de Campañas")
    
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

# ==============================================================================
# MÓDULO 2: EDITOR DE CAMPAÑAS (NUEVA GRILLA INTEGRADA)
# ==============================================================================
elif opcion_menu == "⚙️ Editor de Campañas":
    st.title("⚙️ Editor de Campañas y Configuración de Estados")
    st.caption("Haz doble clic en cualquier celda para editar de manera fluida. Al finalizar, presiona el botón **Guardar Cambios**.")
    
    if df_campanas.empty:
        st.warning("⚠️ No hay datos disponibles para editar.")
        st.stop()
        
    # Acordeón para guiar al operador con las relaciones de ID de Supermercado
    with st.expander("🏪 Ver Catálogo de IDs de Supermercados", expanded=False):
        if not df_supermercados.empty:
            st.dataframe(df_supermercados, use_container_width=True, hide_index=True)
        else:
            st.caption("No hay supermercados registrados en la base de datos.")

    # Removemos columnas calculadas temporales para aislar el esquema crudo de SQL
    df_editor_base = df_campanas.drop(columns=["id_campana_str", "supermercado"], errors="ignore")

    # Mapeo estricto de columnas con las restricciones del SCHEMA de PostgreSQL y los desplegables solicitados
    columnas_config = {
        "id_campana": st.column_config.NumberColumn(
            "ID Campaña", 
            disabled=True, 
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

    # Despliegue de la grilla interactiva st.data_editor
    datos_editados = st.data_editor(
        df_editor_base,
        column_config=columnas_config,
        use_container_width=True,
        hide_index=True,
        key="editor_campanas_grid"
    )

    # Capturar del session_state local las filas modificadas
    cambios = st.session_state["editor_campanas_grid"].get("edited_rows", {})

    if cambios:
        st.warning(f"⚠️ Tienes {len(cambios)} fila(s) modificada(s) pendientes de guardar.")
        
        if st.button("💾 Guardar Cambios en Neon", type="primary"):
            exito_total = True
            
            # Iterar de forma dirigida únicamente sobre las filas afectadas
            for indice_fila, campos_modificados in cambios.items():
                fila_original = df_editor_base.iloc[int(indice_fila)]
                id_campana_target = int(fila_original["id_campana"])
                
                # Fusión de datos (valor editado en celda o valor persistente original)
                valores_update = (
                    int(campos_modificados.get("id_super", fila_original["id_super"])),
                    str(campos_modificados.get("nombre_campana", fila_original["nombre_campana"])),
                    str(campos_modificados.get("fecha_inicio", fila_original["fecha_inicio"])) if pd.notna(campos_modificados.get("fecha_inicio", fila_original["fecha_inicio"])) else None,
                    str(campos_modificados.get("fecha_fin", fila_original["fecha_fin"])) if pd.notna(campos_modificados.get("fecha_fin", fila_original["fecha_fin"])) else None,
                    str(campos_modificados.get("tipo_campana", fila_original["tipo_campana"])) if pd.notna(campos_modificados.get("tipo_campana", fila_original["tipo_campana"])) else None,
                    str(campos_modificados.get("estado_campana", fila_original["estado_campana"])),
                    str(campos_modificados.get("mes", fila_original["mes"])) if pd.notna(campos_modificados.get("mes", fila_original["mes"])) else None,
                    str(campos_modificados.get("estado_carga", fila_original["estado_carga"])) if pd.notna(campos_modificados.get("estado_carga", fila_original["estado_carga"])) else None,
                    str(campos_modificados.get("estado_maqueta", fila_original["estado_maqueta"])) if pd.notna(campos_modificados.get("estado_maqueta", fila_original["estado_maqueta"])) else None,
                    id_campana_target
                )
                
                query_update = """
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
                
                if not ejecutar_update_neon(query_update, valores_update):
                    exito_total = False
            
            if exito_total:
                st.success("🎉 ¡Sincronización completada! Todos los cambios han sido aplicados en Neon.")
                st.cache_data.clear()  # Resetea la caché para actualizar el Dashboard inmediatamente
                st.rerun()
            else:
                st.error("❌ Ocurrieron problemas al actualizar ciertas filas. Revisa la consola o los logs superiores.")
    else:
        st.info("💡 Los datos están sincronizados. Modifica las celdas deseadas y aparecerá el botón de guardado.")
