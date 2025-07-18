import streamlit as st
import pandas as pd
import folium
import requests
from concurrent.futures import ThreadPoolExecutor
from streamlit_folium import st_folium

# Funções auxiliares
def limpar_coordenada(valor):
    return pd.to_numeric(str(valor).strip().replace(',', '.').replace(' ', '').replace('\xa0', ''), errors='coerce')

@st.cache_data
def carregar_dados(path):
    df = pd.read_excel(path, sheet_name='Custo')
    for coluna in ['Origem_Lat', 'Origem_Lon', 'Destino_Lat', 'Destino_Lon']:
        df[coluna] = df[coluna].map(limpar_coordenada)
    return df.dropna(subset=['Origem_Lat', 'Origem_Lon', 'Destino_Lat', 'Destino_Lon'])

df_custo = carregar_dados('Dataset_Rotas_BI.xlsx')

# Interface Streamlit
st.title("📍 Gerador de Rotas Rodoviárias")

grupos = ['Todos'] + df_custo['Agrupamento'].dropna().unique().tolist()
grupo_selecionado = st.selectbox("Selecione o Agrupamento:", grupos)

if grupo_selecionado == 'Todos':
    clientes = df_custo['Cliente'].dropna().unique().tolist()
    clientes_selecionados = st.multiselect("Selecione os Clientes:", clientes, default=clientes[:3])
else:
    clientes_selecionados = df_custo[df_custo['Agrupamento'] == grupo_selecionado]['Cliente'].dropna().tolist()
    st.info(f"Clientes do grupo **{grupo_selecionado}** selecionados automaticamente.")

veiculos = df_custo['Veículo'].dropna().unique().tolist()
veiculo_selecionado = st.selectbox("Selecione o Veículo:", veiculos)

def requisitar_rota(origem_lat, origem_lon, destino_lat, destino_lon):
    url = f"http://router.project-osrm.org/route/v1/driving/{origem_lon},{origem_lat};{destino_lon},{destino_lat}?overview=full&geometries=geojson"
    try:
        resp = requests.get(url, timeout=15)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None

def gerar_mapa(lista_clientes, veiculo):
    df_filtrado = df_custo[df_custo['Cliente'].isin(lista_clientes)]
    linha_veiculo = df_custo[df_custo['Veículo'] == veiculo].iloc[0]
    consumo_kml, preco_combustivel = linha_veiculo['Consumo KM/L'], linha_veiculo['Custo Combustível']

    centro_lat = pd.concat([df_filtrado['Origem_Lat'], df_filtrado['Destino_Lat']]).mean()
    centro_lon = pd.concat([df_filtrado['Origem_Lon'], df_filtrado['Destino_Lon']]).mean()

    m = folium.Map(location=[centro_lat, centro_lon], zoom_start=8, tiles='OpenStreetMap')

    cores = ['purple', 'blue', 'orange', 'green', 'darkred', 'cadetblue']
    total_custo = total_tempo = total_litros = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        rotas = list(executor.map(
            lambda linha: requisitar_rota(linha.Origem_Lat, linha.Origem_Lon,
                                          linha.Destino_Lat, linha.Destino_Lon),
            df_filtrado.itertuples()
        ))

    for idx, (linha, rota) in enumerate(zip(df_filtrado.itertuples(), rotas)):
        origem = (linha.Origem_Lat, linha.Origem_Lon)
        destino = (linha.Destino_Lat, linha.Destino_Lon)
        cliente = linha.Cliente

        folium.Marker(
            origem,
            popup=f"""<div style='font-size:12px; width:220px;'>
                        <strong>Origem:</strong> {linha.Origem}<br>
                        <strong>CD:</strong> {linha.CD}
                      </div>""",
            tooltip=f"{linha.CD} - Origem",
            icon=folium.Icon(color='green')
        ).add_to(m)

        if rota:
            rota_data = rota['routes'][0]
            coords = [[lat, lon] for lon, lat in rota_data['geometry']['coordinates']]
            distancia_km = rota_data['distance']/1000
            tempo_min = rota_data['duration']/60
            litros = distancia_km/consumo_kml
            custo = litros*preco_combustivel

            total_custo += custo
            total_tempo += tempo_min
            total_litros += litros

            folium.PolyLine(coords, color=cores[idx % len(cores)], weight=5,
                            tooltip=f"{cliente}: {distancia_km:.1f} km").add_to(m)

            folium.Marker(
                destino,
                popup=f"""<div style='font-size:12px; width:220px;'>
                            <strong>Cliente:</strong> {cliente}<br>
                            <strong>Distância:</strong> {distancia_km:.1f} km<br>
                            <strong>Tempo:</strong> {tempo_min:.0f} min<br>
                            <strong>Consumo:</strong> {litros:.2f} L<br>
                            <strong>Custo:</strong> R$ {custo:.2f}
                          </div>""",
                tooltip=f"{cliente} - Destino",
                icon=folium.Icon(color='red')
            ).add_to(m)

        else:
            folium.Marker(
                destino,
                popup=f"""<div style='font-size:12px;width:200px;'>
                            ❗ Falha OSRM para {cliente}
                          </div>""",
                icon=folium.Icon(color='gray')
            ).add_to(m)

    folium.Marker(
        [centro_lat, centro_lon],
        popup=f"""<div style='font-size:12px; width:220px;'>
                    <strong>Custo Total:</strong> R$ {total_custo:.2f}<br>
                    <strong>Tempo Total:</strong> {total_tempo:.0f} min<br>
                    <strong>Litros:</strong> {total_litros:.2f} L
                  </div>""",
        icon=folium.Icon(color='darkpurple', icon='usd', prefix='fa')
    ).add_to(m)

    st.markdown(f"### 📊 Resultados Gerais:\n- Rotas selecionadas: {len(lista_clientes)}\n- Custo Total: R$ {total_custo:.2f}\n- Tempo Total: {total_tempo:.0f} min\n- Consumo Total: {total_litros:.2f} L")

    return m

if st.button("🚛 Gerar Mapa"):
    if not clientes_selecionados:
        st.warning("Selecione ao menos um cliente!")
    else:
        with st.spinner('Gerando mapa...'):
            mapa = gerar_mapa(clientes_selecionados, veiculo_selecionado)
            st.success("Mapa gerado com sucesso!")
            st_folium(mapa, width=725, height=500, returned_objects=[], key="mapa_rotas")
