from django.urls import path
from . import views

urlpatterns = [
    # Watchlist
    path('watchlist/', views.watchlist, name='watchlist'),
    path('watchlist/<int:pk>/', views.watchlist_detail, name='watchlist-detail'),

    # Bot control
    path('bot/status/', views.bot_status, name='bot-status'),
    path('bot/start/', views.bot_start, name='bot-start'),
    path('bot/stop/', views.bot_stop, name='bot-stop'),

    # Live market data
    path('positions/', views.positions, name='positions'),
    path('orders/', views.orders, name='orders'),
    path('capital/', views.capital, name='capital'),

    # P&L
    path('pnl/', views.pnl_history, name='pnl-history'),
    path('pnl/today/', views.pnl_today, name='pnl-today'),
    path('pnl/summary/', views.pnl_summary, name='pnl-summary'),

    # Sessions
    path('sessions/', views.sessions, name='sessions'),
]
