"""AWSAPIRouter

inherited from APIRouter so we can pass kwargs to get, post, put, delete decorators
"""

from typing import Any, Callable, Type

from fastapi import APIRouter
from fastapi.routing import APIRoute
from fastapi.types import DecoratedCallable

from .route import AWSAPIRoute


class AWSAPIRouter(APIRouter):
    def __init__(self, *args, route_class: Type[AWSAPIRoute] = AWSAPIRoute, **kwargs):
        super().__init__(*args, route_class=route_class, **kwargs)

    def add_api_route(
        self, path: str, endpoint: Callable[..., Any], **kwargs: Any
    ) -> None:
        route_class = kwargs.pop("route_class_override", None) or self.route_class

        # check if this route has AWS integration parameters
        aws_services = set(AWSAPIRoute._integration_registry or {}).intersection(
            set(kwargs)
        )

        if aws_services or "aws_iam_arn" in kwargs:
            # this route has AWS integrations, use AWSAPIRoute
            route = route_class(path, endpoint, **kwargs)
        else:
            # no aws integrations, use standard APIRoute to avoid processing AWS args
            route = APIRoute(path, endpoint, **kwargs)

        self.routes.append(route)

    def api_route(
        self, path: str, **kwargs: Any
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.add_api_route(path, func, **kwargs)
            return func

        return decorator

    # Override the HTTP method decorators to accept aws_lambda_uri
    def get(self, path: str, **kwargs: Any):
        return self.api_route(path, methods=["GET"], **kwargs)

    def post(self, path: str, **kwargs: Any):
        return self.api_route(path, methods=["POST"], **kwargs)

    def put(self, path: str, **kwargs: Any):
        return self.api_route(path, methods=["PUT"], **kwargs)

    def delete(self, path: str, **kwargs: Any):
        return self.api_route(path, methods=["DELETE"], **kwargs)
