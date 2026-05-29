from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('ws/charts/', consumers.ChartLiveConsumer.as_asgi()),
]
