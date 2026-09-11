# ==============================================================================
# PROGRAMA: cargar_campanas_imagen.py | PARTE 1 DE 5
# MODULO: CONFIGURACIÓN GENERAL, ESTILOS E INICIALIZACIÓN CORE NEON
# ==============================================================================
import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import urllib.parse
from datetime import datetime

# CONFIGURACIÓN GENERAL E INICIALIZACIÓN CORE
APP_VERSION = "15.2"
st.set_page_config(page_title="Espejo de Carga Express (Neon)", layout="wide", page_icon="🖼️")
st.title("🏬 Central de Carga del Golpe por Pasillos (Neon)")
st.caption(f"Copia Fiel del Programa Original Pruebas de Inserción Masiva Simultánea v{APP_VERSION}")

# Estilos CSS Pro para alta densidad visual oscura
st.markdown("""
<style>
.stApp { background-color: #0f111a; color: #cdd6f4; }
div[data-testid="stMetric"] { background-color: #1e1e2e; border: 1px solid #313244; padding: 15px; border-radius: 8px; }
div[data-testid="stMetricValue"] { color: #f9e2af; font-size: 2rem; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# 1. CANDADOS PERSISTENTES DE MEMORIA (Fórmula anti-congelamiento)
if "exp_cat_id" not in st.session_state:
    st.session_state.exp_cat_id = None
if "exp_sub_id" not in st.session_state:
    st.session_state.exp_sub_id = None

# --- 2. VALIDACIÓN DE SECRETOS NEON ---
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
# PROGRAMA: cargar_campanas_imagen.py | PARTE 2 DE 5
# MODULO: DESCARGA RELACIONAL 3FN Y SELECTORES DE ENTRADA COMERCIAL
# ==============================================================================

try:
    # Descarga directa de PostgreSQL sin límites de paginación REST API
    res_o = ejecutar_consulta_neon("SELECT * FROM public.ofertas;") or []
    
    query_prod = """
        SELECT id_producto, nombre, marca, tamano, unidad, codigo_barras, id_cat, id_subcat, url_imagen 
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

# Conversión a DataFrames limpios en RAM
df_o = pd.DataFrame(res_o) if res_o else pd.DataFrame()
df_p = pd.DataFrame(res_p) if res_p else pd.DataFrame()
df_c = pd.DataFrame(res_c) if res_c else pd.DataFrame()
mapa_supers_ram = {int(s["id_super"]): s["nombre_supermercado"] for s in res_s} if res_s else {}


# POOL ACTUAL: RECONSTRUCCIÓN GENERAL DE HISTÓRICOS EN RAM
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

# RENDERIZADO DE COORDENADAS SUPERIORES (INTERFAZ VISUAL)
st.markdown("#### 1. Coordenadas de Entrada Comercial")
col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns([1.2, 1.4, 1.1, 1.1, 1.4])

with col_s1:
    ids_supers_activos = {s.get('id_super'): s.get('nombre_supermercado') for s in res_s if s.get('id_super')}
    id_super_contexto = st.selectbox("Supermercado Objetivo:", options=ids_supers_activos, format_func=lambda x: mapa_supers_ram.get(x, f"Super #{x}"))

with col_s2:
    # 1. Inicializamos todas las variables vacías para evitar NameError
    campanas_filtradas = []
    lista_ids_campanas = []
    dict_campanas = {}

    # 2. Obtenemos el ID del supermercado desde la sesión de forma segura
    id_super_actual = st.session_state.get("id_super_operador")

    # 3. Filtramos de manera estricta asegurando que ambos IDs sean tratados como enteros
    if res_c and id_super_actual is not None:
        for c in res_c:
            try:
                # Convertimos ambos IDs a enteros antes de comparar para evitar fallas de tipo (str vs int)
                id_campana_super = int(c.get('id_super', 0))
                id_filtro_super = int(id_super_actual)
                
                if id_campana_super == id_filtro_super:
                    campanas_filtradas.append(c)
            except (ValueError, TypeError):
                # Si algún ID viene corrupto o vacío, ignoramos ese registro en lugar de romper la app
                continue
                
        # 4. Construimos las estructuras solo con las campañas que pasaron el filtro
        lista_ids_campanas = [c['id_campana'] for c in campanas_filtradas]
        dict_campanas = {
            c['id_campana']: f"ID: {c['id_campana']} | {c['nombre_campana'].upper()} [{c['fecha_inicio']} al {c['fecha_fin']}]" 
            for c in campanas_filtradas
        }
    
    # 5. Desplegamos el selectbox (aparecerá vacío o deshabilitado si no hay coincidencias)
    campana_destino_sel = st.selectbox(
        "📅 Campaña / Folleto Destino *:", 
        options=sorted(lista_ids_campanas), 
        format_func=lambda x: dict_campanas.get(x, f"ID: {x}"),
        index=0 if lista_ids_campanas else None,
        disabled=not lista_ids_campanas
    )
    
    # 6. Asignamos el ID de la campaña seleccionada
    id_campana_destino = None
    if campana_destino_sel:
        id_campana_destino = int(campana_destino_sel)


with col_s5:
    columnas_elegidas = st.slider("Columnas por Fila (Densidad):", min_value=6, max_value=15, value=9, step=3)
    config_zoom = {
        6: {"altura_px": 85, "font_b": "0.72rem", "font_span": "0.62rem", "trim": 20},
        9: {"altura_px": 65, "font_b": "0.65rem", "font_span": "0.58rem", "trim": 14},
        12: {"altura_px": 50, "font_b": "0.58rem", "font_span": "0.52rem", "trim": 10},
        15: {"altura_px": 42, "font_b": "0.52rem", "font_span": "0.48rem", "trim": 8}
    }
    layout_dinamico = config_zoom.get(columnas_elegidas, config_zoom[9])
    
# =====================================================================
# PROGRAMA: registro_ofertas_mosaico_fiel.py | PARTE 3 DE 5 (FILTRO JERÁRQUICO)
# MODULO: CARGA DIRECTA Y DESTRUIDOR DE DUPLICADOS DE SKU COMERCIAL
# =====================================================================
df_laboratorio_activo = pd.DataFrame()

try:
    # 1. Leemos la pizarra única global de Neon
    res_po_actual = ejecutar_consulta_neon("SELECT * FROM public.ofertas_activas;") or []
    if res_po_actual:
        df_laboratorio_activo = pd.DataFrame(res_po_actual)
        df_laboratorio_activo["id_producto"] = df_laboratorio_activo["id_producto"].astype(str).str.strip()
        # Aseguramos que la fecha sea interpretada correctamente para ordenar
        df_laboratorio_activo["updated_at"] = pd.to_datetime(df_laboratorio_activo["updated_at"])
except Exception as e:
    st.error(f"❌ Error al conectar con la pizarra de ofertas activas: {e}")
    df_laboratorio_activo = pd.DataFrame()

# Inicializaciones de Session State
if "stat_lider" not in st.session_state: st.session_state.stat_lider = 0
if "stat_otros" not in st.session_state: st.session_state.stat_otros = 0
if "stat_total" not in st.session_state: st.session_state.stat_total = 0
if "formulario_imagenes_dict" not in st.session_state: st.session_state["formulario_imagenes_dict"] = {}

lista_items = []
df_pool_unicos = pd.DataFrame()

# 2. ALGORITMO CRUZADO DE DESDUPLICACIÓN JERÁRQUICA
if not df_laboratorio_activo.empty and not df_p.empty:
    df_lab = df_laboratorio_activo.copy()
    
    # Marcamos temporalmente cuáles registros pertenecen al Líder actual para la jerarquía
    df_lab["es_del_lider"] = df_lab["id_super"].fillna(0).astype(int) == int(id_super_contexto)
    
    # ORDENAMIENTO DE PRIORIDAD ESTRATÉGICA:
    # Primero ponemos los del Líder (True va antes que False si ordenamos descendente)
    # Si ninguno es del Líder, se ordena por la fecha de actualización más nueva (updated_at)
    df_lab_ordenado = df_lab.sort_values(
        by=["id_producto", "es_del_lider", "updated_at"], 
        ascending=[True, False, False]
    )
    
    # ELIMINACIÓN DE DUPLICADOS: Conserva estrictamente el primer registro de cada producto (Aplica tu regla)
    df_lab_limpio = df_lab_ordenado.drop_duplicates(subset=["id_producto"], keep="first").copy()
    
    # 3. CRUCE CON MAESTRO DE PRODUCTOS
    df_prod = df_p.copy()
    df_prod["id_producto"] = df_prod["id_producto"].astype(str).str.strip()
    
    df_lote_express = pd.merge(df_lab_limpio, df_prod, on="id_producto", how="inner")
    
    if not df_lote_express.empty:
        df_lote_express["precio_oferta"] = df_lote_express["precio_oferta_proyectado"].astype(float)
        df_lote_express["es_local"] = df_lote_express["es_del_lider"]
        
        # Sincronización inmediata de métricas basadas en SKUs únicos reales en pantalla
        st.session_state.stat_total = len(df_lote_express)
        st.session_state.stat_lider = int(df_lote_express["es_local"].sum())
        st.session_state.stat_otros = st.session_state.stat_total - st.session_state.stat_lider
        
        # Ordenamiento visual alfabético estándar por pasillos
        df_lote_express["id_cat"] = df_lote_express["id_cat"].fillna(0).astype(int)
        df_lote_express["id_subcat"] = df_lote_express["id_subcat"].fillna(0).astype(int)
        df_lote_express["nombre_sort"] = df_lote_express["nombre"].fillna("").astype(str).str.strip().str.lower()
        
        df_pool_unicos = df_lote_express.sort_values(by=["id_cat", "id_subcat", "nombre_sort"], ascending=[True, True, True])
        lista_items = df_pool_unicos.to_dict(orient="records")

# RENDER DE PANEL EJECUTIVO SUPERIOR
st.write("### Resumen Ejecutivo de la Pizarra de Activos (SKUs Únicos)")
metric_col1, metric_col2, metric_col3 = st.columns(3)
with metric_col1: st.metric(label="📊 Productos Propios (Líder)", value=st.session_state.get("stat_lider", 0))
with metric_col2: st.metric(label="🏪 SKUs Alerta Competencia", value=st.session_state.get("stat_otros", 0))
with metric_col3: st.metric(label="📦 Total Mosaico Único", value=st.session_state.get("stat_total", 0))


# =====================================================================
# PROGRAMA: registro_ofertas_mosaico_fiel.py | PARTE 4 DE 5
# MODULO: FUNCIÓN DE REJILLA VERTICAL (COMPATIBLE CON STRING TEXT IDs)
# =====================================================================
def dibujar_rejilla_mosaico_fiel(items_mosaico, _df_lab_activo, layout, _columnas_elegidas, _id_campana_destino):
    COLUMNAS_POR_FILA = _columnas_elegidas
    for i in range(0, len(items_mosaico), COLUMNAS_POR_FILA):
        bloque_items = items_mosaico[i:i + COLUMNAS_POR_FILA]
        columnas_ui = st.columns(COLUMNAS_POR_FILA)
        
        for idx, fila_p in enumerate(bloque_items):
            with columnas_ui[idx]:
                # NORMALIZACIÓN SEGURA: Mantenemos el ID como texto sin truncar con int()
                id_p_raw = str(fila_p["id_producto"]).strip()
                
                # Buscamos si ya tiene registro guardado en la pizarra para precargar datos
                match_pizarra = _df_lab_activo[_df_lab_activo["id_producto"] == id_p_raw]
                
                id_activa_real = None
                precio_defecto = float(fila_p.get("precio_oferta", 0.0))
                check_inicial = False
                
                if not match_pizarra.empty:
                    fila_reciente = match_pizarra.tail(1)
                    precio_defecto = float(fila_reciente["precio_oferta_proyectado"].values[0])
                    id_activa_real = int(fila_reciente["id_oferta_activa"].values[0])
                    # APLICACIÓN DE OPCIÓN 2: Lectura tolerante a fallos de inicialización del Scope
                    id_operador_seguro = st.session_state.get("id_super_operador", 0)
                    
                    # Si el producto pertenece a la cadena que estamos operando, se asume pre-incluido
                    if int(fila_reciente["id_super"].values[0]) == int(id_operador_seguro):
                        check_inicial = True               
                # Ajuste dinámico de texto según slider de densidad
                limite_caracteres = layout["trim"]
                nombre_lbl = str(fila_p.get("nombre", "")).strip().upper()[:limite_caracteres]
                marca_lbl = str(fila_p.get("marca", "Sin Marca")).strip()[:10]
                formato_empaque = f"{fila_p.get('tamano', '')} {fila_p.get('unidad', '')}".strip()
                
                sufijo_lider = "<span style='color: #f38ba8; font-weight: bold;'>(L)</span>" if fila_p.get("es_local", False) else ""
                
                html_especificacion = f"""
                <b style='font-size: {layout["font_b"]}; color:#cdd6f4;'>{nombre_lbl}{sufijo_lider}</b><br>
                <div style='line-height:1.1; margin-bottom:4px; height: 42px; overflow: hidden;'>
                    <span style='font-size: {layout["font_span"]}; color: #a6adc8;'>{marca_lbl} | {formato_empaque}</span>
                </div>
                """
                
                url_foto_render = fila_p.get("url_imagen") or "https://picsum.photos"
                
                with st.container(border=True):
                    st.image(url_foto_render, use_container_width=True)
                    st.markdown(html_especificacion, unsafe_allow_html=True)
                    # --- ADAPTACIÓN DE CLAVES ÚNICAS POR COMBINACIÓN DE PRODUCTO + SUPERMERCADO
                    id_sanitizado = id_p_raw.replace(" ", "_")
                    id_super_oferta = int(fila_p.get("id_super", 0)) # Capturamos el súper dueño de esta oferta específica
                    
                    # Inyectamos el id_super_oferta en la cadena para romper cualquier duplicidad de SKUs
                    p_key_string = f"num_pvp_{id_sanitizado}_{id_super_oferta}_{_id_campana_destino}"
                    m_key_string = f"chk_load_{id_sanitizado}_{id_super_oferta}_{_id_campana_destino}"
                    
                    # Los widgets ahora nacerán con identificadores totalmente aislados en la RAM
                    st.number_input("PVP ($):", min_value=0.0, value=precio_defecto, step=0.01, format="%.2f", key=p_key_string)
                    st.checkbox("Incluir", value=check_inicial, key=m_key_string)
                                     
                    # Conservamos el mapeo en RAM indexado por el ID de texto original
                    st.session_state["formulario_imagenes_dict"][id_p_raw] = {
                        "id_registro": id_activa_real,
                        "id_producto": id_p_raw,
                        "precio_key": p_key_string,
                        "marcado_key": m_key_string
                    }

# =====================================================================
# PROGRAMA: registro_ofertas_mosaico_fiel.py | PARTE 5 DE 5
# MODULO: INTERFAZ DINÁMICA DE PASILLOS Y PERSISTENCIA CORPORATIVA (UPSERT)
# =====================================================================
if form_categorias:
    nombres_pestanas = [cat["nombre"].upper() for cat in form_categorias]
    pestanas_ui = st.tabs(nombres_pestanas)
    
    for index_tab, cat_info in enumerate(form_categorias):
        id_categoria_actual = cat_info["id_cat"]
        items_del_pasillo = [item for item in lista_items if int(item.get("id_cat", 0)) == int(id_categoria_actual)]
        
        with pestanas_ui[index_tab]:
            sub_filtradas = [s for s in form_subcategorias if int(s["id_cat"]) == int(id_categoria_actual)]
            opciones_sub = [{"id_subcat": None, "nombre": "--- VER TODO EL PASILLO ---"}] + sub_filtradas
            sub_seleccionada = st.selectbox(f"Refinar surtido en {cat_info['nombre']}:", opciones_sub, format_func=lambda x: x["nombre"].upper(), key=f"sel_sub_{id_categoria_actual}")
            
            if sub_seleccionada["id_subcat"] is not None:
                items_finales_mosaico = [item for item in items_del_pasillo if int(item.get("id_subcat", 0)) == int(sub_seleccionada["id_subcat"])]
            else:
                items_finales_mosaico = items_del_pasillo
                
            if items_finales_mosaico:
                st.caption(f"Mostrando {len(items_finales_mosaico)} artículos en este segmento")
                dibujar_rejilla_mosaico_fiel(items_finales_mosaico, df_laboratorio_activo, layout_dinamico, columnas_elegidas, id_campana_destino)
            else:
                st.info("No hay productos registrados con ofertas activas en este segmento.")

# --- PANEL DE ACCIONES COMERCIALES CORPORATIVAS
st.write("---")
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("🚀 Disparar Inyección Express de Todo lo Seleccionado", use_container_width=True, type="primary"):
        payload_rafaga = []
        
        # Leemos las referencias guardadas en RAM por la rejilla
        for id_prod, referencias in st.session_state.get("formulario_imagenes_dict", {}).items():
            marcado_final = st.session_state.get(referencias["marcado_key"], False)
            precio_final = st.session_state.get(referencias["precio_key"], 0.0)
            id_reg_activa = referencias.get("id_registro")
            
            # Solo procesamos lo que el usuario marcó con precio válido
            if marcado_final and precio_final > 0.0:
                payload_rafaga.append({
                    "id_producto": str(id_prod).strip(),
                    "precio": float(precio_final),
                    "id_activa": id_reg_activa
                })
        
        if payload_rafaga:
            conn = None
            try:
                conn = psycopg2.connect(url_limpia)
                cur = conn.cursor()
                
                for reg in payload_rafaga:
                    # 1. Inserción limpia en la tabla histórica oficial de ofertas (Con su Campaña)
                    query_insert = """
                        INSERT INTO public.ofertas (
                            id_producto, id_super, precio_oferta, id_campana, 
                            id_sucursal, numero_pagina, posicion_slot, tipo_oferta, 
                            es_favorita, en_lista_compras, oferta_comprada
                        )
                        VALUES (%s, %s, %s, %s, NULL, NULL, NULL, 'C', False, False, False);
                    """
                    cur.execute(query_insert, (
                        reg["id_producto"], 
                        int(st.session_state["id_super_operador"]), 
                        reg["precio"], 
                        id_campana_destino
                    ))
                    
                    # 2. UPSERT en ofertas_activas: Sincroniza y actualiza el último precio en la pizarra general
                    query_upsert_activa = """
                        INSERT INTO public.ofertas_activas (id_producto, id_super, precio_oferta_proyectado)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (id_producto, id_super) 
                        DO UPDATE SET 
                            precio_oferta_proyectado = EXCLUDED.precio_oferta_proyectado,
                            updated_at = CURRENT_TIMESTAMP;
                    """
                    cur.execute(query_upsert_activa, (
                        reg["id_producto"], 
                        int(st.session_state["id_super_operador"]), 
                        reg["precio"]
                    ))
                
                conn.commit()
                st.toast("¡Inyección Histórica y Pizarra Activa Sincronizadas!", icon="✅")
                st.cache_data.clear()
                st.rerun()
                
            except Exception as err_api:
                if conn: conn.rollback()
                st.error(f"❌ Error de persistencia relacional en Neon: {err_api}")
            finally:
                if conn: conn.close()
        else:
            st.warning("⚠️ No se ha detectado ningún elemento incluido con precio válido.")

with col_btn2:
    if st.button("🧹 Limpiar y Resetear Pizarra Completa de Activos", use_container_width=True, type="secondary"):
        query_delete = "DELETE FROM public.ofertas_activas;"
        if ejecutar_consulta_neon(query_delete, (), fetch=False, commit=True):
            st.session_state["formulario_imagenes_dict"] = {}
            st.toast("¡Pizarra de últimos precios reseteada por completo!", icon="🗑️")
            st.cache_data.clear()
            st.rerun()

# --- BITÁCORA DE CONTROL DE OFERTAS OFICIALES CONSOLIDADAS
st.write("---")
st.markdown(f"#### 3. Monitoreo de Ofertas Publicadas (Historial de Campaña)")
df_o_grid = pd.DataFrame(res_o) if res_o else pd.DataFrame()

if not df_o_grid.empty and "id_campana" in df_o_grid.columns:
    df_o_grid = df_o_grid[df_o_grid["id_campana"].fillna(0).astype(int) == int(id_campana_destino)]

if df_o_grid.empty:
    st.info("ℹ️ No se registran ofertas oficiales guardadas aún en esta campaña.")
else:
    df_p_grid = pd.DataFrame(res_p) if res_p else pd.DataFrame()
    if not df_p_grid.empty:
        df_o_grid["id_producto"] = df_o_grid["id_producto"].astype(str).str.strip()
        df_p_grid["id_producto"] = df_p_grid["id_producto"].astype(str).str.strip()
        
        df_merged = pd.merge(df_o_grid, df_p_grid, on="id_producto", how="inner")
        if not df_merged.empty:
            df_render_final = pd.DataFrame({
                "ID Oferta": df_merged.get("id_oferta", "-"),
                "Marca": df_merged["marca"].fillna("Sin Marca"),
                "Artículo": df_merged["nombre"],
                "Presentación": df_merged["tamano"].astype(str) + " " + df_merged["unidad"].astype(str),
                "Precio Corporativo ($)": df_merged["precio_oferta"].astype(float),
                "Cobertura": "CORPORATIVO (Nacional)"
            }).sort_values(by=["Artículo", "ID Oferta"], ascending=[True, False])
            
            st.dataframe(
                df_render_final,
                column_config={"Precio Corporativo ($)": st.column_config.NumberColumn(format="$ %.2f")},
                hide_index=True,
                use_container_width=True,
                key=f"grilla_audit_fiel_{id_campana_destino}_{len(df_render_final)}"
            )

with st.sidebar:
    st.markdown("### 🏢 Centro de Control")
    st.info(f"**Ámbito:** Corporativo\n\n**Mosaico:** Fiel Activo\n\n**Neon Status:** Conectado")
