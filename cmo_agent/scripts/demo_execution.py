#!/usr/bin/env python3
"""
Demo of CMO Agent Execution Engine
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

try:
    from scripts.run_execution import ExecutionEngine
except ImportError:
    from run_execution import ExecutionEngine


async def demo_job_execution():
    """Demo job submission and monitoring"""
    print("🚀 CMO Agent Execution Engine Demo")
    print("=" * 50)

    # Initialize engine
    engine = ExecutionEngine(num_workers=2)

    if not await engine.initialize():
        print("❌ Failed to initialize engine")
        return

    print("✅ Engine initialized successfully")

    # Submit a demo job
    job_goal = "Find 5 Python repos with CI, extract 3 maintainers each (demo)"
    print(f"\n📝 Submitting job: {job_goal}")

    try:
        job_id = await engine.submit_job(job_goal, created_by="demo_user")
        print(f"✅ Job submitted with ID: {job_id}")

        # Monitor job progress
        print("\n📊 Monitoring job progress...")
        print("(Press Ctrl+C to stop monitoring)")

        while True:
            status = await engine.get_job_status(job_id)

            if status:
                print(f"\n🔄 Status: {status['status']}")
                print(f"🎯 Goal: {status['goal']}")

                if status['progress']:
                    progress = status['progress']
                    print(f"📈 Stage: {progress['stage']}")
                    print(f"🔢 Step: {progress['step']}")
                    print(f"📊 Metrics: {progress['metrics']}")

                if status['status'] in ['completed', 'failed', 'cancelled']:
                    print(f"🏁 Job finished with status: {status['status']}")
                    break

            await asyncio.sleep(2)  # Check every 2 seconds

    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")

        # Cancel the job
        cancelled = await engine.cancel_job(job_id)
        if cancelled:
            print(f"✅ Job {job_id} cancelled")
        else:
            print(f"❌ Failed to cancel job {job_id}")

    except Exception as e:
        print(f"\n💥 Demo error: {e}")
        import traceback
        traceback.print_exc()


async def demo_engine_stats():
    """Demo engine statistics"""
    print("\n📊 Engine Statistics Demo")
    print("=" * 30)

    engine = ExecutionEngine(num_workers=1)

    if await engine.initialize():
        stats = engine.get_stats()
        print(f"🚀 Engine Status: {stats['engine_status']}")
        print(f"👷 Workers: {stats['workers']}")
        print(f"📋 Jobs: {stats['jobs']}")
        print(f"🔄 Queue: {stats['queue']}")


async def demo_job_management():
    """Demo job management operations"""
    print("\n🎮 Job Management Demo")
    print("=" * 25)

    engine = ExecutionEngine(num_workers=1)

    if not await engine.initialize():
        return

    # Submit a job
    job_id = await engine.submit_job("Demo job for management operations", "demo")
    print(f"✅ Job created: {job_id}")

    # Get status
    status = await engine.get_job_status(job_id)
    print(f"📊 Initial status: {status['status']}")

    # Try to pause (might fail if not running yet)
    paused = await engine.pause_job(job_id)
    print(f"⏸️ Pause result: {'Success' if paused else 'Failed/Not running'}")

    # Try to resume
    resumed = await engine.resume_job(job_id)
    print(f"▶️ Resume result: {'Success' if resumed else 'Failed/Not paused'}")

    # Cancel job
    cancelled = await engine.cancel_job(job_id)
    print(f"❌ Cancel result: {'Success' if cancelled else 'Failed'}")

    # Check final status
    final_status = await engine.get_job_status(job_id)
    print(f"🏁 Final status: {final_status['status']}")


async def main():
    """Run all demos"""
    try:
        await demo_engine_stats()
        await demo_job_management()

        print("\n🎯 Starting full job execution demo...")
        print("Note: This will try to run an actual CMO Agent job")
        print("Make sure you have API keys configured if you want it to work fully")

        await demo_job_execution()

    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n🎉 All demos completed!")
    print("💡 Next steps:")
    print("1. Set up API keys in .env file")
    print("2. Run: python scripts/run_execution.py --job 'Find 2k Py maintainers'")
    print("3. Monitor: python scripts/run_execution.py --status <job_id>")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
