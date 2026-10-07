import random

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

def snake_collision_measure():
    qc = QuantumCircuit(1, 1)
    qc.ry(np.pi / 8, 0)
    qc.measure(0, 0)
    return Statevector.from_instruction(qc)

class QuantumState:
    def __init__(self):
        self._operations = {}
        self._next_ghost_id = 0
        self.qc = QuantumCircuit(0)

    @property
    def ghost_phases(self):
        return {
            ghost_id: operations[-1][1]
            for ghost_id, operations in self._operations.items()
            if operations[-1][0] == "ry"
        }

    @property
    def ghost_gates(self):
        return {ghost_id: list(operations) for ghost_id, operations in self._operations.items()}

    def add_ghost(self):
        ghost_id = self._next_ghost_id
        self._next_ghost_id += 1
        self._operations[ghost_id] = [("h", None)]
        self._rebuild_circuit()
        return ghost_id

    def apply_green_apple(self):
        angle = random.choice((np.pi / 4, 3 * np.pi / 4))
        for operations in self._operations.values():
            operations.append(("ry", angle))
        self._rebuild_circuit()
        return angle

    def measure(self):
        if not self._operations:
            return {}

        ghost_ids = list(self._operations)
        state = Statevector.from_instruction(self.qc)
        outcomes = {}
        for qubit, ghost_id in enumerate(ghost_ids):
            outcome, state = state.measure([qubit])
            outcomes[ghost_id] = int(outcome)

        self._operations.clear()
        self._rebuild_circuit()
        return outcomes

    def remove_ghost(self, ghost_id):
        if ghost_id in self._operations:
            del self._operations[ghost_id]
            self._rebuild_circuit()

    def _rebuild_circuit(self):
        ghost_ids = list(self._operations)
        qc = QuantumCircuit(len(ghost_ids))
        for qubit, ghost_id in enumerate(ghost_ids):
            for gate, angle in self._operations[ghost_id]:
                if gate == "h":
                    qc.h(qubit)
                else:
                    qc.ry(angle, qubit)
        self.qc = qc
