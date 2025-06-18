from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.db.models import F
from datetime import datetime

from .hashing_algorithms import ChainingHashTable, LinearProbingHashTable, \
                              QuadraticProbingHashTable, DoubleHashingHashTable
from .models import HashingLog, HashTableSlot, ChainedElement # Importa los modelos

# Dimension de la tabla hash
TABLE_SIZE = 10

# Diccionario para almacenar las instancias de las tablas hash
# Ahora estas instancias solo orquestan las operaciones con la DB
_hashing_tables = {
    'chaining': ChainingHashTable(TABLE_SIZE),
    'linear_probing': LinearProbingHashTable(TABLE_SIZE),
    'quadratic_probing': QuadraticProbingHashTable(TABLE_SIZE),
    'double_hashing': DoubleHashingHashTable(TABLE_SIZE),
}

class HashingBaseView(APIView):
    def get_hashing_table(self, algorithm_type):
        if algorithm_type not in _hashing_tables:
            return None
        return _hashing_tables[algorithm_type]

    def save_log_to_db(self, algorithm_type, operation_type, key, value, result, table_state, collisions, probes):
        try:
            HashingLog.objects.create(
                algorithm_type=algorithm_type,
                operation_type=operation_type,
                key=key,
                value=value,
                result=str(result),
                table_state_json=table_state,
                collisions=collisions,
                probes=probes
            )
        except Exception as e:
            print(f"Error al guardar log en MySQL: {e}")

class HashingOperationView(HashingBaseView):
    def post(self, request, algorithm_type):
        table = self.get_hashing_table(algorithm_type)
        if not table:
            return Response({"error": "Algoritmo de hashing no válido."}, status=status.HTTP_400_BAD_REQUEST)

        key = request.data.get('key')
        value = request.data.get('value')
        operation = request.data.get('operation') # 'insert' o 'search'

        if not key or not operation:
            return Response({"error": "Faltan 'key' o 'operation'."}, status=status.HTTP_400_BAD_REQUEST)

        operation_result = None
        try:
            if operation == 'insert':
                if value is None:
                    return Response({"error": "Falta 'value' para la operación de inserción."}, status=status.HTTP_400_BAD_REQUEST)
                table.insert(key, value)
                message = f"'{key}':'{value}' insertado/actualizado con {algorithm_type}."
                operation_result = "success"
            elif operation == 'search':
                result = table.search(key)
                message = f"Búsqueda de '{key}' en {algorithm_type}."
                operation_result = result
            else:
                return Response({"error": "Operación no válida. Use 'insert' o 'search'."}, status=status.HTTP_400_BAD_REQUEST)

            table_state = table.get_state()
            self.save_log_to_db(
                algorithm_type=algorithm_type,
                operation_type=operation,
                key=key,
                value=value,
                result=operation_result,
                table_state=table_state,
                collisions=table_state['collisions_count'],
                probes=table_state['probes_count']
            )
            return Response({
                "message": message,
                "result": operation_result, # Para búsqueda
                "table_state": table_state
            }, status=status.HTTP_200_OK)

        except Exception as e:
            error_message = f"Error en la operación de hashing: {e}"
            table_state = table.get_state() # Intentar obtener el estado antes de guardar el error
            self.save_log_to_db(
                algorithm_type=algorithm_type,
                operation_type=operation,
                key=key,
                value=value,
                result=f"Error: {e}",
                table_state=table_state,
                collisions=table_state['collisions_count'],
                probes=table_state['probes_count']
            )
            return Response({"error": error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HashingStateView(HashingBaseView):
    def get(self, request, algorithm_type):
        table = self.get_hashing_table(algorithm_type)
        if not table:
            return Response({"error": "Algoritmo de hashing no válido."}, status=status.HTTP_400_BAD_REQUEST)

        # Las estadísticas de colisiones/sondas se resetearon en la última operación.
        # Si quieres que persistan para un estado general, tendrías que modificar el modelo.
        # Por ahora, solo reportan las de la última operación.
        return Response(table.get_state(), status=status.HTTP_200_OK)

class ResetHashingStateView(HashingBaseView):
    def post(self, request, algorithm_type):
        with transaction.atomic():
            if algorithm_type == 'all':
                HashTableSlot.objects.all().delete()
                ChainedElement.objects.all().delete()
                # Re-inicializar las instancias para que los slots se creen de nuevo
                for alg_type in _hashing_tables.keys():
                    if alg_type == 'chaining':
                        _hashing_tables[alg_type] = ChainingHashTable(TABLE_SIZE)
                    elif alg_type == 'linear_probing':
                        _hashing_tables[alg_type] = LinearProbingHashTable(TABLE_SIZE)
                    elif alg_type == 'quadratic_probing':
                        _hashing_tables[alg_type] = QuadraticProbingHashTable(TABLE_SIZE)
                    elif alg_type == 'double_hashing':
                        _hashing_tables[alg_type] = DoubleHashingHashTable(TABLE_SIZE)
                message = "Todas las tablas hash han sido reseteadas y re-inicializadas en la base de datos."
            else:
                table = self.get_hashing_table(algorithm_type)
                if not table:
                    return Response({"error": "Algoritmo de hashing no válido."}, status=status.HTTP_400_BAD_REQUEST)

                # Eliminar solo los slots y elementos para el algoritmo específico
                HashTableSlot.objects.filter(algorithm_type=algorithm_type).delete()
                if algorithm_type == 'chaining':
                    # Para encadenamiento, necesitamos eliminar los elementos encadenados asociados
                    # (CASCADE en FK ya lo hace, pero si quieres ser explícito)
                    pass # El delete de HashTableSlot ya se encarga por CASCADE

                # Re-inicializar solo la tabla específica
                if algorithm_type == 'chaining':
                    _hashing_tables[algorithm_type] = ChainingHashTable(TABLE_SIZE)
                elif algorithm_type == 'linear_probing':
                    _hashing_tables[algorithm_type] = LinearProbingHashTable(TABLE_SIZE)
                elif algorithm_type == 'quadratic_probing':
                    _hashing_tables[algorithm_type] = QuadraticProbingHashTable(TABLE_SIZE)
                elif algorithm_type == 'double_hashing':
                    _hashing_tables[algorithm_type] = DoubleHashingHashTable(TABLE_SIZE)
                message = f"La tabla hash '{algorithm_type}' ha sido reseteada y re-inicializada en la base de datos."

        return Response({"message": message}, status=status.HTTP_200_OK)

class HashingLogsView(APIView):
    def get(self, request):
        try:
            # Limitar a los últimos 100 logs para evitar sobrecarga
            logs = HashingLog.objects.all().order_by('-timestamp')[:100]
            # Serializar los logs (Django REST Framework ya ayuda con esto si usas Serializers)
            # Para simplificar, convertimos a dict directamente aquí
            serialized_logs = []
            for log in logs:
                serialized_logs.append({
                    'id': log.id,
                    'algorithm_type': log.algorithm_type,
                    'operation_type': log.operation_type,
                    'key': log.key,
                    'value': log.value,
                    'timestamp': log.timestamp.isoformat(),
                    'result': log.result,
                    'table_state': log.table_state_json,
                    'collisions': log.collisions,
                    'probes': log.probes,
                })
            return Response(serialized_logs, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Error al recuperar logs de MySQL: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)