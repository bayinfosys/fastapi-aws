from typing import Any, Dict, List
import json


from ..route import register_integration


@register_integration("mock")
def mock_integration(
    uri: str, iam_arn: str, path_parameters: List[str], **kwargs
) -> Dict[str, Any]:
    """returns a mock integration which has a fixed response value
    NB: this function should take parameters for the fixed responses.
    NB: this can currently be used for a 'not implemented' response.
    """
    return dict(
        uri="",
        integration_type="mock",
        vtl_request_template={"statusCode": 200},
        responses={
            "default": {
                "statusCode": 501,
                "responseTemplates": {
                    "application/json": json.dumps({"status": "not implemented"})
                },
            }
        },
    )
