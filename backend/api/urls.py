from django.urls import path
from . import views
from . import auth_views
from . import broker_views
from . import chart_views
from . import chartink_views

urlpatterns = [
    # Auth
    path('auth/csrf/', auth_views.auth_csrf, name='auth-csrf'),
    path('auth/login/', auth_views.auth_login, name='auth-login'),
    path('auth/logout/', auth_views.auth_logout, name='auth-logout'),
    path('auth/me/', auth_views.auth_me, name='auth-me'),

    # Watchlist
    path('watchlist/', views.watchlist, name='watchlist'),
    path('watchlist/<int:pk>/', views.watchlist_detail, name='watchlist-detail'),

    # Chartink — config/ must be before <secret>/ or "config" is treated as the secret
    path(
        'webhooks/chartink/config/',
        chartink_views.chartink_webhook_config,
        name='chartink-webhook-config',
    ),
    path(
        'webhooks/chartink/<str:secret>/',
        chartink_views.chartink_webhook,
        name='chartink-webhook',
    ),

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
    path('orders/cleanup-orphans/', broker_views.cleanup_orphan_orders, name='orders-cleanup-orphans'),
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
