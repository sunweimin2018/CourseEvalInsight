from rest_framework.response import Response
from rest_framework import status


def api_response(data=None, msg='success', code=200, http_status=None):
    if http_status is None:
        http_status = status.HTTP_200_OK if code == 200 else status.HTTP_400_BAD_REQUEST
    return Response({'code': code, 'msg': msg, 'data': data}, status=http_status)
