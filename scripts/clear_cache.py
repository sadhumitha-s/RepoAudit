
import os
import sys
import shutil
import redis
from supabase import create_client, Client

# Add backend to path to use config
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from config import get_settings

def clear_cache():
    settings = get_settings()
    
    # 1. Clear Redis
    try:
        print(f"Connecting to Redis at {settings.redis_url}...")
        r = redis.from_url(settings.redis_url)
        r.flushall()
        print("✅ Redis cache cleared (FLUSHALL).")
    except Exception as e:
        print(f"❌ Failed to clear Redis: {e}")

    # 2. Clear Supabase Audits
    try:
        print(f"Connecting to Supabase at {settings.supabase_url}...")
        supabase: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        # Deleting all audits. Using a filter that matches all is safer than no filter in some clients.
        # We delete all audits. repo and other meta can stay.
        res = supabase.table("audits").delete().neq("score", -1).execute()
        print(f"✅ Supabase 'audits' table cleared.")
    except Exception as e:
        print(f"❌ Failed to clear Supabase: {e}")

    # 3. Clear Local Clones
    try:
        clone_dir = settings.clone_base_dir
        if os.path.exists(clone_dir):
            shutil.rmtree(clone_dir)
            os.makedirs(clone_dir)
            print(f"✅ Local clones directory cleared: {clone_dir}")
        else:
            print(f"ℹ️ Local clones directory does not exist: {clone_dir}")
    except Exception as e:
        print(f"❌ Failed to clear local clones: {e}")

if __name__ == "__main__":
    confirm = input("⚠️ This will DELETE all audit history. Are you sure? (y/N): ")
    if confirm.lower() == 'y':
        clear_cache()
        print("\n✨ Workspace is now clean. Deploy the latest code and start fresh!")
    else:
        print("Operation cancelled.")
