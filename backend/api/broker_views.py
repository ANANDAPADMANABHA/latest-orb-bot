from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from trading.broker_cache import format_broker_error, get_angel_client


@api_view(['GET'])
def broker_live(request):
    """
    Positions + order book in one Angel One session (fewer logins than two separate calls).
    """
    try:
        client = get_angel_client()
        return Response({
            'positions': client.get_positions(),
            'orders': client.get_order_book(),
        })
    except Exception as e:
        return Response(
            {'error': format_broker_error(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
