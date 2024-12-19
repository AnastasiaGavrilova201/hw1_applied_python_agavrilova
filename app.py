import streamlit as st
import requests, json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
from datetime import datetime
import polars as pl

st.title("Анализ температуры")
st.header("Загрузка данных")
uploaded_file = st.file_uploader("Выберите CSV-файл c историческими данными о погоде", type=["csv"])

# Если файл загружен, показать данные 
if uploaded_file is not None:
    data = pd.read_csv(uploaded_file)
    st.info("Превью данных:")
    st.dataframe(data)
else:
    st.info("Пожалуйста, загрузите не пустой CSV-файл.")

# Доступные города на русском и английском 
# для интерфейса и анализа данных, соответственно
options = {'Нью-Йорк': 'New York', 'Лондон': 'London',
           'Париж': 'Paris', 'Токио': 'Tokyo',
           'Москва': 'Moscow', 'Сидней':'Sydney',
           'Берлин':'Berlin', "Пекин":'Beijing',
           "Рио-де-Жанейро": 'Rio de Janeiro',  "Дубай":'Dubai', 
           "Лос-Анжелес": 'Los Angeles', "Сингапур": 'Singapore', 
           "Мумбаи":'Mumbai', "Каир": 'Cairo', "Мехико":'Mexico City'}

# Месяцы для определения текущего сезона
month_to_season = {12: "winter", 1: "winter", 2: "winter",
                   3: "spring", 4: "spring", 5: "spring",
                   6: "summer", 7: "summer", 8: "summer",
                   9: "autumn", 10: "autumn", 11: "autumn"}

# Месяцы на русском и английском 
# для интерфейса и анализа данных, соответственно
month_ru = {"winter": "Зима", 
                   "spring": "Весна", 
                   "summer": "Лето", 
                    "autumn": "Осень"}

# Расчет описательной статистики
def polars_describe(df):
    data = df
    result2 = data.group_by(['city']).agg([
        pl.col('temperature').min().alias('min'),
        pl.col('temperature').max().alias('max'),
        pl.col('temperature').mean().alias('mean')])
    return result2

# Расчет сезонного профиля
def polars_season_profile(df):
    data = df
    result1 = data.group_by(['city', 'season']).agg([
        pl.col('temperature').mean().alias('mean'),
        pl.col('temperature').std().alias('std')])
    return result1

# Расчет граничных значений температур для поиска аномалий
def polars_anomaly(df):
    polars_df = df
    polars_df = polars_df.with_columns(
      pl.col('temperature').rolling_mean(window_size=30, min_periods=0).fill_null(pl.col('temperature').first()).alias('SlidingAvg'))
    polars_df = polars_df.with_columns(
      pl.col('temperature').rolling_std(window_size=30, min_periods=0).fill_null(0).alias('SlidingStd'))
    # нижняя граница нормы
    polars_df = polars_df.with_columns((pl.col('SlidingAvg') - 2*pl.col('SlidingStd')).alias('start'))
    # верхняя граница нормы
    polars_df = polars_df.with_columns((pl.col('SlidingAvg') + 2*pl.col('SlidingStd')).alias('end'))
    return polars_df

st.header("Текущие данные о погоде")

# Данные для подключения к АПИ
# Ключ
api_key = st.text_input("Ваш API-ключ:")
# Город
city_ru = st.selectbox("Выберите город:", sorted(options.keys()))
city = options[city_ru]
base_url = "http://api.openweathermap.org/data/2.5/weather?"
flg_success = 0 

# Если ключ заполнен, делаем запрос
if api_key != "":
    complete_url = base_url + "appid=" + api_key + "&units=metric" + "&q=" + city
    response = requests.get(complete_url)
    if response.status_code == 200:
        flg_success = 1
        x = response.json()
        your_temp = x['main']['temp']
        st.markdown(f'### Текущая температура в городе {city_ru}:')
        st.success(str(round(your_temp,1))+' '+ u'\u00B0C')
    elif response.status_code == 401: 
        st.error({"cod": 401,
                  "message": "Invalid API key. Please see https://openweathermap.org/faq#error401 for more info."})
    else:
        st.error('error code ', response.status_code)
else:
    st.info('Введите ваш API-ключ')

# Если файл загружен, анализируем данные для выбранного города 
if uploaded_file is not None:
    st.header(f"Анализ в контексте исторических данных о погоде в городе {city_ru}")
    st.info(u'Все числовые показатели (минимум, максимум и др.) представлены в градусах Цельсия (\u00B0C)')
    st.markdown("### Описательная статистика температуры")

    # Покажем описательную статистику
    data1 = pl.DataFrame(data)
    data1 = data1.filter(pl.col("city") == city)
    descriptive_data = pd.DataFrame(polars_describe(data1))
    # Переведем все на русский и округлим значения
    descriptive_data.columns = ['Город', 'Минимум', 'Максимум', 'Среднее']
    desc = descriptive_data
    st.dataframe(round(desc.replace(city, city_ru),1))

    # Покажем сезонный профиль
    st.markdown('### Сезонный профиль температуры')
    stata = pd.DataFrame(polars_season_profile(data1))
    # Переведем все на русский и округлим значения
    stata.columns = ['Город', 'Сезон', 'Среднее', 'Стандартное отклонение']
    st.dataframe(round(stata.replace(city, city_ru).replace(month_ru),1))

    #Если подкдючились к АПИ, смотрим, нормальна ли температура
    if flg_success == 1:
        # Узнаем сезон для сегодняшней даты
        current_month = datetime.now().month
        your_season = month_to_season[current_month]
        your_row = stata[stata['Сезон'] == your_season]
        # Определим, нормальная ли температура для текущего сезона
        if abs(your_row['Среднее'].iloc[0] - your_temp) <= 2*your_row['Стандартное отклонение'].iloc[0]:
            st.success(f'Температура в городе {city_ru} нормальна')
        elif your_temp < your_row['Среднее'].iloc[0] - 2*your_row['Стандартное отклонение'].iloc[0]:
            st.info(f'Температура в городе {city_ru} аномальна (ниже нормы)')
        else: 
            st.error(f'Температура в городе {city_ru} аномальна (выше нормы)')
        
    st.markdown('### График температуры')
    cur_data = pd.DataFrame(polars_anomaly(data1))
    cur_data.columns = ['city', 'timestamp', 'temperature', 'season',
                        'SlidingAvg','SlidingStd', 'start', 'end']
    # Определим, какие значения нормальны (выше и ниже 0),
    # какие аномальны (выше или ниже нормы) и покрасим их разными цветами -- всего 4 цвета
    conditions = [
    (cur_data['temperature'] < cur_data['start']),
    (cur_data['temperature'] < 0) & (cur_data['temperature'] >= cur_data['start']) & (cur_data['temperature'] <= cur_data['end']),
    (cur_data['temperature'] > cur_data['end']),
    (cur_data['temperature'] >= 0) & (cur_data['temperature'] >= cur_data['start']) & (cur_data['temperature'] <= cur_data['end'])
    ]

    choices = [1,2,3,4]
    cur_data['points'] = np.select(conditions, choices)
    cur_data = pd.DataFrame(cur_data)
    
    plt.figure(figsize=(13, 8))
    plt.scatter(cur_data['timestamp'], cur_data['temperature'], 
                c = cur_data.points.map({1: '#0000FF', 
                                         2: '#63B8FF',
                                         3:'#FF3030',
                                         4:'#FFA07A'}), s=20)
    
    colormap = np.array(['#0000FF', '#63B8FF', '#FF3030', '#FFAEB9'])
    pop_nn = mpatches.Patch(color='#0000FF', label='Ниже нормы')
    pop_cn = mpatches.Patch(color='#63B8FF', label='Норма (t<0)')
    pop_vn = mpatches.Patch(color='#FF3030', label='Выше нормы')
    pop_hn = mpatches.Patch(color='#FFA07A', label='Норма (t>0)')
    # Покажем график температур
    plt.xticks(cur_data['timestamp'][::300], rotation = 'vertical') 
    plt.xlabel('Дата')
    plt.ylabel(u'\u00B0C')
    plt.title(f'Температура в городе {city_ru} c 2010 по 2019 г.')
    
    plt.legend(handles=[pop_vn, pop_hn ,pop_cn, pop_nn])
    st.pyplot(plt.gcf())
