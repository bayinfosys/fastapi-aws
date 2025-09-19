import logging

from typing import Any, Dict, List


from ..route import register_integration


logger = logging.getLogger(__name__)


@register_integration("aws_dynamodb_table_name")
def dynamodb_integration(
    service_value: str,  # renamed from table_name
    iam_arn: str,
    path_parameters: List[str] = None,
    http_method: str = "POST",
    vtl_mapping_template: str = None,  # renamed from mapping_template
    vtl_responses_template: str = None,
    dynamodb_pk_pattern: str = None,  # renamed from pk_pattern
    dynamodb_sk_pattern: str = None,  # renamed from sk_pattern
    dynamodb_fields: str = None,  # renamed from field_patterns
    dynamodb_query_expr: str = None,  # renamed from query_expr
    request_parameters: dict = None,  # now passed in instead of extracted from kwargs
    **kwargs,
) -> Dict[str, Any]:
    """
    Returns an AWS API Gateway integration for DynamoDB PutItem.

    - POST maps to PutItem.
    - Required fields in body: owner, project, eventname, timestamp.
    - PK will be dynamodb_pk_pattern or the default
    - SK will be dynamodb_sk_pattern or the default
    - item fields will be dynamodb_fields or 'timestamp=request.time'

    Optional:
    - vtl_mapping_template: override the default template if provided.
    """

    def create_put_item_mapping_template(
        table_name, ttl, pk_pattern, sk_pattern, fields
    ):
        return """
#set($body = $util.parseJson($input.body))

#set($nowEpochSeconds = $context.requestTimeEpoch / 1000)
#set($expiration = $nowEpochSeconds + {ttl})

{{
  "TableName": "{table_name}",
  "Item": {{
    "PK": {{ "S": "{pk_pattern}" }},
    "SK": {{ "S": "{sk_pattern}" }},
    {fields}
  }}
}}""".format(
            table_name=table_name,
            ttl=ttl,
            pk_pattern=pk_pattern,
            sk_pattern=sk_pattern,
            fields=fields,
        )

    def create_query_mapping_template(table_name: str, query_expr: str):
        """we cannot parameterise this, the user must supply vtl.
        ref: https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_Query.html#API_Query_Examples
        """
        return """
{{
    "TableName": "{table_name}", {query_expr}
}}""".format(
            table_name=table_name, query_expr=query_expr
        )

    table_name = service_value  # service_value is the table name for DynamoDB
    assert table_name is not None
    # default mapping template if not provided
    assert vtl_mapping_template is None, "vtl_mapping_template must be none"

    # Define the AWS service integration URI
    # FIXME: i think we should let the caller set the entire mapping template
    if http_method == "POST":
        default_pk_pattern = "$input.path('$.owner')#$input.path('$.project')"
        default_sk_pattern = "$input.path('$.project')#$input.path('$.eventname')#$input.path('$.timestamp')"
        fields_block = (
            dynamodb_fields or '"timestamp": { "S": "$context.requestTime" }'
        )
        default_ttl = 2592000

        uri = "arn:aws:apigateway:${region}:dynamodb:action/PutItem"
        vtl_mapping_template = create_put_item_mapping_template(
            table_name,
            ttl=default_ttl,
            pk_pattern=dynamodb_pk_pattern or default_pk_pattern,
            sk_pattern=dynamodb_sk_pattern or default_sk_pattern,
            fields=fields_block,
        )
    elif http_method == "GET":
        assert dynamodb_query_expr is not None
        uri = "arn:aws:apigateway:${region}:dynamodb:action/Query"
        vtl_mapping_template = create_query_mapping_template(
            table_name, query_expr=dynamodb_query_expr
        )
    else:
        raise ValueError(
            f"Unsupported HTTP method {http_method} for DynamoDB integration. Only POST (PutItem) or GET (Query) is allowed."
        )

    logger.info("vtl_mapping_template: %s", str(vtl_mapping_template))

    vtl_request_templates = {"application/json": vtl_mapping_template}

    # Initialize request_parameters if not provided
    if request_parameters is None:
        request_parameters = {}

    # set up request parameters if needed to propagate the request params
    if any(
        (
            "$input.params('origin')" in (field or "")
            for field in [
                dynamodb_pk_pattern,
                dynamodb_sk_pattern,
                dynamodb_fields,
                dynamodb_query_expr,
            ]
        )
    ):
        request_parameters.update(
            {"integration.request.header.origin": "method.request.header.origin"}
        )

    responses = {
        "default": {"statusCode": "200"},
        "4xx": {"statusCode": "400"},
        "5xx": {"statusCode": "500"},
    }

    return dict(
        uri=uri,
        integration_type="aws",
        http_method="POST",
        credentials=iam_arn,
        vtl_request_template=vtl_request_templates,
        vtl_responses_template=vtl_responses_template,
        responses=responses,
        request_parameters=request_parameters if request_parameters else None,
    )
