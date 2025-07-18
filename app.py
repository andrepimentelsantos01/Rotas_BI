import streamlit as st
import pandas as pd
import folium
import requests
from concurrent.futures import ThreadPoolExecutor
from streamlit_folium import st_folium
from geopy.distance import geodesic

def limpar_coordenada(valor):
    return pd.to_numeric(str(valor).strip().replace(',', '.').replace(' ', '').replace('\xa0', ''), errors='coerce')

@st.cache_data
def carregar_dados(path):
    df = pd.read_excel(path, sheet_name='Custo')
    for coluna in ['Origem_Lat', 'Origem_Lon', 'Destino_Lat', 'Destino_Lon']:
        df[coluna] = df[coluna].map(limpar_coordenada)
    return df.dropna(subset=['Origem_Lat', 'Origem_Lon', 'Destino_Lat', 'Destino_Lon'])

df_custo = carregar_dados('Dataset_Rotas_BI.xlsx')

st.title("📍 Gerador de Rotas Rodoviárias")

cds = df_custo['CD'].dropna().unique().tolist()
cd_selecionado = st.selectbox("Selecione o CD (Origem):", cds)

df_filtrado_cd = df_custo[df_custo['CD'] == cd_selecionado]

grupos = ['Todos'] + df_filtrado_cd['Agrupamento'].dropna().unique().tolist()
grupo_selecionado = st.selectbox("Selecione o Agrupamento:", grupos)

if grupo_selecionado == 'Todos':
    clientes = df_filtrado_cd['Cliente'].dropna().unique().tolist()
    clientes_selecionados = st.multiselect("Selecione os Clientes:", clientes)
else:
    clientes_selecionados = df_filtrado_cd[df_filtrado_cd['Agrupamento'] == grupo_selecionado]['Cliente'].dropna().tolist()
    st.info(f"Clientes do grupo **{grupo_selecionado}** selecionados automaticamente.")

veiculos = df_filtrado_cd['Veículo'].dropna().unique().tolist()
veiculo_selecionado = st.selectbox("Selecione o Veículo:", veiculos)

tipo_rota = st.selectbox("Tipo de Roteirização:", ['/route', '/trip'])

def requisitar_rota(origem_lat, origem_lon, destino_lat, destino_lon):
    url = f"http://router.project-osrm.org/route/v1/driving/{origem_lon},{origem_lat};{destino_lon},{destino_lat}?overview=full&geometries=geojson"
    try:
        resp = requests.get(url, timeout=15)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None

def gerar_mapa(lista_clientes, veiculo, tipo_rota):
    df_filtrado = df_filtrado_cd[df_filtrado_cd['Cliente'].isin(lista_clientes)]
    linha_veiculo = df_filtrado_cd[df_filtrado_cd['Veículo'] == veiculo].iloc[0]
    consumo_kml, preco_combustivel = linha_veiculo['Consumo KM/L'], linha_veiculo['Custo Combustível']

    centro_lat = pd.concat([df_filtrado['Origem_Lat'], df_filtrado['Destino_Lat']]).mean()
    centro_lon = pd.concat([df_filtrado['Origem_Lon'], df_filtrado['Destino_Lon']]).mean()

    m = folium.Map(location=[centro_lat, centro_lon], zoom_start=8, tiles='OpenStreetMap')

    total_custo = total_tempo = total_litros = total_distancia = 0

    origem_lat = df_filtrado.iloc[0]['Origem_Lat']
    origem_lon = df_filtrado.iloc[0]['Origem_Lon']
    origem_coord = (origem_lat, origem_lon)

    folium.Marker(
        [origem_lat, origem_lon],
        popup=f"""<div style='font-size:12px; width:300px;'><strong>Origem:</strong> {df_filtrado.iloc[0]['Origem']}<br><strong>CD:</strong> {df_filtrado.iloc[0]['CD']}</div>""",
        tooltip=f"{df_filtrado.iloc[0]['CD']} - Origem",
        icon=folium.Icon(color='green')
    ).add_to(m)

    if tipo_rota == '/trip':
        df_filtrado = df_filtrado.copy()
        df_filtrado['Distancia_CD_km'] = df_filtrado.apply(
            lambda row: geodesic(origem_coord, (row['Destino_Lat'], row['Destino_Lon'])).km, axis=1
        )
        df_filtrado = df_filtrado.sort_values(by='Distancia_CD_km').reset_index(drop=True)

    cores = ['purple', 'blue', 'orange', 'green', 'darkred', 'cadetblue']

    if tipo_rota == '/route':
        with ThreadPoolExecutor(max_workers=10) as executor:
            rotas = list(executor.map(
                lambda linha: requisitar_rota(linha.Origem_Lat, linha.Origem_Lon, linha.Destino_Lat, linha.Destino_Lon),
                df_filtrado.itertuples()
            ))

        for idx, (linha, rota) in enumerate(zip(df_filtrado.itertuples(), rotas)):
            origem = (linha.Origem_Lat, linha.Origem_Lon)
            destino = (linha.Destino_Lat, linha.Destino_Lon)
            cliente = linha.Cliente

            if rota:
                rota_data = rota['routes'][0]
                coords = [[lat, lon] for lon, lat in rota_data['geometry']['coordinates']]
                distancia_km = rota_data['distance']/1000
                tempo_min = rota_data['duration']/60
                litros = distancia_km/consumo_kml
                custo = litros*preco_combustivel

                total_distancia += distancia_km
                total_custo += custo
                total_tempo += tempo_min
                total_litros += litros

                folium.PolyLine(coords, color=cores[idx % len(cores)], weight=5,
                                tooltip=f"{cliente}: {distancia_km:.1f} km").add_to(m)

                folium.Marker(
                    [destino[0], destino[1]],
                    popup=f"""<div style='font-size:12px; width:300px;'><strong>Cliente:</strong> {cliente}<br><strong>Distância:</strong> {distancia_km:.1f} km<br><strong>Tempo:</strong> {tempo_min:.0f} min<br><strong>Consumo:</strong> {litros:.2f} L<br><strong>Custo:</strong> R$ {custo:.2f}</div>""",
                    tooltip=f"{cliente} - Destino",
                    icon=folium.Icon(color='red')
                ).add_to(m)

            else:
                folium.Marker(
                    [destino[0], destino[1]],
                    popup=f"""<div style='font-size:12px;width:200px;'>❗ Falha OSRM para {cliente}</div>""",
                    icon=folium.Icon(color='gray')
                ).add_to(m)

    else:  # /trip sequencial
        origem_lat_atual, origem_lon_atual = origem_lat, origem_lon
        for idx, linha in enumerate(df_filtrado.itertuples()):
            destino_lat = linha.Destino_Lat
            destino_lon = linha.Destino_Lon
            cliente = linha.Cliente

            rota = requisitar_rota(origem_lat_atual, origem_lon_atual, destino_lat, destino_lon)

            if rota and rota.get('routes'):
                rota_data = rota['routes'][0]
                coords = [[lat, lon] for lon, lat in rota_data['geometry']['coordinates']]
                distancia_km = rota_data['distance']/1000
                tempo_min = rota_data['duration']/60
                litros = distancia_km/consumo_kml
                custo = litros*preco_combustivel

                total_distancia += distancia_km
                total_custo += custo
                total_tempo += tempo_min
                total_litros += litros

                folium.PolyLine(coords, color=cores[idx % len(cores)], weight=5,
                                tooltip=f"{cliente}: {distancia_km:.1f} km").add_to(m)

                folium.Marker(
                    [destino_lat, destino_lon],
                    popup=f"""<div style='font-size:12px; width:300px;'><strong>Cliente:</strong> {cliente}<br><strong>Distância:</strong> {distancia_km:.1f} km<br><strong>Tempo:</strong> {tempo_min:.0f} min<br><strong>Consumo:</strong> {litros:.2f} L<br><strong>Custo:</strong> R$ {custo:.2f}</div>""",
                    tooltip=f"{cliente} - Destino",
                    icon=folium.Icon(color='red')
                ).add_to(m)

                origem_lat_atual, origem_lon_atual = destino_lat, destino_lon

    folium.Marker(
        [centro_lat, centro_lon],
        popup=f"""<div style='font-size:12px; width:300px;'><strong>Custo Total:</strong> R$ {total_custo:.2f}<br><strong>Tempo Total:</strong> {total_tempo:.0f} min<br><strong>Litros:</strong> {total_litros:.2f} L<br><strong>Distância:</strong> {total_distancia:.2f} km</div>""",
        icon=folium.Icon(color='darkpurple', icon='usd', prefix='fa')
    ).add_to(m)

    st.markdown(f"### 📊 Resultados Gerais:\n- Rotas selecionadas: {len(df_filtrado)}\n- Distância Total: {total_distancia:.2f} km\n- Custo Total: R$ {total_custo:.2f}\n- Tempo Total: {total_tempo:.0f} min\n- Consumo Total: {total_litros:.2f} L")

    if tipo_rota == '/trip':
        st.markdown("### 📋 Ordem das Entregas (Mais Próximo → Mais Distante):")
        for idx, linha in enumerate(df_filtrado.itertuples(), 1):
            st.markdown(f"{idx}. {linha.Cliente} - {linha.Distancia_CD_km:.1f} km")

    return m

if st.button("🚛 Gerar Mapa"):
    if not clientes_selecionados:
        st.warning("Selecione ao menos um cliente!")
    else:
        with st.spinner('Gerando mapa...'):
            mapa = gerar_mapa(clientes_selecionados, veiculo_selecionado, tipo_rota)
            st.success("Mapa gerado com sucesso!")
            st_folium(mapa, width=725, height=500, returned_objects=[], key="mapa_rotas")
