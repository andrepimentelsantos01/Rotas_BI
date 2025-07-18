# 📍 Gerador de Rotas Rodoviárias

## 🇧🇷 Português - Brasil

Este projeto tem como objetivo fornecer uma ferramenta simples e interativa para **visualização de rotas rodoviárias**, realizando simulações de custos logísticos entre um centro de distribuição (CD) e múltiplos clientes.

### ✅ Funcionalidades:

* Seleção de **CD (Origem)**, **Agrupamento**, **Clientes** e **Veículo**;
* Cálculo de rotas utilizando duas opções:

  * **/route**: cálculo bruto, considerando cada rota do CD até o cliente individualmente;
  * **/trip**: cálculo sequencial, organizando entregas do mais próximo ao mais distante do CD, acumulando consumo e custo ao longo do percurso;
* Mapa interativo via **Folium** com rotas desenhadas e pop-ups detalhados;
* Relatório com **custo total**, **tempo total**, **distância total** e **consumo total**.

### 🚀 Como executar:

1. Faça o clone deste repositório;
2. Instale as dependências via:

```bash
pip install -r requirements.txt
```

3. Execute localmente via:

```bash
streamlit run app.py
```

ou
4\. Utilize diretamente via **Streamlit Cloud**.

---

## 🇺🇸 English

This project provides a simple and interactive tool for **road route visualization**, allowing for logistical cost simulations between a distribution center (CD) and multiple client destinations.

### ✅ Features:

* Selection of **Distribution Center (Origin)**, **Grouping**, **Clients**, and **Vehicle**;
* Route calculation with two modes:

  * **/route**: basic calculation considering each route from the CD to the client separately;
  * **/trip**: sequential route calculation, ordering deliveries from the nearest to the farthest from the CD, accumulating costs and fuel consumption;
* Interactive map using **Folium** with plotted routes and detailed pop-ups;
* Summary report with **total cost**, **total time**, **total distance**, and **total fuel consumption**.

### 🚀 How to run:

1. Clone this repository;
2. Install dependencies via:

```bash
pip install -r requirements.txt
```

3. Run locally via:

```bash
streamlit run app.py
```

or
4\. Use it directly through **Streamlit Cloud**.

---

## 🇲🇽 Español - México

Este proyecto tiene como objetivo ofrecer una herramienta sencilla e interactiva para la **visualización de rutas por carretera**, permitiendo simulaciones de costos logísticos entre un centro de distribución (CD) y múltiples clientes.

### ✅ Funcionalidades:

* Selección de **Centro de Distribución (Origen)**, **Agrupamiento**, **Clientes** y **Vehículo**;
* Cálculo de rutas con dos opciones:

  * **/route**: cálculo simple, considerando cada ruta del CD al cliente individualmente;
  * **/trip**: cálculo secuencial, organizando las entregas del más cercano al más lejano del CD, acumulando distancia, consumo y costo;
* Mapa interactivo con **Folium**, rutas dibujadas y pop-ups detallados;
* Reporte con **costo total**, **tiempo total**, **distancia total** y **consumo total**.

### 🚀 ¿Cómo ejecutar?

1. Clona este repositorio;
2. Instala las dependencias con:

```bash
pip install -r requirements.txt
```

3. Ejecuta localmente con:

```bash
streamlit run app.py
```

o
4\. Utilízalo directamente desde **Streamlit Cloud**.
