from abc import ABC, abstractmethod
from django.db import transaction
from .models import HashTableSlot, ChainedElement

class HashTable(ABC):
    """
    Clase abstracta para definir la interfaz de una tabla hash,
    que interactúa con la base de datos.
    """
    def __init__(self, size, algorithm_type):
        self.size = size
        self.algorithm_type = algorithm_type
        self.collisions_count = 0
        self.probes_count = 0
        self._initialize_table_slots()

    def _initialize_table_slots(self):
        """Asegura que los slots de la tabla existan en la DB."""
        with transaction.atomic():
            for i in range(self.size):
                HashTableSlot.objects.get_or_create(
                    algorithm_type=self.algorithm_type,
                    slot_index=i,
                    defaults={'key_value': None, 'actual_value': None}
                )

    @abstractmethod
    def _hash_function(self, key):
        """Función hash primaria."""
        pass

    @abstractmethod
    def insert(self, key, value):
        """Inserta un par clave-valor en la tabla hash."""
        pass

    @abstractmethod
    def search(self, key):
        """Busca un valor en la tabla hash."""
        pass

    def reset_stats(self):
        self.collisions_count = 0
        self.probes_count = 0

    def get_state(self):
        """Retorna el estado actual de la tabla hash para visualización."""
        table_data = []
        slots = HashTableSlot.objects.filter(algorithm_type=self.algorithm_type).order_by('slot_index')

        for slot in slots:
            if self.algorithm_type == 'chaining':
                # Para encadenamiento, obtener los elementos encadenados
                chained_items = []
                for item in slot.chained_elements.all():
                    chained_items.append({'key': item.key_value, 'value': item.actual_value})
                table_data.append(chained_items)
            else:
                # Para sondeo, solo el elemento del slot
                table_data.append({'key': slot.key_value, 'value': slot.actual_value} if slot.key_value else None)

        return {
            "size": self.size,
            "table": table_data,
            "collisions_count": self.collisions_count,
            "probes_count": self.probes_count,
            "algorithm": self.algorithm_type
        }

class ChainingHashTable(HashTable):
    """
    Implementación de la tabla hash con Encadenamiento usando MySQL.
    """
    def __init__(self, size):
        super().__init__(size, 'chaining')

    def _hash_function(self, key):
        return hash(key) % self.size

    def insert(self, key, value):
        self.reset_stats()
        index = self._hash_function(key)
        self.probes_count += 1

        with transaction.atomic():
            slot, created = HashTableSlot.objects.get_or_create(
                algorithm_type=self.algorithm_type,
                slot_index=index
            )
            if not created: # Si el slot ya existía, potencial colisión si hay elementos
                if ChainedElement.objects.filter(slot=slot).exists():
                    self.collisions_count += 1

            # Intentar actualizar el elemento si ya existe en la cadena
            updated = False
            try:
                existing_element = ChainedElement.objects.get(slot=slot, key_value=key)
                existing_element.actual_value = value
                existing_element.save()
                updated = True
            except ChainedElement.DoesNotExist:
                pass

            if not updated:
                # Crear nuevo elemento si no existe
                ChainedElement.objects.create(slot=slot, key_value=key, actual_value=value)


    def search(self, key):
        self.reset_stats()
        index = self._hash_function(key)
        self.probes_count += 1

        try:
            slot = HashTableSlot.objects.get(algorithm_type=self.algorithm_type, slot_index=index)
            chained_elements = ChainedElement.objects.filter(slot=slot)
            for item in chained_elements:
                self.probes_count += 1 # Cada elemento en la cadena es una sonda
                if item.key_value == key:
                    return item.actual_value
            return None # No encontrado en la cadena
        except HashTableSlot.DoesNotExist:
            return None # Slot no existe, clave no está aquí

class LinearProbingHashTable(HashTable):
    """
    Implementación de la tabla hash con Sondeo Lineal usando MySQL.
    """
    def __init__(self, size):
        super().__init__(size, 'linear_probing')

    def _hash_function(self, key):
        return hash(key) % self.size

    def insert(self, key, value):
        self.reset_stats()
        initial_index = self._hash_function(key)
        self.probes_count += 1

        for i in range(self.size):
            index = (initial_index + i) % self.size
            slot = HashTableSlot.objects.get(algorithm_type=self.algorithm_type, slot_index=index)

            if slot.key_value is None: # Slot vacío
                slot.key_value = key
                slot.actual_value = value
                slot.save()
                return
            elif slot.key_value == key: # Actualizar si la clave ya existe
                slot.actual_value = value
                slot.save()
                return
            else: # Colisión, el slot está ocupado por otra clave
                self.collisions_count += 1
                self.probes_count += 1 # Sonda adicional para el siguiente intento
        raise Exception("Tabla hash llena. No se pudo insertar el elemento.")


    def search(self, key):
        self.reset_stats()
        initial_index = self._hash_function(key)
        self.probes_count += 1

        for i in range(self.size):
            index = (initial_index + i) % self.size
            slot = HashTableSlot.objects.get(algorithm_type=self.algorithm_type, slot_index=index)

            if slot.key_value is None: # Slot vacío, no se encontró
                return None
            elif slot.key_value == key: # Clave encontrada
                return slot.actual_value
            self.probes_count += 1 # Sonda adicional para el siguiente intento
        return None # Recorrió toda la tabla, no se encontró

class QuadraticProbingHashTable(HashTable):
    """
    Implementación de la tabla hash con Sondeo Cuadrático usando MySQL.
    """
    def __init__(self, size):
        super().__init__(size, 'quadratic_probing')

    def _hash_function(self, key):
        return hash(key) % self.size

    def insert(self, key, value):
        self.reset_stats()
        initial_index = self._hash_function(key)
        self.probes_count += 1

        for i in range(self.size):
            offset = i * i
            index = (initial_index + offset) % self.size
            slot = HashTableSlot.objects.get(algorithm_type=self.algorithm_type, slot_index=index)

            if slot.key_value is None:
                slot.key_value = key
                slot.actual_value = value
                slot.save()
                return
            elif slot.key_value == key:
                slot.actual_value = value
                slot.save()
                return
            else:
                self.collisions_count += 1
                self.probes_count += 1
        raise Exception("Tabla hash llena. No se pudo insertar el elemento.")

    def search(self, key):
        self.reset_stats()
        initial_index = self._hash_function(key)
        self.probes_count += 1

        for i in range(self.size):
            offset = i * i
            index = (initial_index + offset) % self.size
            slot = HashTableSlot.objects.get(algorithm_type=self.algorithm_type, slot_index=index)

            if slot.key_value is None:
                return None
            elif slot.key_value == key:
                return slot.actual_value
            self.probes_count += 1
        return None

class DoubleHashingHashTable(HashTable):
    """
    Implementación de la tabla hash con Doble Hashing usando MySQL.
    """
    def __init__(self, size):
        super().__init__(size, 'double_hashing')

    def _hash_function(self, key):
        return hash(key) % self.size

    def _hash_function2(self, key):
        # Una segunda función hash que no retorna 0.
        # Se recomienda usar un primo para esto.
        # Ejemplo: 7 - (hash(key) % 7)
        # Asegúrate de que el resultado no sea 0 para evitar bucles infinitos si h2 es 0.
        # Aquí, usaremos un primo grande para evitar que sea 0 fácilmente.
        h = hash(key) % (self.size - 1) # Asegura que el resultado sea < size-1
        return h + 1 # Asegura que el resultado nunca sea 0

    def insert(self, key, value):
        self.reset_stats()
        h1 = self._hash_function(key)
        h2 = self._hash_function2(key)
        self.probes_count += 1

        for i in range(self.size):
            index = (h1 + i * h2) % self.size
            slot = HashTableSlot.objects.get(algorithm_type=self.algorithm_type, slot_index=index)

            if slot.key_value is None:
                slot.key_value = key
                slot.actual_value = value
                slot.save()
                return
            elif slot.key_value == key:
                slot.actual_value = value
                slot.save()
                return
            else:
                self.collisions_count += 1
                self.probes_count += 1
        raise Exception("Tabla hash llena. No se pudo insertar el elemento.")

    def search(self, key):
        self.reset_stats()
        h1 = self._hash_function(key)
        h2 = self._hash_function2(key)
        self.probes_count += 1

        for i in range(self.size):
            index = (h1 + i * h2) % self.size
            slot = HashTableSlot.objects.get(algorithm_type=self.algorithm_type, slot_index=index)

            if slot.key_value is None:
                return None
            elif slot.key_value == key:
                return slot.actual_value
            self.probes_count += 1
        return None