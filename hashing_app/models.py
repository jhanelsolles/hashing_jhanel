from django.db import models
from django.utils import timezone
import json

# Constantes para los tipos de algoritmo
ALGORITHM_CHOICES = [
    ('chaining', 'Encadenamiento'),
    ('linear_probing', 'Sondeo Lineal'),
    ('quadratic_probing', 'Sondeo Cuadrático'),
    ('double_hashing', 'Doble Hashing'),
]

class HashTableSlot(models.Model):
    """
    Representa un slot (cubo) en una tabla hash.
    Cada instancia de este modelo es para un algoritmo y un índice específicos.
    """
    algorithm_type = models.CharField(max_length=50, choices=ALGORITHM_CHOICES)
    slot_index = models.IntegerField()
    # Para sondeo: Almacena la clave y el valor directamente
    key_value = models.CharField(max_length=255, null=True, blank=True)
    actual_value = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('algorithm_type', 'slot_index') # Un slot único por algoritmo y índice

    def __str__(self):
        return f"{self.algorithm_type} - Slot {self.slot_index}: {self.key_value}"

class ChainedElement(models.Model):
    """
    Para el algoritmo de encadenamiento: representa un elemento en una cadena.
    """
    slot = models.ForeignKey(HashTableSlot, on_delete=models.CASCADE, related_name='chained_elements')
    key_value = models.CharField(max_length=255)
    actual_value = models.TextField()

    class Meta:
        unique_together = ('slot', 'key_value') # Una clave única por slot en el encadenamiento

    def __str__(self):
        return f"Chained in Slot {self.slot.slot_index}: {self.key_value}"

class HashingLog(models.Model):
    """
    Registra cada operación de hashing y el estado de la tabla en ese momento.
    """
    algorithm_type = models.CharField(max_length=50, choices=ALGORITHM_CHOICES)
    operation_type = models.CharField(max_length=10, choices=[('insert', 'Insertar'), ('search', 'Buscar')])
    key = models.CharField(max_length=255)
    value = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    result = models.TextField(null=True, blank=True)
    # Guardaremos el estado de la tabla como un JSON string
    table_state_json = models.JSONField(default=dict)
    collisions = models.IntegerField(default=0)
    probes = models.IntegerField(default=0)

    def __str__(self):
        return f"Log {self.pk}: {self.algorithm_type} - {self.operation_type} '{self.key}'"