#!/usr/bin/env bash
set -euo pipefail

required=(AWS_REGION AWS_ACCOUNT_ID AWS_DEPLOY_ROLE_ARN RELEASE_MODE RELEASE_SHA FRONTEND_HOST API_HOST)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Required environment variable is empty: $name" >&2
    exit 1
  fi
done

cluster="invoro-demo"
rds_id="invoro-demo-db"
frontend_service="invoro-demo-frontend"
api_service="invoro-demo-api"
worker_service="invoro-demo-worker"
frontend_family="invoro-demo-frontend"
api_family="invoro-demo-api"
worker_family="invoro-demo-worker"
migration_family="invoro-demo-migration"
backend_repository="invoro/backend"
frontend_repository="invoro/frontend"
registry="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
source_dir="${SOURCE_DIR:-.}"

actual_account=$(aws sts get-caller-identity --query Account --output text)
if [[ "$actual_account" != "$AWS_ACCOUNT_ID" ]]; then
  echo "Refusing release in AWS account $actual_account" >&2
  exit 1
fi

service_desired_count() {
  aws ecs describe-services --cluster "$cluster" --services "$1" --query 'services[0].desiredCount' --output text
}

wait_if_running() {
  local service=$1
  if (( $(service_desired_count "$service") > 0 )); then
    aws ecs wait services-stable --cluster "$cluster" --services "$service"
  fi
}

update_service() {
  local service=$1
  local task_definition=$2
  aws ecs update-service --cluster "$cluster" --service "$service" --task-definition "$task_definition" >/dev/null
}

print_migration_failure_logs() {
  local task_arn=$1
  local task_id=${task_arn##*/}
  local log_group="/ecs/${cluster}/migration"
  local log_stream="migration/migration/${task_id}"
  local attempt log_json messages

  for attempt in $(seq 1 6); do
    if log_json=$(aws logs get-log-events \
      --log-group-name "$log_group" \
      --log-stream-name "$log_stream" \
      --limit 100 \
      --output json 2>/dev/null); then
      messages=$(jq -r '.events[].message' <<< "$log_json")
      if [[ -n "$messages" ]]; then
        echo "Migration logs (credentials redacted):" >&2
        printf '%s\n' "$messages" | sed -E \
          -e 's#(postgres(ql)?(\+asyncpg)?://[^:[:space:]]+:)[^@[:space:]]+@#\1***@#gI' \
          -e 's#((password|secret|token)[=:][[:space:]]*)[^[:space:]]+#\1***#gI' >&2
        return
      fi
    fi
    sleep 2
  done

  echo "Migration log stream was not available: $log_stream" >&2
}

find_release_task_definition() {
  local family=$1
  local container=$2
  local arn image
  for arn in $(aws ecs list-task-definitions --family-prefix "$family" --status ACTIVE --sort DESC --query 'taskDefinitionArns[]' --output text); do
    image=$(aws ecs describe-task-definition --task-definition "$arn" --query "taskDefinition.containerDefinitions[?name=='${container}'].image | [0]" --output text)
    if [[ "$image" == *":${RELEASE_SHA}" ]]; then
      printf '%s\n' "$arn"
      return 0
    fi
  done
  echo "No $family revision uses release $RELEASE_SHA" >&2
  return 1
}

if [[ "$RELEASE_MODE" == "rollback" ]]; then
  frontend_task=$(find_release_task_definition "$frontend_family" frontend)
  api_task=$(find_release_task_definition "$api_family" api)
  worker_task=$(find_release_task_definition "$worker_family" worker)
  update_service "$frontend_service" "$frontend_task"
  update_service "$api_service" "$api_task"
  update_service "$worker_service" "$worker_task"
  wait_if_running "$frontend_service"
  wait_if_running "$api_service"
  wait_if_running "$worker_service"
  {
    echo "## Rolled back Invoro AWS demo"
    echo "- Release: \`$RELEASE_SHA\`"
    echo "- Frontend task: \`$frontend_task\`"
    echo "- API task: \`$api_task\`"
    echo "- Worker task: \`$worker_task\`"
    echo "- Database schema was not downgraded."
  } >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi

image_exists() {
  aws ecr describe-images --repository-name "$1" --image-ids "imageTag=$RELEASE_SHA" >/dev/null 2>&1
}

if ! image_exists "$backend_repository"; then
  docker build --pull -f "$source_dir/backend/Dockerfile" -t "$registry/$backend_repository:$RELEASE_SHA" "$source_dir"
  docker push "$registry/$backend_repository:$RELEASE_SHA"
fi

if ! image_exists "$frontend_repository"; then
  docker build --pull -f "$source_dir/frontend/Dockerfile" \
    --build-arg "NEXT_PUBLIC_API_BASE_URL=https://$API_HOST" \
    --build-arg "NEXT_PUBLIC_AWS_DEMO_MODE=true" \
    -t "$registry/$frontend_repository:$RELEASE_SHA" "$source_dir"
  docker push "$registry/$frontend_repository:$RELEASE_SHA"
fi

wait_for_image_scan() {
  local repository=$1
  local attempt wait_output
  for attempt in $(seq 1 12); do
    if wait_output=$(aws ecr wait image-scan-complete \
      --repository-name "$repository" \
      --image-id "imageTag=$RELEASE_SHA" 2>&1); then
      return 0
    fi
    case "$wait_output" in
      *ScanNotFoundException*|*ImageNotFoundException*) ;;
      *)
        echo "$wait_output" >&2
        return 1
        ;;
    esac
    if (( attempt == 12 )); then
      echo "$wait_output" >&2
      echo "$repository:$RELEASE_SHA scan was not created within 60 seconds." >&2
      return 1
    fi
    echo "$repository:$RELEASE_SHA scan is not visible yet; retrying in 5 seconds ($attempt/12)." >&2
    sleep 5
  done
}

scan_image() {
  local repository=$1
  wait_for_image_scan "$repository"
  local findings_file enhanced_count blocking no_fix
  findings_file=$(mktemp)
  aws ecr describe-image-scan-findings \
    --repository-name "$repository" \
    --image-id "imageTag=$RELEASE_SHA" \
    --output json > "$findings_file"
  enhanced_count=$(jq '[.imageScanFindings.enhancedFindings[]?] | length' "$findings_file")
  if (( enhanced_count > 0 )); then
    jq -r '
      [.imageScanFindings.enhancedFindings[]?
        | select(.severity == "CRITICAL" or .severity == "HIGH")]
      | sort_by(.severity, .packageVulnerabilityDetails.vulnerabilityId)
      | .[]
      | (.fixAvailable // "UNKNOWN") as $fix
      | [
          .severity,
          .packageVulnerabilityDetails.vulnerabilityId,
          ([.packageVulnerabilityDetails.vulnerablePackages[]?
            | (.fixedInVersion // "no packaged fix") as $fixed
            | "\(.name)@\(.version) -> \($fixed)"]
            | join(", ")),
          "fix=\($fix)"
        ]
      | @tsv
    ' "$findings_file" >&2
    blocking=$(jq '[.imageScanFindings.enhancedFindings[]?
      | select((.severity == "CRITICAL" or .severity == "HIGH") and .fixAvailable != "NO")]
      | length' "$findings_file")
    no_fix=$(jq '[.imageScanFindings.enhancedFindings[]?
      | select((.severity == "CRITICAL" or .severity == "HIGH") and .fixAvailable == "NO")]
      | length' "$findings_file")
  else
    blocking=$(jq '[.imageScanFindings.findings[]?
      | select(.severity == "CRITICAL" or .severity == "HIGH")]
      | length' "$findings_file")
    no_fix=0
  fi
  rm -f "$findings_file"
  if (( no_fix > 0 )) && [[ "${ALLOW_UNFIXED_IMAGE_FINDINGS:-false}" != "true" ]]; then
    echo "$repository:$RELEASE_SHA has $no_fix High/Critical finding(s) with no packaged fix." >&2
    echo "Review them, then rerun with allow_unfixed_image_findings enabled to accept this release risk." >&2
    exit 1
  fi
  if (( blocking > 0 )); then
    echo "$repository:$RELEASE_SHA has $blocking fixable or unclassified High/Critical finding(s)." >&2
    exit 1
  fi
  if (( no_fix > 0 )); then
    echo "$repository:$RELEASE_SHA: explicitly accepted $no_fix High/Critical finding(s) with no packaged fix." >&2
  fi
}

scan_image "$backend_repository"
scan_image "$frontend_repository"

register_task_definition() {
  local family=$1
  local container=$2
  local image=$3
  local current_file next_file
  current_file=$(mktemp)
  next_file=$(mktemp)
  aws ecs describe-task-definition --task-definition "$family" --query taskDefinition --output json > "$current_file"
  jq --arg container "$container" --arg image "$image" '
    del(
      .taskDefinitionArn,
      .revision,
      .status,
      .requiresAttributes,
      .compatibilities,
      .registeredAt,
      .registeredBy
    )
    | .containerDefinitions |= map(if .name == $container then .image = $image else . end)
  ' "$current_file" > "$next_file"
  aws ecs register-task-definition --cli-input-json "file://$next_file" --query 'taskDefinition.taskDefinitionArn' --output text
  rm -f "$current_file" "$next_file"
}

backend_image="$registry/$backend_repository:$RELEASE_SHA"
frontend_image="$registry/$frontend_repository:$RELEASE_SHA"
frontend_task=$(register_task_definition "$frontend_family" frontend "$frontend_image")
api_task=$(register_task_definition "$api_family" api "$backend_image")
worker_task=$(register_task_definition "$worker_family" worker "$backend_image")
migration_task=$(register_task_definition "$migration_family" migration "$backend_image")

previous_db_state=$(aws rds describe-db-instances --db-instance-identifier "$rds_id" --query 'DBInstances[0].DBInstanceStatus' --output text)
frontend_desired=$(service_desired_count "$frontend_service")
api_desired=$(service_desired_count "$api_service")
worker_desired=$(service_desired_count "$worker_service")
restore_database=false
if [[ "$previous_db_state" == "stopped" || "$previous_db_state" == "stopping" ]] && (( frontend_desired + api_desired + worker_desired == 0 )); then
  restore_database=true
fi

restore_database_if_needed() {
  if [[ "$restore_database" != "true" ]]; then
    return
  fi
  local state
  state=$(aws rds describe-db-instances --db-instance-identifier "$rds_id" --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || true)
  if [[ "$state" == "available" ]]; then
    aws rds stop-db-instance --db-instance-identifier "$rds_id" >/dev/null || true
    aws rds wait db-instance-stopped --db-instance-identifier "$rds_id" || true
  fi
}
trap restore_database_if_needed EXIT

if [[ "$previous_db_state" == "stopped" ]]; then
  aws rds start-db-instance --db-instance-identifier "$rds_id" >/dev/null
elif [[ "$previous_db_state" == "stopping" ]]; then
  aws rds wait db-instance-stopped --db-instance-identifier "$rds_id"
  aws rds start-db-instance --db-instance-identifier "$rds_id" >/dev/null
fi
aws rds wait db-instance-available --db-instance-identifier "$rds_id"

network_configuration=$(aws ecs describe-services --cluster "$cluster" --services "$api_service" --output json | jq -c '{awsvpcConfiguration:.services[0].networkConfiguration.awsvpcConfiguration}')
migration_run=$(aws ecs run-task \
  --cluster "$cluster" \
  --task-definition "$migration_task" \
  --launch-type FARGATE \
  --platform-version 1.4.0 \
  --network-configuration "$network_configuration" \
  --query 'tasks[0].taskArn' \
  --output text)
if [[ -z "$migration_run" || "$migration_run" == "None" ]]; then
  echo "Migration task did not start." >&2
  exit 1
fi
aws ecs wait tasks-stopped --cluster "$cluster" --tasks "$migration_run"
migration_exit=$(aws ecs describe-tasks --cluster "$cluster" --tasks "$migration_run" --query "tasks[0].containers[?name=='migration'].exitCode | [0]" --output text)
if [[ "$migration_exit" != "0" ]]; then
  aws ecs describe-tasks \
    --cluster "$cluster" \
    --tasks "$migration_run" \
    --query 'tasks[0].{StopCode:stopCode,StoppedReason:stoppedReason,Containers:containers[].{Name:name,ExitCode:exitCode,LastStatus:lastStatus,Reason:reason}}' \
    --output json >&2
  print_migration_failure_logs "$migration_run"
  exit 1
fi

update_service "$frontend_service" "$frontend_task"
update_service "$api_service" "$api_task"
update_service "$worker_service" "$worker_task"
wait_if_running "$frontend_service"
wait_if_running "$api_service"
wait_if_running "$worker_service"

{
  echo "## Deployed Invoro AWS demo"
  echo "- Release: \`$RELEASE_SHA\`"
  echo "- Frontend image: \`$frontend_image\`"
  echo "- Backend image: \`$backend_image\`"
  echo "- Frontend task: \`$frontend_task\`"
  echo "- API task: \`$api_task\`"
  echo "- Worker task: \`$worker_task\`"
  echo "- Migration task: \`$migration_task\`"
} >> "$GITHUB_STEP_SUMMARY"
