#!/usr/bin/env python3
"""
Seed jobs into the work pool.

Usage:
    python seed_jobs.py --count 10
    python seed_jobs.py --count 5 --pool my_pool
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from hooks import DistributedWorkerHooks


async def main():
    parser = argparse.ArgumentParser(description="Seed jobs into work pool")
    parser.add_argument("--count", "-n", type=int, default=5, help="Number of jobs to seed")
    parser.add_argument("--pool", "-p", default="default", help="Pool ID")
    parser.add_argument("--db", default=None, help="Database path (optional)")
    args = parser.parse_args()
    
    hooks = DistributedWorkerHooks(db_path=args.db)
    pool = hooks._work.pool(args.pool)
    
    print(f"Seeding {args.count} jobs into pool '{args.pool}'...")
    
    for i in range(args.count):
        job_data = {
            "job_number": i + 1,
            "message": f"Hello from job {i + 1}",
            "delay_seconds": 2,  # Echo processor will wait this long
        }
        
        job_id = await pool.push(job_data, {"max_retries": 3})
        print(f"  Created job {job_id[:8]}... (#{i + 1})")
    
    size = await pool.size()
    print(f"\n✅ Done! Pool now has {size} pending jobs.")


if __name__ == "__main__":
    asyncio.run(main())
