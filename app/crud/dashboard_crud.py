# app/crud/dashboard_crud.py

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.order import Order
from app.models.user import User

def get_executive_dashboard_data(db: Session, period: str):
    now = datetime.utcnow()
    # กำหนดช่วงเวลาตาม period ที่รับมา
    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    elif period == "year":
        start_date = now - timedelta(days=365)
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = now

    # ดึงออเดอร์ในช่วงเวลาที่กำหนด
    orders = db.query(Order).filter(Order.created_at >= start_date, Order.created_at <= end_date).all()

    # จำนวนออเดอร์ทั้งหมดในช่วงเวลา
    total_orders = len(orders)

    # ยอดขายรวม (เฉพาะออเดอร์ที่ completed)
    total_sales = sum(order.total for order in orders if order.status == "completed")

    # จำนวนลูกค้าใหม่ (สมมติว่ามี attribute created_at ใน User)
    try:
        new_customers = db.query(User).filter(
            User.role == "customer",
            User.created_at >= start_date,
            User.created_at <= end_date
        ).count()
    except Exception:
        new_customers = 0

    # คำนวณข้อมูลของช่วงเวลาก่อนหน้า (previous period)
    period_delta = end_date - start_date
    previous_start = start_date - period_delta
    previous_end = start_date

    previous_orders_all = db.query(Order).filter(
        Order.created_at >= previous_start,
        Order.created_at < previous_end
    ).all()
    previous_total_sales = sum(order.total for order in previous_orders_all if order.status == "completed")
    previous_total_orders = len(previous_orders_all)
    try:
        previous_new_customers = db.query(User).filter(
            User.role == "customer",
            User.created_at >= previous_start,
            User.created_at <= previous_end
        ).count()
    except Exception:
        previous_new_customers = 0

    # คำนวณเปอร์เซ็นต์เปลี่ยนแปลง
    growth_rate = ((total_sales - previous_total_sales) / previous_total_sales * 100) if previous_total_sales > 0 else 0.0
    sales_change = ((total_sales - previous_total_sales) / previous_total_sales * 100) if previous_total_sales > 0 else 0.0
    orders_change = ((total_orders - previous_total_orders) / previous_total_orders * 100) if previous_total_orders > 0 else 0.0
    customers_change = ((new_customers - previous_new_customers) / previous_new_customers * 100) if previous_new_customers > 0 else 0.0

    # สรุปยอดขายรายวัน (เฉพาะ completed)
    daily_sales_dict = {}
    for order in orders:
        if order.status != "completed":
            continue
        order_date = order.created_at.strftime("%Y-%m-%d")
        daily_sales_dict[order_date] = daily_sales_dict.get(order_date, 0) + order.total
    daily_sales = [{"date": date, "amount": amount} for date, amount in sorted(daily_sales_dict.items())]

    # สินค้าขายดี: สมมติว่า order.item เป็น JSON string ของรายการสินค้า
    product_sales = {}
    for order in orders:
        try:
            items = json.loads(order.item) if order.item else []
            for item in items:
                name = item.get("name", "Unknown")
                quantity = item.get("quantity", 0)
                product_sales[name] = product_sales.get(name, 0) + quantity
        except Exception:
            continue
    top_products = [
        {"name": name, "quantity": quantity}
        for name, quantity in sorted(product_sales.items(), key=lambda x: x[1], reverse=True)
    ][:5]

    # ออเดอร์ล่าสุด (จำกัด 5 รายการ)
    recent_orders_query = db.query(Order).filter(
        Order.created_at >= start_date, Order.created_at <= end_date
    ).order_by(Order.created_at.desc()).limit(5).all()
    recent_orders = []
    for order in recent_orders_query:
        recent_orders.append({
            "id": order.order_id,
            "customer": order.email,
            "total": order.total,
            "status": order.status
        })

    # สรุปประสิทธิภาพพนักงาน (group by assigned_to)
    staff_dict = {}
    for order in orders:
        if order.assigned_to:
            staff_dict.setdefault(order.assigned_to, []).append(order)
    staff_performance = []
    for staff_id, orders_list in staff_dict.items():
        staff_user = db.query(User).filter(User.id == staff_id).first()
        # เนื่องจาก model User ไม่มี attribute 'name' ให้ใช้ email แทน
        staff_name = staff_user.email if staff_user else "Unknown"
        orders_handled = len(orders_list)
        avg_time = 0  # หากมีข้อมูลเวลาในการประมวลผลให้คำนวณจริง
        rating = 5   # กำหนดค่า dummy rating หากไม่มีข้อมูลจริง
        staff_performance.append({
            "name": staff_name,
            "orders_handled": orders_handled,
            "avg_time": avg_time,
            "rating": rating
        })

    return {
        "total_sales": total_sales,
        "total_orders": total_orders,
        "new_customers": new_customers,
        "growth_rate": round(growth_rate, 1),
        "sales_change": round(sales_change, 1),
        "orders_change": round(orders_change, 1),
        "customers_change": round(customers_change, 1),
        "daily_sales": daily_sales,
        "top_products": top_products,
        "recent_orders": recent_orders,
        "staff_performance": staff_performance
    }
