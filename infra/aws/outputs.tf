output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "github_deploy_role_arn" {
  value = aws_iam_role.github_deploy.arn
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "rds_identifier" {
  value = aws_db_instance.main.identifier
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "app_secret_arn" {
  value = aws_secretsmanager_secret.app.arn
}

output "backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "frontend_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "frontend_service_name" {
  value = aws_ecs_service.frontend.name
}

output "worker_service_name" {
  value = aws_ecs_service.worker.name
}
