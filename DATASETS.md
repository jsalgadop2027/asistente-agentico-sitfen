# 📊 DATASETS.md — Catálogo de datos y fuentes

**Proyecto:** Chatbot Agéntico RAG — Arándano Peruano (Capstone Project II, UTEC)
**Última actualización:** 2026-07-27
**Versión Excel:** [`DATASETS.xlsx`](DATASETS.xlsx)

Este documento cataloga (a) los **datasets y fuentes que la solución ya consume** y
(b) los **datasets recomendados** para dar mayor sustento cuantitativo y analítico al
chatbot. Sirve como evidencia de trazabilidad de datos para la evaluación del Capstone
y como hoja de ruta de ampliación del corpus.

**Leyenda de estado:**
- 🟢 **Usado** — ya integrado en la solución (corpus RAG, evaluación o tools).
- 🔵 **Recomendado** — propuesto para fortalecer la solución.

---

## 1. Datasets / fuentes ya usadas 🟢

### 1.1 Corpus documental RAG (199 PDFs → Firestore Vector Search)

Base de conocimiento principal del RAG. Ingerida vía `ingestion/` (PDF → chunks →
embeddings `text-multilingual-embedding-002` → Firestore KNN).

#### a) Comercio y exportación
| Documento | Entidad / Fuente | Tema |
|---|---|---|
| Documentos-necesarios-exportar-2023.pdf | PROMPERÚ / MINCETUR | Requisitos documentales de exportación |
| Guia_practica_del_exportador.pdf | PROMPERÚ | Proceso de exportación paso a paso |
| Manual-de-exportaciones-con-SIAG.pdf | SENASA | Sistema Integrado de Gestión Agraria |
| IRC-PROMPERU-2024-II.pdf | PROMPERÚ | Informe de Requisitos Comerciales 2024-II |
| Peru-Super-Foods.pdf | PROMPERÚ | Posicionamiento de marca / superalimentos |
| Tarifario_versión_recortada.pdf | Operador logístico | Costos / tarifas |
| Exportación de arándano peruano.pdf | Sector | Panorama exportador del arándano |
| Documentos para exportar (Ficha-Producto-Arandano.pdf) | PROMPERÚ | Ficha técnica comercial del producto |

#### b) Agronomía, inocuidad y normativa
| Documento | Entidad / Fuente | Tema |
|---|---|---|
| GUIA-DE-BUENAS-PRACTICAS-AGRICOLAS.pdf | SENASA | Buenas Prácticas Agrícolas (BPA) |
| Manejo agronómico del cultivo de arándano.pdf | Técnico / academia | Manejo del cultivo |
| Rgto.-Certif.-y-Fiscaliz.-Producc.-Orgánica-II.pdf | SENASA | Reglamento de producción orgánica |
| Protocolo arándano - China.pdf | SENASA / GACC | Protocolo fitosanitario Perú–China |

#### c) Mercado, competitividad y sostenibilidad
| Documento | Entidad / Fuente | Tema |
|---|---|---|
| Los-arandanos-en-el-Peru.pdf | Sector / gremio | Panorama del arándano en Perú |
| Opertunidades-y-retos-en-la-exportación-de-arándanos.pdf | Sector | Oportunidades y retos |
| RELACIÓN-CADENA-DE-SUMINISTRO-Y-LA-COMPETITIVIDAD.pdf | Académico | Cadena de suministro y competitividad |
| MLPE_Research-Arandanos.pdf | Research / consultora | Análisis de mercado |
| Reporte-de-Campana-.pdf | Gremio (p.ej. ProArándanos) | Reporte de campaña |
| IB_Sostenibilidad.pdf | Sector | Sostenibilidad |
| Reporte-de-inflacion-diciembre-2025.pdf | BCRP | Contexto macroeconómico |

#### d) Serie climática ENFEN (98 informes técnicos, 2020–2026)
Serie temporal mensual del **Comité Multisectorial ENFEN** (El Niño / La Niña),
clave para correlacionar variabilidad climática con campañas del arándano.

| Año | Nº de informes |
|---|---|
| 2020 | 13 |
| 2021 | 12 |
| 2022 | 12 |
| 2023 | 20 |
| 2024 | 15 |
| 2025 | 14 |
| 2026 | 12 |
| **Total** | **98** |

> El detalle **archivo por archivo** de los 98 informes ENFEN (con mes/periodo
> identificado) está en la hoja **«Corpus ENFEN»** de [`DATASETS.xlsx`](DATASETS.xlsx).

#### e) Economía y política pública del FEN (31 PDFs — `corpus_documental/economia_fen/`)
| Subgrupo | Nº | Documentos representativos | Entidad / Fuente |
|---|---|---|---|
| Impacto macroeconómico y financiero | 12 | BCRP_RI_jun2023_recuadro1, BCRP_DT007_2024_morosidad_agroexportador, BCRP_Reporte_Estabilidad_Financiera_may2024/may2025, APE_WP97_Impacto_FEN_agroexportaciones, KPMG_Riesgo_cambiario, arXiv_consumer_behavior_El_Nino_2017 | BCRP, APESEG, KPMG, ULima, arXiv |
| Gestión de riesgo de desastres y reconstrucción | 12 | PIRC_Plan_Integral_Reconstruccion_2017, INDECI_Compendio_estadistico_2017, Defensoria_Informe178/005, OSITRAN_Resiliencia_carreteras, CAF_Lecciones_El_Nino_1997_1998 | PIRC, INDECI, Defensoría, OSITRAN, INGEMMET, JICA, CAF, ENFEN |
| Sector agrario frente al FEN | 4 | MIDAGRI_Exportaciones_agrarias_2023, MIDAGRI_Informe5_Nino_costero_campanas, BID_ENESA_Programa_riesgo_agropecuario, APESEG_Fichas_seguro_agrario | MIDAGRI, BID, APESEG |
| Cambio climático / política ambiental | 2 | MINAM_Dossier_El_Nino, MINAM_SINIA_Cambio_climatico_norte | MINAM |
| Política fiscal | 1 | Congreso_Beneficios_incentivos_tributarios | Congreso de la República |

#### f) Agroexportación multi-cultivo del norte (22 PDFs — `corpus_documental/agroexportacion_norte/`)
Mango, palta, uva y espárrago — amplía el corpus más allá del arándano.
| Subgrupo | Nº | Documentos representativos | Entidad / Fuente |
|---|---|---|---|
| Certificación fitosanitaria y procedimientos | 8 | SENASA_Certificacion_Fitosanitaria_Mango/Palto_Hass/Uva_Fresca, SENASA_Procedimiento_Integrado_Exportacion_Vegetal, Exportemos_Requisitos_Fitosanitarios_2023 | SENASA, OPIP, Exportemos |
| Inteligencia de mercado PROMPERÚ | 6 | Ficha_Mercado_Palta_feb2025, Ficha_Mercado_Mango_abr2024, Informe_Mercado_Arandanos_EEUU | PROMPERÚ |
| Estadísticas y coyuntura de comercio exterior | 4 | ADEX_CIEN_Exportacion_Organicos_dic2025, ADEX_CIEN_Reporte_Exportaciones_dic2025, BCRP_Reporte_Inflacion_jun2026 | ADEX, BCRP |
| Competitividad, logística y sostenibilidad | 4 | Camposol_Reporte_Sostenibilidad_2024, LACCEI_2025_competitiveness, CEPAL_Negocio_esparrago | Camposol, LACCEI, CEPAL |

#### g) Agronomía, gestión hídrica y marco normativo/financiero complementario (7 PDFs — `corpus_documental/agronomia_hidrica_norte/`)
| Documento | Entidad / Fuente | Tema |
|---|---|---|
| BlueberriesConsulting_Manejo_Integrado_Plagas_Enfermedades_Arandano.pdf | Blueberries Consulting | MIP / plagas y enfermedades del arándano |
| BlueberriesConsulting_Manejo_Cosecha_Poscosecha_Arandano.pdf | Blueberries Consulting | Poscosecha y calidad |
| ANA_Politica_Estrategia_Nacional_Recursos_Hidricos.pdf | Autoridad Nacional del Agua | Gestión hídrica nacional |
| PREDES_Manual_Riego_por_Goteo.pdf | PREDES | Riego tecnificado |
| Congreso_Ley32434_Transformacion_Sector_Agrario_2025.pdf | Congreso de la República | Marco legal agrario vigente (set-2025) |
| PropuestaCiudadana_FAEAGRO_problema_financiamiento.pdf | Propuesta Ciudadana | Financiamiento MYPE agrario |
| CEPES_PropuestaCiudadana_Asociatividad_Agricultura_Familiar_Ley31335.pdf | CEPES / Propuesta Ciudadana | Asociatividad y cooperativismo |

#### h) Estudios complementarios de balance (22 PDFs — `corpus_documental/estudios_complementarios/`)
| Subgrupo | Nº | Documentos representativos | Entidad / Fuente |
|---|---|---|---|
| Tesis universitarias sobre exportación de arándano | 5 | UCSM_Tesis_Comparativo, ULaSalle_Zavalaga_Tesis, UAP_Tesis_Proyecto_Exportacion | UCSM, ULaSalle, UAP |
| Normativa SENASA | 2 | SENASA_DS016_Reglamento_Plaguicidas, SENASA_Manual_Vigilancia_Moscas_Fruta | SENASA |
| Certificaciones internacionales | 2 | GlobalGAP_Reglamento_General_v6, RainforestAlliance_Estandar_2020 | GlobalGAP, Rainforest Alliance |
| Sostenibilidad corporativa | 2 | Camposol_Reporte_Sostenibilidad_2023, Hortifrut_Reporte_Sostenibilidad_2021 | Camposol, Hortifrut |
| Mercados nuevos | 1 | Exportemos_Guia_Mercado_HongKong | Exportemos / PROMPERÚ |
| Género, empleo y consumo | 4 | CEPES_Mujeres_en_la_Agricultura_2024, MinCultura_Agroexportacion_Empleo_Genero, Datum_Tendencias_Consumo_2024, Ipsos_El_Consumidor_2024 | CEPES, Min. Cultura, Datum, Ipsos |
| Gestión hídrica | 1 | ANA_Plan_Gestion_Recursos_Hidricos_Cuenca_Chira_Piura | ANA |
| Macroeconomía regional | 4 | BCRP_Sintesis_Actividad_Economica_Lambayeque, WorldBank_CCDR_Peru_2022, BBVA_Research_El_Nino_LatinAmerica_2026, MINCETUR_PENX_2025 | BCRP, Banco Mundial, BBVA, MINCETUR |

### 1.2 Dataset de evaluación (golden dataset)
| Recurso | Ubicación | Descripción |
|---|---|---|
| Golden dataset (1000) | [`evaluation/golden_dataset_1000.jsonl`](evaluation/golden_dataset_1000.jsonl) | 1000 pares `question` / `ground_truth` (649 de informes ENFEN + 359 de documentos temáticos), dataset por defecto de RAGAS + DeepEval (juez Gemini). Versión con `category`/`source_document` en [`evaluation/golden_dataset_1000.xlsx`](evaluation/golden_dataset_1000.xlsx). |
| Muestra estratificada (150) | [`evaluation/build_eval_sample.py`](evaluation/build_eval_sample.py) → `evaluation/eval_sample_150.jsonl` | Muestra estratificada por categoría del dataset de 1000, para comparaciones antes/después sin correr las 1000 preguntas completas. |
| Golden dataset (smoke) | [`evaluation/golden_dataset.jsonl`](evaluation/golden_dataset.jsonl) | 8 pares curados; smoke test rápido/barato vía `EVAL_DATASET=golden_dataset.jsonl`. |

### 1.3 Datos en tiempo real vía tools
| Fuente | Integración | Descripción |
|---|---|---|
| Datos meteorológicos (clima) | [`app/agent/tools/weather_tools.py`](app/agent/tools/weather_tools.py) | Tool de clima del agente (dato en vivo, no estático). |

---

## 2. Datasets recomendados 🔵

Para complementar un corpus mayormente textual con **datos estructurados** que habiliten
respuestas cuantitativas (volúmenes, precios, series).

### 2.1 Comercio y precios (alto impacto)
| Dataset | Fuente | Formato | Aporte |
|---|---|---|---|
| Exportaciones partida 0810.40 (arándano) | SUNAT – Aduanas / Datos Abiertos Perú | CSV / API | Volúmenes, FOB, destinos y empresas exportadoras (Perú) |
| Estadísticas de exportación por producto | SIICEX / PROMPERÚ | Web / XLS | Series por mercado de destino |
| Comercio mundial HS 081040 | UN Comtrade | API / CSV | Competidores (Chile, México), precios unitarios |
| Cuotas de mercado y aranceles | ITC Trade Map | Web / XLS | Participación de mercado y tendencias |
| Producción/superficie/rendimiento mundial | FAOSTAT | CSV / API | Serie histórica internacional |

### 2.2 Producción y agronomía nacional
| Dataset | Fuente | Formato | Aporte |
|---|---|---|---|
| Estadística agraria (SIEA) | MIDAGRI | CSV / XLS | Superficie, producción y rendimiento por región |
| Registro de lugares de producción / empacadoras | SENASA | Web / PDF | Trazabilidad fitosanitaria |
| Censo / encuestas agropecuarias | INEI | CSV | Estructura del sector |

### 2.3 Clima y macro (complementa ENFEN)
| Dataset | Fuente | Formato | Aporte |
|---|---|---|---|
| Datos climáticos históricos por estación | SENAMHI | CSV | Clima en zonas productoras (La Libertad, Lambayeque, Lima, Ica) |
| Índice ENSO (ONI) | NOAA / IMARPE | CSV | Serie numérica de El Niño / La Niña |
| Series macro (tipo de cambio, inflación) | BCRP | API / CSV | Contexto económico |
| Clima agroclimático por coordenadas | Open-Meteo / NASA POWER | API | Alineado con la tool de clima existente |

### 2.4 Refuerzo de evaluación y guardrails
| Dataset | Fuente | Aporte |
|---|---|---|
| Golden dataset ampliado (50–100 preguntas, por categoría) | Propio | Mejor cobertura de RAGAS/DeepEval |
| MIRACL (retrieval multilingüe, incluye ES) | Hugging Face | Benchmark de recuperación |
| XQuAD / MLQA (QA en español) | Hugging Face | Benchmark de QA |
| Sets de prompt-injection (Garak / PINT) | Open source | Validación de guardrails anti-inyección |

---

## 3. Buenas prácticas de gobernanza de datos

- **Trazabilidad:** registrar por documento fuente, fecha de descarga, licencia y nº de chunks.
- **Licencias:** verificar términos de uso de fuentes oficiales antes de redistribuir.
- **Versionado:** mantener este catálogo sincronizado con cada actualización del corpus
  (Admin UI registra altas por hash SHA-256).
- **Cumplimiento (Ley 29733 / GDPR):** los datasets recomendados son agregados/no personales;
  evitar ingestar datos con PII.
