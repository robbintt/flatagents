"""
FlatAgents Helloworld - Google Cloud Function Handler

This is the entry point for the Cloud Function.
In production: uses Firestore persistence.
In local dev: falls back to in-memory if Firestore unavailable.
"""

import asyncio
import json
import os
import functions_framework
from flask import jsonify


def get_backend():
    """
    Get appropriate backend based on environment.
    
    - If FIRESTORE_EMULATOR_HOST is set, use Firestore emulator
    - If running in Cloud Functions, use real Firestore
    - Otherwise, fall back to in-memory for local development
    """
    use_memory = os.environ.get("USE_MEMORY_BACKEND", "").lower() in ("1", "true", "yes")
    
    if use_memory:
        from flatagents import InMemoryResultBackend
        from flatagents.persistence import MemoryBackend
        print("Using in-memory backend (no persistence)")
        return MemoryBackend(), InMemoryResultBackend()
    
    try:
        from flatagents.gcp import FirestoreBackend
        collection = os.environ.get("FIRESTORE_COLLECTION", "flatagents-helloworld")
        backend = FirestoreBackend(collection=collection)
        # Test connection by accessing the db
        _ = backend.db  
        print(f"Using Firestore backend (collection: {collection})")
        return backend, backend
    except Exception as e:
        # Fall back to in-memory if Firestore fails
        print(f"Firestore unavailable ({e}), falling back to in-memory backend")
        from flatagents import InMemoryResultBackend
        from flatagents.persistence import MemoryBackend
        return MemoryBackend(), InMemoryResultBackend()


@functions_framework.http
def helloworld(request):
    """
    HTTP Cloud Function entry point.
    
    Request body:
        {
            "target": "Hello World"  // String to build char-by-char
        }
    
    Returns:
        {
            "result": "Hello World",
            "success": true,
            "execution_id": "uuid"
        }
    """
    from flatagents import FlatMachine
    
    # Parse request
    body = request.get_json(silent=True) or {}
    target = body.get("target", "Hello")
    
    # Validate input
    if len(target) > 50:
        return jsonify({"error": "Target string too long (max 50 chars)"}), 400
    
    # Set up backends (Firestore or in-memory fallback)
    persistence, result_backend = get_backend()
    
    # Load machine config (bundled with function)
    config_path = os.path.join(os.path.dirname(__file__), "config", "machine.yml")
    
    machine = FlatMachine(
        config_file=config_path,
        persistence=persistence,
        result_backend=result_backend
    )
    
    # Execute
    try:
        result = asyncio.run(machine.execute(input={"target": target}))
        
        return jsonify({
            "result": result.get("result"),
            "success": result.get("success", True),
            "execution_id": machine.execution_id
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "execution_id": machine.execution_id
        }), 500
