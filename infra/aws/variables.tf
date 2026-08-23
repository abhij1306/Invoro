variable "aws_region" {
  description = "AWS region for the disposable demo."
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "Expected 12-digit AWS account ID."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit AWS account ID."
  }
}

variable "acm_certificate_arn" {
  description = "Validated ACM certificate covering both demo hosts."
  type        = string
}

variable "frontend_host" {
  type    = string
  default = "invoro.cube27.com"
}

variable "api_host" {
  type    = string
  default = "api.invoro.cube27.com"
}

variable "default_admin_email" {
  description = "Only provisioned Invoro account identifier."
  type        = string
}

variable "github_repository" {
  type    = string
  default = "abhij1306/Invoro"
}

variable "github_environment" {
  type    = string
  default = "aws-demo"
}

variable "demo_expiry_date" {
  description = "Mandatory YYYY-MM-DD cleanup date, validated by the workflow as no later than six days after provisioning."
  type        = string

  validation {
    condition = (
      can(regex("^20[0-9]{2}-[0-9]{2}-[0-9]{2}$", var.demo_expiry_date)) &&
      can(formatdate("YYYY-MM-DD", "${var.demo_expiry_date}T00:00:00Z"))
    )
    error_message = "demo_expiry_date must use YYYY-MM-DD."
  }
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

locals {
  name                 = "invoro-demo"
  availability_zones   = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnet_cidrs  = [for index in range(2) : cidrsubnet(var.vpc_cidr, 4, index)]
  private_subnet_cidrs = [for index in range(2) : cidrsubnet(var.vpc_cidr, 4, index + 8)]
  github_oidc_subject  = "repo:${var.github_repository}:environment:${var.github_environment}"
  frontend_url         = "https://${var.frontend_host}"
  api_url              = "https://${var.api_host}"
  backend_repository   = "invoro/backend"
  frontend_repository  = "invoro/frontend"
}
