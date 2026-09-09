# ==============================================================================
# PROGRAMA CENTRAL: app.py (CENTRO DE CONTROL PURIFICADO)
# VERSIÓN: 4.6.0 (INTEGRACIÓN NATIVA DEL CLASIFICADOR DRAG & DROP WEB)
# DESCRIPCIÓN: Panel Central Retail con Navegación por Botones y Control de Auto-Importación
# MODIFICACIÓN: Enrutamiento directo al módulo HTML5 sin requisitos locales de PC.
# ==============================================================================

import streamlit as st

# 1. CONFIGURACIÓN CORPORATIVA DE LA VENTANA WEB DE PRODUCCIÓN
st.set_page_config(
    page_title="Sistema Maestro de Productos",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. DEFINICIÓN DE LA PÁGINA DE PORTADA (CENTRO DE CONTROL)
def mostrar_centro_control():
    st.title("🏭 Centro de Control")
    st.markdown("Bienvenido al ecosistema modular de clasificación, control y analítica de productos.")
    st.markdown("---")

    # Grilla horizontal simétrica de 6 columnas limpias de alta densidad para la suite
    col_inv, col_prod, col_maestro, col_subcat, col_saneamiento, col_bi = st.columns(6)

    with col_inv:
        st.markdown("#### Carga de Inventario")
        st.caption("Carga de archivos planos CSV mediante el diccionario de confianza.")
        if st.button("📤 Batch - Imput Inventario", use_container_width=True, key="btn_p1_inv_v460"):
            st.switch_page(pagina_inventario)


    st.markdown("---")
    st.info("💡 Consejo técnico: Utiliza la barra lateral de la izquierda para ingresar directo a los programas o para cambiar de estación de trabajo con un clic.")

# 3. DECLARACIÓN FORMAL DE INSTANCIAS DE PÁGINAS SATÉLITES EN LA RAÍZ
pagina_inicio = st.Page(mostrar_centro_control, title="🏭 Centro de Control", icon="🏠", default=True)
pagina_asociar = st.Page("asociar_imagen.py", title="Asociar Imagen", icon="📤")
pagina_intelig = st.Page("asociacion_inteligente.py", title="Asociar Imagen Plus", icon="📤")
pagina_grillap = st.Page("grilla_productos.py", title="Grilla Productos", icon="📤")
pagina_productos = st.Page("grilla_productos2.py", title="Grilla Productos Plus", icon="📤")
pagina_carga_masiva = st.Page("carga_masiva_imagen.py", title="Carga Masiva Imagen", icon="📤")
pagina_cargar_imagen = st.Page("cargar_campanas_imagen.py", title="📋 Cargar Imagen", icon="📋")
pagina_cargar21 = st.Page("cargar_campanas_imagen2.py", title="📋 Cargar Imagen 2", icon="📋")
pagina_datos = st.Page("subir_csv.py", title="Subir Datos", icon="⚙️")
pagina_oferta_visual = st.Page("cargar_oferta_visual.py", title="Cargar Oferta Visual", icon="⚙️")
pagina_oferta_activa = st.Page("carga_inicial_oferta_activa.py", title="Carga Inicial Ofertas", icon="⚙️")
pagina_maqueta = st.Page("maquetacion.py", title="Maquetacion", icon="⚙️")
pagina_ofertas = st.Page("ofertas.py", title="Ingresar Ofertas", icon="⚙️")
# 4. CONSTRUCCIÓN AUTOMÁTICA DEL MOTOR DE NAVEGACIÓN EN LA BARRA LATERAL
enrutador_global = st.navigation([
    pagina_inicio,
    pagina_asociar,
    pagina_intelig,
    pagina_carga_masiva,
    pagina_grillap,
    pagina_productos,
    pagina_cargar_imagen,
    pagina_cargar21,
    pagina_maqueta,
    pagina_oferta_activa,
    pagina_oferta_visual,
    pagina_ofertas,
    pagina_datos
    
])

# Componentes fijos de control e identidad comercial en la barra de la izquierda
st.sidebar.markdown("### 🔒 Ecosistema Retail Activo")
st.sidebar.caption("Estaciones de trabajo descentralizadas e independientes.")
st.sidebar.markdown("---")

# 5. DESPACHO CENTRAL SEGURO Y CONTROL DEL HILO DE EJECUCIÓN
enrutador_global.run()
