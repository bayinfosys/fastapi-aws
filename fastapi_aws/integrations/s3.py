from typing import Any, Dict, List


from ..route import register_integration


@register_integration("aws_s3_bucket")
def s3_integration(
    service_value: str,
    iam_arn: str,
    path_parameters: List[str] = None,
    http_method: str = "GET",
    s3_object_key: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Returns an AWS integration for S3 from API Gateway.

    This allows API Gateway to interact with S3 objects via HTTP methods.

    :param bucket_name: Name of the S3 bucket.
    :param iam_arn: IAM role ARN to assume for the integration.
    :param path_parameters: list of path parameters in the apigw request path; if `s3_object_key` is None, the last value here is used as as the object key to lookup
    :param http_method: HTTP method (GET, PUT, DELETE) to use for the integration.
    :param s3_object_key: [optional] fixed object key to return from the bucket

    # TODO: path_parameters could be merged to allow multiple names
    # TODO: s3_object_key_prefix: allow a key prefix to be used for accessing objects by path parameter

    Example OpenAPI integration:

    "x-amazon-apigateway-integration": {
        "uri": "arn:aws:apigateway:${region}:s3:path/{bucket}/{key}",
        "httpMethod": "GET",
        "type": "aws",
        "credentials": "${iam_role_arn}",
        "requestParameters": {
            "integration.request.path.bucket": "bucket_name",
            "integration.request.path.key": "method.request.path.key"
        },
        "responses": {
            "default": {
                "statusCode": "200",
                "responseParameters": {
                    "method.response.header.Content-Type": "'application/octet-stream'"
                }
            }
        }
    }
    """
    bucket_name = service_value

    assert http_method in (
        "GET",
        "PUT",
        "DELETE",
    ), "Invalid HTTP method for S3 integration"

    # define the S3 integration URI using API Gateway's S3 service
    # uri = f"arn:aws:apigateway:${{region}}:s3:path/{bucket_name}/{{key}}"
    # FIXME: add the key parameter here to specify an object; but where should the value coem from?
    #        path_parameters? kwargs?
    # NB: i think uri should be the bucket arn
    uri = f"arn:aws:apigateway:${{region}}:s3:path/{bucket_name}"

    if s3_object_key:
        uri = "/".join((uri, s3_object_key))
    elif path_parameters:
        uri = "/".join([uri] + path_parameters)
    else:
        raise ValueError("expected one of: 's3_object_key', 'path_parameters'")

    # response mapping (simple passthrough)
    # FIXME: take the integration response content type to get the object content type
    default_response_parameters = {
        "default": {
            "statusCode": "200",
            #            "responseParameters": {
            #                "method.response.header.Content-Type": "integration.response.header.Content-Type"
            #            },
        },
        "4xx": {"statusCode": "404"},
        "403": {"statusCode": "404"},
        "404": {"statusCode": "404"},
    }

    responses = kwargs.get("responses") or default_response_parameters

    # generate apigw integration config
    integration = dict(
        uri=uri,
        http_method=http_method,
        integration_type="aws",
        credentials=iam_arn,
        responses=responses,
    )

    return integration
