# ==============================================================================
# PROGRAMA: registro_ofertas_mosaico_fiel.py | PARTE 1 DE 5
# MODULO: CONFIGURACIÓN GENERAL, ESTILOS E INICIALIZACIÓN CORE NEON
# PROGRAMA DUPLICADO: VERSION VIGENTE cargar_campanas_imagen2.py
# ==============================================================================
import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import math

# CONFIGURACIÓN DE METADATOS Y LIENZO WEB
_version_ = "15.5.0-FUSION-FIEL"
st.set_page_config(
    page_title=f"Registro Mosaico v{_version_}",
    layout="wide",
    page_icon="🖼️"
)

# Estilos CSS Pro para alta densidad visual oscura (Mosaico Fiel)
st.markdown("""
<style>
.stApp { background-color: #0f111a; color: #cdd6f4; }
div[data-testid="stMetric"] { background-color: #1e1e2e; border: 1px solid #313244; padding: 15px; border-radius: 8px; }
div[data-testid="stMetricValue"] { color: #f9e2af; font-size: 2rem; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# CANDADOS PERSISTENTES DE MEMORIA
if "exp_cat_id" not in st.session_state: st.session_state.exp_cat_id = None
if "exp_sub_id" not in st.session_state: st.session_state.exp_sub_id = None

# --- VALIDACIÓN DE SECRETOS NEON ---
try:
    url_limpia = st.secrets["neon"]["url"]
except KeyError:
    st.error("❌ Error de configuración: Falta la variable ['neon']['url'] en los secrets.")
    st.stop()

def ejecutar_consulta_neon(query, parametros=(), fetch=True, commit=False):
    """Ejecuta sentencias SQL en Neon administrando de forma segura la conexión."""
    conn = None
    try:
        conn = psycopg2.connect(url_limpia)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, parametros)
        if commit:
            conn.commit()
        if fetch:
            return cur.fetchall()
        return True
    except Exception as e:
        st.error(f"❌ Fallo crítico en motor relacional Neon: {e}")
        if conn and commit:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()
# ==============================================================================
# PROGRAMA: registro_ofertas_mosaico_fiel.py | PARTE 2 DE 5
# MODULO: DESCARGA RELACIONAL 3FN Y SELECTORES DE CONTEXTO
# ==============================================================================

try:
    # Descarga directa sin límites HTTP REST (Remoción de bucles paginados de Supabase)
    res_o = ejecutar_consulta_neon("SELECT * FROM public.ofertas;") or []
    
    query_prod = """
        SELECT id_producto, nombre, marca, tamano, unidad, url_imagen, codigo_barras, id_cat, id_subcat 
        FROM public.productos;
    """
    res_p = ejecutar_consulta_neon(query_prod) or []
    res_s = ejecutar_consulta_neon("SELECT id_super, nombre_supermercado FROM public.supermercados;") or []
    res_c = ejecutar_consulta_neon("SELECT id_campana, id_super, nombre_campana, estado_campana, fecha_inicio, fecha_fin FROM public.campanas;") or []
    form_categorias = ejecutar_consulta_neon("SELECT id_cat, nombre FROM public.categorias ORDER BY nombre;") or []
    form_subcategorias = ejecutar_consulta_neon("SELECT id_subcat, id_cat, nombre FROM public.subcategorias ORDER BY nombre;") or []

except Exception as e:
    st.error(f"❌ Fallo crítico de red en la infraestructura Neon: {e}")
    st.stop()

# Conversión a DataFrames nativos para procesamiento relacional en RAM
df_o = pd.DataFrame(res_o) if res_o else pd.DataFrame()
df_p = pd.DataFrame(res_p) if res_p else pd.DataFrame()
df_c = pd.DataFrame(res_c) if res_c else pd.DataFrame()
mapa_supers_ram = {int(s["id_super"]): s["nombre_supermercado"] for s in res_s} if res_s else {}

# Filtrado estricto de campañas en modo 'Pre-Oferta' para activar el laboratorio
campanas_pre_oferta_global = [c for c in res_c if str(c.get("estado_campana")).strip().lower() == "pre-oferta"]

if not campanas_pre_oferta_global:
    st.info("ℹ️ Por favor, cree primero una campaña en modo 'Pre-Oferta' para activar este laboratorio visual.")
    st.stop()

# POOL ACTUAL: RECONSTRUCCIÓN GENERAL DE HISTÓRICOS CRUZADOS
df_pool_actual = pd.DataFrame()
if not df_o.empty and not df_p.empty and not df_c.empty:
    df_o_temp = df_o.copy()
    df_p_temp = df_p.copy()
    df_c_temp = df_c.copy()
    df_o_temp["id_producto"] = df_o_temp["id_producto"].astype(str).str.strip()
    df_p_temp["id_producto"] = df_p_temp["id_producto"].astype(str).str.strip()
    df_o_temp["id_campana"] = df_o_temp["id_campana"].fillna(0).astype(int)
    df_c_temp["id_campana"] = df_c_temp["id_campana"].fillna(0).astype(int)
    
    df_temp = pd.merge(df_o_temp, df_p_temp, on="id_producto", how="inner")
    df_pool_actual = pd.merge(df_temp, df_c_temp[["id_campana", "fecha_inicio", "fecha_fin"]], on="id_campana", how="inner")

st.markdown("#### 1. Coordenadas de Entrada Comercial")
col_s1, col_s2, col_s5 = st.columns([1.5, 2.0, 2.5])

with col_s1:
    ids_supers_activos = sorted(list(set([int(c["id_super"]) for c in campanas_pre_oferta_global if c.get("id_super") is not None])))
    id_super_contexto = st.selectbox("Supermercado Objetivo:", options=ids_supers_activos, format_func=lambda x: mapa_supers_ram.get(x, f"Super #{x}"))
    if id_super_contexto: st.session_state["id_super_operador"] = id_super_contexto
    campanas_filtradas = [c for c in campanas_pre_oferta_global if int(c.get("id_super", 0)) == id_super_contexto]

with col_s2:
    if not campanas_filtradas:
        st.error("No hay campañas en Pre-Oferta.")
        st.stop()
    campana_destino_sel = st.selectbox("Campaña Contenedora:", options=campanas_filtradas, format_func=lambda x: f"ID: {x['id_campana']} | {x['nombre_campana']}")
    id_campana_destino = int(campana_destino_sel["id_campana"])

with col_s5:
    columnas_elegidas = st.slider("Columnas por Fila (Densidad):", min_value=6, max_value=15, value=9, step=3)
    config_zoom = {
        6: {"altura_px": 85, "font_b": "0.72rem", "font_span": "0.62rem", "trim": 20},
        9: {"altura_px": 65, "font_b": "0.65rem", "font_span": "0.58rem", "trim": 14},
        12: {"altura_px": 50, "font_b": "0.58rem", "font_span": "0.52rem", "trim": 10},
        15: {"altura_px": 42, "font_b": "0.52rem", "font_span": "0.48rem", "trim": 8}
    }
    layout_dinamico = config_zoom.get(columnas_elegidas, config_zoom[9])
# ==============================================================================
# PROGRAMA: registro_ofertas_mosaico_fiel.py | PARTE 3 DE 5
# MODULO: VALIDACIÓN DE LOTE ACTIVO Y PROCESAMIENTO REGLA v15 (L)
# ==============================================================================

df_laboratorio_activo = pd.DataFrame()
tiene_registros_activos = False

try:
    res_po_actual = ejecutar_consulta_neon("SELECT * FROM public.pre_ofertas WHERE id_campana = %s;", (id_campana_destino,))
    if res_po_actual:
        df_laboratorio_activo = pd.DataFrame(res_po_actual)
        df_laboratorio_activo["id_producto"] = df_laboratorio_activo["id_producto"].astype(str).str.strip()
        if len(df_laboratorio_activo) > 0: tiene_registros_activos = True
except Exception:
    df_laboratorio_activo = pd.DataFrame()

# Inicialización obligatoria de estadísticas en session_state
if "stat_lider" not in st.session_state: st.session_state.stat_lider = 0
if "stat_otros" not in st.session_state: st.session_state.stat_otros = 0
if "stat_total" not in st.session_state: st.session_state.stat_total = 0
if "formulario_imagenes_dict" not in st.session_state: st.session_state["formulario_imagenes_dict"] = {}

df_lote_express = pd.DataFrame()
lista_items = []
df_pool_unicos = pd.DataFrame()

# REGLA v15 INTEGRAL: Reconstruimos el conjunto exacto del pool de imágenes
if tiene_registros_activos and not df_p.empty:
    df_lab = df_laboratorio_activo.copy()
    df_prod = df_p.copy()
    df_lab["id_producto"] = df_lab["id_producto"].astype(str).str.strip()
    df_prod["id_producto"] = df_prod["id_producto"].astype(str).str.strip()
    
    # Cruce estricto: El mosaico se limita exactamente al lote de pre_ofertas
    df_lote_express = pd.merge(df_lab, df_prod, on="id_producto", how="inner")
    
    if not df_lote_express.empty:
        if "precio_oferta_proyectado" in df_lote_express.columns:
            df_lote_express["precio_oferta"] = df_lote_express["precio_oferta_proyectado"].astype(float)
            
        # Marcado comercial de sufijo (L) Líder si el producto tiene historial en este súper
        set_productos_con_oferta_en_super = set()
        if not df_o.empty and "id_super" in df_o.columns and "id_producto" in df_o.columns:
            ofertas_del_super = df_o[df_o["id_super"].fillna(0).astype(int) == int(id_super_contexto)]
            set_productos_con_oferta_en_super = set(ofertas_del_super["id_producto"].astype(str).str.strip().tolist())
            
        df_lote_express["es_local"] = df_lote_express["id_producto"].astype(str).str.strip().isin(set_productos_con_oferta_en_super)
        
        # Sincronización inmediata de métricas
        total_pre = len(df_lote_express)
        st.session_state.stat_lider = int(df_lote_express["es_local"].sum())
        st.session_state.stat_total = total_pre
        st.session_state.stat_otros = int(total_pre - st.session_state.stat_lider)
        
        # Ordenamiento estricto idéntico al original: categoría -> subcategoría -> nombre alfabético
        df_lote_express["id_cat"] = df_lote_express["id_cat"].fillna(0).astype(int)
        df_lote_express["id_subcat"] = df_lote_express["id_subcat"].fillna(0).astype(int)
        df_lote_express["nombre_sort"] = df_lote_express["nombre"].fillna("").astype(str).str.strip().str.lower()
        
        df_pool_unicos = df_lote_express.sort_values(by=["id_cat", "id_subcat", "nombre_sort"], ascending=[True, True, True])
        lista_items = df_pool_unicos.to_dict(orient="records")
else:
    st.session_state.stat_lider, st.session_state.stat_otros, st.session_state.stat_total = 0, 0, 0

# RENDER DE PANEL EJECUTIVO SUPERIOR DE MÉTRICAS
st.write("### Resumen Ejecutivo de la Campaña")
metric_col1, metric_col2, metric_col3 = st.columns(3)
with metric_col1: st.metric(label="📸 Imágenes Súper Líder (L)", value=st.session_state.get("stat_lider", 0))
with metric_col2: st.metric(label="🏪 Otros Supermercados", value=st.session_state.get("stat_otros", 0))
with metric_col3: st.metric(label="📦 Total Imágenes en Campaña", value=st.session_state.get("stat_total", 0))
# ==============================================================================
# PROGRAMA: registro_ofertas_mosaico_fiel.py | PARTE 4 DE 5
# MODULO: FUNCIÓN DE REJILLA VERTICAL (FIDELIDAD DE INTERFAZ ORIGINAL)
# ==============================================================================

def dibujar_rejilla_mosaico_fiel(items_mosaico, _df_lab_activo, layout, _columnas_elegidas, _id_campana_destino):
    COLUMNAS_POR_FILA = _columnas_elegidas
    
    for i in range(0, len(items_mosaico), COLUMNAS_POR_FILA):
        bloque_items = items_mosaico[i:i + COLUMNAS_POR_FILA]
        columnas_ui = st.columns(COLUMNAS_POR_FILA)
        
        for idx, fila_p in enumerate(bloque_items):
            with columnas_ui[idx]:
                id_p_raw = int(float(fila_p["id_producto"]))
                match_campana = pd.DataFrame()
                
                # Búsqueda de coincidencia en la campaña activa para mapear valores previos
                if not _df_lab_activo.empty and "id_producto" in _df_lab_activo.columns:
                    id_db_normalizado = _df_lab_activo["id_producto"].fillna(0).astype(float).astype(int).astype(str)
                    condicion_producto = (id_db_normalizado == str(id_p_raw))
                    if "id_campana" in _df_lab_activo.columns:
                        condicion_campana = (_df_lab_activo["id_campana"].astype(str) == str(_id_campana_destino))
                        match_campana = _df_lab_activo[condicion_producto & condicion_campana]
                    else:
                        match_campana = _df_lab_activo[condicion_producto]
                
                id_pre_oferta_real = None
                precio_defecto = float(fila_p.get("precio_oferta", 0.0))
                check_inicial = False
                
                if not match_campana.empty:
                    fila_maqueta_reciente = match_campana.tail(1)
                    precio_defecto = float(fila_maqueta_reciente["precio_oferta_proyectado"].values[0])
                    id_pre_oferta_real = int(fila_maqueta_reciente["id_pre_oferta"].values[0]) if "id_pre_oferta" in fila_maqueta_reciente.columns else None
                    if "clonado_confirmado" in fila_maqueta_reciente.columns:
                        flag_db = fila_maqueta_reciente["clonado_confirmado"].values[0]
                        check_inicial = (flag_db is True or str(flag_db).strip().lower() in ["true", "t", "1"])
                
                # Ajuste dinámico de texto según slider de densidad
                limite_caracteres = layout["trim"]
                nombre_lbl = str(fila_p.get("nombre", "")).strip().upper()[:limite_caracteres]
                marca_lbl = str(fila_p.get("marca", "Sin Marca")).strip()[:10]
                formato_empaque = f"{fila_p.get('tamano', '')} {fila_p.get('unidad', '')}".strip()
                
                sufijo_lider = " <span style='color: #f38ba8; font-weight: bold;'>(L)</span>" if fila_p.get("es_local", False) else ""
                
                html_especificacion = f"""
                <div style='line-height:1.1; margin-bottom:4px; height: 42px; overflow: hidden;'>
                    <b style='font-size: {layout["font_b"]}; color:#cdd6f4;'>{nombre_lbl}{sufijo_lider}</b><br>
                    <span style='font-size: {layout["font_span"]}; color: #a6adc8;'>{marca_lbl} | {formato_empaque}</span>
                </div>
                """
                
                url_foto_render = fila_p.get("url_imagen") or "https://picsum.photos"
                
                with st.container(border=True):
                    st.image(url_foto_render, use_container_width=True)
                    st.markdown(html_especificacion, unsafe_allow_html=True)
                    
                    p_key_string = f"num_pvp_{id_p_raw}_{_id_campana_destino}"
                    m_key_string = f"chk_load_{id_p_raw}_{_id_campana_destino}"
                    
                    st.number_input("PVP ($):", min_value=0.0, value=precio_defecto, step=0.01, format="%.2f", key=p_key_string)
                    st.checkbox("Incluir", value=check_inicial, key=m_key_string)
                    
                    # Conservamos el mapeo en RAM
                    st.session_state["formulario_imagenes_dict"][id_p_raw] = {
                        "id_registro": id_pre_oferta_real,
                        "id_producto": id_p_raw,
                        "precio_key": p_key_string,
                        "marcado_key": m_key_string
                    }
# ==============================================================================
# PROGRAMA: registro_ofertas_mosaico_fiel.py | PARTE 5 DE 5
# MODULO: ALGORITMO CRUZADO DE POBLADO, PERSISTENCIA CORPORATIVA Y AUDITORÍA
# ==============================================================================

if not tiene_registros_activos:
    # ---- AMBIENTE A: INITIAL VOLCADO TOTAL (SI LA CAMPAÑA ESTÁ TOTALMENTE VACÍA) ----
    st.write("---")
    st.info(f"🚀 El contenedor ID ({id_campana_destino}) está vacío en pre_ofertas. El sistema ejecutará el algoritmo cruzado del PDF original.")
    st.markdown("##### Inicialización del Laboratorio Inteligente Multi-Súper")
    
    total_f1_unicos, total_f2_rescatados = 0, 0
    df_pool_molde = df_pool_actual[df_pool_actual["id_super"] == id_super_contexto].copy() if not df_pool_actual.empty else pd.DataFrame()
    set_productos_lider = set()
    df_f1_listo = pd.DataFrame()
    df_f2_listo = pd.DataFrame()
    
    if not df_pool_molde.empty:
        df_pool_ordenado = df_pool_molde.sort_values(by="id_oferta", ascending=False)
        df_f1_listo = df_pool_ordenado.drop_duplicates(subset=["id_producto"], keep="first").copy()
        set_productos_lider = set(df_f1_listo["id_producto"].astype(str).str.strip().tolist())
        total_f1_unicos = len(df_f1_listo)
        
    df_pool_resto = df_pool_actual[df_pool_actual["id_super"] != id_super_contexto].copy() if not df_pool_actual.empty else pd.DataFrame()
    if not df_pool_resto.empty:
        df_resto_filtrado = df_pool_resto[~df_pool_resto["id_producto"].astype(str).str.strip().isin(set_productos_lider)]
        df_resto_ordenado = df_resto_filtrado.sort_values(by="id_oferta", ascending=False)
        df_f2_listo = df_resto_ordenado.drop_duplicates(subset=["id_producto"], keep="first").copy()
        total_f2_rescatados = len(df_f2_listo)
        
    m1, m2, m3 = st.columns(3)
    m1.metric("SKUs Súper Líder (Fase 1)", total_f1_unicos)
    m2.metric("SKUs Rescatados Competencia (Fase 2)", total_f2_rescatados)
    m3.metric("Lote Total Neto Proyectado", total_f1_unicos + total_f2_rescatados)
    
    if st.button("🎬 Inicialización Completa de Catálogo Histórico Cruzado", use_container_width=True, type="primary"):
        if total_f1_unicos == 0 and total_f2_rescatados == 0:
            st.error("Alerta: No se registran ofertas históricas previas para poblar este contenedor.")
        else:
            conn = None
            try:
                conn = psycopg2.connect(url_limpia)
                cur = conn.cursor()
                
                # Inyección Fase 1 (Productos Propios)
                if not df_f1_listo.empty:
                    for _, fila_m in df_f1_listo.iterrows():
                        query_f1 = "INSERT INTO public.pre_ofertas (id_producto, id_campana, id_super, precio_oferta_proyectado, numero_pagina, posicion_slot, alineacion, clonado_confirmado) VALUES (%s, %s, %s, %s, 0, 0, 'C', False);"
                        cur.execute(query_f1, (int(float(fila_m["id_producto"])), id_campana_destino, int(id_super_contexto), float(fila_m["precio_oferta"])))
                
                # Inyección Fase 2 (Productos Competencia Rescatados)
                if not df_f2_listo.empty:
                    for _, fila_m in df_f2_listo.iterrows():
                        query_f2 = "INSERT INTO public.pre_ofertas (id_producto, id_campana, id_super, precio_oferta_proyectado, numero_pagina, posicion_slot, alineacion, clonado_confirmado) VALUES (%s, %s, %s, %s, 0, 0, 'C', False);"
                        cur.execute(query_f2, (int(float(fila_m["id_producto"])), id_campana_destino, int(id_super_contexto), float(fila_m["precio_oferta"])))
                
                conn.commit()
                st.toast("¡Laboratorio poblado con éxito en Neon!", icon="✅")
                st.rerun()
            except Exception as ex_v:
                st.error(f"Falla transaccional en Neon: {ex_v}")
                if conn: conn.rollback()
            finally:
                if conn: conn.close()
else:
    # ---- AMBIENTE B: LA CAMPAÑA YA CONTIENE REGISTROS (MUESTRA EL MOSAICO v15) ----
    if form_categorias:
        nombres_pestanas = [cat["nombre"].upper() for cat in form_categorias]
        pestanas_ui = st.tabs(nombres_pestanas)
        
        for index_tab, cat_info in enumerate(form_categorias):
            id_categoria_actual = cat_info["id_cat"]
            with pestanas_ui[index_tab]:
                items_del_pasillo = [item for item in lista_items if int(item.get("id_cat", 0)) == int(id_categoria_actual)]
                sub_filtradas = [s for s in form_subcategorias if int(s["id_cat"]) == int(id_categoria_actual)]
                
                opciones_sub = [{"id_subcat": None, "nombre": "--- VER TODO EL PASILLO ---"}] + sub_filtradas
                sub_seleccionada = st.selectbox("Refinar surtido:", opciones_sub, format_func=lambda x: x["nombre"].upper(), key=f"sub_tab_react_{id_categoria_actual}")
                
                if sub_seleccionada["id_subcat"] is not None:
                    items_finales_mosaico = [item for item in items_del_pasillo if int(item.get("id_subcat", 0)) == int(sub_seleccionada["id_subcat"])]
                else:
                    items_finales_mosaico = items_del_pasillo
                    
                if items_finales_mosaico:
                    st.caption(f"Mostrando {len(items_finales_mosaico)} artículos en este segmento")
                    dibujar_rejilla_mosaico_fiel(items_finales_mosaico, df_laboratorio_activo, layout_dinamico, columnas_elegidas, id_campana_destino)

# --- PANEL DE ACCIONES COMERCIALES CORPORATIVAS ---
st.write("---")
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("🔥 Disparar Inyección Express de Todo lo Seleccionado", use_container_width=True, type="primary"):
        payload_rafaga = []
        for id_prod, referencias in st.session_state.get("formulario_imagenes_dict", {}).items():
            marcado_final = st.session_state.get(referencias["marcado_key"], False)
            precio_final = st.session_state.get(referencias["precio_key"], 0.0)
            id_reg_pre_oferta = referencias.get("id_registro")
            
            if marcado_final and precio_final > 0.0:
                payload_rafaga.append({"id_producto": int(id_prod), "precio": float(precio_final), "id_pre": id_reg_pre_oferta})
                
        if payload_rafaga:
            conn = None
            try:
                conn = psycopg2.connect(url_limpia)
                cur = conn.cursor()
                
                for reg in payload_rafaga:
                    # 1. Inserción limpia a nivel corporativo oficial (id_sucursal, pagina, slot = NULL)
                    query_insert = """
                        INSERT INTO public.ofertas (id_producto, id_super, precio_oferta, id_campana, id_sucursal, numero_pagina, posicion_slot, alineacion, es_favorita, en_lista_compras, oferta_comprada)
                        VALUES (%s, %s, %s, %s, NULL, NULL, NULL, 'C', False, False, False);
                    """
                    cur.execute(query_insert, (reg["id_producto"], int(st.session_state["id_super_operador"]), reg["precio"], id_campana_destino))
                    
                    # 2. Actualizamos el estado en pre_ofertas para que refleje el guardado oficial
                    if reg["id_pre"] is not None:
                        cur.execute("UPDATE public.pre_ofertas SET precio_oferta_proyectado = %s, clonado_confirmado = True WHERE id_pre_oferta = %s;", (reg["precio"], reg["id_pre"]))
                        
                conn.commit()
                st.toast("🚀 ¡Inyección Corporativa Exitosa en Neon!", icon="✅")
                st.cache_data.clear()
                st.rerun()
            except Exception as err_api:
                st.error(f"❌ Error de persistencia relacional en Neon: {err_api}")
                if conn: conn.rollback()
            finally:
                if conn: conn.close()
        else:
            st.warning("⚠️ No se ha detectado ningún elemento incluido con precio válido.")

with col_btn2:
    if st.button("🗑️ Vaciar y Resetear esta Campaña", use_container_width=True, type="secondary"):
        if id_campana_destino > 0:
            query_delete = "DELETE FROM public.pre_ofertas WHERE id_campana = %s;"
            if ejecutar_consulta_neon(query_delete, (id_campana_destino,), fetch=False, commit=True):
                st.session_state["formulario_imagenes_dict"] = {}
                st.toast("¡Contenedor reseteado con éxito!", icon="🧹")
                st.cache_data.clear()
                st.rerun()

# --- BITÁCORA DE CONTROL DE OFERTAS OFICIALES CONSOLIDADAS ---
st.write("---")
st.markdown(f"#### 📋 3. Monitoreo de Ofertas Publicadas (Historial Corporativo)")

df_o_grid = pd.DataFrame(res_o) if res_o else pd.DataFrame()
if not df_o_grid.empty:
    df_o_grid = df_o_grid[df_o_grid["id_campana"].fillna(0).astype(int) == int(id_campana_destino)]

if df_o_grid.empty:
    st.info("🍃 No se registran ofertas oficiales guardadas aún en esta campaña.")
else:
    df_p_grid = pd.DataFrame(res_p) if res_p else pd.DataFrame()
    if not df_p_grid.empty:
        df_o_grid["id_producto"] = df_o_grid["id_producto"].astype(int)
        df_p_grid["id_producto"] = df_p_grid["id_producto"].astype(int)
        df_merged = pd.merge(df_o_grid, df_p_grid, on="id_producto", how="inner")
        
        if not df_merged.empty:
            df_render_final = pd.DataFrame({
                "ID Oferta": df_merged["id_oferta"],
                "Marca": df_merged["marca"].fillna("Sin Marca"),
                "Artículo": df_merged["nombre"],
                "Presentación": df_merged["tamano"].astype(str) + " " + df_merged["unidad"].astype(str),
                "Precio Corporativo ($)": df_merged["precio_oferta"].astype(float),
                "Cobertura": "CORPORATIVO (Nacional)"
# ==============================================================================
# PROGRAMA: registro_ofertas_mosaico_fiel.py | PARTE 5 (CONTINUACIÓN)
# MODULO: BITÁCORA DE CONTROL DE OFERTAS OFICIALES CONSOLIDADAS Y AUDITORÍA
# ==============================================================================
            }).sort_values(by=["Artículo", "ID Oferta"], ascending=[True, False])

            st.dataframe(
                df_render_final, 
                column_config={"Precio Corporativo ($)": st.column_config.NumberColumn(format="$ %.2f")}, 
                hide_index=True, 
                use_container_width=True, 
                key=f"grilla_audit_fiel_{id_campana_destino}_{len(df_render_final)}"
            )

with st.sidebar:
    st.markdown("### ⚙️ Centro de Control")
    st.info(f"**Ámbito:** Corporativo\n\n**Mosaico:** Fiel `cargar_campanas_imagenes`\n\n**Neon Status:** Conectado")
