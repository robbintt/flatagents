"""
Google Cloud Platform backends for FlatAgents.

Provides Firestore-based persistence and result storage for
Cloud Functions and Firebase deployments.

Usage:
    from flatagents.gcp import FirestoreBackend
    
    backend = FirestoreBackend(collection="flatagents")
    machine = FlatMachine(
        config_file="machine.yml",
        persistence=backend,
        result_backend=backend
    )

Requirements:
    pip install google-cloud-firestore
"""

from .firestore import FirestoreBackend

__all__ = [
    "FirestoreBackend",
]
