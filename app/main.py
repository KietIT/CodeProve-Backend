from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CodeProve API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    from app.features.auth.router import router as auth_router
    app.include_router(auth_router)

    from app.features.exercises.router import router as exercises_router
    app.include_router(exercises_router)

    from app.features.attempts.router import router as attempts_router
    app.include_router(attempts_router)

    return app


app = create_app()
