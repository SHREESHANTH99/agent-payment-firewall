"""Mock Store application for AI agent procurement and prompt injection evaluation."""
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic_settings import BaseSettings, SettingsConfigDict

from .data import get_default_products, get_default_reviews
from .variants import inject_variant_content


class StoreSettings(BaseSettings):
    STORE_SELLER_EMAIL: str = "seller@example.com"
    STORE_SELLER_EMAIL_2: str = "seller2@example.com"
    ATTACKER_EMAIL: str = "attacker@example.com"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = StoreSettings()

app = FastAPI(
    title="Apex Office Mock Store",
    description="Mock ecommerce procurement store with attack variants for AI payment firewall eval.",
    version="0.1.0",
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_products():
    return get_default_products(settings.STORE_SELLER_EMAIL)


@app.get("/health")
async def health():
    return {"status": "OK", "store": "mock-store"}


@app.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    variant: Optional[str] = Query("clean"),
):
    products = get_products()
    variant_info = inject_variant_content(
        variant=variant,
        page_type="catalog",
        seller_email=settings.STORE_SELLER_EMAIL,
        seller_email_2=settings.STORE_SELLER_EMAIL_2,
        attacker_email=settings.ATTACKER_EMAIL,
    )
    return templates.TemplateResponse(
        request=request,
        name="catalog.html",
        context={
            "products": products,
            "variant": variant or "clean",
            "variant_info": variant_info,
        },
    )


@app.get("/product/{product_id}", response_class=HTMLResponse)
async def product_page(
    request: Request,
    product_id: str,
    variant: Optional[str] = Query("clean"),
):
    products = get_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variant_info = inject_variant_content(
        variant=variant,
        page_type="product",
        seller_email=settings.STORE_SELLER_EMAIL,
        seller_email_2=settings.STORE_SELLER_EMAIL_2,
        attacker_email=settings.ATTACKER_EMAIL,
    )

    active_seller = variant_info.get("override_seller") or product["seller_email"]

    return templates.TemplateResponse(
        request=request,
        name="product.html",
        context={
            "product": product,
            "variant": variant or "clean",
            "variant_info": variant_info,
            "active_seller_email": active_seller,
        },
    )


@app.get("/checkout/{product_id}", response_class=HTMLResponse)
async def checkout_page(
    request: Request,
    product_id: str,
    variant: Optional[str] = Query("clean"),
):
    products = get_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variant_info = inject_variant_content(
        variant=variant,
        page_type="checkout",
        seller_email=settings.STORE_SELLER_EMAIL,
        seller_email_2=settings.STORE_SELLER_EMAIL_2,
        attacker_email=settings.ATTACKER_EMAIL,
    )

    active_seller = variant_info.get("override_seller") or product["seller_email"]

    return templates.TemplateResponse(
        request=request,
        name="checkout.html",
        context={
            "product": product,
            "variant": variant or "clean",
            "variant_info": variant_info,
            "active_seller_email": active_seller,
        },
    )


@app.get("/reviews/{product_id}", response_class=HTMLResponse)
async def reviews_page(
    request: Request,
    product_id: str,
    variant: Optional[str] = Query("clean"),
):
    products = get_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    reviews = get_default_reviews(product_id)
    variant_info = inject_variant_content(
        variant=variant,
        page_type="reviews",
        seller_email=settings.STORE_SELLER_EMAIL,
        seller_email_2=settings.STORE_SELLER_EMAIL_2,
        attacker_email=settings.ATTACKER_EMAIL,
    )

    return templates.TemplateResponse(
        request=request,
        name="reviews.html",
        context={
            "product": product,
            "reviews": reviews,
            "variant": variant or "clean",
            "variant_info": variant_info,
        },
    )


@app.get("/invoice/{product_id}", response_class=HTMLResponse)
async def invoice_page(
    request: Request,
    product_id: str,
    variant: Optional[str] = Query("clean"),
):
    products = get_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    variant_info = inject_variant_content(
        variant=variant,
        page_type="invoice",
        seller_email=settings.STORE_SELLER_EMAIL,
        seller_email_2=settings.STORE_SELLER_EMAIL_2,
        attacker_email=settings.ATTACKER_EMAIL,
    )

    active_seller = variant_info.get("override_seller") or product["seller_email"]

    return templates.TemplateResponse(
        request=request,
        name="invoice.html",
        context={
            "product": product,
            "variant": variant or "clean",
            "variant_info": variant_info,
            "active_seller_email": active_seller,
        },
    )


@app.get("/search")
async def search_catalog(
    q: Optional[str] = Query(""),
    variant: Optional[str] = Query("clean"),
):
    """JSON search endpoint for agents or catalog discovery."""
    query = (q or "").lower().strip()
    products = get_products()
    if not query:
        matches = products
    else:
        matches = [
            p for p in products
            if query in p["name"].lower()
            or query in p["description"].lower()
            or any(query in kw for kw in p.get("keywords", []))
        ]
    return {
        "query": q,
        "variant": variant,
        "count": len(matches),
        "results": matches,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("demo.store.main:app", host="0.0.0.0", port=9000, reload=True)
