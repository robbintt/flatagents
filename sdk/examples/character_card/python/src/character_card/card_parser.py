"""
Character Card Parser

Extracts character data from PNG/APNG/JSON files following:
- V1: Flat structure (TavernCardV1)
- V2: malfoyslastname/character-card-spec-v2 (chara_card_v2)
- V3: kwaroran/character-card-spec-v3 (chara_card_v3)

Character data in PNG files is stored in tEXt chunk as base64-encoded
JSON with keyword "chara" (case-insensitive).

Best-effort parsing: missing fields get sensible defaults.
"""

import base64
import json
import struct
from pathlib import Path
from typing import Any, Dict, Optional


def read_png_text_chunks(filepath: str) -> Dict[str, str]:
    """
    Read all tEXt chunks from a PNG file.
    
    Returns dict of keyword -> value for all tEXt chunks found.
    Handles tEXt chunks in any position (not just after IHDR).
    """
    text_chunks = {}
    
    with open(filepath, 'rb') as f:
        # Verify PNG signature
        sig = f.read(8)
        if sig != b'\x89PNG\r\n\x1a\n':
            raise ValueError("Not a valid PNG file")
        
        # Read all chunks, looking for tEXt anywhere
        while True:
            length_bytes = f.read(4)
            if len(length_bytes) < 4:
                break
            
            length = struct.unpack('>I', length_bytes)[0]
            chunk_type = f.read(4)
            
            # Handle potential read errors
            if len(chunk_type) < 4:
                break
                
            chunk_type_str = chunk_type.decode('ascii', errors='ignore')
            data = f.read(length)
            crc = f.read(4)  # Skip CRC
            
            # Extract tEXt chunks
            if chunk_type_str == 'tEXt' and len(data) > 0:
                null_idx = data.find(b'\x00')
                if null_idx != -1:
                    try:
                        keyword = data[:null_idx].decode('latin-1')
                        value = data[null_idx + 1:].decode('latin-1')
                        text_chunks[keyword.lower()] = value
                    except Exception:
                        pass  # Skip malformed chunks
            
            # Also check iTXt (international text) and zTXt (compressed)
            elif chunk_type_str == 'iTXt' and len(data) > 0:
                null_idx = data.find(b'\x00')
                if null_idx != -1:
                    try:
                        keyword = data[:null_idx].decode('utf-8')
                        # iTXt has more complex structure, try to find the text
                        # Format: keyword\x00compression\x00lang\x00translated\x00text
                        rest = data[null_idx + 1:]
                        # Skip compression flag and method
                        if len(rest) > 2:
                            rest = rest[2:]
                            # Find language tag end
                            lang_end = rest.find(b'\x00')
                            if lang_end != -1:
                                rest = rest[lang_end + 1:]
                                # Find translated keyword end
                                trans_end = rest.find(b'\x00')
                                if trans_end != -1:
                                    value = rest[trans_end + 1:].decode('utf-8', errors='ignore')
                                    text_chunks[keyword.lower()] = value
                    except Exception:
                        pass
            
            if chunk_type_str == 'IEND':
                break
    
    return text_chunks


def extract_character_json(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Extract character JSON from a PNG file.
    
    Looks for tEXt/iTXt chunk with keyword "chara" (case-insensitive)
    containing base64-encoded JSON.
    
    Returns:
        Parsed JSON dict, or None if not found
    """
    text_chunks = read_png_text_chunks(filepath)
    
    # Look for "chara" key (case-insensitive already from read_png_text_chunks)
    chara_data = text_chunks.get('chara')
    
    if not chara_data:
        return None
    
    # Decode base64 and parse JSON
    try:
        # Handle potential padding issues
        padding = 4 - len(chara_data) % 4
        if padding != 4:
            chara_data += '=' * padding
        
        json_str = base64.b64decode(chara_data).decode('utf-8')
        return json.loads(json_str)
    except Exception:
        # Try without padding fix
        try:
            json_str = base64.b64decode(chara_data).decode('utf-8')
            return json.loads(json_str)
        except Exception:
            return None


def detect_version(raw: Dict[str, Any]) -> str:
    """
    Detect character card version.
    
    Returns: 'v1', 'v2', or 'v3'
    """
    spec = raw.get('spec', '')
    
    if spec == 'chara_card_v3':
        return 'v3'
    elif spec == 'chara_card_v2':
        return 'v2'
    else:
        # V1 has flat structure without 'spec' field
        return 'v1'


def parse_card(filepath: str) -> Dict[str, Any]:
    """
    Parse a character card file (PNG, APNG, or JSON).
    
    Supports V1, V2, and V3 specifications with best-effort loading.
    Missing fields get sensible defaults.
    
    Args:
        filepath: Path to PNG or JSON character card
        
    Returns:
        Normalized character data dict with all available fields
    """
    path = Path(filepath)
    raw = None
    
    # Load raw data based on file type
    if path.suffix.lower() in ('.png', '.apng'):
        raw = extract_character_json(filepath)
        if raw is None:
            raise ValueError(f"No character data found in {filepath}")
    elif path.suffix.lower() == '.json':
        try:
            with open(filepath, encoding='utf-8') as f:
                raw = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON: {e}")
    else:
        # Try as JSON anyway
        try:
            with open(filepath, encoding='utf-8') as f:
                raw = json.load(f)
        except Exception:
            raise ValueError(f"Unsupported file type: {path.suffix}")
    
    if not raw:
        raise ValueError("Empty character data")
    
    # Detect version and extract data
    version = detect_version(raw)
    
    if version in ('v2', 'v3'):
        # V2/V3: data is nested under 'data' key
        data = raw.get('data', {})
        if not data:
            # Fallback: maybe data is at root level
            data = raw
    else:
        # V1: flat structure
        data = raw
    
    # Build normalized structure with defaults for all fields
    # Core fields (V1+)
    result = {
        'name': _get_str(data, 'name', 'Unknown'),
        'description': _get_str(data, 'description'),
        'personality': _get_str(data, 'personality'),
        'scenario': _get_str(data, 'scenario'),
        'first_mes': _get_str(data, 'first_mes'),
        'mes_example': _get_str(data, 'mes_example'),
    }
    
    # V2+ fields
    result.update({
        'system_prompt': _get_str(data, 'system_prompt'),
        'post_history_instructions': _get_str(data, 'post_history_instructions'),
        'alternate_greetings': _get_list(data, 'alternate_greetings'),
        'creator_notes': _get_str(data, 'creator_notes'),
        'tags': _get_list(data, 'tags'),
        'creator': _get_str(data, 'creator'),
        'character_version': _get_str(data, 'character_version'),
        'character_book': data.get('character_book'),
        'extensions': data.get('extensions', {}),
    })
    
    # V3+ fields
    result.update({
        'nickname': _get_str(data, 'nickname'),
        'source': _get_list(data, 'source'),
        'group_only_greetings': _get_list(data, 'group_only_greetings'),
        'assets': data.get('assets', []),
        'creator_notes_multilingual': data.get('creator_notes_multilingual', {}),
        'creation_date': data.get('creation_date'),
        'modification_date': data.get('modification_date'),
    })
    
    # Metadata about the card itself
    result['_version'] = version
    result['_spec'] = raw.get('spec', 'v1')
    result['_spec_version'] = raw.get('spec_version', '1.0')
    
    return result


def _get_str(data: Dict, key: str, default: str = '') -> str:
    """Safely get string value with default."""
    val = data.get(key)
    if val is None:
        return default
    return str(val) if not isinstance(val, str) else val


def _get_list(data: Dict, key: str) -> list:
    """Safely get list value with default empty list."""
    val = data.get(key)
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]  # Wrap single value in list
