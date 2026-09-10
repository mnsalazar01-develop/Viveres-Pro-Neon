# ==============================================================================
# PARTE 1: CONFIGURACIÓN, LLAVES DE SEGURIDAD Y CONEXIÓN A NEON
# VERSIÓN: 2.0 - MIGRADO A NEON & IMGBB
# ==============================================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

# CONSTANTES DE VERSIÓN Y CONFIGURACIÓN CORPORATIVA
VERSION_PROGRAMA = "2.0-Neon"
UNIDADES = ["gr", "kg", "ml", "lt", "unidad"]
NOMBRE_PROGRAMA = "Grilla de Productos"
IMGBB_API_URL = "https://imgbb.com"

# 1. CONFIGURACIÓN DE LA VENTANA DE STREAMLIT
st.set_page_config(
    page_title=f"{NOMBRE_PROGRAMA} v{VERSION_PROGRAMA}",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. CARGAR SECRETOS DE FORMA SEGURA DESDE STREAMLIT CLOUD
try:
    url_limpia = st.secrets["neon"]["url"]
    IMGBB_API_KEY = st.secrets["imgbb"]["api_key"]
    IMGBB_ALBUM_ID = st.secrets["imgbb"]["album_id"]
except KeyError as e:
    st.error(f"❌ Error: Falta configurar la variable {e} en los Secrets de Streamlit.")
    st.stop()

# 3. CONEXIÓN SEGURA CON NEON POSTGRESQL (Nativo de Streamlit utilizando url_limpia)
@st.cache_resource
def init_neon_connection(connection_url: str):
    try:
        # Crea la conexión utilizando la URL extraída de tus secretos
        conn = st.connection("neon_db", type="sql", url=connection_url)
        return conn
    except Exception as e:
        st.error(f"❌ Error de Conexión Base a Neon: {e}")
        st.stop()

conn = init_neon_connection(url_limpia)

# 4. INICIALIZAR ESTADO DE EDICIÓN INLINE
if "modo_edicion" not in st.session_state:
    st.session_state["modo_edicion"] = False
if "prod_id_edicion" not in st.session_state:
    st.session_state["prod_id_edicion"] = None

st.title(f"📦 {NOMBRE_PROGRAMA}")
st.markdown(f"**Versión {VERSION_PROGRAMA}** — Edición inline + acciones en modal operando en Neon.")

# 5. FUNCIÓN AUXILIAR: Normalizar valores de Pandas / SQL (evita errores de compilación por NaN o None)
def safe_str(val, default=""):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return str(val) if str(val) != default else default

def safe_float(val, default=0.0):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def safe_bool(val, default=False):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return bool(val)

# ==============================================================================
# PARTE 2: CONTROLADORES DE DATOS (SQL) Y SUBIDA A IMGBB
# ==============================================================================

# 3. FUNCIONES AUXILIARES DE CARGA DE DATOS MAESTROS (Neon SQL)
@st.cache_data(ttl=60)
def cargar_categorias():
    try:
        df = conn.query("SELECT id_cat, nombre FROM categorias;", ttl="1m")
        return pd.DataFrame(df)
    except Exception as e:
        st.error(f"❌ Error cargando categorías: {e}")
        return pd.DataFrame(columns=["id_cat", "nombre"])

@st.cache_data(ttl=60)
def cargar_subcategorias():
    try:
        df = conn.query("SELECT id_subcat, id_cat, nombre FROM subcategorias;", ttl="1m")
        return pd.DataFrame(df)
    except Exception as e:
        st.error(f"❌ Error cargando subcategorías: {e}")
        return pd.DataFrame(columns=["id_subcat", "id_cat", "nombre"])

@st.cache_data(ttl=60)
def cargar_productos():
    try:
        df = conn.query("SELECT * FROM productos;", ttl="1m")
        return pd.DataFrame(df)
    except Exception as e:
        st.error(f"❌ Error cargando productos: {e}")
        return pd.DataFrame()

# 3.1 FUNCIÓN AUXILIAR: SUBIR IMAGEN A IMGBB (Evita problemas de Egress)
def subir_imagen_storage(archivo) -> str:
    try:
        api_key = st.secrets["imgbb"]["api_key"]
        file_bytes = archivo.getvalue()
        
        payload = {
            "key": api_key,
        }
        files = {
            "image": file_bytes
        }
        
        # Pausa táctica anti-saturación para la API de ImgBB
        time.sleep(0.5) 
        
        response = requests.post(IMGBB_API_URL, data=payload, files=files)
        res_json = response.json()
        
        if response.status_code == 200 and res_json.get("success"):
            return str(res_json["data"]["url"])
        else:
            st.error(f"❌ Error devuelto por ImgBB: {res_json.get('error', {}).get('message', 'Desconocido')}")
            return ""
    except Exception as e:
        st.error(f"❌ Error crítico subiendo a ImgBB: {e}")
        return ""

def eliminar_imagen_storage(url_imagen: str) -> bool:
    # La API gratuita de ImgBB no ofrece borrado simple por URL sin tokens previos;
    # se retorna True para evitar bloquear los flujos relacionales de la BD.
    return True
# ==============================================================================
# PARTE 3: MODALES INTERACTIVOS (DUPLICAR Y ELIMINAR)
# ==============================================================================

@st.dialog("📋 Duplicar Producto", width="large")
def dialog_duplicar_producto(prod: dict, df_cats: pd.DataFrame, df_subcats: pd.DataFrame, mapa_cat_nombre_a_id: dict, mapa_subcat_nombre_a_id: dict):
    prod_nombre = safe_str(prod.get("nombre"), "")
    prod_marca = safe_str(prod.get("marca"), "")
    prod_tamano = safe_float(prod.get("tamano"), 0.0)
    prod_unidad = safe_str(prod.get("unidad"), "")
    prod_fav = safe_bool(prod.get("es_favorito"), False)
    prod_dem = safe_bool(prod.get("alta_demanda"), False)
    prod_est = safe_bool(prod.get("es_estrategico"), False)
    prod_verif = safe_bool(prod.get("cod_verif"), False)
    prod_cat = safe_str(prod.get("nombre_cat"), "")
    prod_subcat = safe_str(prod.get("nombre_subcat"), "")
    prod_url_imagen = safe_str(prod.get("url_imagen"), "")
    
    lista_categorias = sorted(df_cats["nombre"].dropna().unique().tolist()) if not df_cats.empty else []
    st.markdown(f"**Duplicando:** {prod_nombre}")
    st.markdown("---")
    
    col_cat, col_subcat = st.columns(2)
    with col_cat:
        dup_cat = st.selectbox("Categoría:", lista_categorias, index=lista_categorias.index(prod_cat) if prod_cat in lista_categorias else 0, key=f"dlg_dup_cat_{prod_nombre[:10]}")
    with col_subcat:
        id_cat_sel = mapa_cat_nombre_a_id.get(dup_cat)
        subcats_disp = []
        if id_cat_sel is not None and not df_subcats.empty:
            subcats_disp = sorted(df_subcats[df_subcats["id_cat"] == id_cat_sel]["nombre"].dropna().unique().tolist())
        idx_sub = subcats_disp.index(prod_subcat) if prod_subcat in subcats_disp else 0
        dup_subcat = st.selectbox("Subcategoría:", subcats_disp if subcats_disp else ["- Sin subcategorías -"], index=idx_sub if subcats_disp else 0, disabled=not subcats_disp, key=f"dlg_dup_subcat_{prod_nombre[:10]}")
        
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        dup_nombre = st.text_input("Nombre del Producto *", value=f"{prod_nombre} (Copia)", key=f"dlg_dup_nom_{prod_nombre[:10]}")
    with col2:
        dup_marca = st.text_input("Marca:", value=prod_marca, key=f"dlg_dup_mar_{prod_nombre[:10]}")
    with col3:
        dup_codigo = st.text_input("Código de Barras:", value="", placeholder="Dejar vacío si no aplica", key=f"dlg_dup_cc_{prod_nombre[:10]}")
        
    col4, col5 = st.columns(2)
    with col4:
        dup_tamano = st.number_input("Tamaño:", min_value=0.0, step=0.01, value=prod_tamano, key=f"dlg_dup_tam_{prod_nombre[:10]}")
    with col5:
        idx_unidad = UNIDADES.index(prod_unidad) if prod_unidad in UNIDADES else 0
        dup_unidad = st.selectbox("Unidad de medida:", UNIDADES, index=idx_unidad, key=f"dlg_dup_uni_{prod_nombre[:10]}")
        
    col6, col7, col8, col9 = st.columns(4)
    with col6:
        dup_fav = st.checkbox("⭐ Favorito", value=prod_fav, key=f"dlg_dup_fav_{prod_nombre[:10]}")
    with col7:
        dup_dem = st.checkbox("🔥 Alta Demanda", value=prod_dem, key=f"dlg_dup_dem_{prod_nombre[:10]}")
    with col8:
        dup_est = st.checkbox("🎯 Estratégico", value=prod_est, key=f"dlg_dup_est_{prod_nombre[:10]}")
    with col9:
        dup_verif = st.checkbox("✔ Cod. Verif.", value=prod_verif, key=f"dlg_dup_ver_{prod_nombre[:10]}")
        
    st.markdown("---")
    st.markdown("#### Imagen del Producto")
    col_img_prev, col_img_up = st.columns([1, 2])
    with col_img_prev:
        if prod_url_imagen:
            st.image(prod_url_imagen, width=120)
        else:
            st.markdown("*Sin imagen*")
    with col_img_up:
        usar_misma = st.checkbox("Reutilizar imagen actual", value=True, key=f"dlg_dup_sameimg_{prod_nombre[:10]}")
        dup_archivo = None
        if not usar_misma:
            dup_archivo = st.file_uploader("Subir nueva imagen a ImgBB:", type=["png", "jpg", "jpeg", "webp", "gif"], key=f"dlg_dup_img_{prod_nombre[:10]}")
            
    st.markdown("---")
    if st.button("Crear Copia en Neon", type="primary", use_container_width=True, key=f"dlg_dup_btn_{prod_nombre[:10]}"):
        if not dup_nombre.strip():
            st.error("❌ El nombre es obligatorio.")
            return
        if dup_subcat == "- Sin subcategorías -":
            st.error("❌ Selecciona una subcategoría válida.")
            return
            
        id_subcat_db = mapa_subcat_nombre_a_id.get(dup_subcat)
        id_cat_db = mapa_cat_nombre_a_id.get(dup_cat)
        
        url_img = prod_url_imagen if usar_misma else ""
        if not usar_misma and dup_archivo is not None:
            url_img = subir_imagen_storage(dup_archivo)
            
        try:
            with conn.session as session:
                query = """
                    INSERT INTO productos (nombre, id_cat, id_subcat, marca, codigo_barras, tamano, unidad, es_favorito, alta_demanda, es_estrategico, cod_verif, url_imagen)
                    VALUES (:nombre, :id_cat, :id_subcat, :marca, :codigo_barras, :tamano, :unidad, :es_favorito, :alta_demanda, :es_estrategico, :cod_verif, :url_imagen);
                """
                session.execute(query, {
                    "nombre": dup_nombre.strip(),
                    "id_cat": int(id_cat_db),
                    "id_subcat": int(id_subcat_db),
                    "marca": dup_marca.strip() if dup_marca.strip() else None,
                    "codigo_barras": dup_codigo.strip() if dup_codigo.strip() else None,
                    "tamano": dup_tamano if dup_tamano > 0 else None,
                    "unidad": dup_unidad if dup_unidad else None,
                    "es_favorito": dup_fav,
                    "alta_demanda": dup_dem,
                    "es_estrategico": dup_est,
                    "cod_verif": dup_verif,
                    "url_imagen": url_img if url_img else None
                })
                session.commit()
            st.success("✔️ Copia guardada exitosamente en Neon.")
            cargar_productos.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al crear copia en Neon: {e}")

@st.dialog("🗑️ Eliminar Producto", width="small")
def dialog_eliminar_producto(prod: dict):
    prod_id = int(prod["id_producto"])
    prod_nombre = safe_str(prod.get("nombre"), "")

    st.error(f"¿Eliminar permanentemente ***{prod_nombre}*** (ID `{prod_id}`)?")
    st.markdown("Esta acción modificará la base de datos de Neon inmediatamente.")

    confirmar = st.checkbox("Sí, confirmo la eliminación permanente", key=f"dlg_del_conf_{prod_id}")
    if st.button("Eliminar Permanentemente", type="secondary", disabled=not confirmar, use_container_width=True, key=f"dlg_del_btn_{prod_id}"):
        try:
            with conn.session as session:
                session.execute("DELETE FROM productos WHERE id_producto = :id;", {"id": prod_id})
                session.commit()
            st.success(f"✔️ Producto ID {prod_id} eliminado de Neon.")
            cargar_productos.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error al eliminar en Neon: {e}")
# ==============================================================================
# PARTE 4: PROCESAMIENTO DE CATÁLOGO, FILTROS Y PANEL DE ACCIONES
# ==============================================================================

# 4. CARGA DE DATOS EN MEMORIA (Neon Directo)
df_categorias = cargar_categorias()
df_subcategorias = cargar_subcategorias()
df_productos_raw = cargar_productos()

if df_productos_raw.empty:
    st.warning("⚠️ No se encontraron productos en la base de datos de Neon o la tabla está vacía.")
    st.stop()

# 5. ENRIQUECIMIENTO DEL DATASET
df = df_productos_raw.copy()
if not df_categorias.empty:
    df = df.merge(df_categorias.rename(columns={"nombre": "nombre_cat", "id_cat": "id_cat_ref"}), left_on="id_cat", right_on="id_cat_ref", how="left")
    df.drop(columns=["id_cat_ref"], inplace=True, errors="ignore")
else:
    df["nombre_cat"] = "-"

if not df_subcategorias.empty:
    df = df.merge(df_subcategorias.rename(columns={"nombre": "nombre_subcat", "id_subcat": "id_subcat_ref"}), left_on="id_subcat", right_on="id_subcat_ref", how="left")
    df.drop(columns=["id_subcat_ref"], inplace=True, errors="ignore")
else:
    df["nombre_subcat"] = "-"

# MAPEOS
lista_categorias = sorted(df_categorias["nombre"].dropna().unique().tolist()) if not df_categorias.empty else []
mapa_cat_nombre_a_id = dict(zip(df_categorias["nombre"], df_categorias["id_cat"])) if not df_categorias.empty else {}
mapa_subcat_nombre_a_id = dict(zip(df_subcategorias["nombre"], df_subcategorias["id_subcat"])) if not df_subcategorias.empty else {}

# 6. RESUMEN DEL CATÁLOGO
st.markdown("### 📊 Resumen del Catálogo (Neon)")
col_k1, col_k2, col_k3, col_k4, col_k5 = st.columns(5)
col_k1.metric("Total Productos", len(df))
col_k2.metric("Filtrados", len(df))
col_k3.metric("Categorías", df_categorias["id_cat"].nunique() if not df_categorias.empty else 0)
col_k4.metric("Subcategorías", df_subcategorias["id_subcat"].nunique() if not df_subcategorias.empty else 0)
col_k5.metric("Marcas Únicas", df["marca"].nunique() if "marca" in df.columns else 0)

# 7. FILTROS DE BÚSQUEDA
f1, f2, f3 = st.columns([3, 2, 2])
with f1:
    busqueda = st.text_input("Buscar producto:", placeholder="Nombre, marca o código de barras...", label_visibility="collapsed")
with f2:
    opciones_cat = ["Todas"] + lista_categorias
    filtro_cat = st.selectbox("Categoría:", opciones_cat, label_visibility="collapsed")
with f3:
    if filtro_cat != "Todas" and not df_subcategorias.empty:
        id_cat_sel = mapa_cat_nombre_a_id.get(filtro_cat)
        subcats_filtradas = df_subcategorias[df_subcategorias["id_cat"] == id_cat_sel]["nombre"].dropna().unique().tolist()
        opciones_subcat = ["Todas"] + sorted(subcats_filtradas)
    else:
        opciones_subcat = ["Todas"] + (sorted(df_subcategorias["nombre"].dropna().unique().tolist()) if not df_subcategorias.empty else [])
    filtro_subcat = st.selectbox("Subcategoría:", opciones_subcat, label_visibility="collapsed")

# 8. APLICACIÓN DE FILTROS
mask = pd.Series([True] * len(df))
if busqueda:
    busqueda_lower = busqueda.lower()
    mask_nombre = df["nombre"].fillna("").str.lower().str.contains(busqueda_lower, na=False)
    mask_marca = df["marca"].fillna("").str.lower().str.contains(busqueda_lower, na=False)
    mask_codigo = df["codigo_barras"].fillna("").str.lower().str.contains(busqueda_lower, na=False)
    mask &= (mask_nombre | mask_marca | mask_codigo)
if filtro_cat != "Todas" and "nombre_cat" in df.columns:
    mask &= (df["nombre_cat"] == filtro_cat)
if filtro_subcat != "Todas" and "nombre_subcat" in df.columns:
    mask &= (df["nombre_subcat"] == filtro_subcat)

df_filtrado = df[mask].copy()

# 10. PANEL DE ACCIONES UNIFICADO
if df_filtrado.empty:
    st.info("💡 No hay productos que coincidan con los filtros seleccionados.")
    prod_sel = None
else:
    listado_filtrado = df_filtrado.to_dict("records")
    def formateador_desambiguado(x):
        marca_lbl = x.get('marca') or 'Sin Marca'
        tamano_lbl = float(x.get('tamano')) if x.get('tamano') else 0.0
        unidad_lbl = x.get('unidad') or ''
        sku_lbl = x.get('codigo_barras') or 'SIN SKU'
        return f"{x['nombre']} | {marca_lbl} ({tamano_lbl} {unidad_lbl}) [{sku_lbl}]"

    with st.container(border=True):
        prod_sel = st.selectbox("Seleccione la presentación exacta para ejecutar acciones:", listado_filtrado, format_func=formateador_desambiguado, index=None, placeholder="🔍 Elige un producto para acciones...", key="m_sel")

    if prod_sel is not None:
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("📝 Modificar", type="primary", use_container_width=True, key="btn_modificar_v2"):
                st.session_state["modo_edicion"] = True
                st.session_state["prod_id_edicion"] = int(prod_sel["id_producto"])
                st.rerun()
        with col_btn2:
            if st.button("📋 Duplicar", use_container_width=True, key="btn_duplicar_v2"):
                dialog_duplicar_producto(prod_sel, df_categorias, df_subcategorias, mapa_cat_nombre_a_id, mapa_subcat_nombre_a_id)
        with col_btn3:
            if st.button("🗑️ Eliminar", use_container_width=True, key="btn_eliminar_v2"):
                dialog_eliminar_producto(prod_sel)

# ==============================================================================
# PARTE 5: FORMULARIO DE EDICIÓN, GRILLA PRINCIPAL Y CREADOR
# ==============================================================================

# 10.1 FORMULARIO DE EDICIÓN INLINE (Acoplado a Neon)
if st.session_state.get("modo_edicion") and st.session_state.get("prod_id_edicion"):
    prod_id_edit = st.session_state["prod_id_edicion"]
    prod_edit = next((p for p in listado_filtrado if int(p["id_producto"]) == prod_id_edit), None)

    if prod_edit is not None:
        st.markdown("---")
        st.markdown("### 📝 Editar Producto en Neon")
        with st.container(border=True):
            prod_nombre = safe_str(prod_edit.get("nombre"), "")
            prod_marca = safe_str(prod_edit.get("marca"), "")
            prod_codigo = safe_str(prod_edit.get("codigo_barras"), "")
            prod_tamano = safe_float(prod_edit.get("tamano"), 0.0)
            prod_unidad = safe_str(prod_edit.get("unidad"), "")
            prod_fav = safe_bool(prod_edit.get("es_favorito"), False)
            prod_dem = safe_bool(prod_edit.get("alta_demanda"), False)
            prod_est = safe_bool(prod_edit.get("es_estrategico"), False)
            prod_verif = safe_bool(prod_edit.get("cod_verif"), False)
            prod_cat = safe_str(prod_edit.get("nombre_cat"), "")
            prod_subcat = safe_str(prod_edit.get("nombre_subcat"), "")
            prod_url_imagen = safe_str(prod_edit.get("url_imagen"), "")

            st.markdown(f"**Editando:** {prod_nombre} (ID `{prod_id_edit}`)")

            col_cat, col_subcat = st.columns(2)
            with col_cat:
                edit_cat = st.selectbox("Categoría:", lista_categorias, index=lista_categorias.index(prod_cat) if prod_cat in lista_categorias else 0, key=f"inline_edit_cat_{prod_id_edit}")
            with col_subcat:
                id_cat_sel = mapa_cat_nombre_a_id.get(edit_cat)
                subcats_disp = []
                if id_cat_sel is not None and not df_subcategorias.empty:
                    subcats_disp = sorted(df_subcategorias[df_subcategorias["id_cat"] == id_cat_sel]["nombre"].dropna().unique().tolist())
                idx_sub = subcats_disp.index(prod_subcat) if prod_subcat in subcats_disp else 0
                edit_subcat = st.selectbox("Subcategoría:", subcats_disp if subcats_disp else ["- Sin subcategorías -"], index=idx_sub if subcats_disp else 0, disabled=not subcats_disp, key=f"inline_edit_subcat_{prod_id_edit}")

            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                edit_nombre = st.text_input("Nombre:", value=prod_nombre, key=f"inline_edit_nom_{prod_id_edit}")
            with col2:
                edit_marca = st.text_input("Marca:", value=prod_marca, key=f"inline_edit_mar_{prod_id_edit}")
            with col3:
                edit_codigo = st.text_input("Código de Barras:", value=prod_codigo, key=f"inline_edit_cod_{prod_id_edit}")

            col4, col5 = st.columns(2)
            with col4:
                edit_tamano = st.number_input("Tamaño:", value=prod_tamano, step=0.01, key=f"inline_edit_tam_{prod_id_edit}")
            with col5:
                idx_unidad = UNIDADES.index(prod_unidad) if prod_unidad in UNIDADES else 0
                edit_unidad = st.selectbox("Unidad de medida:", UNIDADES, index=idx_unidad, key=f"inline_edit_uni_{prod_id_edit}")

            col6, col7, col8, col9 = st.columns(4)
            with col6:
                edit_fav = st.checkbox("⭐ Favorito", value=prod_fav, key=f"inline_edit_fav_{prod_id_edit}")
            with col7:
                edit_dem = st.checkbox("🔥 Alta Demanda", value=prod_dem, key=f"inline_edit_dem_{prod_id_edit}")
            with col8:
                edit_est = st.checkbox("🎯 Estratégico", value=prod_est, key=f"inline_edit_est_{prod_id_edit}")
            with col9:
                edit_verif = st.checkbox("✔ Cod. Verif.", value=prod_verif, key=f"inline_edit_ver_{prod_id_edit}")

            st.markdown("---")
            st.markdown("#### Imagen del Producto")
            col_img_prev, col_img_up = st.columns([1, 2])
            with col_img_prev:
                if prod_url_imagen:
                    st.image(prod_url_imagen, width=120)
                else:
                    st.markdown("*Sin imagen*")
            with col_img_up:
                cambiar_img = st.checkbox("Cambiar imagen (Sube directo a ImgBB)", value=False, key=f"inline_edit_chgimg_{prod_id_edit}")
                nueva_imagen = None
                if cambiar_img:
                    nueva_imagen = st.file_uploader("Subir nueva imagen:", type=["png", "jpg", "jpeg", "webp", "gif"], key=f"inline_edit_img_{prod_id_edit}")

            st.markdown("---")
            col_guardar, col_cancelar = st.columns(2)
            with col_guardar:
                if st.button("Guardar Cambios en Neon", type="primary", use_container_width=True, key=f"inline_edit_save_{prod_id_edit}"):
                    if edit_subcat == "- Sin subcategorías -":
                        st.error("❌ La categoría seleccionada no tiene subcategorías.")
                        return

                    id_cat_db = mapa_cat_nombre_a_id.get(edit_cat)
                    id_subcat_db = mapa_subcat_nombre_a_id.get(edit_subcat)

                    url_img_final = prod_url_imagen
                    if cambiar_img and nueva_imagen is not None:
                        uploaded_url = subir_imagen_storage(nueva_imagen)
                        if uploaded_url:
                            url_img_final = uploaded_url

                    try:
                        with conn.session as session:
                            query = """
                                UPDATE productos SET 
                                    nombre = :nombre, id_cat = :id_cat, id_subcat = :id_subcat,
                                    marca = :marca, codigo_barras = :codigo_barras, tamano = :tamano,
                                    unidad = :unidad, es_favorito = :es_favorito, alta_demanda = :alta_demanda,
                                    es_estrategico = :es_estrategico, cod_verif = :cod_verif, url_imagen = :url_imagen
                                WHERE id_producto = :id_producto;
                            """
                            session.execute(query, {
                                "nombre": edit_nombre.strip(),
                                "id_cat": int(id_cat_db),
                                "id_subcat": int(id_subcat_db),
                                "marca": edit_marca.strip() if edit_marca.strip() else None,
                                "codigo_barras": edit_codigo.strip() if edit_codigo.strip() else None,
                                "tamano": edit_tamano,
                                "unidad": edit_unidad,
                                "es_favorito": edit_fav,
                                "alta_demanda": edit_dem,
                                "es_estrategico": edit_est,
                                "cod_verif": edit_verif,
                                "url_imagen": url_img_final if url_img_final else None,
                                "id_producto": prod_id_edit
                            })
                            session.commit()
                        st.success("✔️ Producto actualizado correctamente en Neon.")
                        st.session_state["modo_edicion"] = False
                        st.session_state["prod_id_edicion"] = None
                        cargar_productos.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al actualizar en Neon: {e}")

            with col_cancelar:
                if st.button("❌ Cancelar", use_container_width=True, key=f"inline_edit_cancel_{prod_id_edit}"):
                    st.session_state["modo_edicion"] = False
                    st.session_state["prod_id_edicion"] = None
                    st.rerun()

# 10.2 GRILLA VISUAL DE STREAMLIT
st.markdown(f"### 📋 Catálogo — {len(df_filtrado)} registros")

columnas_display = [
    "url_imagen", "id_producto", "nombre", "marca",
    "tamano", "unidad", "nombre_cat", "nombre_subcat",
    "es_favorito", "alta_demanda", "es_estrategico", "cod_verif"
]
columnas_existentes = [c for c in columnas_display if c in df_filtrado.columns]
df_display = df_filtrado[columnas_existentes].copy()

renombres = {
    "url_imagen": "Imagen",
    "id_producto": "ID",
    "nombre": "Nombre del Producto",
    "marca": "Marca",
    "tamano": "Tamaño",
    "unidad": "Unidad",
    "nombre_cat": "Categoría",
    "nombre_subcat": "Subcategoría",
    "es_favorito": "⭐ Fav",
    "alta_demanda": "🔥 Dem",
    "es_estrategico": "🎯 Est",
    "cod_verif": "✔ Verif",
}
df_display.rename(columns=renombres, inplace=True)

if "ID" in df_display.columns:
    df_display = df_display.sort_values(by="ID", ascending=True).reset_index(drop=True)

st.dataframe(
    df_display,
    use_container_width=True,
    height=400,
    column_config={
        "Imagen": st.column_config.ImageColumn("Imagen", help="Vista previa desde URL pública de ImgBB", width="small"),
        "ID": st.column_config.NumberColumn("ID", width="small"),
        "Marca": st.column_config.TextColumn("Marca", width="small"),
        "Nombre del Producto": st.column_config.TextColumn("Nombre del Producto", width="medium"),
        "Tamaño": st.column_config.NumberColumn("Tamaño", format="%.2f", width="small"),
        "Unidad": st.column_config.TextColumn("Unidad", width="small"),
        "Categoría": st.column_config.TextColumn("Categoría", width="small"),
        "Subcategoría": st.column_config.TextColumn("Subcategoría", width="small"),
    },
    hide_index=True
)


