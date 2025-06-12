# app/crud/order_status_log.py

from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.order_status_log import OrderStatusLog
from app.models.user import User
from app.models.account import Account
from app.schemas.order_status_log import OrderStatusLogCreate
from typing import List, Optional

def create_order_status_log(db: Session, log: OrderStatusLogCreate) -> OrderStatusLog:
    """
    สร้าง log การเปลี่ยนสถานะออเดอร์ใหม่
    """
    db_log = OrderStatusLog(**log.dict())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_order_status_logs(db: Session, order_id: int) -> List[OrderStatusLog]:
    """
    ดึงประวัติการเปลี่ยนสถานะของออเดอร์
    """
    return (
        db.query(OrderStatusLog)
        .filter(OrderStatusLog.order_id == order_id)
        .order_by(desc(OrderStatusLog.created_at))
        .all()
    )

def get_order_status_logs_with_user_info(db: Session, order_id: int) -> List[dict]:
    """
    ดึงประวัติการเปลี่ยนสถานะพร้อมข้อมูลผู้เปลี่ยน
    """
    logs = (
        db.query(OrderStatusLog, Account.name.label('changed_by_name'))
        .outerjoin(User, OrderStatusLog.changed_by == User.id)
        .outerjoin(Account, User.account_id == Account.id)
        .filter(OrderStatusLog.order_id == order_id)
        .order_by(desc(OrderStatusLog.created_at))
        .all()
    )
    
    result = []
    for log, changed_by_name in logs:
        result.append({
            "id": log.id,
            "order_id": log.order_id,
            "old_status": log.old_status,
            "new_status": log.new_status,
            "reason": log.reason,
            "changed_by": log.changed_by,
            "created_at": log.created_at,
            "changed_by_name": changed_by_name or "Unknown"
        })
    
    return result

def get_all_order_status_logs(db: Session, skip: int = 0, limit: int = 100) -> List[OrderStatusLog]:
    """
    ดึงประวัติการเปลี่ยนสถานะทั้งหมด
    """
    return (
        db.query(OrderStatusLog)
        .order_by(desc(OrderStatusLog.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_recent_status_changes(db: Session, limit: int = 20) -> List[dict]:
    """
    ดึงการเปลี่ยนสถานะล่าสุด
    """
    logs = (
        db.query(OrderStatusLog, Account.name.label('changed_by_name'))
        .outerjoin(User, OrderStatusLog.changed_by == User.id)
        .outerjoin(Account, User.account_id == Account.id)
        .order_by(desc(OrderStatusLog.created_at))
        .limit(limit)
        .all()
    )
    
    result = []
    for log, changed_by_name in logs:
        result.append({
            "id": log.id,
            "order_id": log.order_id,
            "old_status": log.old_status,
            "new_status": log.new_status,
            "reason": log.reason,
            "changed_by": log.changed_by,
            "created_at": log.created_at,
            "changed_by_name": changed_by_name or "Unknown"
        })
    
    return result
