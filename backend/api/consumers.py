import asyncio

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from api.models import WatchlistTicker
from trading.market_stream import CHANNEL_GROUP, start_live_stream, stop_live_stream


def _active_watchlist_symbols() -> list:
    return list(
        WatchlistTicker.objects.filter(is_active=True)
        .order_by('symbol')
        .values_list('symbol', flat=True)
    )


class ChartLiveConsumer(AsyncJsonWebsocketConsumer):
    """Relay Angel One WebSocket v2 ticks to the Charts page."""

    async def connect(self):
        await self.channel_layer.group_add(CHANNEL_GROUP, self.channel_name)
        await self.accept()

        symbols = await sync_to_async(_active_watchlist_symbols)()
        if symbols:
            await self.send_json({'type': 'status', 'message': 'connecting', 'symbols': symbols})
            await self._start_stream(symbols)
        else:
            await self.send_json({'type': 'status', 'message': 'no_symbols'})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(CHANNEL_GROUP, self.channel_name)
        # Do not block Daphne shutdown on Angel WS teardown (tab switch / refresh).
        asyncio.create_task(sync_to_async(stop_live_stream)())

    async def chart_message(self, event):
        await self.send_json(event['payload'])

    async def _start_stream(self, symbols):
        await sync_to_async(start_live_stream)(symbols)

    async def _stop_stream(self):
        await sync_to_async(stop_live_stream)()
