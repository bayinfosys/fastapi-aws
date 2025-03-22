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
CORS_HEADERS = os.getenv("CORS_HEADERS", "Content-Type,Authorization").split(",")
CORS_METHODS = os.getenv("CORS_METHODS", "*").split(",")


def cors_origins() -> str:
    """format the cors origins for apigw
    NB: we only really allow the wildcard or a single origin, so not sure what use this is
    """
    return "'%s'" % ",".join(CORS_ORIGINS)


def cors_headers() -> str:
    """format the cors headers for apigw"""
    return "'%s'" % ",".join(CORS_HEADERS)


def cors_methods() -> str:
    """format the cors methods for apigw"""
    # return "'%s'" % ",".join(CORS_METHODS)
    return "'OPTIONS,GET,POST,DELETE'"


def add_cors_headers(response: Response):
    """add CORS headers to response objects for fastapi"""
    response.headers["Access-Control-Allow-Origin"] = cors_origins()
    response.headers["Access-Control-Allow-Headers"] = cors_headers()
    response.headers["Access-Control-Allow-Methods"] = cors_methods()
    return response


def cors_headers_dependency(
    response: Response,
    access_control_allow_origin: str = Header(),
    access_control_allow_headers: str = Header(),
    access_control_allow_methods: str = Header(),
):
    return add_cors_headers(response)


def add_cors_dependency_to_router(router):
    """Add CORS headers dependency to all routes in the router"""
    for route in router.routes:
        if any(x in route.methods for x in CORS_METHODS):
            route.dependencies.append(Depends(cors_headers_dependency))


def cors_headers_schema():
    return {
        "Access-Control-Allow-Origin": {"schema": {"type": "string"}},
        "Access-Control-Allow-Methods": {"schema": {"type": "string"}},
        "Access-Control-Allow-Headers": {"schema": {"type": "string"}},
    }


def cors_response_defaults():
    return {
        "method.response.header.Access-Control-Allow-Methods": cors_methods(),
        "method.response.header.Access-Control-Allow-Headers": cors_headers(),
        "method.response.header.Access-Control-Allow-Origin": cors_origins(),
    }


def add_cors_preflight_routes(app: FastAPI):
    """automatically add OPTIONS routes for CORS

    These are require for the apigw spec, otherwise CORS requests fails.

    NB: these preflight routes are added via fastapi, but we could do directly via schema modification
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
                "200": {"description": "200 response", "headers": cors_headers_schema()}
            },
            openapi_extra={
                "x-amazon-apigateway-integration": {
                    "responses": {
                        "default": {
                            "statusCode": "200",
                            "responseParameters": cors_response_defaults(),
                        }
                    },
                    "passthroughBehavior": "when_no_match",
                    "timeoutInMillis": 29000,
                    "requestTemplates": {
                        "application/json": json.dumps({"statusCode": 200})
                    },
                    "type": "mock",
                }
            },
        )

    return opt_router


def inject_cors_headers(openapi_schema):
    """Inject CORS headers into all responses in the OpenAPI schema.

    This ensures that all responses (200, 4xx, 5xx, etc.) include:
    - Access-Control-Allow-Origin
    - Access-Control-Allow-Headers
    - Access-Control-Allow-Methods

    Required for AWS API Gateway to properly handle CORS for REST APIs.

    Args:
        openapi_schema (dict): The OpenAPI JSON schema.

    Returns:
        dict: Updated OpenAPI schema with CORS headers injected.
    """
    cors_headers = cors_headers_schema()
    cors_response_parameters = cors_response_defaults()

    for path, methods in openapi_schema.get("paths", {}).items():
        for method, details in methods.items():
            # Skip OPTIONS, as it's already handled by add_cors_preflight_routes()
            if method.upper() == "OPTIONS":
                continue

            # Ensure responses exist
            if "responses" not in details:
                details["responses"] = {}

            # Iterate through each response (e.g., 200, 400, 500)
            for status_code, response in details["responses"].items():
                if "headers" not in response:
                    response["headers"] = {}

                # Inject CORS headers into each response
                response["headers"].update(cors_headers)

            # Ensure x-amazon-apigateway-integration exists
            if "x-amazon-apigateway-integration" in details:
                integration = details["x-amazon-apigateway-integration"]

                if "responses" in integration:
                    for response_key, integration_response in integration[
                        "responses"
                    ].items():
                        if "responseParameters" not in integration_response:
                            integration_response["responseParameters"] = {}

                        # Inject responseParameters into API Gateway integration responses
                        integration_response["responseParameters"].update(
                            cors_response_parameters
                        )

    return openapi_schema


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
    remove_keys_by_pattern(openapi_schema, "x-amazon-apigateway-*")
    return openapi_schema


def default_cors_headers(define_cors=True):
    headers = {
        "allowOrigins": "'*'",
        "allowMethods": ["'%s'" % x for x in CORS_METHODS],
        "allowHeaders": ["'%s'" % x for x in CORS_HEADERS],
    }

    return {"x-amazon-apigateway-cors": headers}


def aws_gateway_responses(define_cors=True):
    """Add custom apigw responses to the openapi schema
    see: https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-gateway-responses.html
    """
    default_cors = {
        "gatewayresponse.header.Access-Control-Allow-Origin": cors_origins(),
        "gatewayresponse.header.Access-Control-Allow-Methods": cors_methods(),
        "gatewayresponse.header.Access-Control-Allow-Headers": cors_headers(),
    }

    responses = {
        "DEFAULT_4XX": {
            "statusCode": 400,
            "responseTemplates": {
                "application/json": json.dumps({"message": "Client error occurred"})
            },
        },
        "DEFAULT_5XX": {
            "statusCode": 500,
            "responseTemplates": {
                "application/json": json.dumps({"message": "Internal server error"})
            },
        },
        "ACCESS_DENIED": {
            "statusCode": 403,
            "responseTemplates": {
                "application/json": json.dumps({"message": "Access Denied"})
            },
        },
        "UNAUTHORIZED": {
            "statusCode": 401,
            "responseTemplates": {
                "application/json": json.dumps({"message": "Unauthorized"})
            },
        },
        "MISSING_AUTHENTICATION_TOKEN": {
            "statusCode": 404,
            "responseTemplates": {
                "application/json": json.dumps({"message": "Route not found"})
            },
        },
    }

    if define_cors:
        for k in responses:
            responses[k].update({"responseParameters": default_cors})

    return {"x-amazon-apigateway-gateway-responses": responses}


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
        help="include CORS methods and resources for pre-flight responses",
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
        app.include_router(add_cors_preflight_routes(app))

    # print(app.routes)

    openapi_schema = get_openapi(
        title=args.title,
        version=args.version,
        openapi_version=OPENAPI_VERSION,
        routes=app.routes,
    )

    #    if args.cors:
    #        add_cors_responses(openapi_schema)

    openapi_schema.update(aws_gateway_responses(args.cors))
    openapi_schema.update(default_cors_headers(args.cors))
    openapi_schema = inject_cors_headers(openapi_schema)

    # write the private api definition (wuth all x-amazon-apigateway-integration info)
    private = openapi_schema
    with open(args.out_private, "w") as f:
        json.dump(private, f, indent=2)

    # write the public api definition (with all x-amazon-apigateway-integration and cors data scrubbed)
    public = make_public_api_schema(openapi_schema)
    with open(args.out_public, "w") as f:
        json.dump(public, f, indent=2)
