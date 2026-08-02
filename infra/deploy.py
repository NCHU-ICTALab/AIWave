"""Deploy the AIWave AWS foundation without requiring the AWS CLI.

The first deployment intentionally keeps Aurora disabled and the API at one task.
The current application still uses SQLite and in-memory sessions, so enabling the
formal database or horizontal scaling before those adapters are migrated would
create a misleading and inconsistent environment.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import secrets
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError, WaiterError

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "infra" / "cloudformation"
BOOTSTRAP_TEMPLATE = TEMPLATE_DIR / "bootstrap.yaml"
APPLICATION_TEMPLATE = TEMPLATE_DIR / "application.yaml"
PROJECT = "aiwave"
ENVIRONMENT = "production"
BOOTSTRAP_STACK = f"{PROJECT}-{ENVIRONMENT}-bootstrap"
APPLICATION_STACK = f"{PROJECT}-{ENVIRONMENT}-app"


def session(region: str) -> boto3.Session:
    return boto3.Session(region_name=region)


def run(command: list[str], *, cwd: Path = ROOT, stdin: str | None = None) -> None:
    printable = " ".join(command)
    print(f"+ {printable}")
    executable = shutil.which(command[0]) or command[0]
    subprocess.run(
        [executable, *command[1:]],
        cwd=cwd,
        input=stdin,
        text=True,
        check=True,
    )


def stack_exists(cf: Any, name: str) -> bool:
    try:
        cf.describe_stacks(StackName=name)
        return True
    except ClientError as exc:
        if "does not exist" in str(exc):
            return False
        raise


def stack_outputs(cf: Any, name: str) -> dict[str, str]:
    stack = cf.describe_stacks(StackName=name)["Stacks"][0]
    return {item["OutputKey"]: item["OutputValue"] for item in stack.get("Outputs", [])}


def recent_failure_events(cf: Any, name: str) -> list[dict[str, str]]:
    try:
        events = cf.describe_stack_events(StackName=name)["StackEvents"]
    except ClientError:
        return []
    failures: list[dict[str, str]] = []
    for event in events:
        status = event.get("ResourceStatus", "")
        reason = event.get("ResourceStatusReason", "")
        if "FAILED" in status or "ROLLBACK" in status:
            failures.append(
                {
                    "resource": event.get("LogicalResourceId", ""),
                    "type": event.get("ResourceType", ""),
                    "status": status,
                    "reason": reason,
                }
            )
        if len(failures) == 12:
            break
    return failures


def deploy_stack(
    aws: boto3.Session,
    *,
    name: str,
    template: Path,
    parameters: dict[str, str | None],
) -> dict[str, str]:
    cf = aws.client("cloudformation")
    exists = stack_exists(cf, name)
    if exists:
        current_status = cf.describe_stacks(StackName=name)["Stacks"][0]["StackStatus"]
        if current_status == "ROLLBACK_COMPLETE":
            print(f"Deleting failed empty stack {name} before retry ...")
            cf.delete_stack(StackName=name)
            cf.get_waiter("stack_delete_complete").wait(
                StackName=name,
                WaiterConfig={"Delay": 10, "MaxAttempts": 60},
            )
            exists = False

    serialized_parameters: list[dict[str, Any]] = []
    for key, value in parameters.items():
        if value is None:
            if not exists:
                raise ValueError(f"Cannot preserve parameter {key} when creating stack {name}")
            serialized_parameters.append({"ParameterKey": key, "UsePreviousValue": True})
        else:
            serialized_parameters.append({"ParameterKey": key, "ParameterValue": value})

    body = template.read_text(encoding="utf-8")
    request = {
        "StackName": name,
        "TemplateBody": body,
        "Parameters": serialized_parameters,
        "Capabilities": ["CAPABILITY_IAM"],
        "Tags": [
            {"Key": "Project", "Value": PROJECT},
            {"Key": "Environment", "Value": ENVIRONMENT},
            {"Key": "ManagedBy", "Value": "CloudFormation"},
        ],
    }
    try:
        if exists:
            print(f"Updating CloudFormation stack {name} ...")
            cf.update_stack(**request)
            waiter = cf.get_waiter("stack_update_complete")
        else:
            print(f"Creating CloudFormation stack {name} ...")
            cf.create_stack(**request, OnFailure="ROLLBACK")
            waiter = cf.get_waiter("stack_create_complete")
        waiter.wait(StackName=name, WaiterConfig={"Delay": 20, "MaxAttempts": 90})
    except ClientError as exc:
        if "No updates are to be performed" not in str(exc):
            raise
        print(f"CloudFormation stack {name} is already up to date.")
    except WaiterError:
        print(json.dumps(recent_failure_events(cf, name), ensure_ascii=False, indent=2))
        raise
    outputs = stack_outputs(cf, name)
    print(json.dumps({"stack": name, "outputs": outputs}, ensure_ascii=False, indent=2))
    return outputs


def validate(aws: boto3.Session) -> None:
    cf = aws.client("cloudformation")
    for template in (BOOTSTRAP_TEMPLATE, APPLICATION_TEMPLATE):
        response = cf.validate_template(TemplateBody=template.read_text(encoding="utf-8"))
        parameters = [item["ParameterKey"] for item in response.get("Parameters", [])]
        print(json.dumps({"template": str(template.relative_to(ROOT)), "parameters": parameters}))


def deploy_bootstrap(aws: boto3.Session) -> dict[str, str]:
    return deploy_stack(
        aws,
        name=BOOTSTRAP_STACK,
        template=BOOTSTRAP_TEMPLATE,
        parameters={"ProjectName": PROJECT, "EnvironmentName": ENVIRONMENT},
    )


def image_tag() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short=10", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sha = "workspace"
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"{sha}-{stamp}"


def build_and_push_image(
    aws: boto3.Session,
    repository_uri: str,
    *,
    local_image: str | None = None,
) -> str:
    ecr = aws.client("ecr")
    auth = ecr.get_authorization_token()["authorizationData"][0]
    username, password = base64.b64decode(auth["authorizationToken"]).decode("utf-8").split(":", 1)
    registry = auth["proxyEndpoint"]
    tag = image_tag()
    image_uri = f"{repository_uri}:{tag}"
    source_image = local_image or f"{PROJECT}-api:{tag}"
    run(["docker", "login", "--username", username, "--password-stdin", registry], stdin=password)
    if local_image is None:
        run(["docker", "build", "--platform", "linux/amd64", "--tag", source_image, "."])
    else:
        run(["docker", "image", "inspect", source_image])
        print(f"Using prevalidated local image {source_image}; external registry base pulls are skipped.")
    run(["docker", "tag", source_image, image_uri])
    run(["docker", "push", image_uri])
    print(json.dumps({"image_uri": image_uri, "source_image": source_image}))
    return image_uri


def deploy_application(
    aws: boto3.Session,
    *,
    image_uri: str,
    frontend_bucket: str,
    deploy_database: bool | None,
    desired_count: int,
) -> dict[str, str]:
    cf = aws.client("cloudformation")
    preserve_existing = stack_exists(cf, APPLICATION_STACK)
    existing_parameter_keys: set[str] = set()
    if preserve_existing:
        stack = cf.describe_stacks(StackName=APPLICATION_STACK)["Stacks"][0]
        preserve_existing = stack["StackStatus"] != "ROLLBACK_COMPLETE"
        if preserve_existing:
            existing_parameter_keys = {item["ParameterKey"] for item in stack.get("Parameters", [])}

    if deploy_database is None:
        database_value = None if "DeployDatabase" in existing_parameter_keys else "false"
        database_confirmation = None if "ConfirmDatabaseCosts" in existing_parameter_keys else "false"
    else:
        database_value = str(deploy_database).lower()
        database_confirmation = str(deploy_database).lower()

    preserve_origin_header = "OriginVerifyHeaderValue" in existing_parameter_keys
    return deploy_stack(
        aws,
        name=APPLICATION_STACK,
        template=APPLICATION_TEMPLATE,
        parameters={
            "ProjectName": PROJECT,
            "EnvironmentName": ENVIRONMENT,
            "ImageUri": image_uri,
            "FrontendBucketName": frontend_bucket,
            "OriginVerifyHeaderValue": None if preserve_origin_header else secrets.token_urlsafe(32),
            "ApiDesiredCount": str(desired_count),
            "DeployDatabase": database_value,
            "ConfirmDatabaseCosts": database_confirmation,
            "AuroraMinCapacity": "2",
            "AuroraMaxCapacity": "8",
        },
    )


def cache_control(path: Path) -> str:
    if path.name == "index.html":
        return "no-cache, no-store, must-revalidate"
    if "assets" in path.parts:
        return "public, max-age=31536000, immutable"
    return "public, max-age=300"


def publish_frontend(aws: boto3.Session, *, bucket: str, distribution_id: str) -> None:
    app_dir = ROOT / "web" / "app"
    dist_dir = app_dir / "dist"
    run(["npm", "run", "build"], cwd=app_dir)
    s3 = aws.client("s3")
    local_keys: set[str] = set()
    for file in sorted(path for path in dist_dir.rglob("*") if path.is_file()):
        key = file.relative_to(dist_dir).as_posix()
        local_keys.add(key)
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        s3.upload_file(
            str(file),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type, "CacheControl": cache_control(file.relative_to(dist_dir))},
        )
        print(f"Uploaded s3://{bucket}/{key}")
    remote_keys: set[str] = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        remote_keys.update(item["Key"] for item in page.get("Contents", []))
    stale = sorted(remote_keys - local_keys)
    for offset in range(0, len(stale), 1000):
        batch = stale[offset : offset + 1000]
        if batch:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key} for key in batch]})
    cloudfront = aws.client("cloudfront")
    invalidation = cloudfront.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": ["/*"]},
            "CallerReference": datetime.now(UTC).isoformat(),
        },
    )["Invalidation"]
    print(json.dumps({"invalidation_id": invalidation["Id"], "status": invalidation["Status"]}))


def status(aws: boto3.Session) -> None:
    cf = aws.client("cloudformation")
    result: dict[str, Any] = {}
    for name in (BOOTSTRAP_STACK, APPLICATION_STACK):
        if not stack_exists(cf, name):
            result[name] = {"exists": False}
            continue
        stack = cf.describe_stacks(StackName=name)["Stacks"][0]
        result[name] = {
            "exists": True,
            "status": stack["StackStatus"],
            "outputs": stack_outputs(cf, name),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "bootstrap", "image", "application", "frontend", "status", "deploy"])
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--image-uri")
    parser.add_argument("--local-image", help="Prevalidated local Docker image to tag and push without rebuilding.")
    parser.add_argument(
        "--deploy-database",
        action="store_true",
        default=None,
        help="Explicitly enable Aurora; omitted on updates preserves the current database state.",
    )
    parser.add_argument(
        "--confirm-database-costs",
        action="store_true",
        help="Required with --deploy-database; acknowledges Aurora 2-8 ACU cost and deletion protection.",
    )
    parser.add_argument("--desired-count", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.deploy_database and not args.confirm_database_costs:
        raise SystemExit(
            "--deploy-database requires --confirm-database-costs because Aurora runs at 2-8 ACU "
            "and deletion protection must be disabled before teardown."
        )
    aws = session(args.region)
    if args.command == "validate":
        validate(aws)
        return 0
    if args.command == "status":
        status(aws)
        return 0

    bootstrap = deploy_bootstrap(aws) if args.command in {"bootstrap", "deploy"} else stack_outputs(aws.client("cloudformation"), BOOTSTRAP_STACK)
    if args.command == "bootstrap":
        return 0

    image_uri = args.image_uri
    if args.command in {"image", "deploy"}:
        image_uri = build_and_push_image(
            aws,
            bootstrap["EcrRepositoryUri"],
            local_image=args.local_image,
        )
    if args.command == "image":
        return 0
    if not image_uri and args.command == "application":
        raise SystemExit("--image-uri is required for the application command")

    if args.command in {"application", "deploy"}:
        application = deploy_application(
            aws,
            image_uri=str(image_uri),
            frontend_bucket=bootstrap["FrontendBucketName"],
            deploy_database=args.deploy_database,
            desired_count=args.desired_count,
        )
    else:
        application = stack_outputs(aws.client("cloudformation"), APPLICATION_STACK)
    if args.command == "application":
        return 0

    if args.command in {"frontend", "deploy"}:
        publish_frontend(
            aws,
            bucket=bootstrap["FrontendBucketName"],
            distribution_id=application["CloudFrontDistributionId"],
        )
    status(aws)
    return 0


if __name__ == "__main__":
    sys.exit(main())
