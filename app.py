import streamlit as st
import pandas as pd
import folium
import requests
from concurrent.futures import ThreadPoolExecutor
from streamlit_folium import st_folium
from geopy.distance import geodesic

st.set_page_config(page_title="Gerador de Rotas", layout="wide")

# --------------------------
# Utilidades e carregamento
# --------------------------
def limpar_coordenada(valor):
    return pd.to_numeric(
        str(valor).strip().replace(',', '.').replace(' ', '').replace('\xa0', ''),
        errors='coerce'
    )

@st.cache_data
def carregar_raw(path):  # base crua (para CDs/origens)
    df = pd.read_excel(path, sheet_name='Custo')
    for c in ['Origem_Lat', 'Origem_Lon', 'Destino_Lat', 'Destino_Lon']:
        df[c] = df[c].map(limpar_coordenada)
    return df

@st.cache_data
def carregar_dados(path):  # base filtrada (destinos/veículos válidos)
    df = pd.read_excel(path, sheet_name='Custo')
    for c in ['Origem_Lat', 'Origem_Lon', 'Destino_Lat', 'Destino_Lon']:
        df[c] = df[c].map(limpar_coordenada)
    return df.dropna(subset=['Origem_Lat', 'Origem_Lon', 'Destino_Lat', 'Destino_Lon'])

df_raw   = carregar_raw('Dataset_Rotas_BI.xlsx')      # CDs/origens
df_custo = carregar_dados('Dataset_Rotas_BI.xlsx')    # clientes/destinos + veículos

st.title("📍 Gerador de Rotas Rodoviárias")

# --------------------------
# Filtros (independentes)
# --------------------------
# CD: origem independente
cds = sorted(df_raw['CD'].dropna().unique().tolist())
cd_selecionado = st.selectbox("Selecione o CD (Origem):", cds)

# lookup da origem do CD
df_cd = df_raw[(df_raw['CD'] == cd_selecionado) & df_raw['Origem_Lat'].notna() & df_raw['Origem_Lon'].notna()]
if df_cd.empty:
    st.error(f"CD '{cd_selecionado}' sem coordenadas de origem na planilha.")
    st.stop()

origem_lat = float(df_cd.iloc[0]['Origem_Lat'])
origem_lon = float(df_cd.iloc[0]['Origem_Lon'])
origem_end = str(df_cd.iloc[0].get('Origem', cd_selecionado))

# Agrupamentos: globais (não dependem do CD)
grupos = ['Todos'] + sorted(df_custo['Agrupamento'].dropna().unique().tolist())
grupo_selecionado = st.selectbox("Selecione o Agrupamento:", grupos)

# Clientes: independentes do CD
if grupo_selecionado == 'Todos':
    clientes = sorted(df_custo['Cliente'].dropna().unique().tolist())
    clientes_selecionados = st.multiselect("Selecione os Clientes:", clientes)
else:
    clientes_selecionados = sorted(
        df_custo.loc[df_custo['Agrupamento'] == grupo_selecionado, 'Cliente'].dropna().unique().tolist()
    )
    st.info(f"Clientes do grupo **{grupo_selecionado}** selecionados automaticamente.")

# Veículos: independentes (como já era)
veiculos = sorted(df_custo['Veículo'].dropna().unique().tolist())
veiculo_selecionado = st.selectbox("Selecione o Veículo:", veiculos)

tipo_rota = st.selectbox("Tipo de Roteirização:", ['/route', '/trip'])

# --------------------------
# OSRM
# --------------------------
def requisitar_rota(origem_lat, origem_lon, destino_lat, destino_lon):
    # OSRM espera lon,lat
    url = f"http://router.project-osrm.org/route/v1/driving/{origem_lon},{origem_lat};{destino_lon},{destino_lat}?overview=full&geometries=geojson"
    try:
        resp = requests.get(url, timeout=15)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None

# --------------------------
# Mapa
# --------------------------
def gerar_mapa(cd, lista_clientes, veiculo, tipo_rota):
    # Destinos (somente clientes selecionados)
    df_dest = df_custo[df_custo['Cliente'].isin(lista_clientes)][
        ['Cliente', 'Destino', 'Destino_Lat', 'Destino_Lon']
    ].copy()

    if df_dest.empty:
        st.warning("Nenhum cliente válido selecionado (com coordenadas de destino).")
        st.stop()

    # Veículo (consumo/custos)
    linha_veiculo = df_custo[df_custo['Veículo'] == veiculo]
    if linha_veiculo.empty:
        st.error(f"⚠️ O veículo '{veiculo}' não foi encontrado na planilha com métricas.")
        st.stop()

    linha_veiculo = linha_veiculo.iloc[0]
    consumo_kml = float(linha_veiculo['Consumo KM/L'])
    preco_combustivel = float(linha_veiculo['Custo Combustível'])
    capacidade_carga_m3 = float(linha_veiculo['Capacidade de Carga m3'])

    # mapa
    centro_lat, centro_lon = origem_lat, origem_lon
    m = folium.Map(location=[centro_lat, centro_lon], zoom_start=10, tiles='OpenStreetMap')

    # ---------- AJUSTE 1: ORIGEM VERDE + CD/ENDEREÇO ----------
    folium.Marker(
        [origem_lat, origem_lon],
        popup=(
            f"<div style='font-size:12px; width:320px;'>"
            f"<strong>CD:</strong> {cd}<br>"
            f"<strong>Endereço:</strong> {origem_end}<br>"
            f"<strong>Lat/Lon:</strong> {origem_lat:.6f}, {origem_lon:.6f}</div>"
        ),
        tooltip=f"CD: {cd}",
        icon=folium.Icon(color='green', icon='home', prefix='fa')
    ).add_to(m)

    total_custo = total_tempo = total_litros = total_distancia = 0.0
    cores = ['purple', 'blue', 'orange', 'green', 'darkred', 'cadetblue']

    # ---------- AJUSTE 2: AUTO-ZOOM (bounds) ----------
    bounds = [[origem_lat, origem_lon]]

    if tipo_rota == '/route':
        # Paraleliza: sempre origem = CD selecionado
        def _call(row):
            return requisitar_rota(origem_lat, origem_lon, float(row.Destino_Lat), float(row.Destino_Lon))

        with ThreadPoolExecutor(max_workers=10) as ex:
            rotas = list(ex.map(_call, df_dest.itertuples(index=False)))

        for idx, (row, rota) in enumerate(zip(df_dest.itertuples(index=False), rotas)):
            cliente = row.Cliente
            dest_lat = float(row.Destino_Lat)
            dest_lon = float(row.Destino_Lon)

            if rota and rota.get('routes'):
                rota_data = rota['routes'][0]
                coords = [[lat, lon] for lon, lat in rota_data['geometry']['coordinates']]
                distancia_km = rota_data['distance'] / 1000
                tempo_min = rota_data['duration'] / 60
                litros = distancia_km / consumo_kml
                custo = litros * preco_combustivel

                total_distancia += distancia_km
                total_custo += custo
                total_tempo += tempo_min
                total_litros += litros

                folium.PolyLine(
                    coords, color=cores[idx % len(cores)], weight=5,
                    tooltip=f"{cliente}: {distancia_km:.1f} km"
                ).add_to(m)

                folium.Marker(
                    [dest_lat, dest_lon],
                    popup=(
                        f"<div style='font-size:12px; width:300px;'>"
                        f"<strong>Cliente:</strong> {cliente}<br>"
                        f"<strong>Distância:</strong> {distancia_km:.1f} km<br>"
                        f"<strong>Tempo:</strong> {tempo_min:.0f} min<br>"
                        f"<strong>Consumo:</strong> {litros:.2f} L<br>"
                        f"<strong>Custo:</strong> R$ {custo:.2f}</div>"
                    ),
                    tooltip=f"{cliente} - Destino",
                    icon=folium.Icon(color='red')
                ).add_to(m)
            else:
                folium.Marker(
                    [dest_lat, dest_lon],
                    popup=f"<div style='font-size:12px;width:220px;'>❗ Falha OSRM para {cliente}</div>",
                    icon=folium.Icon(color='gray')
                ).add_to(m)

            # adiciona destino aos bounds
            bounds.append([dest_lat, dest_lon])

    else:
        # /trip: ordena por proximidade geodésica ao CD e faz perna a perna
        df_dest['Distancia_CD_km'] = df_dest.apply(
            lambda r: geodesic((origem_lat, origem_lon), (float(r['Destino_Lat']), float(r['Destino_Lon']))).km,
            axis=1
        )
        df_dest = df_dest.sort_values(by='Distancia_CD_km').reset_index(drop=True)

        o_lat, o_lon = origem_lat, origem_lon
        for idx, row in enumerate(df_dest.itertuples(index=False)):
            cliente = row.Cliente
            dest_lat = float(row.Destino_Lat)
            dest_lon = float(row.Destino_Lon)

            rota = requisitar_rota(o_lat, o_lon, dest_lat, dest_lon)
            if rota and rota.get('routes'):
                rota_data = rota['routes'][0]
                coords = [[lat, lon] for lon, lat in rota_data['geometry']['coordinates']]
                distancia_km = rota_data['distance'] / 1000
                tempo_min = rota_data['duration'] / 60
                litros = distancia_km / consumo_kml
                custo = litros * preco_combustivel

                total_distancia += distancia_km
                total_custo += custo
                total_tempo += tempo_min
                total_litros += litros

                folium.PolyLine(
                    coords, color=cores[idx % len(cores)], weight=5,
                    tooltip=f"{cliente}: {distancia_km:.1f} km"
                ).add_to(m)

                folium.Marker(
                    [dest_lat, dest_lon],
                    popup=(
                        f"<div style='font-size:12px; width:300px;'>"
                        f"<strong>Cliente:</strong> {cliente}<br>"
                        f"<strong>Distância:</strong> {distancia_km:.1f} km<br>"
                        f"<strong>Tempo:</strong> {tempo_min:.0f} min<br>"
                        f"<strong>Consumo:</strong> {litros:.2f} L<br>"
                        f"<strong>Custo:</strong> R$ {custo:.2f}</div>"
                    ),
                    tooltip=f"{cliente} - Destino",
                    icon=folium.Icon(color='red')
                ).add_to(m)

                # próxima perna parte deste destino
                o_lat, o_lon = dest_lat, dest_lon
            else:
                folium.Marker(
                    [dest_lat, dest_lon],
                    popup=f"<div style='font-size:12px;width:220px;'>❗ Falha OSRM para {cliente}</div>",
                    icon=folium.Icon(color='gray')
                ).add_to(m)

            # adiciona destino aos bounds
            bounds.append([dest_lat, dest_lon])

        # Lista de ordem (mais perto -> mais longe)
        st.markdown("### 📋 Ordem das Entregas (Mais Próximo → Mais Distante):")
        for idx, row in enumerate(df_dest.itertuples(index=False), 1):
            st.markdown(f"{idx}. {row.Cliente} - {row.Distancia_CD_km:.1f} km")

    # marcador de resumo (mantido)
    folium.Marker(
        [origem_lat, origem_lon],
        popup=(
            f"<div style='font-size:12px; width:300px;'>"
            f"<strong>Custo Total:</strong> R$ {total_custo:.2f}<br>"
            f"<strong>Tempo Total:</strong> {total_tempo:.0f} min<br>"
            f"<strong>Litros:</strong> {total_litros:.2f} L<br>"
            f"<strong>Distância:</strong> {total_distancia:.2f} km</div>"
        ),
        icon=folium.Icon(color='darkpurple', icon='usd', prefix='fa')
    ).add_to(m)

    # ---------- AJUSTE 2 (final): aplica o fit_bounds ----------
    if len(bounds) > 1:
        m.fit_bounds(bounds)

    # Painel resumo (mantido)
    st.markdown(f"""
### 📊 Resultados Gerais:
- CD (Origem): **{cd}**
- Endereço do CD: **{origem_end}**
- Veículo: **{veiculo}**
- Capacidade de Carga: **{capacidade_carga_m3:.1f} m³**
- Consumo: **{consumo_kml:.2f} km/l**
- Rotas selecionadas: {len(df_dest)}
- Distância Total: {total_distancia:.2f} km
- Custo Total: R$ {total_custo:.2f}
- Tempo Total: {total_tempo:.0f} min
- Consumo Total: {total_litros:.2f} L
""")

    return m

# --------------------------
# Ação
# --------------------------
if st.button("🚛 Gerar Mapa"):
    if not clientes_selecionados:
        st.warning("Selecione ao menos um cliente!")
    else:
        with st.spinner('Gerando mapa...'):
            mapa = gerar_mapa(cd_selecionado, clientes_selecionados, veiculo_selecionado, tipo_rota)
            st.success("Mapa gerado com sucesso!")
            st_folium(mapa, width=900, height=560, returned_objects=[], key="mapa_rotas")
