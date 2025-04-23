# app/utils/product_categories.py

# กำหนดประเภทสินค้าตามรหัสสินค้า (product_id)
PRODUCT_CATEGORIES = {
    1: "arduino",     # Arduino Mega 2560
    2: "arduino",     # Arduino UNO WiFi Rev2
    3: "raspberry",   # Raspberry Pi Compute Module 4 IO Board
    4: "raspberry",   # Raspberry Pi 4 Power Supply
    5: "accessory",   # SparkFun RedBoard
    6: "raspberry",   # Raspberry Pi 7" Touchscreen Display
    7: "accessory",   # BeagleBone Black Rev C
    8: "arduino",     # Arduino Uno R3
    9: "accessory",   # Thunderboard EFM32GG12
    10: "accessory",  # MSP432 P401R LaunchPad Development Kit
    11: "sensor",     # RPI NOIR Camera V2
    12: "sensor",     # Power Profik Kit II
    13: "raspberry",  # Raspberry Pi 5 - 8GB RAM
    14: "sensor",     # Arducam
    15: "raspberry",  # Raspberry Pi AI Kit
    16: "accessory",  # Raspberry Pi Active Cooler
    17: "accessory",  # Arducam ABS Case for IMX... 25° 24mm Camera Boards
}

# ฟังก์ชันสำหรับดึงประเภทสินค้าจาก product_id
def get_product_category(product_id):
    """
    ดึงประเภทสินค้าจาก product_id
    
    Args:
        product_id (int): รหัสสินค้า
        
    Returns:
        str: ประเภทสินค้า (arduino, raspberry, sensor, accessory) หรือ 'other' ถ้าไม่พบ
    """
    return PRODUCT_CATEGORIES.get(product_id, "other")

# ฟังก์ชันสำหรับดึงรายการสินค้าในประเภทที่ระบุ
def get_products_by_category(products, category):
    """
    กรองรายการสินค้าตามประเภทที่ระบุ
    
    Args:
        products (list): รายการสินค้าทั้งหมด
        category (str): ประเภทสินค้าที่ต้องการ
        
    Returns:
        list: รายการสินค้าที่อยู่ในประเภทที่ระบุ
    """
    if category == "all":
        return products
    
    filtered_products = []
    for product in products:
        product_id = product.product_id
        if PRODUCT_CATEGORIES.get(product_id) == category:
            filtered_products.append(product)
    
    return filtered_products

# รายชื่อประเภทสินค้าทั้งหมด
CATEGORIES = {
    "all": "ทั้งหมด",
    "arduino": "Arduino",
    "raspberry": "Raspberry Pi",
    "sensor": "เซ็นเซอร์และโมดูล",
    "accessory": "อุปกรณ์เสริม IoT",
}