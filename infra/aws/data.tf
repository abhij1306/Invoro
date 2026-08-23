resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db"
  subnet_ids = aws_subnet.private_data[*].id
}

resource "aws_db_instance" "main" {
  identifier                  = "${local.name}-db"
  engine                      = "postgres"
  engine_version              = "15"
  instance_class              = "db.t4g.micro"
  allocated_storage           = 20
  max_allocated_storage       = 0
  storage_type                = "gp3"
  storage_encrypted           = true
  db_name                     = "invoro"
  username                    = "invoro_admin"
  manage_master_user_password = true
  port                        = 5432
  db_subnet_group_name        = aws_db_subnet_group.main.name
  vpc_security_group_ids      = [aws_security_group.database.id]
  publicly_accessible         = false
  multi_az                    = false
  backup_retention_period     = 1
  auto_minor_version_upgrade  = true
  apply_immediately           = true
  deletion_protection         = false
  skip_final_snapshot         = true
  copy_tags_to_snapshot       = true

  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name}-redis"
  subnet_ids = aws_subnet.private_data[*].id
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = "${local.name}-redis"
  description                = "Disposable Invoro Feedonomics demo"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = "cache.t4g.micro"
  port                       = 6379
  num_cache_clusters         = 1
  automatic_failover_enabled = false
  multi_az_enabled           = false
  at_rest_encryption_enabled = true
  transit_encryption_enabled = false
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.redis.id]
  apply_immediately          = true
  snapshot_retention_limit   = 0
}

resource "aws_efs_file_system" "main" {
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"

  tags = { Name = "${local.name}-files" }
}

resource "aws_efs_mount_target" "main" {
  count = 2

  file_system_id  = aws_efs_file_system.main.id
  subnet_id       = aws_subnet.private_data[count.index].id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "artifacts" {
  file_system_id = aws_efs_file_system.main.id

  posix_user {
    uid = 10001
    gid = 10001
  }

  root_directory {
    path = "/invoro/artifacts"
    creation_info {
      owner_uid   = 10001
      owner_gid   = 10001
      permissions = "0750"
    }
  }

  tags = { Name = "${local.name}-artifacts" }
}

resource "aws_efs_access_point" "cookie_store" {
  file_system_id = aws_efs_file_system.main.id

  posix_user {
    uid = 10001
    gid = 10001
  }

  root_directory {
    path = "/invoro/cookie_store"
    creation_info {
      owner_uid   = 10001
      owner_gid   = 10001
      permissions = "0700"
    }
  }

  tags = { Name = "${local.name}-cookie-store" }
}

resource "aws_ecr_repository" "backend" {
  name                 = local.backend_repository
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = local.frontend_repository
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "images" {
  for_each = {
    backend  = aws_ecr_repository.backend.name
    frontend = aws_ecr_repository.frontend.name
  }

  repository = each.value
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the newest 15 immutable releases"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 15
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "invoro/demo/app"
  recovery_window_in_days = 0
  description             = "Invoro demo JWT, encryption, and one-shot admin bootstrap values"
}

resource "aws_cloudwatch_log_group" "service" {
  for_each = toset(["frontend", "api", "worker", "migration"])

  name              = "/ecs/${local.name}/${each.value}"
  retention_in_days = 7
}
