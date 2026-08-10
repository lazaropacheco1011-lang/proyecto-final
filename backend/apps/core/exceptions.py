"""Manejo de errores consistente para toda la API."""
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    message = detail
    if isinstance(detail, dict):
        if 'detail' in detail:
            message = detail['detail']
        else:
            errors = []
            for field, value in detail.items():
                if isinstance(value, list):
                    value = value[0] if value else ''
                errors.append(f'{field}: {value}')
            message = '; '.join(errors)

    # Los ValidationError globales llegan como lista: se aplana a texto legible.
    if isinstance(message, list):
        message = message[0] if message else 'Ocurrió un error inesperado.'

    response.data = {
        'status': response.status_code,
        'message': message,
        'errors': detail if isinstance(detail, dict) else None,
    }
    return response
