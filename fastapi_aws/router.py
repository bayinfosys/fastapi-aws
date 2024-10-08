from fastapi.routing import APIRoute
from fastapi import APIRouter
from fastapi.types import DecoratedCallable
from typing import Any, Callable, Optional, Type


from .route import AWSAPIRoute


class AWSAPIRouter(APIRouter):
    def __init__(self, *args, route_class: Type[APIRoute] = AWSAPIRoute, **kwargs):
        super().__init__(*args, route_class=route_class, **kwargs)

    def add_api_route(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        aws_integration_uri: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        route_class = self.route_class
        route = route_class(path, endpoint, aws_integration_uri=aws_integration_uri, **kwargs)
        self.routes.append(route)

    def api_route(self, path: str, *, aws_integration_uri: Optional[str] = None, **kwargs: Any) -> Callable[[DecoratedCallable], DecoratedCallable]:
        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            self.add_api_route(path, func, aws_integration_uri=aws_integration_uri, **kwargs)
            return func

        return decorator

    # Override the HTTP method decorators to accept aws_integration_uri
    def get(self, path: str, *, aws_integration_uri: Optional[str] = None, **kwargs: Any):
        return self.api_route(path, aws_integration_uri=aws_integration_uri, methods=["GET"], **kwargs)

    def post(self, path: str, *, aws_integration_uri: Optional[str] = None, **kwargs: Any):
        return self.api_route(path, aws_integration_uri=aws_integration_uri, methods=["POST"], **kwargs)

    def put(self, path: str, *, aws_integration_uri: Optional[str] = None, **kwargs: Any):
        return self.api_route(path, aws_integration_uri=aws_integration_uri, methods=["PUT"], **kwargs)

    def delete(self, path: str, *, aws_integration_uri: Optional[str] = None, **kwargs: Any):
        return self.api_route(path, aws_integration_uri=aws_integration_uri, methods=["DELETE"], **kwargs)
