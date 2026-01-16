"""
FlatAgents Parallelism - Google Cloud Function Handler

Demonstrates all backend interfaces in a cloud deployment:
- PersistenceBackend: Checkpoints for crash recovery
- ResultBackend: Collecting results from parallel machines
- ExecutionLock: Preventing duplicate runs
- MachineInvoker: Parallel execution, foreach, fire-and-forget launches

Uses Firestore in production, falls back to in-memory for local dev.
"""

import asyncio
import json
import os
import functions_framework
from flask import jsonify


def get_backends():
    """
    Get appropriate backends based on environment.
    
    Returns:
        tuple: (persistence, result_backend, lock, invoker)
    """
    # Check if we should force in-memory backends
    use_memory = os.environ.get("USE_MEMORY_BACKEND", "").lower() in ("1", "true", "yes")
    
    if use_memory:
        return _get_memory_backends()
    
    try:
        return _get_firestore_backends()
    except Exception as e:
        print(f"Firestore unavailable ({e}), falling back to in-memory backends")
        return _get_memory_backends()


def _get_memory_backends():
    """Get in-memory backends for local development."""
    from flatagents import InMemoryResultBackend
    from flatagents.persistence import MemoryBackend
    from flatagents.locking import NoOpLock
    from flatagents.actions import InlineInvoker
    
    print("Using in-memory backends (no persistence)")
    return MemoryBackend(), InMemoryResultBackend(), NoOpLock(), InlineInvoker()


def _get_firestore_backends():
    """Get Firestore backends for GCP deployment."""
    from flatagents.gcp import FirestoreBackend
    from flatagents.locking import NoOpLock  # TODO: Add FirestoreLock
    from flatagents.actions import InlineInvoker  # TODO: Add CloudTasksInvoker for true fire-and-forget
    
    collection = os.environ.get("FIRESTORE_COLLECTION", "flatagents-parallelism")
    backend = FirestoreBackend(collection=collection)
    
    # Test connection
    _ = backend.db
    print(f"Using Firestore backend (collection: {collection})")
    
    # Note: For production, you'd want:
    # - FirestoreLock for distributed locking
    # - CloudTasksInvoker or PubSubInvoker for true fire-and-forget launches
    return backend, backend, NoOpLock(), InlineInvoker()


@functions_framework.http
def parallelism(request):
    """
    HTTP Cloud Function entry point.
    
    Request body:
        {
            "type": "parallel_aggregation" | "foreach_sentiment" | "background_notifications",
            "texts": ["text1", "text2"],      // for parallel_aggregation or foreach_sentiment
            "message": "hello"                 // for background_notifications
        }
    
    Returns:
        {
            "result": "...",
            "execution_id": "uuid"
        }
    """
    from flatagents import FlatMachine
    
    # Parse request
    body = request.get_json(silent=True) or {}
    exec_type = body.get("type", "parallel_aggregation")
    texts = body.get("texts", ["Sample text 1", "Sample text 2"])
    message = body.get("message", "Hello from parallelism demo")
    
    # Validate
    if exec_type not in ("parallel_aggregation", "foreach_sentiment", "background_notifications"):
        return jsonify({"error": f"Invalid type: {exec_type}"}), 400
    
    if len(texts) > 10:
        return jsonify({"error": "Too many texts (max 10)"}), 400
    
    # Get backends
    persistence, result_backend, lock, invoker = get_backends()
    
    # Load machine config
    config_path = os.path.join(os.path.dirname(__file__), "config", "machine.yml")
    
    machine = FlatMachine(
        config_file=config_path,
        persistence=persistence,
        result_backend=result_backend,
        lock=lock,
        invoker=invoker
    )
    
    # Execute
    try:
        result = asyncio.run(machine.execute(input={
            "type": exec_type,
            "texts": texts,
            "message": message
        }))
        
        return jsonify({
            "result": result.get("result"),
            "execution_id": machine.execution_id
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "execution_id": machine.execution_id
        }), 500
