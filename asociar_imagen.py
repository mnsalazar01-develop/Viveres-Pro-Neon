    # === MODALIDAD 2: INYECTOR MASIVO DESDE LA COMPUTADORA ===
    elif opcion_metodo == "Asociar a imagen existente en el álbum":
        st.write("🚀 **Inyector Masivo Automático (Sáltate la web de ImgBB)**")
        st.info("💡 Olvídate de la página de ImgBB. Arrastra aquí todas las fotos de tus productos juntas. El sistema las subirá automáticamente a internet, buscará a qué producto pertenecen y las guardará en Neon.")

        # Permitir seleccionar múltiples archivos locales a la vez
        archivos_locales = st.file_uploader(
            "Selecciona o arrastra múltiples imágenes de productos:", 
            type=["jpg", "jpeg", "png", "webp"], 
            accept_multiple_files=True
        )

        umbral_confianza = st.slider("Ajustar nivel de precisión mínimo (%)", min_value=50, max_value=100, value=75, step=5, key="slider_masivo")
        umbral_decimal = umbral_confianza / 100.0

        if archivos_locales:
            st.success(f"📦 Has cargado **{len(archivos_locales)}** imágenes en la cola de procesamiento.")
            
            if st.button("🔥 Iniciar Procesamiento e Inyección Masiva", type="primary", use_container_width=True):
                progreso = st.progress(0)
                contador_exitos = 0
                
                # Obtener el catálogo de productos actualizado en memoria
                lista_productos = obtener_lista_productos()
                
                for index, archivo in enumerate(archivos_locales):
                    nombre_archivo_limpio = limpiar_texto(archivo.name)
                    palabras_img = set(nombre_archivo_limpio.split())
                    
                    mejor_similitud = 0.0
                    producto_asociado = None
                    
                    # 1. Buscar de manera inteligente a qué producto de Neon pertenece esta foto
                    for prod in lista_productos:
                        componentes = [
                            str(prod["nombre"] or ""),
                            str(prod["marca"] or ""),
                            str(prod["tamano"] or ""),
                            str(prod["unidad"] or "")
                        ]
                        id_completa_prod = " ".join([c.strip() for c in componentes if c.strip()])
                        prod_limpio = limpiar_texto(id_completa_prod)
                        palabras_producto = set(prod_limpio.split())
                        
                        # FILTRO CRUCIAL: Evitar café vs carne molida
                        if not palabras_producto.intersection(palabras_img):
                            continue
                            
                        similitud = SequenceMatcher(None, prod_limpio, nombre_archivo_limpio).ratio()
                        if similitud > mejor_similitud:
                            mejor_similitud = similitud
                            producto_asociado = prod
                    
                    # 2. Si pasa el umbral de confianza, la subimos a ImgBB y la guardamos en Neon
                    if mejor_similitud >= umbral_decimal and producto_asociado:
                        componentes_asoc = [
                            str(producto_asociado["nombre"] or ""),
                            str(producto_asociado["marca"] or ""),
                            str(producto_asociado["tamano"] or ""),
                            str(producto_asociado["unidad"] or "")
                        ]
                        nombre_final_prod = " ".join([c.strip() for c in componentes_asoc if c.strip()])
                        
                        st.write(f"🔄 Procesando: `{archivo.name}` ➡️ Asociado a `{nombre_final_prod}` ({mejor_similitud*100:.1f}%)")
                        
                        # Subir archivo directamente a la API de ImgBB usando sus bytes
                        url_nueva_imgbb = subir_imagen_a_album(archivo.getvalue(), nombre_final_prod)
                        
                        if url_nueva_imgbb:
                            # Guardar en Neon
                            if guardar_url_en_neon(producto_asociado["id_producto"], url_nueva_imgbb):
                                contador_exitos += 1
                    else:
                        st.warning(f"⚠️ Saltado: `{archivo.name}` no encontró un producto compatible en la base de datos con suficiente confianza.")
                    
                    # Actualizar barra de progreso de la interfaz
                    progreso.progress((index + 1) / len(archivos_locales))
                
                st.success(f"🎉 ¡Proceso terminado! Se subieron y asociaron con éxito **{contador_exitos}** de **{len(archivos_locales)}** imágenes en Neon.")
                st.balloons()
