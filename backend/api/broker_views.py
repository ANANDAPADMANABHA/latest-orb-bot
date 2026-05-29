from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.models import ManagedPosition
from trading.broker_cache import format_broker_error, get_angel_client
from trading.pnl_service import record_pnl_trade


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


@api_view(['POST'])
def exit_position_view(request):
    """Square off one position at market and cancel pending orders for that symbol."""
    tradingsymbol = (request.data.get('tradingsymbol') or '').strip()
    if not tradingsymbol:
        return Response(
            {'error': 'tradingsymbol is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        client = get_angel_client()
        result = client.exit_position(tradingsymbol)
        ticker = result.get('ticker') or tradingsymbol.replace('-EQ', '').upper()
        ManagedPosition.objects.filter(symbol=ticker, is_active=True).update(is_active=False)
        if result.get('square_off', {}).get('placed'):
            record_pnl_trade(
                ticker,
                result.get('quantity', 0),
                result.get('realized_pnl', 0),
            )
        return Response(result)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': format_broker_error(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
