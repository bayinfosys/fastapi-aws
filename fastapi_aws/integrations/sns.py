"""Create an integration for SNS

This is a tricky one because we need urlencoded query strings
rather than POST submission.

refs:
  https://repost.aws/knowledge-center/api-gateway-proxy-integrate-service
"""

from ..route import register_integration


@register_integration("aws_sns_topic_arn")
def sns_integration(
    service_value: str,
    iam_arn: str,
    **kwargs,
):
    """SNS integration for publishing messages from API Gateway.

    service_value: sns topic arn
    iam_arn: iam with permissions for publish

    NB: this passes the body of the request into the sns as the
    message body. We do **NOT** transform the request via vtl.
    """

    # Build URL-encoded form data as per AWS docs
    # NB: we pass the $input.body directly.
    # VTL + urlEncoding is difficult.
    action = "Publish"
    topic_arn = service_value
    message = "$input.body"
    mime_type = "'application/x-www-form-urlencoded'"

    query_string = "&".join(
        [
            f"Action={action}",
            f'TopicArn=$util.urlEncode("{topic_arn}")',
            f'Message=$util.urlEncode("{message}")',
        ]
    )

    request_parameters = {"integration.request.header.Content-Type": mime_type}

    return dict(
        uri="arn:aws:apigateway:${region}:sns:action/Publish",
        integration_type="aws",
        http_method="POST",
        credentials=iam_arn,
        vtl_request_template={"application/json": query_string},
        request_parameters=request_parameters,
        responses={
            "default": {"statusCode": "200"},
            "4xx": {"statusCode": "400"},
            "5xx": {"statusCode": "500"},
        },
    )
