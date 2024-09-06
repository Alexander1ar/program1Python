from flask import Flask, render_template_string, request
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
import matplotlib
matplotlib.use('Agg')  # Evitar GUI de Matplotlib
import matplotlib.pyplot as plt
import io
import base64
import seaborn as sns
from scipy import stats
import numpy as np
import os

app = Flask(__name__)

# Configuración de la base de datos mediante variables de entorno
db_config = {
    'host': os.getenv('DB_HOST', 'autorack.proxy.rlwy.net'),
    'port': os.getenv('DB_PORT', '23931'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'SfTUudJuiVGsyjkUUXZpagNKcYocDxvn'),
    'database': os.getenv('DB_NAME', 'railway')
}

# Crear el engine de SQLAlchemy con un pool de conexiones
engine = create_engine(
    f"mysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}",
    poolclass=NullPool  # NullPool evita que se mantengan conexiones abiertas si no es necesario
)

# Fecha de inicio para el filtro de datos
start_date = '2024-08-01'

def create_histogram_with_fit(variable_name, data):
    # Crear el histograma
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(data, bins=20, edgecolor='black', alpha=0.6, density=True)

    # Ajuste de distribución normal
    mu, std = stats.norm.fit(data)
    p = stats.norm.pdf(np.linspace(min(data), max(data), 100), mu, std)
    ax.plot(np.linspace(min(data), max(data), 100), p, 'k', linewidth=2)

    ax.set_title(f'Histograma de {variable_name} con Ajuste Gaussiano')
    ax.set_xlabel(variable_name)
    ax.set_ylabel('Densidad')
    ax.grid(True)

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    img_data = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()
    return img_data

def create_correlation_plot(var1, var2):
    fig, ax = plt.subplots(figsize=(10, 6))

    query = f"""
        SELECT {var1}, {var2}
        FROM emeteorologicaps
        WHERE fecha >= '{start_date}'
    """
    df = pd.read_sql(query, engine)

    # Eliminar valores nulos
    df.dropna(subset=[var1, var2], inplace=True)

    # Convertir a numpy arrays
    x = (df[var1] - df[var1].mean()) / df[var1].std(ddof=1)
    y = (df[var2] - df[var2].mean()) / df[var2].std(ddof=1)

    sns.scatterplot(x=x, y=y, ax=ax)
    sns.regplot(x=x, y=y, scatter=False, color='red', ax=ax)
    ax.set_title(f'Correlación entre {var1} y {var2}')
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
            df = pd.read_sql(query, engine)
            img_data_dict[var] = create_histogram_with_fit(var, df[var])

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

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    from waitress import serve
    serve(app, host="0.0.0.0", port=port)
