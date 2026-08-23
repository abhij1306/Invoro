locals {
  backend_environment = [
    { name = "APP_ENV", value = "production" },
    { name = "FRONTEND_URL", value = local.frontend_url },
    { name = "FRONTEND_ORIGINS", value = local.frontend_url },
    { name = "REGISTRATION_ENABLED", value = "false" },
    { name = "MONITORING_ENABLED", value = "false" },
    { name = "PUBLIC_DOCS_ENABLED", value = "false" },
    { name = "PUBLIC_METRICS_ENABLED", value = "false" },
    { name = "BOOTSTRAP_ADMIN_ONCE", value = "false" },
    { name = "POSTGRES_HOST", value = aws_db_instance.main.address },
    { name = "POSTGRES_PORT", value = tostring(aws_db_instance.main.port) },
    { name = "POSTGRES_DB", value = aws_db_instance.main.db_name },
    { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0" },
    { name = "REDIS_STATE_ENABLED", value = "false" },
    { name = "CELERY_DISPATCH_ENABLED", value = "true" },
    { name = "SCHEDULER_DRIVER", value = "celery" },
    { name = "PLAYWRIGHT_HEADLESS", value = "true" },
    { name = "BROWSER_POOL_SIZE", value = "2" },
    { name = "SYSTEM_MAX_CONCURRENT_URLS", value = "4" },
    { name = "CRAWLER_RUNTIME_BROWSER_REAL_CHROME_ENABLED", value = "false" },
    { name = "CRAWLER_RUNTIME_API_RATE_LIMIT_TRUSTED_PROXIES", value = jsonencode([var.vpc_cidr]) },
  ]

  backend_secrets = [
    { name = "POSTGRES_USER", valueFrom = "${aws_db_instance.main.master_user_secret[0].secret_arn}:username::" },
    { name = "POSTGRES_PASSWORD", valueFrom = "${aws_db_instance.main.master_user_secret[0].secret_arn}:password::" },
    { name = "JWT_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.app.arn}:JWT_SECRET_KEY::" },
    { name = "ENCRYPTION_KEY", valueFrom = "${aws_secretsmanager_secret.app.arn}:ENCRYPTION_KEY::" },
  ]

  backend_mount_points = [
    { sourceVolume = "artifacts", containerPath = "/app/backend/artifacts", readOnly = false },
    { sourceVolume = "cookie-store", containerPath = "/app/backend/cookie_store", readOnly = false },
  ]
}

resource "aws_lb" "main" {
  name                       = local.name
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  drop_invalid_header_fields = true
  desync_mitigation_mode     = "strictest"
  enable_deletion_protection = false
  idle_timeout               = 60
}

resource "aws_lb_target_group" "frontend" {
  name        = "${local.name}-frontend"
  port        = 4000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    enabled             = true
    path                = "/"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-api"
  port        = 9000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    enabled             = true
    path                = "/health/live"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.acm_certificate_arn
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Not Found"
      status_code  = "404"
    }
  }
}

resource "aws_lb_listener_rule" "api_disabled_monitoring" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 5

  action {
    type = "fixed-response"
    fixed_response {
      content_type = "application/json"
      message_body = jsonencode({ detail = "Not Found" })
      status_code  = "404"
    }
  }

  condition {
    host_header { values = [var.api_host] }
  }
  condition {
    path_pattern {
      values = [
        "/api/monitors*",
        "/api/alerts*",
        "/api/notifications*",
        "/api/v1/alerts*",
      ]
    }
  }
}

resource "aws_lb_listener_rule" "api_disabled_metrics" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 6

  action {
    type = "fixed-response"
    fixed_response {
      content_type = "application/json"
      message_body = jsonencode({ detail = "Not Found" })
      status_code  = "404"
    }
  }

  condition {
    host_header { values = [var.api_host] }
  }
  condition {
    path_pattern { values = ["/api/metrics*"] }
  }
}

resource "aws_lb_listener_rule" "api_disabled_docs" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 7

  action {
    type = "fixed-response"
    fixed_response {
      content_type = "application/json"
      message_body = jsonencode({ detail = "Not Found" })
      status_code  = "404"
    }
  }

  condition {
    host_header { values = [var.api_host] }
  }
  condition {
    path_pattern { values = ["/docs*", "/redoc*", "/openapi.json"] }
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  condition {
    host_header { values = [var.api_host] }
  }
}

resource "aws_lb_listener_rule" "frontend" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
  condition {
    host_header { values = [var.frontend_host] }
  }
}

resource "aws_ecs_cluster" "main" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${local.name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = "${aws_ecr_repository.frontend.repository_url}:bootstrap"
    essential = true
    portMappings = [{
      containerPort = 4000
      hostPort      = 4000
      protocol      = "tcp"
    }]
    environment = [
      { name = "NODE_ENV", value = "production" },
      { name = "HOSTNAME", value = "0.0.0.0" },
      { name = "PORT", value = "4000" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.service["frontend"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "frontend"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  volume {
    name = "artifacts"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.main.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.artifacts.id
        iam             = "DISABLED"
      }
    }
  }

  volume {
    name = "cookie-store"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.main.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.cookie_store.id
        iam             = "DISABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name        = "api"
    image       = "${aws_ecr_repository.backend.repository_url}:bootstrap"
    essential   = true
    command     = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000", "--proxy-headers", "--forwarded-allow-ips=${var.vpc_cidr}"]
    environment = local.backend_environment
    secrets     = local.backend_secrets
    mountPoints = local.backend_mount_points
    portMappings = [{
      containerPort = 9000
      hostPort      = 9000
      protocol      = "tcp"
    }]
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/health/live', timeout=4).read()\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.service["api"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 2048
  memory                   = 4096
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  volume {
    name = "artifacts"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.main.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.artifacts.id
        iam             = "DISABLED"
      }
    }
  }

  volume {
    name = "cookie-store"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.main.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.cookie_store.id
        iam             = "DISABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name        = "worker"
    image       = "${aws_ecr_repository.backend.repository_url}:bootstrap"
    essential   = true
    command     = ["celery", "-A", "app.core.celery_app.celery_app", "worker", "--loglevel=INFO", "--concurrency=2"]
    environment = local.backend_environment
    secrets     = local.backend_secrets
    mountPoints = local.backend_mount_points
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.service["worker"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "worker"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${local.name}-migration"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name      = "migration"
    image     = "${aws_ecr_repository.backend.repository_url}:bootstrap"
    essential = true
    command   = ["python", "init_db.py"]
    environment = concat([
      for item in local.backend_environment : item
      if item.name != "BOOTSTRAP_ADMIN_ONCE"
      ], [
      { name = "BOOTSTRAP_ADMIN_ONCE", value = "true" },
      { name = "DEFAULT_ADMIN_EMAIL", value = var.default_admin_email },
    ])
    secrets = concat(local.backend_secrets, [
      { name = "DEFAULT_ADMIN_PASSWORD", valueFrom = "${aws_secretsmanager_secret.app.arn}:DEFAULT_ADMIN_PASSWORD::" },
    ])
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.service["migration"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "migration"
      }
    }
  }])
}

resource "aws_ecs_service" "frontend" {
  name                              = "${local.name}-frontend"
  cluster                           = aws_ecs_cluster.main.id
  task_definition                   = aws_ecs_task_definition.frontend.arn
  desired_count                     = 0
  launch_type                       = "FARGATE"
  platform_version                  = "1.4.0"
  health_check_grace_period_seconds = 60

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 4000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  lifecycle {
    ignore_changes = [desired_count, task_definition]
  }

  depends_on = [aws_lb_listener_rule.frontend]
}

resource "aws_ecs_service" "api" {
  name                              = "${local.name}-api"
  cluster                           = aws_ecs_cluster.main.id
  task_definition                   = aws_ecs_task_definition.api.arn
  desired_count                     = 0
  launch_type                       = "FARGATE"
  platform_version                  = "1.4.0"
  health_check_grace_period_seconds = 120

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 9000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  lifecycle {
    ignore_changes = [desired_count, task_definition]
  }

  depends_on = [aws_lb_listener_rule.api, aws_efs_mount_target.main]
}

resource "aws_ecs_service" "worker" {
  name             = "${local.name}-worker"
  cluster          = aws_ecs_cluster.main.id
  task_definition  = aws_ecs_task_definition.worker.arn
  desired_count    = 0
  launch_type      = "FARGATE"
  platform_version = "1.4.0"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  lifecycle {
    ignore_changes = [desired_count, task_definition]
  }

  depends_on = [aws_efs_mount_target.main]
}
