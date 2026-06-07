"""Thin entrypoint — composition root em apps.salon.api.app_factory."""
import uvicorn

from apps.salon.api.app_factory import create_salon_app


def create_app():
    """Factory compatível com testes e scripts legados."""
    return create_salon_app()


app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
