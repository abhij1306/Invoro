# Invoro AWS demo infrastructure

Disposable, single-admin Feedonomics demo. Terraform creates no NAT Gateway, WAF,
CloudFront, EC2 application host, ECS Beat service, or application task role.

Use the manual GitHub workflows. Do not run local apply with ad-hoc credentials.
The remote S3 backend bucket and GitHub bootstrap role are owner-created prerequisites.

Required GitHub environment variables:

- `AWS_ACCOUNT_ID`
- `AWS_REGION`
- `AWS_BOOTSTRAP_ROLE_ARN`
- `AWS_DEPLOY_ROLE_ARN` after first apply
- `TF_STATE_BUCKET`
- `ACM_CERTIFICATE_ARN`
- `INVORO_FRONTEND_HOST`
- `INVORO_API_HOST`
- `DEFAULT_ADMIN_EMAIL`
- `DEMO_EXPIRY_DATE`

Terraform creates `invoro/demo/app` without a value. Before deploy, the owner must
set `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, and `DEFAULT_ADMIN_PASSWORD` in that secret.
