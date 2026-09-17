import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor

st.set_page_config(page_title="Gestor de Agrupaciones - Neon", layout="wide")

# 🔌 Conexión segura usando tu bloque exacto de secretos
def get_db_connection():
    try:
        url_limpia = st.secrets["neon"]["url"]
        conn = psycopg2.connect(url_limpia, cursor_factory=RealDictCursor)
        return conn
    except KeyError:
        st.error("❌ Error de configuración: Falta la variable ['neon']['url'] en los secrets.")
        st.stop()
    except Exception as e:
        st.error(f"❌ Error al conectar a la base de datos Neon: {e}")
        return None

# --- CONSULTAS COMPATIBLES CON TU ESQUEMA ---
def obtener_productos_reales(conn):
    with conn.cursor() as cur:
        # Filtramos por es_pack = false o null
        cur.execute("""
            SELECT id_producto, nombre, marca, tamano, unidad 
            FROM public.productos 
            WHERE es_pack IS NOT TRUE 
            ORDER BY nombre ASC;
        """)
        return cur.fetchall()

def obtener_packs_existentes(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id_producto, nombre FROM public.productos WHERE es_pack = TRUE ORDER BY nombre ASC;")
        return cur.fetchall()

def obtener_campanas_con_super(conn):
    with conn.cursor() as cur:
        # Cruzamos con supermercados para mostrar una UI clara al usuario
        cur.execute("""
            SELECT c.id_campana, c.nombre_campana, c.id_super, s.nombre_supermercado 
            FROM public.campanas c
            LEFT JOIN public.supermercados s ON c.id_super = s.id_super
            ORDER BY c.id_campana DESC;
        """)
        return cur.fetchall()

def obtener_componentes_pack(conn, id_pack):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT p.nombre, p.marca, pc.cantidad 
            FROM public.pack_componentes pc
            JOIN public.productos p ON pc.id_producto_real = p.id_producto
            WHERE pc.id_pack = %s;
        """, (id_pack,))
        return cur.fetchall()

# --- INTERFAZ GRÁFICA ---
st.sidebar.title("🎯 Menú de Operaciones")
opcion = st.sidebar.radio("Selecciona una acción:", ["🚀 Cargar Pack en Campaña", "⚙️ Crear / Gestionar Packs"])

conn = get_db_connection()

if conn:
    # ---------------------------------------------------------
    # OPCIÓN 1: CARGA EXPRESS A OFERTAS DE CAMPAÑA
    # ---------------------------------------------------------
    if opcion == "🚀 Cargar Pack en Campaña":
        st.title("🚀 Carga Express de Agrupaciones")
        st.subheader("Expande múltiples SKUs en la tabla de ofertas con un solo clic")
        st.divider()

        campanas = obtener_campanas_con_super(conn)
        packs = obtener_packs_existentes(conn)

        if not campanas or not packs:
            st.warning("⚠️ Asegúrate de tener campañas y al menos un Pack registrado en el sistema.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                # Diccionario indexado por id_campana para recuperar rápido su id_super correspondiente
                dict_campanas = {c['id_campana']: c for c in campanas}
                
                campana_id = st.selectbox(
                    "1. Selecciona la Campaña Destino:",
                    options=list(dict_campanas.keys()),
                    format_func=lambda x: f"{dict_campanas[x]['nombre_campana']} ({dict_campanas[x]['nombre_supermercado']})"
                )
                
                # Extraemos el id_super asociado a esa campaña
                id_super_asociado = dict_campanas[campana_id]['id_super']

                pack_id = st.selectbox(
                    "2. Selecciona la Agrupación (Pack) a desplegar:",
                    options=[p['id_producto'] for p in packs],
                    format_func=lambda x: next(p['nombre'] for p in packs if p['id_producto'] == x)
                )

            with col2:
                st.markdown("### 📋 Productos Reales incluidos:")
                componentes = obtener_componentes_pack(conn, pack_id)
                if componentes:
                    for comp in componentes:
                        st.markdown(f"- **{comp['nombre']}** ({comp['marca']}) — *Cant: {comp['cantidad']}*")
                else:
                    st.caption("Este pack está vacío. Ve a la sección de gestión para añadirle productos.")

            st.divider()
            
            if st.button("⚡ Inyectar todos los productos a la Campaña", type="primary", use_container_width=True):
                try:
                    with conn.cursor() as cur:
                        # QUERY ADAPTADA: Inserta directo a 'ofertas' mapeando id_producto, id_campana e id_super
                        # Evita duplicados gracias al ON CONFLICT con tu restricción única
                        query = """
                            INSERT INTO public.ofertas (id_campana, id_super, id_producto, precio_oferta)
                            SELECT %s, %s, id_producto_real, 0.0
                            FROM public.pack_componentes 
                            WHERE id_pack = %s
                            ON CONFLICT ON CONSTRAINT unique_producto_super_campana DO NOTHING;
                        """
                        cur.execute(query, (campana_id, id_super_asociado, pack_id))
                        filas_insertadas = cur.rowcount
                    
                    conn.commit()
                    if filas_insertadas > 0:
                        st.success(f"🎉 ¡Éxito! Se cargaron {filas_insertadas} productos automáticamente a la tabla de ofertas.")
                    else:
                        st.info("ℹ️ Los productos de este pack ya se encontraban asignados a esta campaña anteriormente.")
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error en la carga masiva: {e}")

    # ---------------------------------------------------------
    # OPCIÓN 2: ADMINISTRADOR DE PACKS (CREACIÓN)
    # ---------------------------------------------------------
    elif opcion == "⚙️ Crear / Gestionar Packs":
        st.title("⚙️ Maestro de Agrupaciones (Packs)")
        st.subheader("Define las plantillas de productos que se repiten con frecuencia")
        st.divider()

        productos_reales = obtener_productos_reales(conn)

        with st.form("form_nuevo_pack", clear_on_submit=True):
            st.markdown("### 🆕 Crear Nueva Agrupación")
            
            # Como tu id_producto es BIGINT PRIMARY KEY, pedimos un ID numérico único para el Pack
            id_pack_nuevo = st.number_input("Asigna un ID único numérico para el Pack (Ej: 90001):", min_value=1, step=1)
            nombre_pack = st.text_input("Nombre de la Agrupación (Ej: Pack Fideos + Salsa):")
            
            seleccionados = st.multiselect(
                "Selecciona los productos individuales que se cargarán juntos:",
                options=[p['id_producto'] for p in productos_reales],
                format_func=lambda x: next(f"{p['nombre']} ({p['marca']} - {p['tamano']} {p['unidad']})" for p in productos_reales if p['id_producto'] == x)
            )

            if st.form_submit_button("Guardar Pack Estático"):
                if not nombre_pack or len(seleccionados) < 2:
                    st.error("❌ Completa el nombre y selecciona al menos 2 productos para agrupar.")
                else:
                    try:
                        with conn.cursor() as cur:
                            # 1. Insertar el Pack en la tabla madre de productos con es_pack = True
                            cur.execute("""
                                INSERT INTO public.productos (id_producto, nombre, es_pack) 
                                VALUES (%s, %s, TRUE);
                            """, (id_pack_nuevo, nombre_pack))
                            
                            # 2. Insertar los componentes individuales en la tabla relacional
                            for prod_id in seleccionados:
                                cur.execute("""
                                    INSERT INTO public.pack_componentes (id_pack, id_producto_real, cantidad) 
                                    VALUES (%s, %s, 1);
                                """, (id_pack_nuevo, prod_id))
                                
                        conn.commit()
                        st.success(f"✨ El pack '{nombre_pack}' ha sido creado exitosamente con {len(seleccionados)} productos.")
                        st.rerun()
                    except psycopg2.errors.UniqueViolation:
                        conn.rollback()
                        st.error("❌ El ID numérico asignado al Pack ya existe en la tabla de productos. Usa uno diferente.")
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error al guardar en Neon: {e}")

    conn.close()
