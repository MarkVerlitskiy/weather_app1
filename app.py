
from flask import Flask, request, render_template_string
import requests
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster

app = Flask(__name__)

API_KEY = "cnPA2o0MVjDEqCLRjcmlNdVVZrwd1oKe"
BASE_URL = "http://dataservice.accuweather.com/forecasts/v1/daily/"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Weather Service</title>
    <style>
        #map { width: 100%; height: 400px; margin-top: 30px; }  /* Отступ сверху для карты */
        h1, h2, h3 { text-align: center; }
        .container { width: 80%; margin: 0 auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Прогноз погоды для маршрута</h1>
        <form method="POST">
            <label for="route_points">Точки маршрута (формат: lat1,lon1; lat2,lon2; ...):</label><br>
            <input type="text" id="route_points" name="route_points" required><br><br>

            <label for="forecast_days">Количество дней:</label><br>
            <select id="forecast_days" name="forecast_days">
                <option value="1">1 день</option>
                <option value="3">3 дня</option>
                <option value="5">5 дней</option>
            </select><br><br>

            <button type="submit">Получить прогноз</button>
        </form>

        {% if weather_result %}
            {% if weather_result.error %}
                <p style="color: red; text-align: center;">{{ weather_result.error }}</p>
            {% else %}
                <h2>Результаты:</h2>

                <!-- График температур -->
                <h3>График температур:</h3>
                <div style="text-align: center;">{{ weather_graph | safe }}</div> <!-- Для графика -->

                <!-- Карта -->
                <h3>Маршрут:</h3>
                <div id="map" style="text-align: center;">{{ map_html | safe }}</div> <!-- Для карты -->

                {% for point, forecast in weather_result.items() %}
                    <h3>Точка маршрута: {{ point }}</h3>
                    <ul>
                        {% for day in forecast %}
                            <li>{{ day.date }}: {{ day.min_temp }}°C - {{ day.max_temp }}°C</li>
                        {% endfor %}
                    </ul>
                {% endfor %}
            {% endif %}
        {% else %}
            <p>Введите координаты маршрута.</p>
        {% endif %}
    </div>
</body>
</html>
"""

def get_weather_data(lat, lon, days):

    try:
        location_url = f"http://dataservice.accuweather.com/locations/v1/cities/geoposition/search"
        params = {"apikey": API_KEY, "q": f"{lat},{lon}"}
        location_response = requests.get(location_url, params=params).json()
        if "Key" not in location_response:
            error_message = location_response.get("Message", "Неизвестная ошибка.")
            return {"error": f"Не удалось определить местоположение: {error_message}"}

        location_key = location_response["Key"]
        forecast_url = f"{BASE_URL}{'1day' if days == 1 else '5day'}/{location_key}"
        forecast_params = {"apikey": API_KEY, "metric": True}
        forecast_response = requests.get(forecast_url, params=forecast_params).json()

        if "DailyForecasts" not in forecast_response:
            return {"error": "Не удалось получить прогноз погоды."}
        forecast_data = []
        for day in forecast_response["DailyForecasts"]:
            forecast_data.append({
                "date": day["Date"],
                "min_temp": day["Temperature"]["Minimum"]["Value"],
                "max_temp": day["Temperature"]["Maximum"]["Value"],
            })

        return forecast_data
    except Exception as e:
        return {"error": f"Произошла ошибка: {str(e)}"}

def create_weather_graph(weather_result):
    fig = go.Figure()

    for point, forecast in weather_result.items():
        dates = [day['date'] for day in forecast]
        min_temps = [day['min_temp'] for day in forecast]
        max_temps = [day['max_temp'] for day in forecast]

        fig.add_trace(go.Scatter(x=dates, y=min_temps, mode='lines', name=f'Min temp {point}', hovertemplate="Мин. темп: %{y}°C<br>Дата: %{x}"))
        fig.add_trace(go.Scatter(x=dates, y=max_temps, mode='lines', name=f'Max temp {point}', hovertemplate="Макс. темп: %{y}°C<br>Дата: %{x}"))

    fig.update_layout(
        title='Прогноз температур для точек маршрута',
        xaxis_title='Дата',
        yaxis_title='Температура (°C)',
        template="plotly_dark",
        hovermode="closest"
    )

    return fig.to_html()

@app.route("/", methods=["GET", "POST"])
def weather_service():
    weather_result = {}

    if request.method == "POST":
        points = request.form.get("route_points", "").strip()
        forecast_days = int(request.form.get("forecast_days", 5))

        if not points:
            return render_template_string(HTML_TEMPLATE, weather_result={"error": "Введите точки маршрута."})

        points_list = points.split(";")
        for point in points_list:
            try:
                lat, lon = map(float, point.split(","))
                forecast = get_weather_data(lat, lon, forecast_days)
                if isinstance(forecast, dict) and "error" in forecast:
                    return render_template_string(HTML_TEMPLATE, weather_result={"error": forecast["error"]})
                weather_result[point.strip()] = forecast
            except ValueError:
                return render_template_string(HTML_TEMPLATE, weather_result={"error": "Неверный формат координат."})
        weather_graph = create_weather_graph(weather_result)

        map_center = [float(points_list[0].split(",")[0]), float(points_list[0].split(",")[1])]
        m = folium.Map(location=map_center, zoom_start=6)
        marker_cluster = MarkerCluster().add_to(m)

        for point, forecast in weather_result.items():
            lat, lon = map(float, point.split(","))
            popup_content = f"Точка маршрута: {point}<br>"
            for day in forecast:
                popup_content += f"{day['date']}: {day['min_temp']}°C - {day['max_temp']}°C<br>"
            folium.Marker([lat, lon], popup=popup_content).add_to(marker_cluster)

        map_html = m._repr_html_()

        return render_template_string(HTML_TEMPLATE, weather_result=weather_result, weather_graph=weather_graph,
                                      map_html=map_html)

    return render_template_string(HTML_TEMPLATE, weather_result=weather_result)


if __name__ == "__main__":
    app.run(debug=True)
