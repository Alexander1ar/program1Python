from flask import Flask, render_template_string, request
import pandas as pd
import mysql.connector
import matplotlib.pyplot as plt
import io
import base64
import seaborn as sns
from scipy import stats
import numpy as np
from datetime import datetime

app = Flask(__name__)

# Configuración de la base de datos
db_config = {
    'host': 'autorack.proxy.rlwy.net',
    'port': '23931',
    'user': 'root',
    'password': 'SfTUudJuiVGsyjkUUXZpagNKcYocDxvn',
    'database': 'railway'
}

# Fecha de inicio para el filtro de datos
start_date = '2024-08-01'

def create_histogram_with_fit(variable_name, data):
    # Crear el histograma
    fig, ax = plt.subplots(figsize=(10, 6))
    n, bins, patches = ax.hist(data, bins=20, edgecolor='black', alpha=0.6, density=True)

    # Ajuste de distribución normal
    mu, std = stats.norm.fit(data)
    p = stats.norm.pdf(bins, mu, std)
    ax.plot(bins, p, 'k', linewidth=2)

    # Añadir título y etiquetas
    ax.set_title(f'Histograma de {variable_name} con Ajuste Gaussiano')
    ax.set_xlabel(variable_name)
    ax.set_ylabel('Densidad')
    ax.grid(True)

    # Guardar el gráfico en un buffer de memoria
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    img_data = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()

    return img_data

def calculate_pearson_correlation(x, y):
    # Convertir a arrays de numpy
    x = np.array(x)
    y = np.array(y)
    
    # Calcular medias
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    
    # Calcular desviaciones estándar
    x_std = np.std(x, ddof=1)
    y_std = np.std(y, ddof=1)
    
    # Calcular la covarianza
    covariance = np.mean((x - x_mean) * (y - y_mean))
    
    # Calcular el coeficiente de correlación
    r = covariance / (x_std * y_std)
    
    return r

def create_correlation_plot(var1, var2):
    fig, ax = plt.subplots(figsize=(10, 6))

    # Conexión a la base de datos
    conn = mysql.connector.connect(
        host=db_config['host'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database']
    )

    # Consulta SQL para obtener los datos del último mes
    query = f"""
        SELECT {var1}, {var2}
        FROM emeteorologicaps
        WHERE fecha >= '{start_date}'
    """
    df = pd.read_sql(query, conn)
    conn.close()

    # Eliminar valores nulos
    df.dropna(subset=[var1, var2], inplace=True)

    # Convertir a numpy arrays
    x = df[var1].to_numpy()
    y = df[var2].to_numpy()

    # Normalización de los datos
    x = (x - np.mean(x)) / np.std(x, ddof=1)
    y = (y - np.mean(y)) / np.std(y, ddof=1)

    # Calcular el coeficiente de correlación de Pearson manualmente
    r_manual = calculate_pearson_correlation(x, y)
    
    # Calcular el coeficiente de correlación de Pearson usando stats.pearsonr
    r, p_value = stats.pearsonr(x, y)
    
    # Crear el gráfico de dispersión con la línea de ajuste
    sns.scatterplot(x=x, y=y, ax=ax)
    sns.regplot(x=x, y=y, scatter=False, color='red', ax=ax)
    ax.set_title(f'Correlación de Pearson entre {var1} y {var2} (Coeficiente: {r:.2f}, Manual: {r_manual:.2f})')
    ax.set_xlabel(var1)
    ax.set_ylabel(var2)
    ax.grid(True)

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    img_data = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()

    return img_data

@app.route('/')
def index():
    try:
        # Conexión a la base de datos
        conn = mysql.connector.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database']
        )

        # Consulta SQL para obtener los datos del último mes
        variables = [
            'temperaturaaire', 'humedadaire', 'intensidadluz',
            'indiceuv', 'velocidadviento', 'direccionviento', 'presionbarometrica'
        ]

        img_data_dict = {}
        for var in variables:
            query = f"""
                SELECT {var}
                FROM emeteorologicaps
                WHERE fecha >= '{start_date}'
            """
            df = pd.read_sql(query, conn)
            img_data_dict[var] = create_histogram_with_fit(var, df[var])

        conn.close()

        # HTML para renderizar las imágenes
        html = '''
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <title>Histogramas con Ajuste Gaussiano</title>
          </head>
          <body>
            <h1>Histogramas con Ajuste Gaussiano</h1>
            {% for var, img_data in img_data_dict.items() %}
              <h2>Histograma de {{ var }}</h2>
              <img src="data:image/png;base64,{{ img_data }}" alt="Histograma de {{ var }}">
            {% endfor %}

            <h1>Correlación de Pearson</h1>
            <form action="/correlation" method="get">
              <label for="var1">Selecciona la primera variable:</label>
              <select id="var1" name="var1">
                {% for var in variables %}
                  <option value="{{ var }}">{{ var }}</option>
                {% endfor %}
              </select>

              <label for="var2">Selecciona la segunda variable:</label>
              <select id="var2" name="var2">
                {% for var in variables %}
                  <option value="{{ var }}">{{ var }}</option>
                {% endfor %}
              </select>

              <button type="submit">Ver Correlación</button>
            </form>
          </body>
        </html>
        '''

        return render_template_string(html, img_data_dict=img_data_dict, variables=variables)

    except Exception as e:
        return f"An error occurred: {e}"

@app.route('/correlation')
def correlation():
    var1 = request.args.get('var1')
    var2 = request.args.get('var2')

    if var1 and var2:
        img_data = create_correlation_plot(var1, var2)
        html = f'''
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <title>Correlación de Pearson</title>
          </head>
          <body>
            <h1>Correlación de Pearson entre {var1} y {var2}</h1>
            <img src="data:image/png;base64,{img_data}" alt="Correlación de Pearson">
            <a href="/">Volver</a>
          </body>
        </html>
        '''
        return html
    else:
        return "No variables selected. Go back and select two variables."

if __name__ == '__main__':
    app.run(debug=True)
