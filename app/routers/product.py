# app/routers/product.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.product import ProductCreate, ProductUpdate, ProductOut
from app.crud.product import create_product, get_product_by_id, get_all_products, update_product, delete_product

router = APIRouter(
    prefix="/products",
    tags=["Products"],
)

@router.post("/", response_model=ProductOut)
def create_new_product(product: ProductCreate, db: Session = Depends(get_db)):
    return create_product(db=db, product=product)

@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    db_product = get_product_by_id(db=db, product_id=product_id)
    if db_product:
        return db_product
    raise HTTPException(status_code=404, detail="Product not found")

@router.get("/", response_model=List[ProductOut])
def get_products(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    return get_all_products(db=db, skip=skip, limit=limit)

@router.put("/{product_id}", response_model=ProductOut)
def update_product_info(product_id: int, product: ProductUpdate, db: Session = Depends(get_db)):
    db_product = update_product(db=db, product_id=product_id, product=product)
    if db_product:
        return db_product
    raise HTTPException(status_code=404, detail="Product not found")

@router.delete("/{product_id}", response_model=ProductOut)
def delete_product_info(product_id: int, db: Session = Depends(get_db)):
    db_product = delete_product(db=db, product_id=product_id)
    if db_product:
        return db_product
    raise HTTPException(status_code=404, detail="Product not found")