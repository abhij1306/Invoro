# Invoro AWS Demo Owner Runbook

**Environment:** `aws-demo`
**Region:** `us-east-1`
**Frontend:** `https://invoro.cube27.com`
**API:** `https://api.invoro.cube27.com`
**Scope:** one provisioned admin, maximum one week

Steps 1–12 from the original owner setup are complete: root/IAM protection, budget,
GitHub environment, Terraform state bucket, GitHub OIDC/bootstrap role, ACM
certificate, and the initial GitHub variables. Continue here.

## 13. Add the cleanup date

In GitHub → Settings → Environments → `aws-demo` → Environment variables, add:

```text
DEMO_EXPIRY_DATE=2026-08-29
```

Use the actual mandatory cleanup date. It must be today or within the next six days
when provisioning runs. Destroy by that date, before RDS can auto-start after seven
consecutive stopped days.

Expected variables before provisioning:

```text
AWS_ACCOUNT_ID
AWS_REGION
AWS_BOOTSTRAP_ROLE_ARN
TF_STATE_BUCKET
ACM_CERTIFICATE_ARN
INVORO_FRONTEND_HOST
INVORO_API_HOST
DEFAULT_ADMIN_EMAIL
DEMO_EXPIRY_DATE
```

Do not add application passwords or keys to GitHub.

## 14. Review and apply Terraform

GitHub → Actions → **Provision Invoro AWS Demo**.

1. Run `action=plan`.
2. Confirm the plan contains frontend/API/worker services, one migration task, ALB,
   RDS, Redis, EFS, ECR, logs, VPC, security groups, and IAM.
3. Confirm it contains no NAT Gateway, WAF, CloudFront, EC2 app host, EKS, or Beat.
4. Run again with `action=apply` and `confirmation=APPLY`.
5. Save these workflow outputs:

```text
alb_dns_name
github_deploy_role_arn
rds_identifier
redis_endpoint
app_secret_arn
```

All ECS desired counts must remain zero.

## 15. Add the routine deploy role

Add this GitHub `aws-demo` environment variable using Terraform output:

```text
AWS_DEPLOY_ROLE_ARN=<github_deploy_role_arn>
```

The deploy role cannot read Secrets Manager. Keep the bootstrap Administrator role
only for Terraform apply/destroy, then remove it after final destroy.

## 16. Verify infrastructure in AWS

- VPC CIDR is `10.20.0.0/16`, with two public and two private-data subnets.
- No NAT Gateway exists.
- ALB accepts public 80/443; 80 redirects to 443.
- ECS security group accepts 4000/9000 only from the ALB security group.
- RDS is PostgreSQL 15, `db.t4g.micro`, encrypted, private, single-AZ, 20 GiB.
- Redis is one private `cache.t4g.micro`, encrypted at rest, without transit encryption.
- EFS is encrypted and access points use UID/GID `10001`.
- ECS contains only frontend, API, and worker services at desired/running zero.
- ECR repositories are immutable and scan on push.
- CloudWatch contains frontend/API/worker/migration groups with seven-day retention.

Stop if PostgreSQL, Redis, EFS, or ECS container ports are publicly reachable.

## 17. Populate the application secret

AWS Secrets Manager → `invoro/demo/app` → set exactly:

```text
JWT_SECRET_KEY=<independent random token, at least 64 bytes>
ENCRYPTION_KEY=<independent random token, at least 48 bytes>
DEFAULT_ADMIN_PASSWORD=<password-manager generated, 20+ characters>
```

The password must contain upper/lowercase letters, a digit, and a special character.
Save it in the password manager. Do not add `POSTGRES_PASSWORD`; RDS owns that secret.

The API and worker never receive `DEFAULT_ADMIN_PASSWORD`. Only the migration task
receives it while creating or verifying the single admin. Bootstrap fails without
changing users if the database contains any conflicting account state.

## 18. Add Cloudflare DNS-only records

Create CNAMEs pointing to `alb_dns_name`:

```text
invoro      -> <alb_dns_name>
api.invoro  -> <alb_dns_name>
```

Keep both gray-cloud **DNS only**. Preserve ACM validation CNAMEs.

## 19. Deploy the release

GitHub → Actions → **Deploy Invoro to AWS**:

```text
mode=deploy
release_sha=<blank for current main>
allow_unfixed_image_findings=false
```

The workflow runs full backend/frontend gates, builds SHA images, prints each
High/Critical ECR finding with its package and fix status, starts RDS if needed, runs
migrations/admin bootstrap, registers all task revisions, preserves service counts,
and restores a previously stopped RDS. Fixable or unclassified High/Critical findings
always block deployment.

Keep `allow_unfixed_image_findings=false` unless every remaining High/Critical finding
shows `fix=NO` and you have reviewed the release risk. If accepted for this temporary
demo, rerun with it enabled. This input cannot bypass a finding with an available or
unknown fix.

If migration fails, do not start services. Inspect `/ecs/invoro-demo/migration`.

## 20. Start and perform the launch gate

Run **Control Invoro AWS Demo** with `action=start`.

Required checks:

- [ ] `https://api.invoro.cube27.com/health/ready` returns 200.
- [ ] `https://invoro.cube27.com` loads and the single admin can log in.
- [ ] `/api/auth/register`, docs, OpenAPI, metrics, monitors, alerts, and notifications return 404.
- [ ] Unauthenticated crawl/review/export requests fail.
- [ ] Run one HTTP-first crawl and verify review/export.
- [ ] Run one Patchright/browser fallback crawl and verify worker completion.
- [ ] Run one small batch upload below the 1 MiB/1,000 URL limits.
- [ ] Open selector preview; page content renders but scripts cannot execute.
- [ ] Monitoring/alert navigation and notification bell are absent.
- [ ] CloudWatch logs contain no passwords, authentication/encryption secret material, cookies, or DB URLs.
- [ ] Restart the environment and confirm database data and EFS artifacts persist.

Do not create an API key unless the presentation needs it. If created, revoke it
immediately after the demo.

## 21. Rehearse rollback

After two successful releases exist, run **Deploy Invoro to AWS**:

```text
mode=rollback
rollback_to_sha=<previous known-good full SHA>
```

Confirm all three services select that release and stabilize. Database migrations are
never downgraded. Then redeploy the intended SHA.

## 22. Normal operating state

After rehearsal, run **Control Invoro AWS Demo** with `action=stop`.

Do not leave the stopped database in place for seven consecutive days. Destroy the
stack by `DEMO_EXPIRY_DATE`; if cleanup is delayed, check status daily and stop RDS
again if AWS auto-starts it.

Expected idle state:

```text
frontend/API/worker desired = 0
RDS = stopped
ALB, Redis, EFS, ECR, VPC = available
```

On presentation day, run `action=start`, check readiness, log in, run one known-good
crawl, and stop changing code/infrastructure.

## 23. After the presentation

1. Run `action=stop` immediately.
2. Revoke any demo API key.
3. Remove both application DNS CNAMEs.
4. Run **Destroy Invoro AWS Demo** with `confirmation=DESTROY`.
5. Verify demo compute, data, load balancer, ECR, secret, logs, VPC, and routine role are gone.
6. Delete/detach the powerful bootstrap role only after destroy succeeds.
7. Keep the Terraform state bucket until destroy/state verification is complete.

## Troubleshooting

- **OIDC denied:** trust subject must be `repo:abhij1306/Invoro:environment:aws-demo`.
- **Cannot pull/secrets:** task must use public subnet + public IP and the ECS execution role.
- **ALB 502:** check target health, task logs, and ALB-to-ECS security-group rules.
- **Database unavailable:** start `invoro-demo-db`; never make it public.
- **Redis unavailable:** endpoint uses `redis://<private-endpoint>:6379/0`.
- **EFS timeout:** both private subnets need mount targets; NFS source is ECS SG only.
- **Chromium failure:** worker must stay at 2 vCPU/4 GiB; lower concurrency before redesigning.
- **Frontend calls localhost:** rebuild with the production API build argument.

## Launch verdict

Repository implementation alone is not proof of live controls. Verdict remains
**NO-GO** until every step 16–21 check passes and evidence is recorded in the
implementation plan. After that, verdict may become **GO for this bounded demo only**.
