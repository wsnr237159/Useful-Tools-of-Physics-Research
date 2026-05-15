"""Local research tools launcher package."""


def create_app(*args, **kwargs):
    from .app import create_app as create_flask_app

    return create_flask_app(*args, **kwargs)

__all__ = ["create_app"]
