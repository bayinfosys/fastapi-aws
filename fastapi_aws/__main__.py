"""export the openapi.json to a given directory

This script loads a fastapi.router from the --router parameter and creates two openapi specs:
+ public for sharing with public consumers of the api.
+ private with CORS and integration definitions for the aws apigateway to consume.
"""
import sys
import os
import argparse
import json
import fnmatch

from uvicorn.importer import import_from_string

from fastapi import FastAPI, Request, Response, APIRouter, Depends, Header
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

# from fastapi.middleware.cors import CORSMiddleware

OPENAPI_VERSION = os.getenv("OPENAPI_VERSION", "3.0.1")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")


# Function to add CORS headers to responses
def add_cors_headers(response: Response):
    response.headers["Access-Control-Allow-Origin"] = CORS_ORIGINS
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "OPTIONS, GET, POST, PUT, DELETE"
    return response


def cors_headers(
    response: Response,
    access_control_allow_origin: str = Header(),
    access_control_allow_headers: str = Header(),
    access_control_allow_methods: str = Header(),
):
    return add_cors_headers(response)


def add_cors_dependency_to_router(router):
    """Add CORS headers dependency to all routes in the router"""
    for route in router.routes:
        if (
            "GET" in route.methods
            or "POST" in route.methods
            or "PUT" in route.methods
            or "DELETE" in route.methods
            or "PATCH" in route.methods
        ):
            route.dependencies.append(Depends(cors_headers))


def add_cors_to_openapi(openapi_schema):
    """Add CORS headers to the OpenAPI schema"""
    for path, methods in openapi_schema["paths"].items():
        for method, details in methods.items():
            if "responses" in details:
                for status, response in details["responses"].items():
                    if "headers" not in response:
                        response["headers"] = {}
                    response["headers"]["Access-Control-Allow-Origin"] = {
                        "schema": {"type": "string"},
                        "example": "*",
                    }
                    response["headers"]["Access-Control-Allow-Headers"] = {
                        "schema": {"type": "string"},
                        "example": "Content-Type, Authorization, X-Api-Key",
                    }
                    response["headers"]["Access-Control-Allow-Methods"] = {
                        "schema": {"type": "string"},
                        "example": "OPTIONS, GET, POST, PUT, DELETE, PATCH",
                    }
    return openapi_schema


def add_options_routes(app: FastAPI):
    """automatically add OPTIONS routes for CORS

    These are require for the apigw spec, otherwise CORS requests fails.
    """
    opt_router = APIRouter(dependencies=[Depends(cors_headers)])
    rts = [r for r in app.routes if isinstance(r, APIRoute)]
    for route in rts:
        print("route: '%s'" % str(route))

        async def options_handler(request: Request):
            return add_cors_headers(JSONResponse(content={}))

        opt_router.add_api_route(
            path=route.path,
            endpoint=options_handler,
            methods=["OPTIONS"],
            # tags=route.tags if route.tags else None,
            # summary=f"Options for {route.summary}" if route.summary else None,
            # include_in_schema=False,
            tags=(route.tags or []) + ["CORS"],
            responses={
                "200": {
                    "description": "200 response",
                    "headers": {
                        "Access-Control-Allow-Origin": {"schema": {"type": "string"}},
                        "Access-Control-Allow-Methods": {"schema": {"type": "string"}},
                        "Access-Control-Allow-Headers": {"schema": {"type": "string"}},
                    },
                }
            },
            openapi_extra={
                "x-amazon-apigateway-integration": {
                    "responses": {
                        "default": {
                            "statusCode": "200",
                            "responseParameters": {
                                "method.response.header.Access-Control-Allow-Methods": "'OPTIONS,HEAD,GET,POST,PUT,PATCH,DELETE'",
                                "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                                "method.response.header.Access-Control-Allow-Origin": "'*'",
                            },
                        }
                    },
                    "passthroughBehavior": "when_no_match",
                    "timeoutInMillis": 29000,
                    "requestTemplates": {"application/json": '{ "statusCode": 200 }'},
                    "type": "mock",
                }
            },
        )

    return opt_router


def remove_keys_by_pattern(obj, pattern):
    """Recursively remove keys from a dict matching the given pattern."""
    if isinstance(obj, dict):
        keys_to_delete = [key for key in obj if fnmatch.fnmatch(key, pattern)]
        for key in keys_to_delete:
            del obj[key]
        for value in obj.values():
            remove_keys_by_pattern(value, pattern)
    elif isinstance(obj, list):
        for item in obj:
            remove_keys_by_pattern(item, pattern)


def make_public_api_schema(openapi_schema):
    """Create a public version of the API schema with private data scrubbed.

    This will match for any "x-amazon-apigateway-*" pattern.
    Including:
    + x-amazon-apigateway-integration
    + x-amazon-apigateway-authtype
    + x-amazon-apigateway-authorizer
    """
    remove_keys_by_pattern(openapi_schema, 'x-amazon-apigateway-*')
    return openapi_schema


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "app", help="app import string. e.g. 'main:app'", default="main:app"
    )
    parser.add_argument("--router", help="router import string", default=None)
    parser.add_argument("-t", "--title", help="title of the API", default="untitled")
    parser.add_argument("-v", "--version", help="version of the API", default="0.0.1")
    parser.add_argument(
        "--out-public",
        help="public openapi definition (x-integration information removed)",
        default="-",
    )
    parser.add_argument(
        "--out-private",
        help="openapi filename with x-integration information",
        default=None,
    )
    parser.add_argument(
        "--cors",
        default=True,
        action="store_true",
        help="include CORS methods and resources",
    )

    args = parser.parse_args()

    print(f"importing app from {args.app}")
    router = import_from_string(args.router)
    print(f"imported router: '{type(router)}'")

    if router is None:
        print("ERR: must include a router")
        sys.exit(1)

    app = FastAPI(default_route_class=type(router))
    app.router = router

    # print(app.routes)

    if args.cors:
        app.include_router(add_options_routes(app))

    # print(app.routes)

    openapi_schema = get_openapi(
        title=args.title,
        version=args.version,
        openapi_version=OPENAPI_VERSION,
        routes=app.routes,
    )

    if args.cors:
        add_cors_to_openapi(openapi_schema)

    # write the private api definition (wuth all x-amazon-apigateway-integration info)
    private = openapi_schema
    with open(args.out_private, "w") as f:
        json.dump(private, f, indent=2)

    # write the public api definition (with all x-amazon-apigateway-integration and cors data scrubbed)
    public = make_public_api_schema(openapi_schema)
    with open(args.out_public, "w") as f:
        json.dump(public, f, indent=2)
