from django.urls import path
from . import views
from . import broker_views
from . import chart_views

urlpatterns = [
    # Watchlist
    path('watchlist/', views.watchlist, name='watchlist'),
    path('watchlist/<int:pk>/', views.watchlist_detail, name='watchlist-detail'),

    # Bot control
    path('bot/status/', views.bot_status, name='bot-status'),
    path('bot/start/', views.bot_start, name='bot-start'),
    path('bot/stop/', views.bot_stop, name='bot-stop'),
    path('bot/settings/', views.bot_settings, name='bot-settings'),

    # Charts + dashboard ORB snapshot (watchlist intraday / ORB levels)
    path('charts/watchlist/', chart_views.charts_watchlist, name='charts-watchlist'),
    path('orb/watchlist/', chart_views.orb_watchlist, name='orb-watchlist'),

    # Live market data (broker_live = one login for positions + orders)
    path('broker/live/', broker_views.broker_live, name='broker-live'),
    path('positions/', views.positions, name='positions'),
    path('positions/exit/', broker_views.exit_position_view, name='positions-exit'),
    path('orders/', views.orders, name='orders'),
    path('capital/', views.capital, name='capital'),

    # P&L
    path('pnl/', views.pnl_history, name='pnl-history'),
    path('pnl/today/', views.pnl_today, name='pnl-today'),
    path('pnl/summary/', views.pnl_summary, name='pnl-summary'),
    path('pnl/sync/', views.pnl_sync, name='pnl-sync'),

    # Sessions
    path('sessions/', views.sessions, name='sessions'),

    # System health
    path('health/', views.system_health, name='system-health'),
]
