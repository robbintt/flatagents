"""
Google Cloud Platform backends for FlatMachines.

Provides Firestore-based persistence and result storage for
Cloud Functions and Firebase deployments.

Usage:
    from flatmachines.gcp import FirestoreBackend
    
    backend = FirestoreBackend(collection="flatmachines")
    machine = FlatMachine(
        config_file="machine.yml",
        persistence=backend,
        result_backend=backend
    )

Requirements:
    pip install flatmachines[gcp]
"""

from .firestore import FirestoreBackend

__all__ = [
    "FirestoreBackend",
]
