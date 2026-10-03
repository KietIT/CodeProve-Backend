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

    from app.features.admin.router import auth_router as admin_auth_router, router as admin_router
    app.include_router(admin_auth_router)
    app.include_router(admin_router)
    from app.features.admin.exercises import router as admin_exercises_router
    app.include_router(admin_exercises_router)
    from app.features.admin.users import router as admin_users_router
    app.include_router(admin_users_router)
    from app.features.admin.overview import router as admin_overview_router
    app.include_router(admin_overview_router)

    from app.features.exercises.router import router as exercises_router
    app.include_router(exercises_router)

    from app.features.attempts.router import router as attempts_router
    app.include_router(attempts_router)

    from app.features.mentor.router import router as mentor_router
    app.include_router(mentor_router)

    from app.features.dashboard.router import router as dashboard_router
    app.include_router(dashboard_router)

    from app.features.daily.router import router as daily_router
    app.include_router(daily_router)

    from app.features.practice.router import router as practice_router
    app.include_router(practice_router)

    from app.features.learner.router import router as learner_router
    app.include_router(learner_router)

    from app.features.privacy.router import router as privacy_router
    app.include_router(privacy_router)

    return app


app = create_app()
