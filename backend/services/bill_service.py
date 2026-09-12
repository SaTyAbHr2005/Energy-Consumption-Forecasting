import os
from datetime import datetime
from typing import List, Dict, Any
from backend.services.auth_service import supabase_admin

def save_bill(user_id: str, bill_date: str, cost: float, consumption: float, storage_path: str):
    # Duplicate check
    res = supabase_admin.table('user_bills').select('id').eq('user_id', user_id).eq('bill_date', bill_date).execute()
    if res.data:
        raise ValueError(f"A bill for {bill_date} has already been uploaded.")
        
    created_at = datetime.utcnow().isoformat()
    record = {
        "user_id": user_id,
        "bill_date": bill_date,
        "cost": cost,
        "consumption": consumption,
        "storage_path": storage_path,
        "created_at": created_at
    }
    supabase_admin.table('user_bills').insert(record).execute()

def get_user_bills(user_id: str) -> List[Dict[str, Any]]:
    res = supabase_admin.table('user_bills').select('id, bill_date, cost, consumption, storage_path, created_at').eq('user_id', user_id).order('created_at', desc=True).execute()
    return res.data

def delete_bill(user_id: str, bill_id: int):
    res = supabase_admin.table('user_bills').delete().eq('id', bill_id).eq('user_id', user_id).execute()
    return len(res.data) > 0 if res.data else True
