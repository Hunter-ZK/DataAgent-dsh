from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from agent3.contracts.authz import AuthzContext, DataScope
from agent3.services.core import Agent3Core


class ValidateRequest(BaseModel):
    sql: str
    dialect: str = "maxcompute"
    metric_id: str | None = None


class SearchRequest(BaseModel):
    query: str
    limit: int = 8


def create_app(core: Agent3Core, *, service_token: str) -> FastAPI:
    if not service_token:
        raise ValueError("HTTP adapter requires an explicit service token")
    app = FastAPI(title="Agent3 API", version="0.1.0")

    def authz(x_service_token: str = Header(...), x_principal: str = Header(...), x_region_scope: str | None = Header(None)) -> AuthzContext:
        if x_service_token != service_token:
            raise HTTPException(status_code=401, detail="invalid service token")
        scopes = ()
        if x_region_scope:
            values = tuple(v.strip() for v in x_region_scope.split(",") if v.strip())
            if values:
                scopes = (DataScope("region_code", values),)
        return AuthzContext(principal=x_principal, data_scopes=scopes, purpose="http-api")

    @app.post("/v1/search-tables")
    def search_tables(payload: SearchRequest, context: AuthzContext = Depends(authz)):
        return core.search_tables(context, payload.query, limit=payload.limit)

    @app.post("/v1/validate-sql")
    def validate_sql(payload: ValidateRequest, context: AuthzContext = Depends(authz)):
        return core.validate_sql(context, payload.sql, dialect=payload.dialect, metric_id=payload.metric_id)

    return app
