from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import files_api, form_api, signature
from app.middleware.middlewareLogger import LoggerMiddleware
from auth_app.app.api.routes import auth_verify, columns, users, admin
from auth_app.app.database.connection import db
from config import config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: store all routes
    routes_info = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                if method != "HEAD":
                    routes_info.append({
                        "method": method,
                        "path": route.path,
                        "name": route.name,
                        "tags": route.tags or []
                    })
    await db.routes.delete_many({})
    if routes_info:
        await db.routes.insert_many(routes_info)
    print(f"✅ Stored {len(routes_info)} routes in MongoDB.")
    yield
    # Shutdown logic if any

def init_application() -> FastAPI:
    app = FastAPI(
        title="Doculan",
        description="Form Management",
        lifespan=lifespan
    )

    # Routers
    app.include_router(auth_verify.router, tags=["Auth"])
    app.include_router(admin.admin_router,tags=["Admin"])
    app.include_router(columns.router, tags=["Columns"])
    app.include_router(users.router, tags=["Users"])
    app.include_router(form_api.router, tags=["Form Manage"])
    app.include_router(signature.router, tags=["Document Tracker"])
    app.include_router(files_api.router, tags=["Files Operation"])

    # Middleware
    app.add_middleware(LoggerMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_HOSTS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app

app = init_application()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
