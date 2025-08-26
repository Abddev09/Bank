from rest_framework import status
from rest_framework.response import Response

from transfer.models import Error
from transfer.serializer import ErrorSerializer

def error_response(code: int, http_status=status.HTTP_400_BAD_REQUEST):
    try:
        error = Error.objects.get(code=code)
        return Response({"error": ErrorSerializer(error).data}, status=http_status)
    except Error.DoesNotExist:
        return Response({"error": {"code": code, "message": "Unknown error"}}, status=http_status)