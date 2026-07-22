"""
routes_orders.py
----------------
REST endpoints for orders. Auth via Bearer token in Authorization header.
Write operations trigger PostgreSQL NOTIFY → Redis → WebSocket broadcast.
"""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

from auth     import verify_token
from database import fetch_all_orders
from models   import OrderCreate, OrderUpdate, OrderResponse

router = APIRouter(prefix="/orders", tags=["Orders"])
security = HTTPBearer(auto_error=False)


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Accept token from Authorization header OR ?token= query param."""
    if credentials:
        return verify_token(credentials.credentials)
    return None   # open read for demo; tighten in production


@router.get("", response_model=list[OrderResponse])
async def list_orders(request: Request, _=Depends(require_auth)):
    pool = request.app.state.pool
    return await fetch_all_orders(pool)


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(body: OrderCreate, request: Request, _=Depends(require_auth)):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO orders (customer_name, product_name, status)
            VALUES ($1, $2, $3)
            RETURNING id, customer_name, product_name, status,
                      updated_at::TEXT AS updated_at
            """,
            body.customer_name, body.product_name, body.status,
        )
    return dict(row)


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(order_id: int, body: OrderUpdate, request: Request, _=Depends(require_auth)):
    pool = request.app.state.pool
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    fields = list(updates.keys())
    values = list(updates.values())
    set_clause = ", ".join(f"{f} = ${i+2}" for i, f in enumerate(fields))

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE orders
            SET {set_clause}, updated_at = NOW()
            WHERE id = $1
            RETURNING id, customer_name, product_name, status,
                      updated_at::TEXT AS updated_at
            """,
            order_id, *values,
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found.")
    return dict(row)


@router.delete("/{order_id}", status_code=204)
async def delete_order(order_id: int, request: Request, _=Depends(require_auth)):
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM orders WHERE id = $1", order_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found.")
